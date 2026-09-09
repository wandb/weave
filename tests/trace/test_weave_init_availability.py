"""Tests for weave init server availability checking."""

import json
from unittest.mock import MagicMock

import pytest

from weave.trace import weave_init
from weave.trace_server_bindings import remote_http_trace_server


def test_get_server_info_reports_the_underlying_error():
    """Test that _get_server_info surfaces why the server could not be reached."""
    mock_server = MagicMock(spec=remote_http_trace_server.RemoteHTTPTraceServer)
    mock_server.server_info.side_effect = json.JSONDecodeError("test error", "doc", 0)

    with pytest.raises(RuntimeError) as excinfo:
        weave_init._get_server_info(mock_server)

    assert str(excinfo.value) == (
        "Weave is not available on the server: test error: line 1 column 1 (char 0). "
        "Please contact support."
    )
    assert isinstance(excinfo.value.__cause__, json.JSONDecodeError)
    mock_server.server_info.assert_called_once()


def test_get_server_info_success():
    """Test that _get_server_info returns server info when server is available."""
    mock_server = MagicMock(spec=remote_http_trace_server.RemoteHTTPTraceServer)
    server_info = {"version": "1.0.0"}
    mock_server.server_info.return_value = server_info

    result = weave_init._get_server_info(mock_server)

    assert result == server_info
    mock_server.server_info.assert_called_once()
