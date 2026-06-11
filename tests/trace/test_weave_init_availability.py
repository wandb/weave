"""Tests for weave init server availability checking."""

import json
from unittest.mock import MagicMock

from weave.trace import weave_init
from weave.trace_server_bindings import stainless_remote_http_trace_server


def test_get_server_info_json_decode_error():
    """Test that _get_server_info returns None when server info cannot be decoded."""
    mock_server = MagicMock(spec=stainless_remote_http_trace_server.StainlessRemoteHTTPTraceServer)
    mock_server.server_info.side_effect = json.JSONDecodeError("test error", "doc", 0)

    result = weave_init._get_server_info(mock_server)

    assert result is None
    mock_server.server_info.assert_called_once()


def test_get_server_info_success():
    """Test that _get_server_info returns server info when server is available."""
    mock_server = MagicMock(spec=stainless_remote_http_trace_server.StainlessRemoteHTTPTraceServer)
    server_info = {"version": "1.0.0"}
    mock_server.server_info.return_value = server_info

    result = weave_init._get_server_info(mock_server)

    assert result == server_info
    mock_server.server_info.assert_called_once()
