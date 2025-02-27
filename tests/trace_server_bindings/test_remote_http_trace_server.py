from __future__ import annotations

import datetime
import json
from unittest.mock import MagicMock

import pytest

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
    return server


@pytest.fixture
def small_limit_trace_server(trace_server):
    trace_server.remote_request_bytes_limit = 1024  # 1kb
    return trace_server


def test_batch_splitting(small_limit_trace_server):
    """Test that large batches are properly split into smaller batches."""
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


def test_single_large_item_error(small_limit_trace_server):
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


def test_empty_batch(trace_server):
    """Test that an empty batch doesn't call _send_batch_to_server."""
    batch = []
    trace_server._flush_calls(batch)

    # Verify _send_batch_to_server was not called
    assert trace_server._send_batch_to_server.call_count == 0


def test_small_batch_no_splitting(trace_server):
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
