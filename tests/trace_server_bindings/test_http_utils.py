"""Tests for http_utils error handling."""

import datetime
import json
from unittest.mock import Mock

import httpx
import pytest
from pydantic_core import to_json

from weave.trace.errors import NotFoundError, ObjectDeletedError
from weave.trace_server_bindings import http_utils
from weave.trace_server_bindings.http_utils import (
    CallsCompleteModeRequired,
    handle_response_error,
    process_batch_with_retry,
    retry_on_not_found,
)
from weave.vendor.weave_server_sdk import APIStatusError


def _make_response(status_code: int, body: dict | None) -> httpx.Response:
    """Build the response the two error builders below hang off."""
    return httpx.Response(
        status_code,
        json=body or {},
        request=httpx.Request("POST", "http://example.com"),
    )


def _make_httpx_error(
    status_code: int, body: dict | None = None
) -> httpx.HTTPStatusError:
    """Build the httpx error for a non-2xx response."""
    response = _make_response(status_code, body)
    return httpx.HTTPStatusError(
        str(status_code), request=response.request, response=response
    )


def _make_stainless_error(status_code: int, body: dict | None = None) -> APIStatusError:
    """Build the Stainless equivalent: an httpx response on a non-httpx error class."""
    return APIStatusError(
        str(status_code), response=_make_response(status_code, body), body=body
    )


@pytest.mark.parametrize(
    "error",
    [_make_httpx_error(413), _make_stainless_error(413)],
    ids=["httpx", "stainless"],
)
def test_413_splits_batch_and_retries(error):
    """When server returns 413, split batch in half and retry both halves."""
    sent_batches = []
    first_call = True

    def mock_send(data: bytes) -> None:
        nonlocal first_call
        if first_call:
            first_call = False
            raise error
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


def test_retry_on_not_found_behavior(monkeypatch):
    """Retry a non-deleted 404; skip authoritative deletes and non-404s."""
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "2")
    monkeypatch.setattr(http_utils, "NOT_FOUND_RETRY_WAIT_SECONDS", 0.0)
    calls = {"http": 0, "local": 0, "deleted_http": 0, "deleted_local": 0}

    @retry_on_not_found
    def flaky_http_404():
        calls["http"] += 1
        if calls["http"] == 1:
            raise _make_httpx_error(404, {"reason": "Obj foo:bar not found"})
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
        raise _make_httpx_error(
            404, {"reason": "deleted", "deleted_at": "2024-01-01T00:00:00Z"}
        )

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


def test_permanent_stainless_error_drops_batch():
    """A 4xx from the Stainless client is reported dropped, not requeued."""
    error = _make_stainless_error(400, {"reason": "project is in complete mode"})
    processor = Mock()
    processor.is_accepting_new_work.return_value = True
    dropped = []

    def mock_send(data: bytes) -> None:
        raise error

    process_batch_with_retry(
        [1, 2],
        batch_name="test",
        remote_request_bytes_limit=100_000,
        send_batch_fn=mock_send,
        processor_obj=processor,
        log_dropped_fn=lambda batch, err: dropped.append((batch, err)),
        encode_batch_fn=lambda b: str(b).encode(),
    )

    assert dropped == [([1, 2], error)]
    processor.enqueue.assert_not_called()


def test_retry_on_not_found_retries_stainless_404(monkeypatch):
    """A 404 from the Stainless client is retried like an httpx 404."""
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "2")
    monkeypatch.setattr(http_utils, "NOT_FOUND_RETRY_WAIT_SECONDS", 0.0)
    attempts = 0

    @retry_on_not_found
    def flaky_read():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _make_stainless_error(404, {"reason": "Obj foo:bar not found"})
        return "ok"

    assert flaky_read() == "ok"
    assert attempts == 2


@pytest.mark.parametrize(
    "error",
    [_make_httpx_error(503), _make_stainless_error(503)],
    ids=["httpx", "stainless"],
)
def test_5xx_requeues_batch_without_splitting(error):
    """A server error is retried later as the same batch, not split."""
    processor = Mock()
    processor.is_accepting_new_work.return_value = True
    sent = []

    def mock_send(data: bytes) -> None:
        sent.append(data)
        raise error

    process_batch_with_retry(
        [1, 2, 3, 4],
        batch_name="test",
        remote_request_bytes_limit=100_000,
        send_batch_fn=mock_send,
        processor_obj=processor,
        encode_batch_fn=lambda b: str(b).encode(),
    )

    assert len(sent) == 1
    processor.enqueue.assert_called_once_with([1, 2, 3, 4])


def _encode_failing_on(bad: object, error: Exception):
    """An encoder that raises `error` for any batch holding `bad`."""

    def encode(batch: list) -> bytes:
        if any(item is bad for item in batch):
            raise error
        return to_json(batch)

    return encode


@pytest.mark.parametrize(
    "make_encoder",
    [
        pytest.param(lambda bad: to_json, id="pydantic-serialization-error"),
        pytest.param(
            lambda bad: _encode_failing_on(bad, TypeError("not serializable")),
            id="type-error",
        ),
        pytest.param(
            lambda bad: _encode_failing_on(bad, ValueError("out of range")),
            id="value-error",
        ),
    ],
)
def test_unserializable_item_is_dropped_alone_without_requeue(make_encoder):
    """An item whose value cannot be encoded is dropped; the rest is sent."""
    processor = Mock()
    processor.is_accepting_new_work.return_value = True
    sent: list[bytes] = []
    dropped: list[list] = []
    bad = object()

    process_batch_with_retry(
        ["good-1", bad, "good-2"],
        batch_name="test",
        remote_request_bytes_limit=100_000,
        send_batch_fn=sent.append,
        processor_obj=processor,
        log_dropped_fn=lambda batch, e: dropped.append(batch),
        encode_batch_fn=make_encoder(bad),
    )

    assert sent == [b'["good-1"]', b'["good-2"]']
    assert dropped == [[bad]]
    processor.enqueue.assert_not_called()


def _send_rejecting(bad: set[int], sent: list[list[int]]):
    """A send function whose server rejects (422) any batch holding a bad item."""

    def send(data: bytes) -> None:
        batch = json.loads(data)
        sent.append(batch)
        if bad.intersection(batch):
            raise _make_stainless_error(422)

    return send


@pytest.mark.parametrize(
    ("bad", "expected_requests", "expected_dropped"),
    [
        # One bad item: one half is rejected at each level, 1 + 2 * log2(16).
        ({5}, 9, [[5]]),
        # Every item bad: both halves are rejected, so the batch is dropped.
        (set(range(16)), 3, [list(range(16))]),
        # Bad items in both halves look the same as every item bad.
        ({2, 12}, 3, [list(range(16))]),
        # Both bad items in one half: that half is split further.
        ({1, 2}, 7, [[0, 1, 2, 3]]),
    ],
    ids=["one_bad", "all_bad", "bad_in_both_halves", "bad_in_one_half"],
)
def test_422_finds_bad_items_without_splitting_every_item(
    bad, expected_requests, expected_dropped
):
    """A batch rejected as invalid is split only while one half is the problem."""
    sent: list[list[int]] = []
    dropped: list[list[int]] = []

    process_batch_with_retry(
        list(range(16)),
        batch_name="test",
        remote_request_bytes_limit=100_000,
        send_batch_fn=_send_rejecting(bad, sent),
        processor_obj=None,
        log_dropped_fn=lambda batch, e: dropped.append(batch),
        encode_batch_fn=lambda b: json.dumps(b).encode(),
    )

    assert len(sent) == expected_requests
    assert dropped == expected_dropped
    stored = {item for batch in sent if not bad.intersection(batch) for item in batch}
    assert stored == set(range(16)) - {item for batch in dropped for item in batch}
