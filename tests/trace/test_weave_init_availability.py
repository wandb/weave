"""Tests for weave init server availability checking."""

import json
from unittest.mock import MagicMock

from weave.trace import weave_init
from weave.trace_server_bindings import remote_http_trace_server


def test_weave_is_available_json_decode_error():
    """Test that _weave_is_available returns False server is not available."""
    mock_server = MagicMock(spec=remote_http_trace_server.RemoteHTTPTraceServer)
    mock_server.server_info.side_effect = json.JSONDecodeError("test error", "doc", 0)

    result = weave_init._weave_is_available(mock_server)

    assert result is False
    mock_server.server_info.assert_called_once()


def test_weave_is_available_success():
    """Test that _weave_is_available returns True when server is available."""
    mock_server = MagicMock(spec=remote_http_trace_server.RemoteHTTPTraceServer)
    mock_server.server_info.return_value = {"version": "1.0.0"}

    result = weave_init._weave_is_available(mock_server)

    assert result is True
    mock_server.server_info.assert_called_once()
