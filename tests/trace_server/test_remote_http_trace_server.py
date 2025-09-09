import datetime
from unittest.mock import patch

import pytest
import httpx
from pydantic import ValidationError

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server_bindings.remote_http_trace_server import RemoteHTTPTraceServer


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
    trace_server_url = "http://example.com"
    return RemoteHTTPTraceServer(trace_server_url)


@patch("weave.utils.http_requests.post")
def test_ok(mock_post, trace_server):
    """Test successful call_start request."""
    call_id = generate_id()
    mock_post.return_value = httpx.Response(200)
    mock_post.return_value.json = lambda: dict(
        tsi.CallStartRes(id=call_id, trace_id="test_trace_id")
    )
    mock_post.return_value.status_code = 200
    start = generate_start(call_id)
    trace_server.call_start(tsi.CallStartReq(start=start))
    mock_post.assert_called_once()


@patch("weave.utils.http_requests.post")
def test_400_no_retry(mock_post, trace_server):
    """Test that 400 errors are not retried."""
    call_id = generate_id()
    resp1 = httpx.Response(400)
    resp1.json = lambda: dict(tsi.CallStartRes(id=call_id, trace_id="test_trace_id"))

    mock_post.side_effect = [
        resp1,
    ]

    start = generate_start(call_id)
    with pytest.raises(httpx.HTTPStatusError):
        trace_server.call_start(tsi.CallStartReq(start=start))


def test_invalid_no_retry(trace_server):
    """Test that validation errors are not retried."""
    with pytest.raises(ValidationError):
        trace_server.call_start(tsi.CallStartReq(start={"invalid": "broken"}))


@patch("weave.utils.http_requests.post")
def test_500_502_503_504_429_retry(mock_post, trace_server, monkeypatch):
    """Test that 5xx and 429 errors are retried."""
    # This test has multiple failures, so it needs extra retries!
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "6")
    monkeypatch.setenv("WEAVE_RETRY_MAX_INTERVAL", "0.1")
    call_id = generate_id()

    resp0 = httpx.Response(500)

    resp1 = httpx.Response(502)

    resp2 = httpx.Response(503)

    resp3 = httpx.Response(504)

    resp4 = httpx.Response(429)

    resp5 = httpx.Response(200)
    resp5.json = lambda: dict(tsi.CallStartRes(id=call_id, trace_id="test_trace_id"))

    mock_post.side_effect = [resp0, resp1, resp2, resp3, resp4, resp5]
    start = generate_start(call_id)
    trace_server.call_start(tsi.CallStartReq(start=start))


@patch("weave.utils.http_requests.post")
def test_other_error_retry(mock_post, trace_server, monkeypatch):
    """Test that connection errors are retried."""
    # This test has multiple failures, so it needs extra retries!
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "6")
    monkeypatch.setenv("WEAVE_RETRY_MAX_INTERVAL", "0.1")
    call_id = generate_id()

    resp2 = httpx.Response(200)
    resp2.json = lambda: dict(tsi.CallStartRes(id=call_id, trace_id="test_trace_id"))

    mock_post.side_effect = [
        ConnectionResetError(),
        ConnectionError(),
        OSError(),
        TimeoutError(),
        resp2,
    ]
    start = generate_start(call_id)
    trace_server.call_start(tsi.CallStartReq(start=start))
