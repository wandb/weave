"""Tests for http_utils error handling."""

import datetime
from unittest.mock import Mock

import httpx
import pytest

from weave.trace_server.errors import NotFoundError, ObjectDeletedError
from weave.trace_server_bindings import http_utils
from weave.trace_server_bindings.http_utils import (
    CallsCompleteModeRequired,
    handle_response_error,
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


def _raises_413_once():
    """Send fn factory: raises 413 on first call, succeeds afterwards."""
    state = {"first": True}

    def send(data: bytes) -> None:
        if state["first"]:
            state["first"] = False
            raise httpx.HTTPStatusError(
                "413", request=Mock(), response=Mock(status_code=413)
            )

    return send


def test_repackage_callback_fires_on_413_with_single_item():
    """A single-item batch that 413s and has a repackage callback that returns
    a new item triggers exactly one resend with the repackaged item, no drop.
    """
    dropped: list = []
    repackage_calls: list = []
    encoded_payloads: list[bytes] = []

    def repackage(item):
        repackage_calls.append(item)
        return {"item": item, "repackaged": True}

    def encode(batch):
        encoded_payloads.append(repr(batch).encode())
        return encoded_payloads[-1]

    process_batch_with_retry(
        [{"item": "huge", "repackaged": False}],
        batch_name="calls_complete",
        remote_request_bytes_limit=100_000_000,
        send_batch_fn=_raises_413_once(),
        processor_obj=None,
        encode_batch_fn=encode,
        log_dropped_fn=lambda batch, err: dropped.append((batch, err)),
        repackage_oversize_fn=repackage,
    )

    assert len(repackage_calls) == 1
    assert repackage_calls[0] == {"item": "huge", "repackaged": False}
    # Two encode calls: original + repackaged.
    assert len(encoded_payloads) == 2
    assert b"'repackaged': True" in encoded_payloads[1]
    assert dropped == []


def test_repackage_callback_returning_none_falls_through_to_drop():
    """When the callback can't shrink the payload, drop the batch as before."""
    dropped: list = []

    process_batch_with_retry(
        [{"item": "tiny", "no": "shrink"}],
        batch_name="calls",
        remote_request_bytes_limit=100_000_000,
        send_batch_fn=_raises_413_once(),
        processor_obj=None,
        encode_batch_fn=lambda b: str(b).encode(),
        log_dropped_fn=lambda batch, err: dropped.append((batch, err)),
        repackage_oversize_fn=lambda item: None,
    )

    assert len(dropped) == 1
    assert dropped[0][0] == [{"item": "tiny", "no": "shrink"}]


def test_repackage_callback_raising_falls_through_to_drop():
    """When the callback itself raises, log and drop without crashing."""
    dropped: list = []

    def boom(item):
        raise RuntimeError("save_object hit the network and timed out")

    process_batch_with_retry(
        [{"item": "huge"}],
        batch_name="calls_complete",
        remote_request_bytes_limit=100_000_000,
        send_batch_fn=_raises_413_once(),
        processor_obj=None,
        encode_batch_fn=lambda b: str(b).encode(),
        log_dropped_fn=lambda batch, err: dropped.append((batch, err)),
        repackage_oversize_fn=boom,
    )

    assert len(dropped) == 1


def test_repackage_retry_still_413_falls_through_to_drop():
    """If the repackaged payload is also rejected, drop with the retry error."""
    dropped: list = []

    def always_413(data: bytes) -> None:
        raise httpx.HTTPStatusError(
            "413", request=Mock(), response=Mock(status_code=413)
        )

    process_batch_with_retry(
        [{"item": "huge"}],
        batch_name="calls_complete",
        remote_request_bytes_limit=100_000_000,
        send_batch_fn=always_413,
        processor_obj=None,
        encode_batch_fn=lambda b: str(b).encode(),
        log_dropped_fn=lambda batch, err: dropped.append((batch, err)),
        repackage_oversize_fn=lambda item: {"item": "smaller_but_still_huge"},
    )

    assert len(dropped) == 1


def test_no_callback_preserves_existing_drop_behavior():
    """When repackage_oversize_fn is omitted, 413 + len==1 still drops cleanly."""
    dropped: list = []

    process_batch_with_retry(
        [{"item": "single"}],
        batch_name="calls",
        remote_request_bytes_limit=100_000_000,
        send_batch_fn=_raises_413_once(),
        processor_obj=None,
        encode_batch_fn=lambda b: str(b).encode(),
        log_dropped_fn=lambda batch, err: dropped.append((batch, err)),
    )

    assert len(dropped) == 1


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
