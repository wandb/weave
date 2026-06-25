"""Tests for http_utils error handling."""

import datetime
from unittest.mock import Mock

import httpx
import pytest

from weave.trace_server.errors import NotFoundError, ObjectDeletedError
from weave.trace_server_bindings import http_utils
from weave.trace_server_bindings.http_utils import (
    CallsCompleteModeRequired,
    QueryTooExpensive,
    handle_response_error,
    process_batch_with_retry,
    retry_on_not_found,
)
from weave.utils.retry import _is_retryable_exception


def test_413_splits_batch_and_retries():
    """When server returns 413, split batch in half and retry both halves."""
    sent_batches = []
    first_call = True

    def mock_send(data: bytes) -> None:
        nonlocal first_call
        if first_call:
            first_call = False
            raise httpx.HTTPStatusError(
                "413", request=Mock(), response=Mock(status_code=413)
            )
        sent_batches.append(data)

    process_batch_with_retry(
        list(range(100)),
        batch_name="test",
        remote_request_bytes_limit=100_000,
        send_batch_fn=mock_send,
        processor_obj=None,
        encode_batch_fn=lambda b: str(b).encode(),
    )

    assert len(sent_batches) == 2


def test_calls_complete_mode_required_raises():
    """Map calls_complete mode errors to CallsCompleteModeRequired."""
    response = httpx.Response(
        400,
        json={
            "error_code": "CALLS_COMPLETE_MODE_REQUIRED",
            "message": "calls_complete mode required",
        },
        request=httpx.Request("POST", "http://example.com"),
    )

    with pytest.raises(CallsCompleteModeRequired, match="calls_complete mode required"):
        handle_response_error(response, "/call/upsert_batch")


def test_query_too_expensive_raises():
    """Map a QUERY_TOO_EXPENSIVE error_code to the dedicated QueryTooExpensive error,
    carrying the server's scope-narrowing guidance.
    """
    response = httpx.Response(
        400,
        json={
            "error_code": "QUERY_TOO_EXPENSIVE",
            "reason": (
                "Query is too expensive to run on this dataset. Please limit the "
                "scope of the query by including a date range and/or additional "
                "filter criteria. "
            ),
        },
        request=httpx.Request("POST", "http://example.com"),
    )

    with pytest.raises(QueryTooExpensive, match="limit the scope"):
        handle_response_error(response, "/traces/calls/stream_query")


def test_query_too_expensive_is_not_retryable():
    """A too-expensive query is deterministically doomed, so the SDK must not retry it
    (it is not an HTTPStatusError, which would otherwise default to retryable).
    """
    assert _is_retryable_exception(QueryTooExpensive("too expensive")) is False


def _make_404(body: dict) -> httpx.HTTPStatusError:
    response = httpx.Response(
        404,
        json=body,
        request=httpx.Request("POST", "http://example.com"),
    )
    return httpx.HTTPStatusError("404", request=response.request, response=response)


def test_retry_on_not_found_behavior(monkeypatch):
    """Retry a non-deleted 404; skip authoritative deletes and non-404s."""
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "2")
    monkeypatch.setattr(http_utils, "NOT_FOUND_RETRY_WAIT_SECONDS", 0.0)
    calls = {"http": 0, "local": 0, "deleted_http": 0, "deleted_local": 0}

    @retry_on_not_found
    def flaky_http_404():
        calls["http"] += 1
        if calls["http"] == 1:
            raise _make_404({"reason": "Obj foo:bar not found"})
        return "ok"

    @retry_on_not_found
    def flaky_local_not_found():
        calls["local"] += 1
        if calls["local"] == 1:
            raise NotFoundError("Obj foo:bar not found")
        return "ok"

    @retry_on_not_found
    def deleted_http():
        calls["deleted_http"] += 1
        raise _make_404({"reason": "deleted", "deleted_at": "2024-01-01T00:00:00Z"})

    @retry_on_not_found
    def deleted_local():
        calls["deleted_local"] += 1
        raise ObjectDeletedError(
            "deleted",
            deleted_at=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )

    assert flaky_http_404() == "ok"
    assert flaky_local_not_found() == "ok"
    assert calls["http"] == 2
    assert calls["local"] == 2

    with pytest.raises(httpx.HTTPStatusError):
        deleted_http()
    assert calls["deleted_http"] == 1

    with pytest.raises(ObjectDeletedError):
        deleted_local()
    assert calls["deleted_local"] == 1
