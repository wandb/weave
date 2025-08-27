"""Tests for trace URL generation."""

import os
from unittest import mock

import pytest

from weave.trace import urls


class TestRedirectCall:
    """Test the redirect_call function with various configurations."""

    def test_redirect_call_default(self):
        """Test redirect_call without WF_TRACE_SERVER_URL set."""
        # Ensure WF_TRACE_SERVER_URL is not set
        with mock.patch.dict(os.environ, {}, clear=True):
            url = urls.redirect_call("test-entity", "test-project", "call-123")
            # Should use the default wandb.ai URL
            assert "test-entity/test-project" in url
            assert "/r/call/call-123" in url
            # The actual domain depends on wandb config, but should not be localhost
            assert "localhost" not in url

    def test_redirect_call_with_localhost_trace_server(self):
        """Test redirect_call with WF_TRACE_SERVER_URL set to localhost."""
        with mock.patch.dict(os.environ, {"WF_TRACE_SERVER_URL": "http://localhost:9000"}):
            url = urls.redirect_call("test-entity", "test-project", "call-123")
            assert url == "http://localhost:9000/test-entity/test-project/weave/r/call/call-123"

    def test_redirect_call_with_custom_host(self):
        """Test redirect_call with WF_TRACE_SERVER_URL set to a custom host."""
        with mock.patch.dict(os.environ, {"WF_TRACE_SERVER_URL": "http://custom-host:8080/traces"}):
            url = urls.redirect_call("test-entity", "test-project", "call-123")
            assert url == "http://custom-host:8080/test-entity/test-project/weave/r/call/call-123"

    def test_redirect_call_with_https_url(self):
        """Test redirect_call with HTTPS trace server URL."""
        with mock.patch.dict(os.environ, {"WF_TRACE_SERVER_URL": "https://secure-host:443"}):
            url = urls.redirect_call("test-entity", "test-project", "call-123")
            assert url == "https://secure-host:443/test-entity/test-project/weave/r/call/call-123"

    def test_redirect_call_with_no_port(self):
        """Test redirect_call with trace server URL without explicit port."""
        with mock.patch.dict(os.environ, {"WF_TRACE_SERVER_URL": "http://myhost"}):
            url = urls.redirect_call("test-entity", "test-project", "call-123")
            assert url == "http://myhost/test-entity/test-project/weave/r/call/call-123"

    def test_redirect_call_with_invalid_url_fallback(self):
        """Test redirect_call falls back to localhost:9000 for invalid URLs."""
        # URL without scheme should fallback
        with mock.patch.dict(os.environ, {"WF_TRACE_SERVER_URL": "invalid-url-no-scheme"}):
            url = urls.redirect_call("test-entity", "test-project", "call-123")
            assert url == "http://localhost:9000/test-entity/test-project/weave/r/call/call-123"

    def test_redirect_call_with_special_characters_in_project(self):
        """Test redirect_call properly quotes special characters in project name."""
        with mock.patch.dict(os.environ, {"WF_TRACE_SERVER_URL": "http://localhost:9000"}):
            url = urls.redirect_call("test-entity", "test project/with spaces", "call-123")
            assert "test%20project%2Fwith%20spaces" in url
            assert url == "http://localhost:9000/test-entity/test%20project%2Fwith%20spaces/weave/r/call/call-123"

    def test_redirect_call_preserves_path_in_url(self):
        """Test that redirect_call ignores any path in WF_TRACE_SERVER_URL."""
        # The path "/some/path" should be ignored, only host:port is used
        with mock.patch.dict(os.environ, {"WF_TRACE_SERVER_URL": "http://localhost:9000/some/path"}):
            url = urls.redirect_call("test-entity", "test-project", "call-123")
            assert url == "http://localhost:9000/test-entity/test-project/weave/r/call/call-123"