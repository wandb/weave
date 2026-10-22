"""Tests for the StainlessRemoteHTTPTraceServer binding.

These tests verify the batching, splitting, and retry behavior of the binding.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from queue import Full
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
import requests
from pydantic_core import to_json

from tests.trace_server_bindings.conftest import (
    generate_call_start_end_pair,
    generate_end,
    generate_start,
)
from weave.trace_server_bindings.call_batch_processor import CallBatchProcessor
from weave.trace_server_bindings.models import (
    CompleteBatchItem,
    EndBatchItem,
    StartBatchItem,
)
from weave.trace_server_bindings.stainless_remote_http_trace_server import (
    StainlessRemoteHTTPTraceServer,
)


def _upsert_batch_json(batch: list[StartBatchItem | EndBatchItem]) -> str:
    """The /call/upsert_batch body for `batch`, as the binding encodes it."""
    body = {"batch": [{"mode": item.mode, "req": item.req} for item in batch]}
    return to_json(body, inf_nan_mode="null").decode()


@pytest.mark.parametrize("server", ["small_limit"], indirect=True)
def test_large_batch_is_split_into_multiple_smaller_batches(server):
    """Test that a batch exceeding the size limit is split into smaller batches."""
    batch = []
    for _ in range(20):
        start, end = generate_call_start_end_pair()
        batch.append(StartBatchItem(req=start))
        batch.append(EndBatchItem(req=end))

    # Verify the batch is actually large enough to trigger splitting
    data = _upsert_batch_json(batch)
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
    start["attributes"] = {
        "large_data": "x" * server.remote_request_bytes_limit,
    }
    batch = [StartBatchItem(req={"start": start})]

    # Verify the single item is actually large enough to trigger the error message
    data = _upsert_batch_json(batch)
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
            start["attributes"] = {"data": "x" * 500}
        batch.append(StartBatchItem(req={"start": start}))
        batch.append(EndBatchItem(req={"end": end}))

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
    data = _upsert_batch_json(batch)
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
    start["attributes"] = {"medium_data": "y" * 300}
    batch.append(StartBatchItem(req={"start": start}))

    # Add one large item (but still under the limit)
    start = generate_start()
    start["attributes"] = {
        "large_data": "z" * (server.remote_request_bytes_limit // 2),
    }
    batch.append(StartBatchItem(req={"start": start}))

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
def test_drop_data_when_queue_is_full(server, log_collector):
    """Test that items are dropped when the queue is full."""
    # Set _dropped_item_count to 0 so the next drop (1st) will log
    # (logging happens at 1, 1001, 2001, etc.)
    server.call_processor._dropped_item_count = 0

    # Replace the real queue with a mock that raises Full when put_nowait is called
    mock_queue = MagicMock()
    mock_queue.put_nowait.side_effect = Full
    server.call_processor.queue = mock_queue

    # Send a paired start+end so CallBatchProcessor (default) queues the
    # complete item. A lone start would sit in `_pending_starts` and never
    # hit the queue.
    req_start, req_end = generate_call_start_end_pair(id="test-call-id")
    server.call_start(req_start)
    server.call_end(req_end)

    # CallBatchProcessor queues the pair as one item; AsyncBatchProcessor queues both.
    expected_puts = 1 if isinstance(server.call_processor, CallBatchProcessor) else 2
    assert mock_queue.put_nowait.call_count == expected_puts

    # We can still check logs as a secondary verification
    logs = log_collector.get_warning_logs()
    assert len(logs) == 1
    assert "Queue is full" in logs[0].msg
    assert "Dropping item" in logs[0].msg


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("server", ["normal"], indirect=True)
def test_requeue_after_max_retries(server, caplog):
    """Test that batches are requeued after max retries."""
    caplog.set_level(logging.WARNING)

    # Mock is_accepting_new_work to return True so we can test requeuing
    server.call_processor.is_accepting_new_work = MagicMock(return_value=True)

    # Mock enqueue to verify it gets called, and _send_batch_to_server to throw an exception
    server.call_processor.enqueue = MagicMock()

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


@pytest.mark.parametrize("server", ["normal"], indirect=True)
def test_mixed_batch_encodes_without_extra_field_warnings(server, caplog):
    """Encoding a mixed batch must not try an end as a start."""
    start, end = generate_call_start_end_pair()

    caplog.set_level(logging.WARNING)
    server._flush_calls([StartBatchItem(req=start), EndBatchItem(req=end)])

    encoded = server._send_batch_to_server.call_args[0][0]
    assert json.loads(encoded) == json.loads(
        _upsert_batch_json([StartBatchItem(req=start), EndBatchItem(req=end)])
    )
    assert caplog.records == []


# =============================================================================
# A batch rejected because of one item in it
#
# The client sends call writes as dicts, so a field of the wrong type is only
# caught by the server's request model, a 422 for the whole batch. Only that
# item may be lost.
# =============================================================================

PROJECT = "entity/project"
BatchItem = StartBatchItem | EndBatchItem | CompleteBatchItem


def _call_items(server: Any, call_id: str, thread_id: Any = None) -> list[BatchItem]:
    """The dict batch items the client's processor sends for one finished call."""
    start = StartBatchItem(req={"start": generate_start(call_id, PROJECT)})
    start.req["start"]["thread_id"] = thread_id
    end = EndBatchItem(req={"end": generate_end(call_id, PROJECT)})
    if isinstance(server.call_processor, CallBatchProcessor):
        return [server.call_processor._create_complete(start, end)]
    return [start, end]


def _item_key(item: BatchItem) -> tuple[str, str]:
    call = item.req if item.mode == "complete" else item.req[item.mode]
    return item.mode, call["id"]


def _sent_calls(request: httpx.Request) -> list[tuple[str, dict]]:
    """The (mode, call) of each item in an upsert_batch or calls/complete body."""
    return [
        (item["mode"], item["req"][item["mode"]])
        if "mode" in item
        else ("complete", item)
        for item in json.loads(request.read())["batch"]
    ]


def _rejects_non_string_thread_id(request: httpx.Request) -> int | None:
    """What the server's model does: a non-string thread_id fails the whole batch."""
    calls = [call for _, call in _sent_calls(request)]
    if any(not isinstance(call.get("thread_id"), str | None) for call in calls):
        return 422
    return None


@contextmanager
def _server_over_transport(
    path: str,
    reject: Callable[[httpx.Request], int | None],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[Any, list[httpx.Request], list[tuple[str, str]]]]:
    """Yield a batching binding whose HTTP client talks to a mock server.

    `reject` returns the status the mock answers a batch with, or None to store
    it. Yields the binding, every request it made, and the stored item keys.
    """
    monkeypatch.setenv(
        "WEAVE_USE_CALLS_COMPLETE", "true" if path == "calls_complete" else "false"
    )
    requests_seen: list[httpx.Request] = []
    stored: list[tuple[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        if (status := reject(request)) is not None:
            return httpx.Response(status, json={"detail": "rejected"}, request=request)
        stored.extend((mode, call["id"]) for mode, call in _sent_calls(request))
        return httpx.Response(200, json={}, request=request)

    http_client = httpx.Client(transport=httpx.MockTransport(handle))
    server = StainlessRemoteHTTPTraceServer("http://example.com", should_batch=True)
    server._stainless_client = server._stainless_client.copy(http_client=http_client)
    try:
        yield server, requests_seen, stored
    finally:
        server.call_processor.stop_accepting_new_work_and_flush_queue()
        server.feedback_processor.stop_accepting_new_work_and_flush_queue()


def _flush(server: Any, batch: list[BatchItem]) -> None:
    if isinstance(server.call_processor, CallBatchProcessor):
        server._flush_calls_complete(batch)
    else:
        server._flush_calls(batch)


def _dropped_batch_sizes(caplog: pytest.LogCaptureFixture) -> list[int]:
    """The size of each batch the drop log reports, in order."""
    prefix = "Error sending batch of "
    return [
        int(record.getMessage().removeprefix(prefix).split()[0])
        for record in caplog.records
        if record.getMessage().startswith(prefix)
    ]


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("path", ["calls_complete", "upsert_batch"])
def test_invalid_item_is_dropped_alone(path, monkeypatch, caplog):
    """One call the server's model rejects costs only that call's item."""
    with _server_over_transport(path, _rejects_non_string_thread_id, monkeypatch) as (
        server,
        _,
        stored,
    ):
        good = [_call_items(server, f"good-{i}") for i in range(6)]
        bad = _call_items(server, "bad", thread_id=123)
        batch = [item for items in good[:3] + [bad] + good[3:] for item in items]
        _flush(server, batch)

    # Only the bad call's start (or complete) item carries the bad field; its
    # end item is stored like any other.
    assert sorted(stored) == sorted(
        _item_key(item) for item in batch if item is not bad[0]
    )
    assert _dropped_batch_sizes(caplog) == [1]


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("path", ["calls_complete", "upsert_batch"])
def test_batch_invalid_in_every_item_is_dropped_without_looping(
    path, monkeypatch, caplog
):
    """Both halves rejected too: three requests, then the whole batch is dropped."""
    with _server_over_transport(path, lambda _: 422, monkeypatch) as (
        server,
        requests_seen,
        stored,
    ):
        batch = [_call_items(server, f"call-{i}")[0] for i in range(8)]
        server.call_processor.enqueue = MagicMock()
        _flush(server, batch)

    assert len(requests_seen) == 3
    assert stored == []
    assert _dropped_batch_sizes(caplog) == [len(batch)]
    server.call_processor.enqueue.assert_not_called()


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("path", ["calls_complete", "upsert_batch"])
@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_other_4xx_drops_the_batch_without_splitting(path, status, monkeypatch, caplog):
    """A rejection that applies to every item is not split into more requests."""
    with _server_over_transport(path, lambda _: status, monkeypatch) as (
        server,
        requests_seen,
        stored,
    ):
        batch = [item for i in range(4) for item in _call_items(server, f"call-{i}")]
        server.call_processor.enqueue = MagicMock()
        _flush(server, batch)

    assert len(requests_seen) == 1
    assert stored == []
    assert _dropped_batch_sizes(caplog) == [len(batch)]
    server.call_processor.enqueue.assert_not_called()
