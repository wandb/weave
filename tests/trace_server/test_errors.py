from gql.transport.exceptions import TransportServerError

from weave.trace_server.errors import handle_server_exception


def test_transport_server_error_preserves_status_code():
    """TransportServerError should preserve the HTTP status code from gorilla."""
    exc = TransportServerError("401 Unauthorized", code=401)
    result = handle_server_exception(exc)
    assert result.status_code == 401
    assert result.message == {"reason": "401 Unauthorized"}


def test_transport_server_error_without_code_returns_500():
    """TransportServerError without a code should fall back to 500."""
    exc = TransportServerError("Some error", code=None)
    result = handle_server_exception(exc)
    assert result.status_code == 500
