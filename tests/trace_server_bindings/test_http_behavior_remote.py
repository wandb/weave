"""HTTP behavior tests for RemoteHTTPTraceServer.

These tests verify HTTP request/response handling, retry behavior for various
status codes, and error handling specific to RemoteHTTPTraceServer.
"""

from __future__ import annotations

import datetime
import json
import logging
from types import MethodType
from unittest.mock import MagicMock, patch

import httpx
import pytest
import tenacity
from pydantic import ValidationError

from tests.trace_server_bindings.conftest import (
    generate_end,
    generate_id,
    generate_start,
)
from weave.trace.display.term import configure_logger
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.async_batch_processor import NonRetryableBatchError
from weave.trace_server_bindings.models import (
    CompleteBatchItem,
    EndBatchItem,
    StartBatchItem,
)
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
)


@pytest.fixture
def unbatched_server():
    """Create a RemoteHTTPTraceServer instance without batching for testing."""
    return RemoteHTTPTraceServer("http://example.com")


@patch("weave.utils.http_requests.post")
def test_call_start_ok(mock_post, unbatched_server):
    """Test successful call_start request."""
    call_id = generate_id()
    mock_response = httpx.Response(
        200,
        json=dict(tsi.CallStartRes(id=call_id, trace_id="test_trace_id")),
        request=httpx.Request("POST", "http://test.com"),
    )
    mock_post.return_value = mock_response
    start = generate_start(call_id)
    unbatched_server.call_start(tsi.CallStartReq(start=start))
    mock_post.assert_called_once()


@patch("weave.utils.http_requests.post")
def test_400_no_retry(mock_post, unbatched_server):
    """Test that 400 errors are not retried."""
    call_id = generate_id()
    resp1 = httpx.Response(
        400,
        json=dict(tsi.CallStartRes(id=call_id, trace_id="test_trace_id")),
        request=httpx.Request("POST", "http://test.com"),
    )
    mock_post.side_effect = [resp1]

    start = generate_start(call_id)
    with pytest.raises(httpx.HTTPStatusError):
        unbatched_server.call_start(tsi.CallStartReq(start=start))


def test_invalid_no_retry(unbatched_server):
    """Test that validation errors are not retried."""
    with pytest.raises(ValidationError):
        unbatched_server.call_start(tsi.CallStartReq(start={"invalid": "broken"}))


@patch("weave.utils.http_requests.post")
def test_calls_complete_batch_endpoint_and_payload(mock_post, monkeypatch):
    """Send calls_complete batches to the v2 endpoint with correct payload."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "true")
    server = RemoteHTTPTraceServer("http://example.com", should_batch=True)

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

    mock_post.return_value = httpx.Response(
        200,
        json={},
        request=httpx.Request("POST", "http://example.com"),
    )

    try:
        server._flush_calls_complete(batch)
    finally:
        if server.call_processor:
            server.call_processor.stop_accepting_new_work_and_flush_queue()
        if server.feedback_processor:
            server.feedback_processor.stop_accepting_new_work_and_flush_queue()

    assert mock_post.call_count == 1
    url = mock_post.call_args[0][0]
    assert url == "http://example.com/v2/entity/project/calls/complete"
    sent_data = mock_post.call_args[1]["data"]
    payload = json.loads(sent_data.decode("utf-8"))
    expected = tsi.CallsUpsertCompleteReq(batch=[complete]).model_dump(mode="json")
    assert payload == expected


@patch("weave.utils.http_requests.post")
def test_eager_calls_use_v2_start_end_endpoints(mock_post):
    """Use v2 endpoints for eager start/end and include started_at in end."""
    server = RemoteHTTPTraceServer("http://example.com", should_batch=True)

    start = generate_start(id="call-id", project_id="entity/project")
    ended_at = datetime.datetime.now(tz=datetime.timezone.utc)
    started_at = ended_at - datetime.timedelta(seconds=1)
    end = tsi.EndedCallSchemaForInsertWithStartedAt(
        project_id="entity/project",
        id="call-id",
        ended_at=ended_at,
        started_at=started_at,
        summary={"result": "Test summary"},
    )

    mock_post.side_effect = [
        httpx.Response(200, request=httpx.Request("POST", "http://example.com")),
        httpx.Response(200, request=httpx.Request("POST", "http://example.com")),
    ]

    try:
        server._flush_calls_eager(
            [
                StartBatchItem(req=tsi.CallStartReq(start=start)),
                EndBatchItem(req=tsi.CallEndReq(end=end)),
            ]
        )

        urls = [call[0][0] for call in mock_post.call_args_list]
        assert urls == [
            "http://example.com/v2/entity/project/call/start",
            "http://example.com/v2/entity/project/call/end",
        ]

        end_payload = json.loads(mock_post.call_args_list[1][1]["data"].decode("utf-8"))
        payload_started_at = datetime.datetime.fromisoformat(
            end_payload["end"]["started_at"].replace("Z", "+00:00")
        )
        assert payload_started_at == end.started_at
        assert end_payload["end"]["id"] == "call-id"
    finally:
        if server.call_processor:
            server.call_processor.stop_accepting_new_work_and_flush_queue()
        if server.feedback_processor:
            server.feedback_processor.stop_accepting_new_work_and_flush_queue()


@pytest.mark.disable_logging_error_check
def test_eager_non_retryable_error_drops_item(caplog):
    """Drop eager items on non-retryable errors without raising."""
    server = RemoteHTTPTraceServer("http://example.com", should_batch=True)
    start = generate_start(id="call-id", project_id="entity/project")

    def _raise_non_retryable(_: StartBatchItem) -> None:
        raise httpx.HTTPStatusError(
            "400",
            request=httpx.Request("POST", "http://example.com"),
            response=httpx.Response(
                400, request=httpx.Request("POST", "http://example.com")
            ),
        )

    server._send_call_start_v2 = _raise_non_retryable  # type: ignore[assignment]

    caplog.set_level(logging.ERROR)
    try:
        server._flush_calls_eager([StartBatchItem(req=tsi.CallStartReq(start=start))])
    finally:
        if server.call_processor:
            server.call_processor.stop_accepting_new_work_and_flush_queue()
        if server.feedback_processor:
            server.feedback_processor.stop_accepting_new_work_and_flush_queue()

    assert any("dropped call start ids" in record.message for record in caplog.records)


def test_eager_retryable_error_requeues_batch():
    """Raise NonRetryableBatchError for retryable eager errors."""
    server = RemoteHTTPTraceServer("http://example.com", should_batch=True)
    start = generate_start(id="call-id", project_id="entity/project")

    def _raise_retryable(_: StartBatchItem) -> None:
        raise httpx.HTTPStatusError(
            "500",
            request=httpx.Request("POST", "http://example.com"),
            response=httpx.Response(
                500, request=httpx.Request("POST", "http://example.com")
            ),
        )

    server._send_call_start_v2 = _raise_retryable  # type: ignore[assignment]

    try:
        with pytest.raises(NonRetryableBatchError):
            server._flush_calls_eager(
                [StartBatchItem(req=tsi.CallStartReq(start=start))]
            )
    finally:
        if server.call_processor:
            server.call_processor.stop_accepting_new_work_and_flush_queue()
        if server.feedback_processor:
            server.feedback_processor.stop_accepting_new_work_and_flush_queue()


@patch("weave.utils.http_requests.post")
def test_500_502_503_504_429_retry(mock_post, unbatched_server, monkeypatch):
    """Test that 5xx and 429 errors are retried."""
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "6")
    monkeypatch.setenv("WEAVE_RETRY_MAX_INTERVAL", "0.1")
    call_id = generate_id()

    mock_post.side_effect = [
        httpx.Response(500, request=httpx.Request("POST", "http://test.com")),
        httpx.Response(502, request=httpx.Request("POST", "http://test.com")),
        httpx.Response(503, request=httpx.Request("POST", "http://test.com")),
        httpx.Response(504, request=httpx.Request("POST", "http://test.com")),
        httpx.Response(429, request=httpx.Request("POST", "http://test.com")),
        httpx.Response(
            200,
            json=dict(tsi.CallStartRes(id=call_id, trace_id="test_trace_id")),
            request=httpx.Request("POST", "http://test.com"),
        ),
    ]
    start = generate_start(call_id)
    unbatched_server.call_start(tsi.CallStartReq(start=start))


@patch("weave.utils.http_requests.post")
def test_other_error_retry(mock_post, unbatched_server, monkeypatch):
    """Test that connection errors are retried."""
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "6")
    monkeypatch.setenv("WEAVE_RETRY_MAX_INTERVAL", "0.1")
    call_id = generate_id()

    mock_post.side_effect = [
        ConnectionResetError(),
        ConnectionError(),
        OSError(),
        TimeoutError(),
        httpx.Response(
            200,
            json=dict(tsi.CallStartRes(id=call_id, trace_id="test_trace_id")),
            request=httpx.Request("POST", "http://test.com"),
        ),
    ]
    start = generate_start(call_id)
    unbatched_server.call_start(tsi.CallStartReq(start=start))


@patch("weave.utils.http_requests.post")
def test_timeout_retry_mechanism(mock_post, success_response):
    """Test that timeouts trigger the retry mechanism."""
    server = RemoteHTTPTraceServer("http://example.com", should_batch=True)

    # Mock server to raise errors twice, then succeed
    mock_post.side_effect = [
        httpx.TimeoutException("Connection timed out"),
        httpx.HTTPStatusError(
            "500 Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        ),
        success_response,
    ]

    # Trying to send a batch should fail 2 times, then succeed
    server.call_start(tsi.CallStartReq(start=generate_start()))
    server.call_processor.stop_accepting_new_work_and_flush_queue()

    # Verify that requests.post was called 3 times
    assert mock_post.call_count == 3


@pytest.fixture
def fast_retrying_server():
    """Create a RemoteHTTPTraceServer with fast retry settings for testing."""
    server = RemoteHTTPTraceServer("http://example.com", should_batch=True)
    fast_retry = tenacity.retry(
        wait=tenacity.wait_fixed(0.1),
        stop=tenacity.stop_after_attempt(2),
        reraise=True,
    )
    unwrapped_send_batch_to_server = MethodType(
        server._send_batch_to_server.__wrapped__,  # type: ignore[attr-defined]
        server,
    )
    server._send_batch_to_server = fast_retry(unwrapped_send_batch_to_server)
    yield server
    if server.call_processor:
        server.call_processor.stop_accepting_new_work_and_flush_queue()
    if server.feedback_processor:
        server.feedback_processor.stop_accepting_new_work_and_flush_queue()


@pytest.mark.disable_logging_error_check
@patch("weave.utils.http_requests.post")
def test_post_timeout(mock_post, success_response, fast_retrying_server, log_collector):
    """Test batch recovery after timeout exhaustion.

    This test verifies that we can still send new batches even if one batch
    times out and exhausts all retries.
    """
    configure_logger()
    # Configure mock to timeout twice to exhaust retries
    mock_post.side_effect = [
        httpx.TimeoutException("Connection timed out"),
        httpx.TimeoutException("Connection timed out"),
    ]

    # Phase 1: Try but fail to process the first batch
    fast_retrying_server.call_start(tsi.CallStartReq(start=generate_start()))
    fast_retrying_server.call_processor.stop_accepting_new_work_and_flush_queue()
    logs = log_collector.get_warning_logs()
    assert len(logs) >= 1
    assert any("requeuing batch" in log.msg for log in logs)

    # Phase 2: Reset mock and verify we can still process a new batch
    mock_post.reset_mock()
    mock_post.side_effect = [
        httpx.TimeoutException("Connection timed out"),
        success_response,
    ]

    # Create a new server since the old one has shutdown its batch processor
    new_server = RemoteHTTPTraceServer("http://example.com", should_batch=False)
    fast_retry = tenacity.retry(
        wait=tenacity.wait_fixed(0.1),
        stop=tenacity.stop_after_attempt(2),
        reraise=True,
    )
    unwrapped_send_batch_to_server = MethodType(
        new_server._send_batch_to_server.__wrapped__,  # type: ignore[attr-defined]
        new_server,
    )
    new_server._send_batch_to_server = fast_retry(unwrapped_send_batch_to_server)

    # Should succeed with retry
    start_req = tsi.CallStartReq(start=generate_start())
    response = new_server.call_start(start_req)
    assert response.id == "test_id"
    assert response.trace_id == "test_trace_id"
