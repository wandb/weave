from __future__ import annotations

import datetime
import json
from unittest.mock import MagicMock, patch

import pytest
import requests

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
def trace_server():
    """Mocks sending batches to a remote server."""
    server = RemoteHTTPTraceServer("http://example.com", should_batch=True)
    server._send_batch_to_server = MagicMock()
    yield server

    # Clean up the background thread to prevent test from hanging
    if hasattr(server, "call_processor"):
        server.call_processor.stop_accepting_new_work_and_safely_shutdown()


@pytest.fixture
def small_limit_trace_server(trace_server):
    trace_server.remote_request_bytes_limit = 1024  # 1kb
    return trace_server


def test_large_batch_is_split_into_multiple_smaller_batches(small_limit_trace_server):
    # Create a large batch with many items to exceed the size limit
    batch = []
    for _ in range(20):
        start, end = generate_call_start_end_pair()
        batch.append(StartBatchItem(req=start))
        batch.append(EndBatchItem(req=end))

    # Verify the batch is actually large enough to trigger splitting
    data = Batch(batch=batch).model_dump_json()
    encoded_data = data.encode("utf-8")
    assert len(encoded_data) > small_limit_trace_server.remote_request_bytes_limit

    # Process the batch and verify _send_batch_to_server was called more than once,
    # implying the batch was split into smaller chunks
    small_limit_trace_server._flush_calls(batch)
    assert small_limit_trace_server._send_batch_to_server.call_count > 1

    # Verify all items were sent
    total_items_sent = 0
    for call in small_limit_trace_server._send_batch_to_server.call_args_list:
        called_data = call[0][0]
        decoded_batch = json.loads(called_data.decode("utf-8"))
        total_items_sent += len(decoded_batch["batch"])

    assert total_items_sent == len(batch)


def test_small_batch_is_sent_in_one_request(trace_server):
    """Test that a small batch is sent without splitting."""
    # Create and process a single item
    start, _ = generate_call_start_end_pair()
    batch = [StartBatchItem(req=start)]
    trace_server._flush_calls(batch)

    # Verify _send_batch_to_server was called once with the entire batch
    assert trace_server._send_batch_to_server.call_count == 1
    called_data = trace_server._send_batch_to_server.call_args[0][0]
    decoded_batch = json.loads(called_data.decode("utf-8"))
    assert len(decoded_batch["batch"]) == 1


def test_empty_batch_is_noop(trace_server):
    batch = []
    trace_server._flush_calls(batch)

    # Verify _send_batch_to_server was not called
    assert trace_server._send_batch_to_server.call_count == 0


def test_oversized_item_will_error_without_sending(small_limit_trace_server):
    """Test that a single item that's too large raises an error."""
    # Create a single item with a very large payload
    start = generate_start()
    start.attributes = {
        "large_data": "x" * small_limit_trace_server.remote_request_bytes_limit,
    }
    batch = [StartBatchItem(req=tsi.CallStartReq(start=start))]

    # Verify the single item is actually large enough to trigger the error
    data = Batch(batch=batch).model_dump_json()
    encoded_data = data.encode("utf-8")
    assert len(encoded_data) > small_limit_trace_server.remote_request_bytes_limit

    # Process the batch and expect an error
    with pytest.raises(ValueError) as excinfo:
        small_limit_trace_server._flush_calls(batch)

    # Verify the error message
    assert "Single call size" in str(excinfo.value)
    assert "is too large to send" in str(excinfo.value)

    # Verify _send_batch_to_server was not called
    assert small_limit_trace_server._send_batch_to_server.call_count == 0


def test_multi_level_recursive_splitting(small_limit_trace_server):
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
    small_limit_trace_server._flush_calls(batch)

    # Verify _send_batch_to_server was called multiple times
    # The exact number depends on the batch sizes, but it should be more than just 1 split
    assert small_limit_trace_server._send_batch_to_server.call_count > 2

    # Verify all items were sent
    total_items_sent = 0
    for call in small_limit_trace_server._send_batch_to_server.call_args_list:
        called_data = call[0][0]
        decoded_batch = json.loads(called_data.decode("utf-8"))
        total_items_sent += len(decoded_batch["batch"])

    assert total_items_sent == len(batch)


def test_dynamic_batch_size_adjustment(trace_server):
    """Test that max_batch_size is dynamically adjusted based on item sizes."""
    # Create a batch with consistent item sizes
    batch = []
    for _ in range(10):
        start, end = generate_call_start_end_pair()
        batch.append(StartBatchItem(req=start))

    # Initial max_batch_size should be the default
    original_max_batch_size = trace_server.call_processor.max_batch_size

    # Process the batch
    trace_server._flush_calls(batch)

    # Verify max_batch_size was updated
    new_max_batch_size = trace_server.call_processor.max_batch_size
    assert new_max_batch_size != original_max_batch_size

    # The new max_batch_size should be based on the average item size
    data = Batch(batch=batch).model_dump_json()
    encoded_bytes = len(data.encode("utf-8"))
    estimated_bytes_per_item = encoded_bytes / len(batch)
    expected_max_batch_size = max(
        1, int(trace_server.remote_request_bytes_limit // estimated_bytes_per_item)
    )

    assert new_max_batch_size == expected_max_batch_size


def test_non_uniform_batch_items(small_limit_trace_server):
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
        "large_data": "z" * (small_limit_trace_server.remote_request_bytes_limit // 2)
    }
    batch.append(StartBatchItem(req=tsi.CallStartReq(start=start)))

    # Process the batch
    small_limit_trace_server._flush_calls(batch)

    # The batch should have been split to accommodate the different sized items
    assert small_limit_trace_server._send_batch_to_server.call_count >= 2

    # Verify all items were sent
    total_items_sent = 0
    for call in small_limit_trace_server._send_batch_to_server.call_args_list:
        called_data = call[0][0]
        decoded_batch = json.loads(called_data.decode("utf-8"))
        total_items_sent += len(decoded_batch["batch"])

    assert total_items_sent == len(batch)


@patch("weave.trace_server.requests.post")
def test_http_413_error_handling(mock_post):
    """Test handling of HTTP 413 (Entity Too Large) errors."""
    # Create a server without mocking _send_batch_to_server
    server = RemoteHTTPTraceServer("http://example.com", should_batch=True)

    # Create a response that simulates a 413 error
    error_response = MagicMock()
    error_response.status_code = 413
    error_response.text = json.dumps({"reason": "Request entity too large"})

    # Mock the request to return a 413 error
    mock_post.return_value = error_response

    # Create a batch
    start, _ = generate_call_start_end_pair()
    batch = [StartBatchItem(req=start)]

    # Process the batch and expect an HTTPError due to 413
    with pytest.raises(requests.HTTPError) as excinfo:
        server._flush_calls(batch)

    # Verify the error message contains the reason
    assert "413 Client Error" in str(excinfo.value)
    assert "Request entity too large" in str(excinfo.value)


@pytest.fixture
def success_response():
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"id": "test_id", "trace_id": "test_trace_id"}
    return response


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
    start, _ = generate_call_start_end_pair()
    batch = [StartBatchItem(req=start)]
    server._flush_calls(batch)

    # Verify that requests.post was called 3 times
    assert mock_post.call_count == 3
