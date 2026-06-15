"""Tests for weave init server availability checking."""

import json
from unittest.mock import MagicMock

from weave.trace import weave_init
from weave.trace_server_bindings import remote_http_trace_server


def test_get_server_info_success_and_json_decode_error():
    """_get_server_info returns the server info on success and None when the
    response cannot be decoded; either way it calls server_info exactly once.
    """
    ok_server = MagicMock(spec=remote_http_trace_server.RemoteHTTPTraceServer)
    server_info = {"version": "1.0.0"}
    ok_server.server_info.return_value = server_info
    assert weave_init._get_server_info(ok_server) == server_info
    ok_server.server_info.assert_called_once()

    bad_server = MagicMock(spec=remote_http_trace_server.RemoteHTTPTraceServer)
    bad_server.server_info.side_effect = json.JSONDecodeError("test error", "doc", 0)
    assert weave_init._get_server_info(bad_server) is None
    bad_server.server_info.assert_called_once()
