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


def _send_413(state: dict | None = None):
    """Send fn factory. With `state=None`, always raises 413. Otherwise raises
    on the first call only (uses `state["first"]` for bookkeeping).
    """

    def send(data: bytes) -> None:
        if state is None or state.get("first"):
            if state is not None:
                state["first"] = False
            raise httpx.HTTPStatusError(
                "413", request=Mock(), response=Mock(status_code=413)
            )

    return send


def test_413_single_item_with_callback_repackages_and_retries_then_succeeds():
    """Happy path for the new repackage hook: a single-item batch that 413s
    invokes the callback, retries with the returned item, and does NOT drop.
    """
    dropped: list = []
    encoded: list[bytes] = []
    repackage_calls: list = []

    def repackage(item):
        repackage_calls.append(item)
        return {"item": item, "repackaged": True}

    def encode(batch):
        encoded.append(repr(batch).encode())
        return encoded[-1]

    process_batch_with_retry(
        [{"item": "huge", "repackaged": False}],
        batch_name="calls_complete",
        remote_request_bytes_limit=100_000_000,
        send_batch_fn=_send_413({"first": True}),
        processor_obj=None,
        encode_batch_fn=encode,
        log_dropped_fn=lambda batch, err: dropped.append((batch, err)),
        repackage_oversize_fn=repackage,
    )

    assert repackage_calls == [{"item": "huge", "repackaged": False}]
    # Two encode calls: original + repackaged.
    assert len(encoded) == 2
    assert b"'repackaged': True" in encoded[1]
    assert dropped == []


class _Tracker:
    def __init__(self) -> None:
        self.dropped: list = []

    def log(self, batch, err) -> None:
        self.dropped.append((batch, err))


def _encode_repr(batch) -> bytes:
    return str(batch).encode()


@pytest.mark.disable_logging_error_check
def test_413_single_item_falls_through_to_drop_for_all_unrecoverable_cases():
    """Sad paths for the repackage hook: callback returns None, callback
    raises, retry still 413, no callback supplied. All four collapse to the
    same outcome - one entry in the drop log, no crash.
    """

    def boom(item):
        raise RuntimeError("save_object hit the network")

    cases: list[tuple[str, dict]] = [
        ("callback_returns_none", {"repackage_oversize_fn": lambda item: None}),
        ("callback_raises", {"repackage_oversize_fn": boom}),
        (
            "retry_still_413",
            {"repackage_oversize_fn": lambda item: {"item": "still_huge"}},
        ),
        ("no_callback", {}),
    ]

    for name, extra in cases:
        tracker = _Tracker()
        send_fn = (
            _send_413(None)
            if name == "retry_still_413"
            else _send_413({"first": True})
        )
        process_batch_with_retry(
            [{"item": "huge"}],
            batch_name="calls",
            remote_request_bytes_limit=100_000_000,
            send_batch_fn=send_fn,
            processor_obj=None,
            encode_batch_fn=_encode_repr,
            log_dropped_fn=tracker.log,
            **extra,
        )
        assert len(tracker.dropped) == 1, f"{name}: expected exactly one dropped batch"


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
