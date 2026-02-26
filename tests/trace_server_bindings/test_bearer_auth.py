"""Tests for Bearer auth support with wb_at_ tokens."""

from __future__ import annotations

import pytest

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
        server = RemoteHTTPTraceServer("http://example.com", should_batch=False)
        server.set_auth(("api", "wb_at_sometoken.signature"))

        assert server._auth is None
        assert server._bearer_token == "wb_at_sometoken.signature"

    def test_wb_at_token_injects_bearer_header(self) -> None:
        server = RemoteHTTPTraceServer("http://example.com", should_batch=False)
        server.set_auth(("api", "wb_at_sometoken.signature"))

        headers = server._build_dynamic_request_headers()
        assert headers["Authorization"] == "Bearer wb_at_sometoken.signature"

    def test_regular_key_no_bearer_header(self) -> None:
        server = RemoteHTTPTraceServer("http://example.com", should_batch=False)
        server.set_auth(("api", "regular_api_key_1234567890"))

        headers = server._build_dynamic_request_headers()
        assert "Authorization" not in headers

    def test_constructor_auth_routes_correctly(self) -> None:
        server = RemoteHTTPTraceServer(
            "http://example.com",
            should_batch=False,
            auth=("api", "wb_at_fromconstructor.sig"),
        )
        assert server._auth is None
        assert server._bearer_token == "wb_at_fromconstructor.sig"

    def test_switching_from_bearer_to_basic(self) -> None:
        server = RemoteHTTPTraceServer("http://example.com", should_batch=False)
        server.set_auth(("api", "wb_at_sometoken.signature"))
        assert server._bearer_token is not None

        server.set_auth(("api", "regular_key_1234567890abcdef"))
        assert server._auth == ("api", "regular_key_1234567890abcdef")
        assert server._bearer_token is None


class TestStainlessRemoteHTTPTraceServerAuth:
    """Test auth routing in StainlessRemoteHTTPTraceServer."""

    def test_regular_api_key_uses_basic_auth(self) -> None:
        try:
            from weave.trace_server_bindings.stainless_remote_http_trace_server import (
                StainlessRemoteHTTPTraceServer,
            )
        except ImportError:
            pytest.skip("stainless SDK not available")

        server = StainlessRemoteHTTPTraceServer(
            "http://example.com", should_batch=False
        )
        server.set_auth(("api", "regular_api_key_1234567890"))

        assert server._username == "api"
        assert server._password == "regular_api_key_1234567890"

    def test_wb_at_token_uses_bearer_auth(self) -> None:
        try:
            from weave.trace_server_bindings.stainless_remote_http_trace_server import (
                StainlessRemoteHTTPTraceServer,
            )
        except ImportError:
            pytest.skip("stainless SDK not available")

        server = StainlessRemoteHTTPTraceServer(
            "http://example.com", should_batch=False
        )
        server.set_auth(("api", "wb_at_sometoken.signature"))

        # Bearer mode: username/password cleared, header set on client
        assert server._username == ""
        assert server._password == ""
