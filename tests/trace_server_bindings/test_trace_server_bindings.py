"""Tests for RemoteHTTPTraceServer and StainlessRemoteHTTPTraceServer bindings.

These tests verify the batching, splitting, and retry behavior of both server
implementations. The --remote-http-trace-server flag controls which implementation
is tested (default: "remote", or "stainless").
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
from weave.trace_server_bindings.models import (
    Batch,
    EndBatchItem,
    StartBatchItem,
)
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
)


@pytest.mark.parametrize("server", ["small_limit"], indirect=True)
def test_large_batch_is_split_into_multiple_smaller_batches(server):
    """Test that a batch exceeding the size limit is split into smaller batches."""
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
    """Test that an empty batch doesn't trigger any server calls."""
    batch = []
    server._flush_calls(batch)

    # Verify _send_batch_to_server was not called
    assert server._send_batch_to_server.call_count == 0


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
    assert any("Single calls size" in record.message for record in caplog.records)
    assert any("may be too large" in record.message for record in caplog.records)

    # Verify _send_batch_to_server was still called
    assert server._send_batch_to_server.call_count == 1


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


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("server", ["normal"], indirect=True)
@pytest.mark.parametrize("log_collector", ["warning"], indirect=True)
def test_drop_data_when_queue_is_full(server, server_class, log_collector):
    """Test that items are dropped when the queue is full."""
    # For StainlessRemoteHTTPTraceServer, set _dropped_item_count to 0
    # so the next drop (1st) will log (logging happens at 1, 1001, 2001, etc.)
    if server_class.__name__ == "StainlessRemoteHTTPTraceServer":
        server.call_processor._dropped_item_count = 0

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
def test_requeue_after_max_retries(server, server_class, caplog):
    """Test that batches are requeued after max retries."""
    caplog.set_level(logging.WARNING)

    # Mock is_accepting_new_work to return True so we can test requeuing
    server.call_processor.is_accepting_new_work = MagicMock(return_value=True)

    # Mock enqueue to verify it gets called, and _send_batch_to_server to throw an exception
    server.call_processor.enqueue = MagicMock()

    # Use the appropriate exception type for each implementation
    if server_class == RemoteHTTPTraceServer:
        server._send_batch_to_server = MagicMock(
            side_effect=httpx.ConnectError("Connection error")
        )
    else:
        server._send_batch_to_server = MagicMock(
            side_effect=requests.ConnectionError("Connection error")
        )

    # Create a batch
    start, end = generate_call_start_end_pair()
    batch = [StartBatchItem(req=start), EndBatchItem(req=end)]

    # Process the batch, which should fail and requeue.
    server._flush_calls(batch)
    server.call_processor.enqueue.assert_called_once_with(batch)

    # On enqueue, the user should expect this error message
    assert len(caplog.records) == 1
    msg = caplog.records[0].message
    assert "batch failed after max retries, requeuing batch with" in msg
