"""Tests for Bearer auth support with wb_at_ tokens."""

from __future__ import annotations

import pytest

from weave.trace_server_bindings.http_utils import WB_AGENT_TOKEN_PREFIX
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
)


class TestRemoteHTTPTraceServerAuth:
    """Test auth routing in RemoteHTTPTraceServer."""

    def test_regular_api_key_uses_basic_auth(self) -> None:
        server = RemoteHTTPTraceServer("http://example.com", should_batch=False)
        server.set_auth(("api", "regular_api_key_1234567890"))

        assert server._auth == ("api", "regular_api_key_1234567890")
        assert server._bearer_token is None

    def test_wb_at_token_uses_bearer_auth(self) -> None:
        token = f"{WB_AGENT_TOKEN_PREFIX}sometoken.signature"
        server = RemoteHTTPTraceServer("http://example.com", should_batch=False)
        server.set_auth(("api", token))

        assert server._auth is None
        assert server._bearer_token == token

    def test_wb_at_token_injects_bearer_header(self) -> None:
        token = f"{WB_AGENT_TOKEN_PREFIX}sometoken.signature"
        server = RemoteHTTPTraceServer("http://example.com", should_batch=False)
        server.set_auth(("api", token))

        headers = server._build_dynamic_request_headers()
        assert headers["Authorization"] == f"Bearer {token}"

    def test_regular_key_no_bearer_header(self) -> None:
        server = RemoteHTTPTraceServer("http://example.com", should_batch=False)
        server.set_auth(("api", "regular_api_key_1234567890"))

        headers = server._build_dynamic_request_headers()
        assert "Authorization" not in headers

    def test_constructor_auth_routes_correctly(self) -> None:
        token = f"{WB_AGENT_TOKEN_PREFIX}fromconstructor.sig"
        server = RemoteHTTPTraceServer(
            "http://example.com",
            should_batch=False,
            auth=("api", token),
        )
        assert server._auth is None
        assert server._bearer_token == token

    def test_switching_from_bearer_to_basic(self) -> None:
        token = f"{WB_AGENT_TOKEN_PREFIX}sometoken.signature"
        server = RemoteHTTPTraceServer("http://example.com", should_batch=False)
        server.set_auth(("api", token))
        assert server._bearer_token is not None

        server.set_auth(("api", "regular_key_1234567890abcdef"))
        assert server._auth == ("api", "regular_key_1234567890abcdef")
        assert server._bearer_token is None


def _try_import_stainless():
    try:
        from weave.trace_server_bindings.stainless_remote_http_trace_server import (
            StainlessRemoteHTTPTraceServer,
        )

        return StainlessRemoteHTTPTraceServer
    except ImportError:
        return None


_StainlessServer = _try_import_stainless()
_skip_no_stainless = pytest.mark.skipif(
    _StainlessServer is None, reason="stainless SDK not available"
)


@_skip_no_stainless
class TestStainlessRemoteHTTPTraceServerAuth:
    """Test auth routing in StainlessRemoteHTTPTraceServer."""

    def _make_server(self, **kwargs):
        return _StainlessServer("http://example.com", should_batch=False, **kwargs)

    def test_regular_api_key_uses_basic_auth(self) -> None:
        server = self._make_server()
        server.set_auth(("api", "regular_api_key_1234567890"))

        assert server._username == "api"
        assert server._password == "regular_api_key_1234567890"

    def test_regular_key_no_bearer_header(self) -> None:
        server = self._make_server()
        server.set_auth(("api", "regular_api_key_1234567890"))

        headers = server._stainless_client.default_headers
        assert "Authorization" not in headers

    def test_wb_at_token_uses_bearer_auth(self) -> None:
        token = f"{WB_AGENT_TOKEN_PREFIX}sometoken.signature"
        server = self._make_server()
        server.set_auth(("api", token))

        assert server._username == ""
        assert server._password == ""

    def test_wb_at_token_injects_bearer_header(self) -> None:
        token = f"{WB_AGENT_TOKEN_PREFIX}sometoken.signature"
        server = self._make_server()
        server.set_auth(("api", token))

        headers = server._stainless_client.default_headers
        assert headers["Authorization"] == f"Bearer {token}"

    def test_switching_from_bearer_to_basic(self) -> None:
        token = f"{WB_AGENT_TOKEN_PREFIX}sometoken.signature"
        server = self._make_server()
        server.set_auth(("api", token))

        headers = server._stainless_client.default_headers
        assert headers["Authorization"] == f"Bearer {token}"

        server.set_auth(("api", "regular_key_1234567890abcdef"))
        assert server._username == "api"
        assert server._password == "regular_key_1234567890abcdef"

        headers = server._stainless_client.default_headers
        assert "Authorization" not in headers
