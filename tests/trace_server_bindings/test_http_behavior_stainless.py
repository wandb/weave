"""HTTP behavior tests for StainlessRemoteHTTPTraceServer.

These tests verify HTTP request/response handling, retry behavior for various
status codes, and error handling specific to StainlessRemoteHTTPTraceServer.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests
import tenacity
from pydantic import ValidationError

from tests.trace_server_bindings.conftest import generate_id, generate_start
from weave.trace.display.term import configure_logger
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.stainless_remote_http_trace_server import (
    StainlessRemoteHTTPTraceServer,
)
from weave.utils.retry import with_retry


@pytest.fixture
def unbatched_server():
    """Create a StainlessRemoteHTTPTraceServer instance without batching for testing."""
    return StainlessRemoteHTTPTraceServer("http://example.com")


def make_feedback_create_req(
    feedback_id: str = "feedback-id",
) -> tsi.FeedbackCreateReq:
    return tsi.FeedbackCreateReq(
        id=feedback_id,
        project_id="entity/project",
        weave_ref="weave:///entity/project/object/name:digest",
        feedback_type="custom",
        payload={"score": 1},
    )


def test_flush_feedback_empty_batch_is_noop():
    server = StainlessRemoteHTTPTraceServer("http://example.com", should_batch=True)
    server._stainless_client.feedback.batch_create = MagicMock()

    try:
        server._flush_feedback([])
    finally:
        if server.call_processor:
            server.call_processor.stop_accepting_new_work_and_flush_queue()
        if server.feedback_processor:
            server.feedback_processor.stop_accepting_new_work_and_flush_queue()

    server._stainless_client.feedback.batch_create.assert_not_called()


def test_flush_feedback_sends_batch_without_id_fields():
    server = StainlessRemoteHTTPTraceServer("http://example.com", should_batch=True)
    feedback = make_feedback_create_req()
    server._stainless_client.feedback.batch_create = MagicMock()

    try:
        server._flush_feedback([feedback])
    finally:
        if server.call_processor:
            server.call_processor.stop_accepting_new_work_and_flush_queue()
        if server.feedback_processor:
            server.feedback_processor.stop_accepting_new_work_and_flush_queue()

    server._stainless_client.feedback.batch_create.assert_called_once()
    sent_batch = server._stainless_client.feedback.batch_create.call_args.kwargs[
        "batch"
    ]
    assert sent_batch == [
        feedback.model_dump(exclude={"id", "created_at"}, exclude_none=True)
    ]


def test_flush_feedback_falls_back_to_individual_on_404():
    server = StainlessRemoteHTTPTraceServer("http://example.com", should_batch=True)
    feedback_batch = [
        make_feedback_create_req("feedback-1"),
        make_feedback_create_req("feedback-2"),
    ]

    class _BatchNotFoundError(Exception):
        status_code = 404

    server._stainless_client.feedback.batch_create = MagicMock(
        side_effect=_BatchNotFoundError()
    )
    server._stainless_client.feedback.create = MagicMock()

    try:
        server._flush_feedback(feedback_batch)
    finally:
        if server.call_processor:
            server.call_processor.stop_accepting_new_work_and_flush_queue()
        if server.feedback_processor:
            server.feedback_processor.stop_accepting_new_work_and_flush_queue()

    assert server._stainless_client.feedback.batch_create.call_count == 1
    assert server._stainless_client.feedback.create.call_count == len(feedback_batch)

    for call in server._stainless_client.feedback.create.call_args_list:
        kwargs = call.kwargs
        assert "id" not in kwargs
        assert "created_at" not in kwargs


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
def test_timeout_retry_mechanism(success_response):
    """Test that timeouts trigger the retry mechanism."""
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
def fast_retrying_server():
    """Create a StainlessRemoteHTTPTraceServer with fast retry settings for testing."""
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
