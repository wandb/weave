"""Tests for RemoteHTTPTraceServer and StainlessRemoteHTTPTraceServer bindings.

These tests verify the splitting, retry, and HTTP sending behavior of both server
implementations. The --remote-http-trace-server flag controls which implementation
is tested (default: "remote", or "stainless").

NOTE: Most tests call _flush_calls() directly with constructed batches. This tests
the splitting and sending layer, NOT the CallBatchProcessor pairing behavior. For
pairing tests, see test_call_batch_processor.py.

With the new CallBatchProcessor:
- Pairing of start/end into CompleteBatchItems happens at enqueue time
- _flush_calls() receives already-paired items and just splits/sends them
- Tests passing raw starts+ends to _flush_calls() test the "worst case" where
  items arrive without pairing (e.g., from requeue after network failure)
"""

from __future__ import annotations

import json
import logging
from queue import Full
from unittest.mock import MagicMock

import httpx
import pytest
import requests

from tests.trace_server_bindings.conftest import (
    generate_call_start_end_pair,
    generate_end,
    generate_start,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server_bindings.models import (
    Batch,
    EndBatchItem,
    StartBatchItem,
)
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
)


def get_total_mock_calls(server) -> int:
    """Get total number of batch send calls made."""
    return (
        server._send_calls_start_batch_to_server.call_count
        + server._send_calls_end_batch_to_server.call_count
    )


def count_items_sent(server) -> int:
    """Count total items sent across all mock calls."""
    total_items_sent = 0
    for mock_method in [
        server._send_calls_start_batch_to_server,
        server._send_calls_end_batch_to_server,
    ]:
        for call in mock_method.call_args_list:
            (_, _, encoded_data) = call[0]
            decoded_batch = json.loads(encoded_data.decode("utf-8"))
            total_items_sent += len(decoded_batch["batch"])
    return total_items_sent


@pytest.mark.parametrize("server", ["small_limit"], indirect=True)
def test_large_batch_is_split_into_multiple_smaller_batches(server):
    """Test that a batch exceeding the size limit is split into smaller batches."""
    batch = []
    batch_length = 20
    for _ in range(batch_length):
        start, end = generate_call_start_end_pair()
        batch.append(StartBatchItem(req=start))
        batch.append(EndBatchItem(req=end))

    # Verify the batch is actually large enough to trigger splitting
    data = Batch(batch=batch).model_dump_json()
    encoded_data = data.encode("utf-8")
    assert len(encoded_data) > server.remote_request_bytes_limit

    server._flush_calls(batch)

    # Should split into multiple batches due to size limit
    assert get_total_mock_calls(server) > 1

    # Verify all items were sent (N starts + N ends = 2N items)
    assert count_items_sent(server) == batch_length * 2


@pytest.mark.parametrize("server", ["normal"], indirect=True)
def test_small_batch_is_sent_in_one_request(server):
    """Test that a small batch is sent without splitting."""
    start, _ = generate_call_start_end_pair()
    batch = [StartBatchItem(req=start)]
    server._flush_calls(batch)

    # Small batch should be sent in one request without splitting
    assert get_total_mock_calls(server) == 1

    # Verify the single item was sent
    (_, _, encoded_data) = server._send_calls_start_batch_to_server.call_args[0]
    decoded_batch = json.loads(encoded_data.decode("utf-8"))
    assert len(decoded_batch["batch"]) == 1


@pytest.mark.parametrize("server", ["normal"], indirect=True)
def test_empty_batch_is_noop(server):
    """Test that an empty batch doesn't trigger any server calls."""
    batch = []
    server._flush_calls(batch)

    # Verify no batch endpoints were called
    assert server._send_calls_start_batch_to_server.call_count == 0
    assert server._send_calls_end_batch_to_server.call_count == 0


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("server", ["small_limit"], indirect=True)
def test_oversized_item_will_log_warning_and_send(server, caplog):
    """Test that a single oversized item logs a warning but still attempts to send."""
    caplog.set_level(logging.WARNING)

    # Create a single item with a very large payload
    start = generate_start()
    start.attributes = {
        "large_data": "x" * server.remote_request_bytes_limit,
    }
    batch = [StartBatchItem(req=tsi.CallStartReq(start=start))]

    # Verify the single item is actually large enough to trigger the error message
    data = Batch(batch=batch).model_dump_json()
    encoded_data = data.encode("utf-8")
    assert len(encoded_data) > server.remote_request_bytes_limit

    # Process the batch - should NOT raise an exception
    server._flush_calls(batch)

    # Verify warning was logged
    assert any("Single call_starts size" in record.message for record in caplog.records)
    assert any("may be too large" in record.message for record in caplog.records)

    # Verify batch was still sent
    assert get_total_mock_calls(server) == 1


@pytest.mark.parametrize("server", ["small_limit"], indirect=True)
def test_multi_level_recursive_splitting(server):
    """Test that a very large batch is recursively split multiple times."""
    # Create a very large batch with many items to force multiple levels of splitting
    batch = []
    batch_length = 50
    for i in range(batch_length):
        call_id = generate_id()
        start = generate_start(id=call_id)
        end = generate_end(id=call_id)
        if i % 5 == 0:
            start.attributes = {"data": "x" * 500}
        batch.append(StartBatchItem(req=tsi.CallStartReq(start=start)))
        batch.append(EndBatchItem(req=tsi.CallEndReq(end=end)))

    server._flush_calls(batch)

    # Verify multiple calls due to recursive splitting
    assert get_total_mock_calls(server) > 2

    # Verify all items were sent (N starts + N ends = 2N items)
    assert count_items_sent(server) == batch_length * 2


@pytest.mark.parametrize("server", ["normal"], indirect=True)
def test_dynamic_batch_size_adjustment(server):
    """Test that max_batch_size is dynamically adjusted based on item sizes."""
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

    # Should have sent the batch of starts in one call
    assert server._send_calls_start_batch_to_server.call_count == 1
    (_, _, encoded_data) = server._send_calls_start_batch_to_server.call_args[0]
    encoded_bytes = len(encoded_data)
    estimated_bytes_per_item = encoded_bytes / 10
    expected_max_batch_size = max(
        1, int(server.remote_request_bytes_limit // estimated_bytes_per_item)
    )
    assert new_max_batch_size == expected_max_batch_size


@pytest.mark.parametrize("server", ["small_limit"], indirect=True)
def test_non_uniform_batch_items(server):
    """Test batch with extremely non-uniform item sizes."""
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

    server._flush_calls(batch)

    # Should split to accommodate the different sized items
    assert server._send_calls_start_batch_to_server.call_count >= 2

    # Verify all 7 start items were sent
    total_items_sent = 0
    for call in server._send_calls_start_batch_to_server.call_args_list:
        (_, _, encoded_data) = call[0]
        decoded_batch = json.loads(encoded_data.decode("utf-8"))
        total_items_sent += len(decoded_batch["batch"])

    assert total_items_sent == 7


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("server", ["normal"], indirect=True)
@pytest.mark.parametrize("log_collector", ["warning"], indirect=True)
def test_drop_data_when_queue_is_full(server, log_collector):
    """Test that items are dropped when the queue is full.

    With CallBatchProcessor, starts are buffered in _pending_starts until their ends arrive.
    When an end arrives and pairs with a start, or when an orphan end arrives, items go to
    the queue. This test verifies that overflow is handled correctly.
    """
    # Reset counter so the next drop (1st) will log (logging happens at 1, 1001, 2001, etc.)
    server.call_processor._dropped_item_count = 0

    # Replace the queue with a mock that raises Full when put_nowait is called
    mock_queue = MagicMock()
    mock_queue.put_nowait.side_effect = Full
    server.call_processor.queue = mock_queue

    # Start a call - this buffers the start in _pending_starts
    start, end = generate_call_start_end_pair()
    server.call_start(start)

    # End the call - this pairs with the start and tries to put a CompleteBatchItem in queue
    server.call_end(end)

    # Verify that put_nowait was called (meaning we tried to queue the complete item)
    mock_queue.put_nowait.assert_called_once()

    # Verify warning was logged
    logs = log_collector.get_warning_logs()
    assert len(logs) == 1
    assert "Ready queue full" in logs[0].msg


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("server", ["normal"], indirect=True)
def test_requeue_after_max_retries(server, server_class, caplog):
    """Test that batches are requeued after max retries."""
    caplog.set_level(logging.WARNING)

    # Mock is_accepting_new_work to return True so we can test requeuing
    server.call_processor.is_accepting_new_work = MagicMock(return_value=True)

    # Mock enqueue to verify it gets called
    server.call_processor.enqueue = MagicMock()

    # Use the appropriate exception type for each implementation
    if server_class == RemoteHTTPTraceServer:
        server._send_calls_start_batch_to_server = MagicMock(
            side_effect=httpx.ConnectError("Connection error")
        )
        server._send_calls_end_batch_to_server = MagicMock(
            side_effect=httpx.ConnectError("Connection error")
        )
    else:
        server._send_calls_start_batch_to_server = MagicMock(
            side_effect=requests.ConnectionError("Connection error")
        )
        server._send_calls_end_batch_to_server = MagicMock(
            side_effect=requests.ConnectionError("Connection error")
        )

    # Create a batch
    start, end = generate_call_start_end_pair()
    batch = [StartBatchItem(req=start), EndBatchItem(req=end)]

    # Process the batch, which should fail and requeue.
    server._flush_calls(batch)
    assert server.call_processor.enqueue.call_count >= 1

    # Verify requeue warning was logged
    assert len(caplog.records) >= 1
    assert any(
        "batch failed after max retries, requeuing batch with" in record.message
        for record in caplog.records
    )
