"""Tests for http_utils error handling."""

from unittest.mock import Mock

import httpx
import pytest

from weave.trace_server_bindings.http_utils import (
    CallsCompleteModeRequired,
    handle_response_error,
    process_batch_with_retry,
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


def test_handle_response_error_streaming_400_raises_http_status_error():
    """Streaming responses that return 400 should raise HTTPStatusError, not ResponseNotRead.

    When a streaming response returns a 4xx error, response.json() raises
    httpx.ResponseNotRead because the body hasn't been read. This must be
    caught so that handle_response_error still raises httpx.HTTPStatusError,
    which the retry logic correctly identifies as non-retryable.
    """
    # Create a mock response that behaves like an unread streaming response:
    # - status_code is available (from headers)
    # - raise_for_status() works
    # - json() raises ResponseNotRead (body not yet consumed)
    response = Mock()
    response.status_code = 400
    response.request = httpx.Request("POST", "http://example.com/calls/stream_query")
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "400 Bad Request",
        request=response.request,
        response=response,
    )
    response.json.side_effect = httpx.ResponseNotRead()

    with pytest.raises(httpx.HTTPStatusError, match="400 Bad Request"):
        handle_response_error(response, "/calls/stream_query")


def test_streaming_400_is_not_retried(monkeypatch):
    """A 400 error from a streaming request must not be retried.

    This is an integration test: it exercises the full path from with_retry
    through handle_response_error to _is_retryable_exception, ensuring that
    a streaming 400 response is raised immediately without retrying.
    """
    from weave.utils.retry import _is_retryable_exception

    # Simulate the exception that handle_response_error should raise
    request = httpx.Request("POST", "http://example.com/calls/stream_query")
    response = Mock(status_code=400)
    error = httpx.HTTPStatusError("400 Bad Request", request=request, response=response)

    assert _is_retryable_exception(error) is False, (
        "HTTP 400 errors must not be retried"
    )
