from __future__ import annotations

import datetime
import json
from queue import Full
from types import MethodType
from unittest.mock import MagicMock, patch

import pytest
import requests
import tenacity

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server_bindings.remote_http_trace_server import (
    Batch,
    EndBatchItem,
    RemoteHTTPTraceServer,
    StartBatchItem,
)


def generate_start(id: str | None = None) -> tsi.StartedCallSchemaForInsert:
    return tsi.StartedCallSchemaForInsert(
        project_id="test",
        id=id or generate_id(),
        op_name="test_name",
        trace_id="test_trace_id",
        parent_id="test_parent_id",
        started_at=datetime.datetime.now(tz=datetime.timezone.utc),
        attributes={"a": 5},
        inputs={"b": 5},
    )


def generate_end(id: str | None = None) -> tsi.EndedCallSchemaForInsert:
    return tsi.EndedCallSchemaForInsert(
        project_id="test",
        id=id or generate_id(),
        ended_at=datetime.datetime.now(tz=datetime.timezone.utc)
        + datetime.timedelta(seconds=1),
        outputs={"c": 5},
        error=None,
        summary={"result": "Test summary"},
    )


def generate_call_start_end_pair(
    id: str | None = None,
) -> tuple[tsi.CallStartReq, tsi.CallEndReq]:
    start = generate_start(id)
    end = generate_end(id)
    return tsi.CallStartReq(start=start), tsi.CallEndReq(end=end)


@pytest.fixture
def success_response():
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"id": "test_id", "trace_id": "test_trace_id"}
    return response


@pytest.fixture
def server(request):
    _server = RemoteHTTPTraceServer("http://example.com", should_batch=True)

    if request.param == "normal":
        _server._send_batch_to_server = MagicMock()
    elif request.param == "small_limit":
        _server.remote_request_bytes_limit = 1024  # 1kb
        _server._send_batch_to_server = MagicMock()
    elif request.param == "fast_retrying":
        fast_retry = tenacity.retry(
            wait=tenacity.wait_fixed(0.1),
            stop=tenacity.stop_after_attempt(2),
            reraise=True,
        )
        unwrapped_send_batch_to_server = MethodType(
            _server._send_batch_to_server.__wrapped__, _server
        )
        _server._send_batch_to_server = fast_retry(unwrapped_send_batch_to_server)

    yield _server

    if _server.call_processor:
        _server.call_processor.stop_accepting_new_work_and_flush_queue()


@pytest.mark.parametrize("server", ["small_limit"], indirect=True)
def test_large_batch_is_split_into_multiple_smaller_batches(server):
    # Create a large batch with many items to exceed the size limit
    batch = []
    for _ in range(20):
        start, end = generate_call_start_end_pair()
        batch.append(StartBatchItem(req=start))
        batch.append(EndBatchItem(req=end))

    # Verify the batch is actually large enough to trigger splitting
    data = Batch(batch=batch).model_dump_json()
    encoded_data = data.encode("utf-8")
    assert len(encoded_data) > server.remote_request_bytes_limit

    # Process the batch and verify _send_batch_to_server was called more than once,
    # implying the batch was split into smaller chunks
    server._flush_calls(batch)
    assert server._send_batch_to_server.call_count > 1

    # Verify all items were sent
    total_items_sent = 0
    for call in server._send_batch_to_server.call_args_list:
        called_data = call[0][0]
        decoded_batch = json.loads(called_data.decode("utf-8"))
        total_items_sent += len(decoded_batch["batch"])

    assert total_items_sent == len(batch)


@pytest.mark.parametrize("server", ["normal"], indirect=True)
def test_small_batch_is_sent_in_one_request(server):
    """Test that a small batch is sent without splitting."""
    # Create and process a single item
    start, _ = generate_call_start_end_pair()
    batch = [StartBatchItem(req=start)]
    server._flush_calls(batch)

    # Verify _send_batch_to_server was called once with the entire batch
    assert server._send_batch_to_server.call_count == 1
    called_data = server._send_batch_to_server.call_args[0][0]
    decoded_batch = json.loads(called_data.decode("utf-8"))
    assert len(decoded_batch["batch"]) == 1


@pytest.mark.parametrize("server", ["normal"], indirect=True)
def test_empty_batch_is_noop(server):
    batch = []
    server._flush_calls(batch)

    # Verify _send_batch_to_server was not called
    assert server._send_batch_to_server.call_count == 0


@pytest.mark.parametrize("server", ["small_limit"], indirect=True)
def test_oversized_item_will_error_without_sending(server):
    """Test that a single item that's too large raises an error."""
    # Create a single item with a very large payload
    start = generate_start()
    start.attributes = {
        "large_data": "x" * server.remote_request_bytes_limit,
    }
    batch = [StartBatchItem(req=tsi.CallStartReq(start=start))]

    # Verify the single item is actually large enough to trigger the error
    data = Batch(batch=batch).model_dump_json()
    encoded_data = data.encode("utf-8")
    assert len(encoded_data) > server.remote_request_bytes_limit

    # Process the batch and expect an error
    with pytest.raises(ValueError) as excinfo:
        server._flush_calls(batch)

    # Verify the error message
    assert "Single call size" in str(excinfo.value)
    assert "is too large to send" in str(excinfo.value)

    # Verify _send_batch_to_server was not called
    assert server._send_batch_to_server.call_count == 0


@pytest.mark.parametrize("server", ["small_limit"], indirect=True)
def test_multi_level_recursive_splitting(server):
    """Test that a very large batch is recursively split multiple times."""
    # Create a very large batch with many items to force multiple levels of splitting.
    # Some items are larger than others to test non-uniform sizes.
    batch = []
    for i in range(50):
        start = generate_start()
        end = generate_end()
        if i % 5 == 0:
            start.attributes = {"data": "x" * 500}
        batch.append(StartBatchItem(req=tsi.CallStartReq(start=start)))
        batch.append(EndBatchItem(req=tsi.CallEndReq(end=end)))

    # Process the batch
    server._flush_calls(batch)

    # Verify _send_batch_to_server was called multiple times
    # The exact number depends on the batch sizes, but it should be more than just 1 split
    assert server._send_batch_to_server.call_count > 2

    # Verify all items were sent
    total_items_sent = 0
    for call in server._send_batch_to_server.call_args_list:
        called_data = call[0][0]
        decoded_batch = json.loads(called_data.decode("utf-8"))
        total_items_sent += len(decoded_batch["batch"])

    assert total_items_sent == len(batch)


@pytest.mark.parametrize("server", ["normal"], indirect=True)
def test_dynamic_batch_size_adjustment(server):
    """Test that max_batch_size is dynamically adjusted based on item sizes."""
    # Create a batch with consistent item sizes
    batch = []
    for _ in range(10):
        start, end = generate_call_start_end_pair()
        batch.append(StartBatchItem(req=start))

    # Initial max_batch_size should be the default
    original_max_batch_size = server.call_processor.max_batch_size

    # Process the batch
    server._flush_calls(batch)

    # Verify max_batch_size was updated
    new_max_batch_size = server.call_processor.max_batch_size
    assert new_max_batch_size != original_max_batch_size

    # The new max_batch_size should be based on the average item size
    data = Batch(batch=batch).model_dump_json()
    encoded_bytes = len(data.encode("utf-8"))
    estimated_bytes_per_item = encoded_bytes / len(batch)
    expected_max_batch_size = max(
        1, int(server.remote_request_bytes_limit // estimated_bytes_per_item)
    )

    assert new_max_batch_size == expected_max_batch_size


@pytest.mark.parametrize("server", ["small_limit"], indirect=True)
def test_non_uniform_batch_items(server):
    """Test batch with extremely non-uniform item sizes."""
    # Create a batch with vastly different sized items
    batch = []

    # Add several small items
    for _ in range(5):
        start, _ = generate_call_start_end_pair()
        batch.append(StartBatchItem(req=start))

    # Add one medium item
    start = generate_start()
    start.attributes = {"medium_data": "y" * 300}
    batch.append(StartBatchItem(req=tsi.CallStartReq(start=start)))

    # Add one large item (but still under the limit)
    start = generate_start()
    start.attributes = {
        "large_data": "z" * (server.remote_request_bytes_limit // 2),
    }
    batch.append(StartBatchItem(req=tsi.CallStartReq(start=start)))

    # Process the batch
    server._flush_calls(batch)

    # The batch should have been split to accommodate the different sized items
    assert server._send_batch_to_server.call_count >= 2

    # Verify all items were sent
    total_items_sent = 0
    for call in server._send_batch_to_server.call_args_list:
        called_data = call[0][0]
        decoded_batch = json.loads(called_data.decode("utf-8"))
        total_items_sent += len(decoded_batch["batch"])

    assert total_items_sent == len(batch)


@patch("weave.trace_server.requests.post")
def test_timeout_retry_mechanism(mock_post, success_response):
    """Test that timeouts trigger the retry mechanism."""
    server = RemoteHTTPTraceServer("http://example.com", should_batch=True)

    # Mock server to raise errors twice, then succeed
    mock_post.side_effect = [
        requests.exceptions.Timeout("Connection timed out"),
        requests.exceptions.HTTPError("500 Server Error"),
        success_response,
    ]

    # Trying to send a batch should fail 2 times, then succeed
    server.call_start(tsi.CallStartReq(start=generate_start()))
    server.call_processor.stop_accepting_new_work_and_flush_queue()

    # Verify that requests.post was called 3 times
    assert mock_post.call_count == 3


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("server", ["fast_retrying"], indirect=True)
@patch("weave.trace_server.requests.post")
def test_post_timeout(mock_post, success_response, server, log_collector):
    """Test that we can still send new batches even if one batch times out.

    This test modifies the retry mechanism to use a short wait time and limited retries
    to verify behavior when retries are exhausted.
    """
    # Configure mock to timeout twice to exhaust retries
    mock_post.side_effect = [
        # First batch times out twice
        requests.exceptions.Timeout("Connection timed out"),
        requests.exceptions.Timeout("Connection timed out"),
        # Second batch times out once, but then succeeds
        requests.exceptions.Timeout("Connection timed out"),
        success_response,
    ]

    # Phase 1: Try but fail to process the first batch
    server.call_start(tsi.CallStartReq(start=generate_start()))
    server.call_processor.stop_accepting_new_work_and_flush_queue()
    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert "Failed to send batch after max retries" in logs[0].msg

    # Phase 2: Reset mock and verify we can still process a new batch
    mock_post.side_effect = [
        requests.exceptions.Timeout("Connection timed out"),
        success_response,
    ]

    # Create a new server since the old one has shutdown its batch processor
    server = RemoteHTTPTraceServer("http://example.com", should_batch=False)
    fast_retry = tenacity.retry(
        wait=tenacity.wait_fixed(0.1),
        stop=tenacity.stop_after_attempt(2),
        reraise=True,
    )
    unwrapped_send_batch_to_server = MethodType(
        server._send_batch_to_server.__wrapped__, server
    )
    server._send_batch_to_server = fast_retry(unwrapped_send_batch_to_server)

    # Should succeed with retry
    start_req = tsi.CallStartReq(start=generate_start())
    response = server.call_start(start_req)
    assert response.id == "test_id"
    assert response.trace_id == "test_trace_id"


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("server", ["normal"], indirect=True)
@pytest.mark.parametrize("log_collector", ["warning"], indirect=True)
def test_drop_data_when_queue_is_full(server, log_collector):
    """Test that items are dropped when the queue is full."""
    # Replace the real queue with a mock that raises Full when put_nowait is called
    mock_queue = MagicMock()
    mock_queue.put_nowait.side_effect = Full
    server.call_processor.queue = mock_queue

    server.call_start(tsi.CallStartReq(start=generate_start()))

    # Verify that the put_nowait method was called (meaning we tried to enqueue the item)
    mock_queue.put_nowait.assert_called_once()

    # We can still check logs as a secondary verification
    logs = log_collector.get_warning_logs()
    assert len(logs) == 1
    assert "Queue is full" in logs[0].msg
    assert "Dropping item" in logs[0].msg


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("server", ["normal"], indirect=True)
def test_requeue_after_max_retries(server, caplog):
    """Test that batches are requeued after max retries."""
    import logging

    caplog.set_level(logging.WARNING)

    # Create a batch
    start, end = generate_call_start_end_pair()
    batch = [StartBatchItem(req=start), EndBatchItem(req=end)]

    # Mock the _send_batch_to_server method to throw an exception
    server._send_batch_to_server = MagicMock(
        side_effect=requests.ConnectionError("Connection error")
    )

    # Mock the enqueue method to verify it's called
    original_enqueue = server.call_processor.enqueue
    server.call_processor.enqueue = MagicMock()

    # Process the batch, which should fail and requeue
    server._flush_calls(batch)

    # Verify enqueue was called with the original batch
    server.call_processor.enqueue.assert_called_once_with(batch)

    # Restore the original enqueue method
    server.call_processor.enqueue = original_enqueue

    # Check that the enqueue method was called - this is sufficient to verify our requeue mechanism
    # The logs test can be less strict, just check for the error message
    assert any(
        "Failed to send batch after max retries" in record.message
        for record in caplog.records
    )
