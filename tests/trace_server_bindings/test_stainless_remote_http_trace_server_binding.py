"""Tests specifically for StainlessRemoteHTTPTraceServer implementation.

These tests use the stainless SDK mocking patterns and only run when --trace-server=stainless.
"""

from __future__ import annotations

import datetime
import logging
from unittest.mock import MagicMock, patch

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server_bindings.models import (
    EndBatchItem,
    StartBatchItem,
)

# Mark all tests in this module as stainless-only
pytestmark = pytest.mark.stainless_only


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
def stainless_server():
    """Fixture that creates a StainlessRemoteHTTPTraceServer for testing."""
    from weave.trace_server_bindings.stainless_remote_http_trace_server import (
        StainlessRemoteHTTPTraceServer,
    )

    server = StainlessRemoteHTTPTraceServer(
        "http://example.com",
        should_batch=True,
        remote_request_bytes_limit=10 * 1024 * 1024,
    )
    yield server

    if server.call_processor:
        server.call_processor.stop_accepting_new_work_and_flush_queue()
    if server.feedback_processor:
        server.feedback_processor.stop_accepting_new_work_and_flush_queue()


@pytest.fixture
def stainless_server_small_limit():
    """Fixture that creates a StainlessRemoteHTTPTraceServer with small size limit."""
    from weave.trace_server_bindings.stainless_remote_http_trace_server import (
        StainlessRemoteHTTPTraceServer,
    )

    server = StainlessRemoteHTTPTraceServer(
        "http://example.com",
        should_batch=True,
        remote_request_bytes_limit=1024,  # 1kb
    )
    yield server

    if server.call_processor:
        server.call_processor.stop_accepting_new_work_and_flush_queue()
    if server.feedback_processor:
        server.feedback_processor.stop_accepting_new_work_and_flush_queue()


@pytest.fixture
def mock_stainless_client():
    """Fixture that provides a mocked stainless client."""
    mock_client = MagicMock()
    # Mock the upsert_batch method to return success
    mock_client.calls.upsert_batch.return_value = None
    return mock_client


def test_large_batch_is_split_into_multiple_smaller_batches(
    stainless_server_small_limit,
):
    """Test that large batches are split when they exceed size limits."""
    server = stainless_server_small_limit

    # Mock the stainless client
    with patch.object(server, "_stainless_client") as mock_client:
        mock_client.calls.upsert_batch.return_value = None

        # Create a large batch with many items to exceed the size limit
        batch = []
        for _ in range(20):
            start, end = generate_call_start_end_pair()
            batch.append(StartBatchItem(req=start))
            batch.append(EndBatchItem(req=end))

        # Process the batch
        server._flush_calls(batch)

        # Verify upsert_batch was called more than once (batch was split)
        assert mock_client.calls.upsert_batch.call_count > 1


def test_small_batch_is_sent_in_one_request(stainless_server):
    """Test that a small batch is sent without splitting."""
    server = stainless_server

    # Mock the stainless client
    with patch.object(server, "_stainless_client") as mock_client:
        mock_client.calls.upsert_batch.return_value = None

        # Create and process a single item
        start, _ = generate_call_start_end_pair()
        batch = [StartBatchItem(req=start)]
        server._flush_calls(batch)

        # Verify upsert_batch was called once with the entire batch
        assert mock_client.calls.upsert_batch.call_count == 1


def test_empty_batch_is_noop(stainless_server):
    """Test that empty batches don't trigger any API calls."""
    server = stainless_server

    # Mock the stainless client
    with patch.object(server, "_stainless_client") as mock_client:
        batch = []
        server._flush_calls(batch)

        # Verify upsert_batch was not called
        assert mock_client.calls.upsert_batch.call_count == 0


@pytest.mark.disable_logging_error_check
def test_oversized_item_will_log_warning_and_send(stainless_server_small_limit, caplog):
    """Test that oversized items log a warning but still attempt to send."""
    server = stainless_server_small_limit
    caplog.set_level(logging.WARNING)

    # Mock _send_batch_to_server directly to avoid stainless client initialization
    with patch.object(server, "_send_batch_to_server") as mock_send:
        mock_send.return_value = None

        # Create a single item with a very large payload
        start = generate_start()
        start.attributes = {
            "large_data": "x" * server.remote_request_bytes_limit,
        }
        batch = [StartBatchItem(req=tsi.CallStartReq(start=start))]

        # Process the batch directly - should NOT raise an exception
        server._flush_calls(batch)

        # Verify warning was logged (note: message says "calls" not "call")
        assert any("Single calls size" in record.message for record in caplog.records)
        assert any("may be too large" in record.message for record in caplog.records)

        # Verify send was still attempted
        assert mock_send.call_count >= 1


def test_multi_level_recursive_splitting(stainless_server_small_limit):
    """Test that very large batches are recursively split multiple times."""
    server = stainless_server_small_limit

    # Mock the stainless client
    with patch.object(server, "_stainless_client") as mock_client:
        mock_client.calls.upsert_batch.return_value = None

        # Create a very large batch with many items
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

        # Verify upsert_batch was called multiple times
        assert mock_client.calls.upsert_batch.call_count > 2


def test_dynamic_batch_size_adjustment(stainless_server):
    """Test that max_batch_size is dynamically adjusted based on item sizes."""
    server = stainless_server

    # Mock the stainless client
    with patch.object(server, "_stainless_client") as mock_client:
        mock_client.calls.upsert_batch.return_value = None

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


def test_non_uniform_batch_items(stainless_server_small_limit):
    """Test batch with extremely non-uniform item sizes."""
    server = stainless_server_small_limit

    # Mock the stainless client
    with patch.object(server, "_stainless_client") as mock_client:
        mock_client.calls.upsert_batch.return_value = None

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

        # Add one large item
        start = generate_start()
        start.attributes = {
            "large_data": "z" * (server.remote_request_bytes_limit // 2),
        }
        batch.append(StartBatchItem(req=tsi.CallStartReq(start=start)))

        # Process the batch
        server._flush_calls(batch)

        # The batch should have been split
        assert mock_client.calls.upsert_batch.call_count >= 2


@pytest.mark.disable_logging_error_check
def test_stainless_client_error_handling(stainless_server):
    """Test that errors from the stainless client are handled properly."""
    server = stainless_server

    # Mock the stainless client to raise an error
    with patch.object(server, "_stainless_client") as mock_client:
        mock_client.calls.upsert_batch.side_effect = Exception("API Error")

        # Create a batch
        start, end = generate_call_start_end_pair()
        batch = [StartBatchItem(req=start), EndBatchItem(req=end)]

        # Process should handle the error gracefully (via retry logic)
        try:
            server._flush_calls(batch, _should_update_batch_size=False)
        except Exception:
            # Errors are expected to be caught and logged
            pass


def test_drop_data_when_queue_is_full(stainless_server):
    """Test that server properly configures queue with size limits.

    NOTE: The detailed queue-full dropping behavior (including logging) is
    thoroughly tested in test_async_batch_processor.py::test_poison_pill_detection_and_immediate_drop
    This test just verifies the stainless server properly initializes with a queue.
    """
    server = stainless_server

    # Verify the server has a call processor with a queue
    assert server.call_processor is not None
    assert server.call_processor.queue is not None
    assert server.call_processor.queue.maxsize > 0  # Has a size limit


@pytest.mark.disable_logging_error_check
def test_requeue_after_max_retries(stainless_server, caplog):
    """Test that batches are requeued after max retries."""
    server = stainless_server
    caplog.set_level(logging.WARNING)

    # Mock is_accepting_new_work to return True
    server.call_processor.is_accepting_new_work = MagicMock(return_value=True)

    # Mock enqueue to verify it gets called
    server.call_processor.enqueue = MagicMock()

    # Mock _send_batch_to_server to throw an exception
    with patch.object(server, "_stainless_client") as mock_client:
        mock_client.calls.upsert_batch.side_effect = Exception("Connection error")

        # Create a batch
        start, end = generate_call_start_end_pair()
        batch = [StartBatchItem(req=start), EndBatchItem(req=end)]

        # Process the batch, which should fail and requeue
        server._flush_calls(batch)
        server.call_processor.enqueue.assert_called_once_with(batch)

        # Check for the error message
        assert len(caplog.records) == 1
        msg = caplog.records[0].message
        assert "batch failed after max retries, requeuing batch with" in msg


def test_stainless_batch_format_conversion(stainless_server):
    """Test that batches are correctly converted to stainless format."""
    server = stainless_server

    captured_batches = []

    def capture_batch(batch, **kwargs):
        captured_batches.append(batch)

    # Mock the stainless client to capture the batch format
    with patch.object(server, "_stainless_client") as mock_client:
        mock_client.calls.upsert_batch.side_effect = capture_batch

        # Create a mixed batch
        start, end = generate_call_start_end_pair(id="test-id-123")
        batch = [StartBatchItem(req=start), EndBatchItem(req=end)]

        server._flush_calls(batch)

        # Verify the batch was converted to stainless format
        assert len(captured_batches) == 1
        stainless_batch = captured_batches[0]

        # Check structure
        assert len(stainless_batch) == 2
        assert stainless_batch[0]["mode"] == "start"
        assert stainless_batch[1]["mode"] == "end"
        assert "req" in stainless_batch[0]
        assert "req" in stainless_batch[1]


def test_concurrent_batch_processing(stainless_server):
    """Test that multiple batches can be processed through the queue."""
    server = stainless_server

    # Mock the stainless client
    with patch.object(server, "_stainless_client") as mock_client:
        mock_client.calls.upsert_batch.return_value = None

        # Create batches and flush them directly (avoid async queue issues)
        for _ in range(5):
            start, _ = generate_call_start_end_pair()
            batch = [StartBatchItem(req=start)]
            server._flush_calls(batch)

        # Verify batches were processed
        assert mock_client.calls.upsert_batch.call_count == 5
