import pytest
from gql.transport.exceptions import TransportQueryError, TransportServerError

from weave.trace_server.errors import (
    InvalidRequest,
    NotFoundError,
    handle_server_exception,
)


class TestHandleServerException:
    def test_transport_server_error_preserves_401_status_code(self):
        """TransportServerError with 401 should return 401, not 500."""
        exc = TransportServerError("401 Unauthorized", code=401)
        result = handle_server_exception(exc)
        assert result.status_code == 401
        assert result.message == {"reason": "401 Unauthorized"}

    def test_transport_server_error_preserves_403_status_code(self):
        """TransportServerError with 403 should return 403."""
        exc = TransportServerError("403 Forbidden", code=403)
        result = handle_server_exception(exc)
        assert result.status_code == 403
        assert result.message == {"reason": "403 Forbidden"}

    def test_transport_server_error_preserves_500_status_code(self):
        """TransportServerError with 500 should return 500."""
        exc = TransportServerError("500 Internal Server Error", code=500)
        result = handle_server_exception(exc)
        assert result.status_code == 500
        assert result.message == {"reason": "500 Internal Server Error"}

    def test_transport_server_error_with_none_code_returns_500(self):
        """TransportServerError without a code should fall back to 500."""
        exc = TransportServerError("Some error", code=None)
        result = handle_server_exception(exc)
        assert result.status_code == 500
        assert result.message == {"reason": "Internal server error"}

    def test_transport_query_error_returns_403(self):
        """TransportQueryError should return 403 as registered."""
        exc = TransportQueryError("Query failed")
        result = handle_server_exception(exc)
        assert result.status_code == 403
        assert result.message == {"reason": "Forbidden"}

    def test_invalid_request_returns_400(self):
        """InvalidRequest should return 400."""
        exc = InvalidRequest("Bad request")
        result = handle_server_exception(exc)
        assert result.status_code == 400
        assert result.message == {"reason": "Bad request"}

    def test_not_found_error_returns_404(self):
        """NotFoundError should return 404."""
        exc = NotFoundError("Resource not found")
        result = handle_server_exception(exc)
        assert result.status_code == 404
        assert result.message == {"reason": "Resource not found"}

    def test_unregistered_exception_returns_500(self):
        """Unregistered exceptions should return 500."""

        class CustomException(Exception):
            pass

        exc = CustomException("Something went wrong")
        result = handle_server_exception(exc)
        assert result.status_code == 500
        assert result.message == {"reason": "Internal server error"}
