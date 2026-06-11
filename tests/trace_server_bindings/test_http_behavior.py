"""HTTP behavior tests for StainlessRemoteHTTPTraceServer.

These tests verify HTTP request/response handling, retry behavior for various
status codes, and error handling of the remote trace server binding.

Mocking happens at the httpx transport boundary (the external seam), so the
full stack — SDK encode/decode, event hooks, error translation, retry
predicates — is exercised for real.
"""

from __future__ import annotations

import datetime
import json
import logging
from types import MethodType

import httpx
import pytest
import tenacity
from pydantic import ValidationError
from weave_server_sdk import models as tsi

from tests.trace_server_bindings.conftest import (
    SpyTransport,
    generate_end,
    generate_id,
    generate_start,
)
from weave.trace.display.term import configure_logger
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
from weave.trace_server_bindings.call_batch_processor import CallBatchProcessor
from weave.trace_server_bindings.http_utils import (
    ERROR_CODE_CALLS_COMPLETE_MODE_REQUIRED,
    CallsCompleteModeRequired,
)
from weave.trace_server_bindings.models import (
    CallsCompleteReq,
    CompleteBatchItem,
    CompletedCallSchemaForInsert,
    EndBatchItem,
    FileCreateReq,
    StartBatchItem,
)
from weave.trace_server_bindings.stainless_remote_http_trace_server import (
    StainlessRemoteHTTPTraceServer,
)

BASE_URL = "http://example.com"


def make_server(
    transport: httpx.BaseTransport,
    should_batch: bool = False,
    **kwargs,
) -> StainlessRemoteHTTPTraceServer:
    return StainlessRemoteHTTPTraceServer(
        BASE_URL, should_batch=should_batch, transport=transport, **kwargs
    )


def shutdown(server: StainlessRemoteHTTPTraceServer) -> None:
    if server.call_processor and server.call_processor.is_accepting_new_work():
        server.call_processor.stop_accepting_new_work_and_flush_queue()
    if server.feedback_processor and server.feedback_processor.is_accepting_new_work():
        server.feedback_processor.stop_accepting_new_work_and_flush_queue()


def call_start_ok_response(call_id: str) -> httpx.Response:
    return httpx.Response(
        200, json=tsi.CallStartRes(id=call_id, trace_id="test_trace_id").model_dump()
    )


def make_calls_complete_required_response() -> httpx.Response:
    """Create a 400 response indicating the project requires calls_complete mode."""
    return httpx.Response(
        400,
        json={
            "error_code": ERROR_CODE_CALLS_COMPLETE_MODE_REQUIRED,
            "message": "Project requires calls_complete mode",
        },
    )


def test_call_start_ok():
    """Test successful call_start request."""
    call_id = generate_id()
    transport = SpyTransport(call_start_ok_response(call_id))
    server = make_server(transport)

    start = generate_start(call_id)
    result = server.call_start(tsi.CallStartReq(start=start))

    assert transport.urls == [f"{BASE_URL}/call/start"]
    sent = json.loads(transport.requests[0].content)
    assert sent["start"]["id"] == call_id
    assert result.id == call_id
    assert result.trace_id == "test_trace_id"


def test_400_no_retry():
    """Test that 400 errors are not retried."""
    call_id = generate_id()
    transport = SpyTransport(httpx.Response(400, json={"error": "Bad Request"}))
    server = make_server(transport)

    start = generate_start(call_id)
    with pytest.raises(httpx.HTTPStatusError):
        server.call_start(tsi.CallStartReq(start=start))

    # Should only be called once (no retry for 400)
    assert len(transport.requests) == 1


def test_invalid_no_retry():
    """Test that validation errors are not retried."""
    transport = SpyTransport()
    server = make_server(transport)
    with pytest.raises(ValidationError):
        server.call_start(tsi.CallStartReq(start={"invalid": "broken"}))
    assert len(transport.requests) == 0


def test_500_502_503_504_429_retry(monkeypatch):
    """Test that 5xx and 429 errors are retried."""
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "6")
    monkeypatch.setenv("WEAVE_RETRY_MAX_INTERVAL", "0.1")
    call_id = generate_id()

    transport = SpyTransport(
        httpx.Response(500),
        httpx.Response(502),
        httpx.Response(503),
        httpx.Response(504),
        httpx.Response(429),
        call_start_ok_response(call_id),
    )
    server = make_server(transport)

    start = generate_start(call_id)
    result = server.call_start(tsi.CallStartReq(start=start))
    assert result.id == call_id
    assert len(transport.requests) == 6


def test_other_error_retry(monkeypatch):
    """Test that connection errors are retried."""
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "6")
    monkeypatch.setenv("WEAVE_RETRY_MAX_INTERVAL", "0.1")
    call_id = generate_id()

    transport = SpyTransport(
        ConnectionResetError(),
        ConnectionError(),
        OSError(),
        TimeoutError(),
        call_start_ok_response(call_id),
    )
    server = make_server(transport)

    start = generate_start(call_id)
    result = server.call_start(tsi.CallStartReq(start=start))
    assert result.id == call_id


def test_retry_id_header_injected(monkeypatch):
    """Every request carries the per-attempt X-Weave-Retry-Id header."""
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("WEAVE_RETRY_MAX_INTERVAL", "0.1")
    call_id = generate_id()
    transport = SpyTransport(httpx.Response(500), call_start_ok_response(call_id))
    server = make_server(transport)

    server.call_start(tsi.CallStartReq(start=generate_start(call_id)))

    retry_ids = [r.headers.get("X-Weave-Retry-Id") for r in transport.requests]
    assert all(retry_ids)
    # Same logical request, so both attempts share one retry id
    assert len(set(retry_ids)) == 1


def test_extra_headers_and_auth_are_sent():
    """Constructor extra_headers and auth flow into every request."""
    call_id = generate_id()
    transport = SpyTransport(call_start_ok_response(call_id))
    server = make_server(
        transport, auth=("api", "secret-key"), extra_headers={"X-Custom": "yes"}
    )

    server.call_start(tsi.CallStartReq(start=generate_start(call_id)))

    request = transport.requests[0]
    assert request.headers["X-Custom"] == "yes"
    assert request.headers["Authorization"].startswith("Basic ")


def test_set_auth_applies_to_subsequent_requests():
    """set_auth after construction updates the live client."""
    call_id = generate_id()
    transport = SpyTransport(default_response=None)
    transport.default_response = call_start_ok_response(call_id)
    server = make_server(transport)

    server.call_start(tsi.CallStartReq(start=generate_start(call_id)))
    assert "Authorization" not in transport.requests[0].headers

    server.set_auth(("api", "secret-key"))
    server.call_start(tsi.CallStartReq(start=generate_start(call_id)))
    assert transport.requests[1].headers["Authorization"].startswith("Basic ")


def test_typed_sdk_route_obj_read():
    """A typed SDK route hits the right path and converts the response."""
    transport = SpyTransport(
        httpx.Response(
            200,
            json={
                "obj": {
                    "project_id": "entity/project",
                    "object_id": "my-obj",
                    "created_at": "2024-01-01T00:00:00Z",
                    "deleted_at": None,
                    "digest": "abc",
                    "version_index": 0,
                    "is_latest": 1,
                    "kind": "object",
                    "base_object_class": None,
                    "leaf_object_class": None,
                    "val": {"a": 1},
                }
            },
        )
    )
    server = make_server(transport)

    res = server.obj_read(
        tsi.ObjReadReq(project_id="entity/project", object_id="my-obj", digest="abc")
    )

    assert transport.urls == [f"{BASE_URL}/obj/read"]
    assert isinstance(res, tsi.ObjReadRes)
    assert res.obj.object_id == "my-obj"
    assert res.obj.val == {"a": 1}


def test_calls_complete_batch_endpoint_and_payload(monkeypatch):
    """Send calls_complete batches to the v2 endpoint with correct payload."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "true")
    transport = SpyTransport()
    server = make_server(transport, should_batch=True)

    complete = CompletedCallSchemaForInsert(
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

    try:
        server._flush_calls_complete(batch)
    finally:
        shutdown(server)

    assert transport.urls == [f"{BASE_URL}/v2/entity/project/calls/complete"]
    payload = json.loads(transport.requests[0].content)
    expected = CallsCompleteReq(batch=[complete]).model_dump(mode="json")
    assert payload == expected


def test_eager_calls_use_v2_start_end_endpoints():
    """Use v2 endpoints for eager start/end and include started_at in end."""
    transport = SpyTransport()
    server = make_server(transport, should_batch=True)

    start = generate_start(id="call-id", project_id="entity/project")
    ended_at = datetime.datetime.now(tz=datetime.timezone.utc)
    started_at = ended_at - datetime.timedelta(seconds=1)
    # started_at rides as an extra field (the published SDK model doesn't
    # declare it yet).
    end = tsi.EndedCallSchemaForInsert(
        project_id="entity/project",
        id="call-id",
        ended_at=ended_at,
        started_at=started_at,
        summary={},
    )

    try:
        server._flush_calls_eager(
            [
                StartBatchItem(req=tsi.CallStartReq(start=start)),
                EndBatchItem(req=tsi.CallEndReq(end=end)),
            ]
        )

        assert transport.urls == [
            f"{BASE_URL}/v2/entity/project/call/start",
            f"{BASE_URL}/v2/entity/project/call/end",
        ]

        end_payload = json.loads(transport.requests[1].content)
        payload_started_at = datetime.datetime.fromisoformat(
            end_payload["end"]["started_at"].replace("Z", "+00:00")
        )
        assert payload_started_at == started_at
        assert end_payload["end"]["id"] == "call-id"
    finally:
        shutdown(server)


@pytest.mark.disable_logging_error_check
def test_eager_non_retryable_error_drops_item(caplog):
    """Drop eager items on non-retryable errors without raising."""
    transport = SpyTransport(default_response=httpx.Response(400, json={}))
    server = make_server(transport, should_batch=True)
    start = generate_start(id="call-id", project_id="entity/project")

    caplog.set_level(logging.ERROR)
    try:
        server._flush_calls_eager([StartBatchItem(req=tsi.CallStartReq(start=start))])
    finally:
        shutdown(server)

    assert any("dropped call start ids" in record.message for record in caplog.records)


@pytest.mark.disable_logging_error_check
def test_eager_retryable_error_logs_and_continues(caplog):
    """Log and drop item on retryable error, continue with remaining items."""
    transport = SpyTransport()
    server = make_server(transport, should_batch=True)
    start1 = generate_start(id="call-id-1", project_id="entity/project")
    start2 = generate_start(id="call-id-2", project_id="entity/project")

    call_attempts = []

    def _raise_retryable_once(start) -> None:
        call_attempts.append(start.id)
        if start.id == "call-id-1":
            raise httpx.HTTPStatusError(
                "500",
                request=httpx.Request("POST", BASE_URL),
                response=httpx.Response(500, request=httpx.Request("POST", BASE_URL)),
            )
        # call-id-2 succeeds

    server._send_call_start_v2 = _raise_retryable_once  # type: ignore[assignment]

    try:
        # Should NOT raise - logs and drops item 1, continues with item 2
        server._flush_calls_eager(
            [
                StartBatchItem(req=tsi.CallStartReq(start=start1)),
                StartBatchItem(req=tsi.CallStartReq(start=start2)),
            ]
        )
    finally:
        shutdown(server)

    # Item 1 was logged as dropped
    assert any("dropped call start ids" in record.message for record in caplog.records)
    assert any("call-id-1" in record.message for record in caplog.records)
    # Item 2 was still processed
    assert "call-id-2" in call_attempts


def test_timeout_retry_mechanism(monkeypatch):
    """Test that timeouts trigger the retry mechanism."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "false")
    monkeypatch.setenv("WEAVE_RETRY_MAX_INTERVAL", "0.1")
    transport = SpyTransport(
        httpx.TimeoutException("Connection timed out"),
        httpx.Response(500),
        httpx.Response(200, json={}),
    )
    server = make_server(transport, should_batch=True)

    # Trying to send a batch should fail 2 times, then succeed
    server.call_start(tsi.CallStartReq(start=generate_start()))
    server.call_processor.stop_accepting_new_work_and_flush_queue()

    assert len(transport.requests) == 3
    assert all(url == f"{BASE_URL}/call/upsert_batch" for url in transport.urls)


@pytest.mark.disable_logging_error_check
def test_post_timeout(monkeypatch, log_collector):
    """Test batch recovery after timeout exhaustion.

    This test verifies that we can still send new batches even if one batch
    times out and exhausts all retries.
    """
    configure_logger()
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "false")

    fast_retry = tenacity.retry(
        wait=tenacity.wait_fixed(0.1),
        stop=tenacity.stop_after_attempt(2),
        reraise=True,
    )

    # Phase 1: Try but fail to process the first batch
    transport = SpyTransport(
        default_response=None,
    )
    transport.default_response = None
    transport.queue = [
        httpx.TimeoutException("Connection timed out"),
        httpx.TimeoutException("Connection timed out"),
    ]
    server = make_server(transport, should_batch=True)
    unwrapped_send_batch_to_server = MethodType(
        server._send_batch_to_server.__wrapped__,  # type: ignore[attr-defined]
        server,
    )
    server._send_batch_to_server = fast_retry(unwrapped_send_batch_to_server)

    server.call_start(tsi.CallStartReq(start=generate_start()))
    server.call_processor.stop_accepting_new_work_and_flush_queue()
    logs = log_collector.get_warning_logs()
    assert len(logs) >= 1
    assert any("requeuing batch" in log.msg for log in logs)
    shutdown(server)

    # Phase 2: Verify a fresh server can still process a new batch after a
    # transient timeout
    call_id = generate_id()
    transport2 = SpyTransport(
        httpx.TimeoutException("Connection timed out"),
        call_start_ok_response(call_id),
    )
    new_server = make_server(transport2, should_batch=False)
    fast_retried_call_sdk = fast_retry(
        MethodType(
            new_server._call_sdk.__wrapped__,  # type: ignore[attr-defined]
            new_server,
        )
    )
    new_server._call_sdk = fast_retried_call_sdk

    response = new_server.call_start(tsi.CallStartReq(start=generate_start(call_id)))
    assert response.id == call_id
    assert response.trace_id == "test_trace_id"


def test_auto_upgrade_to_calls_complete_on_error(monkeypatch):
    """Verify client switches to CallBatchProcessor when server returns CALLS_COMPLETE_MODE_REQUIRED."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "false")
    transport = SpyTransport(
        make_calls_complete_required_response(),
        httpx.Response(200, json={}),
    )
    server = make_server(transport, should_batch=True)

    # Verify initial state: using legacy AsyncBatchProcessor
    assert server.use_calls_complete is False
    assert isinstance(server.call_processor, AsyncBatchProcessor)
    assert not isinstance(server.call_processor, CallBatchProcessor)
    old_processor = server.call_processor

    call_id = generate_id()
    start = StartBatchItem(
        req=tsi.CallStartReq(start=generate_start(call_id, "entity/project"))
    )
    end = EndBatchItem(req=tsi.CallEndReq(end=generate_end(call_id, "entity/project")))

    try:
        server._flush_calls([start, end])
        server.call_processor.stop_accepting_new_work_and_flush_queue()

        # Verify upgrade happened
        assert server.use_calls_complete is True
        assert isinstance(server.call_processor, CallBatchProcessor)
        assert old_processor.stop_accepting_work_event.is_set()
        assert any("/calls/complete" in url for url in transport.urls)
    finally:
        shutdown(server)


def test_eager_calls_complete_required_is_reraised(monkeypatch):
    """Verify CallsCompleteModeRequired in eager path is re-raised for caller to handle."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "true")
    transport = SpyTransport(make_calls_complete_required_response())
    server = make_server(transport, should_batch=True)

    start = StartBatchItem(
        req=tsi.CallStartReq(start=generate_start("call-id", "entity/project"))
    )

    try:
        with pytest.raises(CallsCompleteModeRequired):
            server._flush_calls_eager([start])
    finally:
        shutdown(server)


def test_calls_query_stream_parses_jsonl():
    """calls_query_stream yields CallSchema objects from a jsonl response."""
    call = {
        "project_id": "entity/project",
        "id": "call-1",
        "op_name": "op",
        "trace_id": "trace-1",
        "started_at": "2024-01-01T00:00:00Z",
        "attributes": {},
        "inputs": {},
    }
    body = "\n".join([json.dumps(call), json.dumps({**call, "id": "call-2"})])
    transport = SpyTransport(
        httpx.Response(
            200,
            content=body.encode("utf-8"),
            headers={"content-type": "application/jsonl"},
        )
    )
    server = make_server(transport)

    calls = list(
        server.calls_query_stream(tsi.CallsQueryReq(project_id="entity/project"))
    )

    assert transport.urls == [f"{BASE_URL}/calls/stream_query"]
    assert [c.id for c in calls] == ["call-1", "call-2"]
    assert all(isinstance(c, tsi.CallSchema) for c in calls)


def test_file_create_sends_multipart():
    """file_create posts multipart form data (SDK 0.0.1 lost the body)."""
    transport = SpyTransport(httpx.Response(200, json={"digest": "digest-1"}))
    server = make_server(transport)

    res = server.file_create(
        FileCreateReq(project_id="entity/project", name="file.txt", content=b"hello")
    )

    assert res.digest == "digest-1"
    request = transport.requests[0]
    assert str(request.url) == f"{BASE_URL}/files/create"
    assert request.headers["content-type"].startswith("multipart/form-data")
    assert b"hello" in request.content
    assert b"entity/project" in request.content


def test_feedback_create_unbatched_uses_single_route():
    """Unbatched feedback_create posts to /feedback/create (SDK route shadowed)."""
    transport = SpyTransport(
        httpx.Response(
            200,
            json={
                "id": "feedback-1",
                "created_at": "2024-01-01T00:00:00Z",
                "wb_user_id": "user",
                "payload": {"note": "hi"},
            },
        )
    )
    server = make_server(transport)

    res = server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id="entity/project",
            weave_ref="weave:///entity/project/call/call-1",
            feedback_type="wandb.note.1",
            payload={"note": "hi"},
        )
    )

    assert transport.urls == [f"{BASE_URL}/feedback/create"]
    assert res.id == "feedback-1"
