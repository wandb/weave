"""HTTP behavior tests for StainlessRemoteHTTPTraceServer.

These tests verify HTTP request/response handling, retry behavior for various
status codes, and error handling specific to StainlessRemoteHTTPTraceServer.
"""

from __future__ import annotations

import datetime
import json
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock

import httpx
import pytest
import requests
import tenacity
from pydantic import ValidationError
from pydantic_core import to_jsonable_python

from tests.trace_server_bindings.conftest import generate_id, generate_start
from weave.trace.display.term import configure_logger
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
from weave.trace_server_bindings.call_batch_processor import CallBatchProcessor
from weave.trace_server_bindings.http_utils import (
    ERROR_CODE_CALLS_COMPLETE_MODE_REQUIRED,
    TRACE_ID_HEADER,
)
from weave.trace_server_bindings.models import (
    CompleteBatchItem,
    EndBatchItem,
    StartBatchItem,
)
from weave.trace_server_bindings.stainless_remote_http_trace_server import (
    StainlessRemoteHTTPTraceServer,
)
from weave.utils.retry import with_retry
from weave.vendor.weave_server_sdk import APIStatusError, DefaultHttpxClient
from weave.vendor.weave_server_sdk.types import CallStartResponse
from weave.wandb_interface.auth import ApiKeyCredentials, WandbCredentials


@pytest.fixture
def unbatched_server():
    """Create a StainlessRemoteHTTPTraceServer instance without batching for testing."""
    return StainlessRemoteHTTPTraceServer("http://example.com")


def test_federated_auth_refreshes_headers(unbatched_server):
    class RotatingCredentials(WandbCredentials):
        def __init__(self) -> None:
            self.request_count = 0

        def authorization_header(self) -> str:
            self.request_count += 1
            return f"Bearer token-{self.request_count}"

        def bearer_token(self) -> str:
            return "unused"

        def wal_seed(self) -> str:
            return "stable"

    credentials = RotatingCredentials()
    unbatched_server.set_auth(credentials)
    mock_response = MagicMock()
    mock_response.model_dump.return_value = {
        "id": "call-id",
        "trace_id": "test_trace_id",
    }
    unbatched_server._stainless_client.calls.start = MagicMock(
        return_value=mock_response
    )

    unbatched_server.call_start({"start": generate_start("call-id")})

    request_headers = unbatched_server._stainless_client.calls.start.call_args.kwargs[
        "extra_headers"
    ]
    assert request_headers == {"Authorization": "Bearer token-2"}


def test_set_auth_normalizes_api_key_tuple(unbatched_server):
    unbatched_server.set_auth(("api", "secret"))

    assert isinstance(unbatched_server._credentials, ApiKeyCredentials)
    assert unbatched_server._credentials.api_key == "secret"


def test_call_start_ok(unbatched_server):
    """Test successful call_start request."""
    call_id = generate_id()

    response = CallStartResponse(id=call_id, trace_id="test_trace_id")
    unbatched_server._stainless_client.calls.start = MagicMock(return_value=response)

    start = generate_start(call_id)
    result = unbatched_server.call_start({"start": start})

    unbatched_server._stainless_client.calls.start.assert_called_once()
    assert result == CallStartResponse(id=call_id, trace_id="test_trace_id")


def test_400_no_retry(unbatched_server):
    """Test that 400 errors are not retried."""
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
        unbatched_server.call_start({"start": start})

    # Should only be called once (no retry for 400)
    assert unbatched_server._stainless_client.calls.start.call_count == 1


@pytest.mark.disable_logging_error_check
def test_timeout_retry_mechanism(success_response, monkeypatch):
    """Test that timeouts trigger the retry mechanism."""
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
    server.call_start({"start": generate_start()})
    server.call_processor.stop_accepting_new_work_and_flush_queue()

    # Verify that _send_batch_to_server was called 3 times (2 failures + 1 success)
    assert call_count == 3


@pytest.fixture
def batched_server(monkeypatch):
    """Create a batching StainlessRemoteHTTPTraceServer; the test sets the retried send."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "false")
    server = StainlessRemoteHTTPTraceServer("http://example.com", should_batch=True)
    yield server
    if server.call_processor:
        server.call_processor.stop_accepting_new_work_and_flush_queue()
    if server.feedback_processor:
        server.feedback_processor.stop_accepting_new_work_and_flush_queue()


@pytest.mark.disable_logging_error_check
def test_post_timeout(success_response, batched_server, log_collector):
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
    batched_server._send_batch_to_server = with_retry(mock_send_batch_timeout)

    # Phase 1: Try but fail to process the first batch
    batched_server.call_start({"start": generate_start()})
    batched_server.call_processor.stop_accepting_new_work_and_flush_queue()
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
            return CallStartResponse(id="test_id", trace_id="test_trace_id")

    # Create a new server since the old one has shutdown its batch processor
    new_server = StainlessRemoteHTTPTraceServer(
        "http://example.com", should_batch=False
    )
    fast_retry = tenacity.retry(
        wait=tenacity.wait_fixed(0.1),
        stop=tenacity.stop_after_attempt(2),
        reraise=True,
    )
    new_server._stainless_client.calls.start = fast_retry(mock_start_success)

    # Should succeed with retry
    start_req = {"start": generate_start()}
    response = new_server.call_start(start_req)
    assert response.id == "test_id"
    assert response.trace_id == "test_trace_id"


# =============================================================================
# calls_complete mode
#
# These tests drive the binding over an httpx.MockTransport so the vendored
# client raises its own error type, which is the thing the binding recognises.
# =============================================================================

PROJECT = "entity/project"
V2 = "/v2/entity/project"


@contextmanager
def _batching_server(
    handle: Callable[[httpx.Request], httpx.Response],
) -> Iterator[tuple[StainlessRemoteHTTPTraceServer, list[httpx.Request]]]:
    """Yield a batching server whose generated client talks to `handle`."""
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handle(request)

    server = StainlessRemoteHTTPTraceServer("http://example.com", should_batch=True)
    server._stainless_client = server._stainless_client.copy(
        http_client=httpx.Client(transport=httpx.MockTransport(record))
    )
    try:
        yield server, requests
    finally:
        if server.call_processor and server.call_processor.is_accepting_new_work():
            server.call_processor.stop_accepting_new_work_and_flush_queue()
        if server.feedback_processor:
            server.feedback_processor.stop_accepting_new_work_and_flush_queue()


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={}, request=request)


def _calls_complete_required(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/call/upsert_batch":
        return httpx.Response(
            400,
            json={
                "error_code": ERROR_CODE_CALLS_COMPLETE_MODE_REQUIRED,
                "message": "Project requires calls_complete mode",
            },
            request=request,
        )
    return _ok(request)


def _start_end_pair() -> tuple[StartBatchItem, EndBatchItem]:
    ended_at = datetime.datetime.now(tz=datetime.timezone.utc)
    # Every key the client sends, unset ones as None, so the bodies below are
    # the full requests.
    start = {
        **generate_start("call-id", PROJECT),
        "display_name": None,
        "thread_id": None,
        "turn_id": None,
        "otel_dump": None,
        "wb_user_id": None,
        "wb_run_id": None,
        "wb_run_step": None,
    }
    # Distinct trace ids so the header assertions prove each request stamps its
    # own item's trace_id rather than one shared value.
    start["trace_id"] = "trace-eager-start"
    end = {
        "project_id": PROJECT,
        "id": "call-id",
        "trace_id": "trace-eager-end",
        "is_eval": None,
        "ended_at": ended_at,
        "started_at": ended_at - datetime.timedelta(seconds=1),
        "exception": None,
        "output": None,
        "summary": {"result": "Test summary"},
        "wb_run_step_end": None,
    }
    return (
        StartBatchItem(req={"start": start}),
        EndBatchItem(req={"end": end}),
    )


@pytest.mark.parametrize(
    ("setting", "expected_processor"),
    [
        (None, CallBatchProcessor),
        ("true", CallBatchProcessor),
        ("false", AsyncBatchProcessor),
    ],
)
def test_calls_complete_setting_selects_the_processor(
    setting, expected_processor, monkeypatch
):
    """The setting decides which processor the binding starts with; it defaults on."""
    if setting is None:
        monkeypatch.delenv("WEAVE_USE_CALLS_COMPLETE", raising=False)
    else:
        monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", setting)
    with _batching_server(_ok) as (server, _):
        assert server.use_calls_complete is (expected_processor is CallBatchProcessor)
        assert type(server.call_processor) is expected_processor


def test_calls_complete_batch_endpoint_and_payload(monkeypatch):
    """Paired calls go to the v2 calls/complete route with the full payload."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "true")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    # Every key a paired call carries, unset ones as None.
    complete = {
        "project_id": PROJECT,
        "id": "call-id",
        "trace_id": "trace-id",
        "op_name": "test_op",
        "started_at": now,
        "ended_at": now,
        "display_name": None,
        "parent_id": None,
        "thread_id": None,
        "turn_id": None,
        "attributes": {"a": 1},
        "inputs": {"b": 2},
        "output": {"c": 3},
        "summary": {"result": "ok"},
        "otel_dump": None,
        "exception": None,
        "wb_user_id": None,
        "wb_run_id": None,
        "wb_run_step": None,
        "wb_run_step_end": None,
    }

    with _batching_server(_ok) as (server, requests):
        server._flush_calls_complete([CompleteBatchItem(req=complete)])

        assert [r.url.path for r in requests] == [f"{V2}/calls/complete"]
        payload = json.loads(requests[0].read().decode("utf-8"))
        assert payload == to_jsonable_python({"batch": [complete]})


def test_eager_calls_use_v2_start_end_endpoints(monkeypatch):
    """Unpaired calls go to the v2 single-call routes, one request each."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "true")
    start_item, end_item = _start_end_pair()

    with _batching_server(_ok) as (server, requests):
        server._flush_calls_eager([start_item, end_item])

        assert [r.url.path for r in requests] == [
            f"{V2}/call/start",
            f"{V2}/call/end",
        ]
        # The ingest sampler reads the trace id off the header, per request.
        assert [r.headers.get(TRACE_ID_HEADER) for r in requests] == [
            "trace-eager-start",
            "trace-eager-end",
        ]
        start_body = json.loads(requests[0].read().decode("utf-8"))
        end_body = json.loads(requests[1].read().decode("utf-8"))
        assert start_body == to_jsonable_python({"start": start_item.req["start"]})
        assert end_body == to_jsonable_python({"end": end_item.req["end"]})


@pytest.mark.disable_logging_error_check
def test_eager_failure_drops_one_item_and_continues(monkeypatch, caplog):
    """A failed eager item is logged and dropped; the rest of the batch goes out."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "true")
    start_item, end_item = _start_end_pair()

    def fail_the_start(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/call/start"):
            return httpx.Response(400, json={"detail": "no"}, request=request)
        return _ok(request)

    caplog.set_level(logging.ERROR)
    with _batching_server(fail_the_start) as (server, requests):
        server._flush_calls_eager([start_item, end_item])

    assert [r.url.path for r in requests] == [f"{V2}/call/start", f"{V2}/call/end"]
    # The third record is the vendor's own rendering of the error; only the two
    # weave-owned lines are pinned so a vendor regen cannot turn this red.
    assert [r.message for r in caplog.records[:2]] == [
        "Error sending batch of 1 call events to server",
        "dropped call start ids: ['call-id']",
    ]
    assert len(caplog.records) == 3


@pytest.mark.disable_logging_error_check
def test_auto_upgrade_to_calls_complete_on_error(monkeypatch):
    """A 400 CALLS_COMPLETE_MODE_REQUIRED must not cost the batch."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "false")
    start_item, end_item = _start_end_pair()

    with _batching_server(_calls_complete_required) as (server, requests):
        assert type(server.call_processor) is AsyncBatchProcessor
        legacy_processor = server.call_processor

        server.call_start(start_item.req)
        server.call_end(end_item.req)
        # The first drain hits the legacy route and upgrades the processor; the
        # second drains the calls_complete processor the upgrade installed.
        server.call_processor.stop_accepting_new_work_and_flush_queue()
        server.call_processor.stop_accepting_new_work_and_flush_queue()

        assert server.use_calls_complete is True
        assert type(server.call_processor) is CallBatchProcessor
        assert legacy_processor.stop_accepting_work_event.is_set()

        complete = [r for r in requests if r.url.path == f"{V2}/calls/complete"]
        assert len(complete) == 1
        start = start_item.req["start"]
        end = end_item.req["end"]
        paired = {
            "project_id": PROJECT,
            "id": "call-id",
            "trace_id": start["trace_id"],
            "op_name": start["op_name"],
            "started_at": start["started_at"],
            "ended_at": end["ended_at"],
            "display_name": None,
            "parent_id": start["parent_id"],
            "thread_id": None,
            "turn_id": None,
            "attributes": start["attributes"],
            "inputs": start["inputs"],
            "output": None,
            "summary": end["summary"],
            "otel_dump": None,
            "exception": None,
            "wb_user_id": None,
            "wb_run_id": None,
            "wb_run_step": None,
            "wb_run_step_end": None,
        }
        assert json.loads(complete[0].read().decode("utf-8")) == (
            to_jsonable_python({"batch": [paired]})
        )


@pytest.mark.disable_logging_error_check
def test_a_second_rejected_batch_lands_on_the_upgraded_processor(monkeypatch):
    """Items the retired processor was still holding must reach the new one."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "false")
    first_start, first_end = _start_end_pair()
    second_start, second_end = _start_end_pair()
    second_start.req["start"]["id"] = "call-id-2"
    second_end.req["end"]["id"] = "call-id-2"

    with _batching_server(_calls_complete_required) as (server, requests):
        # The first batch upgrades the processor; the second arrives after the swap
        # and takes the already-upgraded path.
        server._flush_calls([first_start, first_end])
        server._flush_calls([second_start, second_end])
        server.call_processor.stop_accepting_new_work_and_flush_queue()

        sent = [
            call["id"]
            for r in requests
            if r.url.path == f"{V2}/calls/complete"
            for call in json.loads(r.read().decode("utf-8"))["batch"]
        ]
        assert sorted(sent) == ["call-id", "call-id-2"]


@pytest.mark.disable_logging_error_check
def test_other_400s_do_not_upgrade(monkeypatch):
    """Only the calls_complete error code may switch the write path."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "false")
    start_item, end_item = _start_end_pair()

    def plain_400(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error_code": "NOPE"}, request=request)

    with _batching_server(plain_400) as (server, requests):
        server._flush_calls([start_item, end_item])

        assert server.use_calls_complete is False
        assert type(server.call_processor) is AsyncBatchProcessor
        assert [r.url.path for r in requests] == ["/call/upsert_batch"]


def test_batched_feedback_that_fails_on_the_client_is_not_sent():
    """A feedback item whose response cannot be built raises and is not queued."""
    feedback = {
        "project_id": PROJECT,
        "weave_ref": f"weave:///{PROJECT}/call/call-id",
        "feedback_type": "note",
    }
    with _batching_server(_ok) as (server, requests):
        with pytest.raises(ValidationError):
            server.feedback_create({**feedback, "payload": "not a dict"})
        server.feedback_create({**feedback, "payload": {"note": "ok"}})
        assert server.feedback_processor is not None
        server.feedback_processor.stop_accepting_new_work_and_flush_queue()

    (request,) = requests
    batch = json.loads(request.read())["batch"]
    assert [item["payload"] for item in batch] == [{"note": "ok"}]


def test_calls_complete_needs_batching(monkeypatch):
    """Without batching there is no processor to pair calls in."""
    monkeypatch.setenv("WEAVE_USE_CALLS_COMPLETE", "true")

    server = StainlessRemoteHTTPTraceServer("http://example.com")

    assert server.use_calls_complete is False
    assert server.call_processor is None


def test_generated_client_gets_our_ssl_and_timeout_settings(monkeypatch):
    """The vendor client built its own httpx client, so both settings were lost."""
    monkeypatch.setenv("WEAVE_INSECURE_DISABLE_SSL", "true")
    monkeypatch.setenv("WEAVE_HTTP_TIMEOUT", "7")
    captured: dict[str, object] = {}

    def spy(**kwargs: object) -> httpx.Client:
        captured.update(kwargs)
        return DefaultHttpxClient(**kwargs)

    monkeypatch.setattr(
        "weave.trace_server_bindings.stainless_remote_http_trace_server.DefaultHttpxClient",
        spy,
    )

    server = StainlessRemoteHTTPTraceServer("http://example.com")

    assert captured == {"verify": False}
    assert server._stainless_client.timeout == 7.0


def test_table_update_over_the_byte_limit_is_split():
    """A table update over the byte limit goes out in parts, each on the last digest.

    Rows are appended in order, every part fits the limit, and the response
    has the last digest and every updated row digest.
    """
    bodies: list[dict] = []
    sizes: list[int] = []

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        sizes.append(len(request.content))
        n = len(bodies)
        return httpx.Response(
            200,
            json={
                "digest": f"d{n}",
                "updated_row_digests": [
                    f"r{n}.{i}" for i in range(len(body["updates"]))
                ],
            },
            request=request,
        )

    server = StainlessRemoteHTTPTraceServer("http://example.com")
    server._stainless_client = server._stainless_client.copy(
        http_client=httpx.Client(transport=httpx.MockTransport(handle))
    )
    server.remote_request_bytes_limit = 4 * 1024
    updates = [{"append": {"row": {"a": i, "b": "x" * 1024}}} for i in range(8)]

    res = server.table_update(
        {"project_id": "e/p", "base_digest": "d0", "updates": updates}
    )

    assert len(bodies) == 4
    assert all(size <= server.remote_request_bytes_limit for size in sizes)
    assert [u for body in bodies for u in body["updates"]] == updates
    assert [body["base_digest"] for body in bodies] == ["d0", "d1", "d2", "d3"]
    assert res.digest == "d4"
    assert res.updated_row_digests == [
        f"r{n}.{i}" for n in range(1, 5) for i in range(2)
    ]
