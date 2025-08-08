import datetime

import httpx
import pytest
from pydantic import ValidationError

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server_bindings.stainless_trace_server import RemoteHTTPTraceServer

BASE_URL = "http://example.com"


def generate_start(id) -> tsi.StartedCallSchemaForInsert:
    """Generate a test StartedCallSchemaForInsert.

    Args:
        id: The call ID to use, or None to generate one.

    Returns:
        A StartedCallSchemaForInsert instance for testing.
    """
    return tsi.StartedCallSchemaForInsert(
        project_id="test",
        id=id or generate_id(),
        op_name="test_name",
        trace_id="test_trace_id",
        parent_id="test_parent_id",
        started_at=datetime.datetime.now(tz=datetime.timezone.utc)
        - datetime.timedelta(seconds=1),
        attributes={"a": 5},
        inputs={"b": 5},
    )


@pytest.fixture
def trace_server():
    """Create a RemoteHTTPTraceServer instance for testing."""
    return RemoteHTTPTraceServer(trace_server_url=BASE_URL)


@pytest.mark.respx(base_url=BASE_URL)
def test_ok(respx_mock, trace_server):
    """Test successful call_start request."""
    call_id = generate_id()
    # Mock the POST request to the trace server
    route = respx_mock.post("/call/start").mock(
        return_value=httpx.Response(
            status_code=200,
            json=dict(tsi.CallStartRes(id=call_id, trace_id="test_trace_id")),
        )
    )
    start = generate_start(call_id)
    trace_server.call_start(tsi.CallStartReq(start=start))
    assert route.called


@pytest.mark.respx(base_url=BASE_URL)
def test_400_no_retry(respx_mock, trace_server):
    """Test that 400 errors are not retried."""
    call_id = generate_id()
    # Mock a 400 response
    respx_mock.post("/call/start").mock(
        return_value=httpx.Response(
            status_code=400,
            json=dict(tsi.CallStartRes(id=call_id, trace_id="test_trace_id")),
        )
    )

    start = generate_start(call_id)
    # Stainless wraps httpx errors in its own APIStatusError
    from weave_server_sdk import APIStatusError

    with pytest.raises(APIStatusError):
        trace_server.call_start(tsi.CallStartReq(start=start))


def test_invalid_no_retry(trace_server):
    """Test that validation errors are not retried."""
    with pytest.raises(ValidationError):
        trace_server.call_start(tsi.CallStartReq(start={"invalid": "broken"}))


@pytest.mark.respx(base_url=BASE_URL)
def test_500_502_503_504_429_retry(respx_mock, trace_server, monkeypatch):
    """Test that 5xx and 429 errors are retried."""
    # This test has multiple failures, so it needs extra retries!
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "6")
    monkeypatch.setenv("WEAVE_RETRY_MAX_INTERVAL", "0.1")
    call_id = generate_id()

    # Set up the mock route with multiple responses
    route = respx_mock.post("/call/start").mock(
        side_effect=[
            httpx.Response(status_code=500),
            httpx.Response(status_code=502),
            httpx.Response(status_code=503),
            httpx.Response(status_code=504),
            httpx.Response(status_code=429),
            httpx.Response(
                status_code=200,
                json=dict(tsi.CallStartRes(id=call_id, trace_id="test_trace_id")),
            ),
        ]
    )
    start = generate_start(call_id)
    trace_server.call_start(tsi.CallStartReq(start=start))
    assert route.call_count == 6


@pytest.mark.respx(base_url=BASE_URL)
def test_other_error_retry(respx_mock, trace_server, monkeypatch):
    """Test that connection errors are retried."""
    # This test has multiple failures, so it needs extra retries!
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "6")
    monkeypatch.setenv("WEAVE_RETRY_MAX_INTERVAL", "0.1")
    call_id = generate_id()

    # Set up the mock route with multiple error responses followed by success
    route = respx_mock.post("/call/start").mock(
        side_effect=[
            httpx.ConnectError("Connection reset"),
            httpx.ConnectError("Connection error"),
            OSError(),
            httpx.TimeoutException("Timeout"),
            httpx.Response(
                status_code=200,
                json=dict(tsi.CallStartRes(id=call_id, trace_id="test_trace_id")),
            ),
        ]
    )
    start = generate_start(call_id)
    trace_server.call_start(tsi.CallStartReq(start=start))
    assert route.call_count == 5
