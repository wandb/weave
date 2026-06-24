"""HTTP behavior tests for StainlessRemoteHTTPTraceServer.

These tests verify HTTP request/response handling, retry behavior for various
status codes, and error handling specific to StainlessRemoteHTTPTraceServer.
"""

from __future__ import annotations

import datetime
import json
from unittest.mock import MagicMock

import pytest
import requests
import tenacity
from pydantic import ValidationError

from tests.trace_server_bindings.conftest import generate_id, generate_start
from weave.trace.display.term import configure_logger
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.http_utils import TRACE_ID_HEADER
from weave.trace_server_bindings.models import (
    CompleteBatchItem,
    EndBatchItem,
    StartBatchItem,
)
from weave.trace_server_bindings.stainless_remote_http_trace_server import (
    StainlessRemoteHTTPTraceServer,
)
from weave.utils.retry import with_retry


@pytest.fixture
def unbatched_server():
    """Create a StainlessRemoteHTTPTraceServer instance without batching for testing."""
    return StainlessRemoteHTTPTraceServer("http://example.com")


def test_call_start_ok(unbatched_server):
    """Test successful call_start request."""
    call_id = generate_id()

    mock_response = MagicMock()
    mock_response.model_dump.return_value = {
        "id": call_id,
        "trace_id": "test_trace_id",
    }
    unbatched_server._stainless_client.calls.start = MagicMock(
        return_value=mock_response
    )

    start = generate_start(call_id)
    result = unbatched_server.call_start(tsi.CallStartReq(start=start))

    unbatched_server._stainless_client.calls.start.assert_called_once()
    assert result.id == call_id
    assert result.trace_id == "test_trace_id"


def test_400_no_retry(unbatched_server):
    """Test that 400 errors are not retried."""
    from weave_server_sdk import APIStatusError

    call_id = generate_id()
    error_response = MagicMock()
    error_response.status_code = 400
    error = APIStatusError(
        message="Bad Request",
        response=error_response,
        body={"error": "Bad Request"},
    )

    unbatched_server._stainless_client.calls.start = MagicMock(side_effect=error)

    start = generate_start(call_id)
    with pytest.raises(APIStatusError):
        unbatched_server.call_start(tsi.CallStartReq(start=start))

    # Should only be called once (no retry for 400)
    assert unbatched_server._stainless_client.calls.start.call_count == 1


def test_invalid_no_retry(unbatched_server):
    """Test that validation errors are not retried."""
    with pytest.raises(ValidationError):
        unbatched_server.call_start(tsi.CallStartReq(start={"invalid": "broken"}))


@pytest.mark.disable_logging_error_check
def test_timeout_retry_mechanism(success_response, monkeypatch):
    """Test that timeouts trigger the retry mechanism on the legacy send path."""
    # This test mocks _send_batch_to_server (the legacy AsyncBatchProcessor
    # path). Force legacy mode so that path is exercised; the default
    # calls_complete path uses _send_calls_complete_to_server and is covered by
    # the calls_complete tests below.
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "false")
    server = StainlessRemoteHTTPTraceServer("http://example.com", should_batch=True)

    # Mock _send_batch_to_server to raise errors twice, then succeed
    call_count = 0

    def mock_send_batch(encoded_data: bytes) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise requests.exceptions.Timeout("Connection timed out")
        elif call_count == 2:
            raise requests.exceptions.HTTPError("500 Server Error")
        else:
            return

    # Wrap the mock with the retry decorator to preserve retry behavior
    server._send_batch_to_server = with_retry(mock_send_batch)

    # Trying to send a batch should fail 2 times, then succeed
    server.call_start(tsi.CallStartReq(start=generate_start()))
    server.call_processor.stop_accepting_new_work_and_flush_queue()

    # Verify that _send_batch_to_server was called 3 times (2 failures + 1 success)
    assert call_count == 3


@pytest.fixture
def fast_retrying_server(monkeypatch):
    """Create a StainlessRemoteHTTPTraceServer with fast retry settings for testing."""
    # These tests mock the legacy _send_batch_to_server path; force legacy mode
    # so the lone start enqueued below is sent (rather than held for pairing by
    # the default CallBatchProcessor, which would block teardown).
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "false")
    server = StainlessRemoteHTTPTraceServer("http://example.com", should_batch=True)
    fast_retry = tenacity.retry(
        wait=tenacity.wait_fixed(0.1),
        stop=tenacity.stop_after_attempt(2),
        reraise=True,
    )
    original_stainless_request = server._stainless_request
    server._stainless_request = fast_retry(original_stainless_request)
    yield server
    if server.call_processor:
        server.call_processor.stop_accepting_new_work_and_flush_queue()
    if server.feedback_processor:
        server.feedback_processor.stop_accepting_new_work_and_flush_queue()


@pytest.mark.disable_logging_error_check
def test_post_timeout(success_response, fast_retrying_server, log_collector):
    """Test batch recovery after timeout exhaustion.

    This test verifies that we can still send new batches even if one batch
    times out and exhausts all retries.
    """
    configure_logger()
    call_count = 0

    def mock_send_batch_timeout(encoded_data: bytes) -> None:
        nonlocal call_count
        call_count += 1
        raise requests.exceptions.Timeout("Connection timed out")

    # Wrap the mock with the retry decorator to preserve retry behavior
    fast_retrying_server._send_batch_to_server = with_retry(mock_send_batch_timeout)

    # Phase 1: Try but fail to process the first batch
    fast_retrying_server.call_start(tsi.CallStartReq(start=generate_start()))
    fast_retrying_server.call_processor.stop_accepting_new_work_and_flush_queue()
    logs = log_collector.get_warning_logs()
    assert len(logs) >= 1
    assert any(
        "requeueing batch" in log.msg or "batch failed" in log.msg for log in logs
    )

    # Phase 2: Reset mock and verify we can still process a new batch
    call_count = 0

    def mock_start_success(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise requests.exceptions.Timeout("Connection timed out")
        else:
            mock_response = MagicMock()
            mock_response.id = "test_id"
            mock_response.trace_id = "test_trace_id"
            mock_response.model_dump.return_value = {
                "id": "test_id",
                "trace_id": "test_trace_id",
            }
            return mock_response

    # Create a new server since the old one has shutdown its batch processor
    new_server = StainlessRemoteHTTPTraceServer(
        "http://example.com", should_batch=False
    )
    fast_retry = tenacity.retry(
        wait=tenacity.wait_fixed(0.1),
        stop=tenacity.stop_after_attempt(2),
        reraise=True,
    )
    original_stainless_request = new_server._stainless_request
    new_server._stainless_request = fast_retry(original_stainless_request)
    new_server._stainless_client.calls.start = mock_start_success

    # Should succeed with retry
    start_req = tsi.CallStartReq(start=generate_start())
    response = new_server.call_start(start_req)
    assert response.id == "test_id"
    assert response.trace_id == "test_trace_id"


@pytest.mark.disable_logging_error_check
def test_calls_complete_batch_endpoint_and_payload(monkeypatch):
    """calls_complete batches POST to the v2 endpoint with the correct payload.

    Verifies the default write path: complete calls are sent through the SDK's
    raw ``post()`` to ``/v2/{entity}/{project}/calls/complete`` (hidden from the
    OpenAPI schema, so there is no typed method).
    """
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "true")
    server = StainlessRemoteHTTPTraceServer("http://example.com", should_batch=True)

    complete = tsi.CompletedCallSchemaForInsert(
        project_id="entity/project",
        id="call-id",
        trace_id="trace-id",
        op_name="test_op",
        started_at=datetime.datetime.now(tz=datetime.timezone.utc),
        ended_at=datetime.datetime.now(tz=datetime.timezone.utc),
        attributes={"a": 1},
        inputs={"b": 2},
        output={"c": 3},
        summary={"result": "ok"},
    )
    batch = [CompleteBatchItem(req=complete)]

    # _update_client_headers() would .copy() the client (dropping the mock) when
    # a retry id is active; no-op it so the instance-level post mock is used.
    server._update_client_headers = MagicMock()
    post_mock = MagicMock()
    server._stainless_client.post = post_mock

    try:
        server._flush_calls_complete(batch)
    finally:
        if server.call_processor:
            server.call_processor.stop_accepting_new_work_and_flush_queue()
        if server.feedback_processor:
            server.feedback_processor.stop_accepting_new_work_and_flush_queue()

    assert post_mock.call_count == 1
    assert post_mock.call_args.args[0] == "/v2/entity/project/calls/complete"
    payload = json.loads(post_mock.call_args.kwargs["content"].decode("utf-8"))
    expected = tsi.CallsUpsertCompleteReq(batch=[complete]).model_dump(mode="json")
    assert payload == expected


@pytest.mark.disable_logging_error_check
def test_eager_calls_use_v2_start_end_endpoints(monkeypatch):
    """Eager start/end items POST to the single v2 endpoints with trace-id headers."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "true")
    server = StainlessRemoteHTTPTraceServer("http://example.com", should_batch=True)

    start = generate_start(id="call-id", project_id="entity/project")
    start.trace_id = "trace-eager-start"
    ended_at = datetime.datetime.now(tz=datetime.timezone.utc)
    end = tsi.EndedCallSchemaForInsertWithStartedAt(
        project_id="entity/project",
        id="call-id",
        trace_id="trace-eager-end",
        ended_at=ended_at,
        started_at=ended_at - datetime.timedelta(seconds=1),
        summary={"result": "Test summary"},
    )

    # _update_client_headers() would .copy() the client (dropping the mock) when
    # a retry id is active; no-op it so the instance-level post mock is used.
    server._update_client_headers = MagicMock()
    post_mock = MagicMock()
    server._stainless_client.post = post_mock

    try:
        server._flush_calls_eager(
            [
                StartBatchItem(req=tsi.CallStartReq(start=start)),
                EndBatchItem(req=tsi.CallEndReq(end=end)),
            ]
        )

        urls = [call.args[0] for call in post_mock.call_args_list]
        assert urls == [
            "/v2/entity/project/call/start",
            "/v2/entity/project/call/end",
        ]
        start_headers = post_mock.call_args_list[0].kwargs["options"]["headers"]
        end_headers = post_mock.call_args_list[1].kwargs["options"]["headers"]
        assert start_headers[TRACE_ID_HEADER] == start.trace_id
        assert end_headers[TRACE_ID_HEADER] == end.trace_id

        end_payload = json.loads(
            post_mock.call_args_list[1].kwargs["content"].decode("utf-8")
        )
        assert end_payload["end"]["id"] == "call-id"
    finally:
        if server.call_processor:
            server.call_processor.stop_accepting_new_work_and_flush_queue()
        if server.feedback_processor:
            server.feedback_processor.stop_accepting_new_work_and_flush_queue()
