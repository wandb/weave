"""Tests for http_utils error handling."""

from unittest.mock import Mock

import httpx
import pytest

from weave.trace_server_bindings import http_utils
from weave.trace_server_bindings.http_utils import (
    CallsCompleteModeRequired,
    handle_response_error,
    not_found_retry_disabled,
    process_batch_with_retry,
    retry_on_not_found,
)


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


def _raise_404(body: dict) -> httpx.HTTPStatusError:
    response = httpx.Response(
        404,
        json=body,
        request=httpx.Request("POST", "http://example.com"),
    )
    return httpx.HTTPStatusError("404", request=response.request, response=response)


def test_retry_on_not_found_behavior(monkeypatch):
    """Retries a replica-lag 404 once, passes on ObjectDeletedError, ignores non-404."""
    monkeypatch.setattr(http_utils, "NOT_FOUND_RETRY_WAIT_SECONDS", 0.0)
    calls = {"missing": 0, "deleted": 0, "server": 0, "disabled": 0}

    @retry_on_not_found
    def flaky_missing():
        calls["missing"] += 1
        if calls["missing"] == 1:
            raise _raise_404({"reason": "Obj foo:bar not found"})
        return "ok"

    @retry_on_not_found
    def deleted():
        calls["deleted"] += 1
        raise _raise_404({"reason": "deleted", "deleted_at": "2024-01-01T00:00:00Z"})

    @retry_on_not_found
    def server_error():
        calls["server"] += 1
        response = httpx.Response(
            500, request=httpx.Request("POST", "http://example.com")
        )
        raise httpx.HTTPStatusError("500", request=response.request, response=response)

    @retry_on_not_found
    def missing_but_disabled():
        calls["disabled"] += 1
        raise _raise_404({"reason": "not found"})

    # Retries once, second attempt succeeds.
    assert flaky_missing() == "ok"
    assert calls["missing"] == 2

    # ObjectDeletedError (body has `deleted_at`) is not retried.
    with pytest.raises(httpx.HTTPStatusError):
        deleted()
    assert calls["deleted"] == 1

    # Non-404s are not in scope for this decorator.
    with pytest.raises(httpx.HTTPStatusError):
        server_error()
    assert calls["server"] == 1

    # Context-scoped opt-out short-circuits retry.
    with not_found_retry_disabled(), pytest.raises(httpx.HTTPStatusError):
        missing_but_disabled()
    assert calls["disabled"] == 1
