"""Tests for trace URL generation."""

from weave.trace import urls


def test_redirect_call_default(monkeypatch):
    """Test redirect_call without WF_TRACE_SERVER_URL set."""
    monkeypatch.delenv("WF_TRACE_SERVER_URL", raising=False)

    url = urls.redirect_call("test-entity", "test-project", "call-123")
    assert "test-entity/test-project" in url
    assert "/r/call/call-123" in url
    assert "wandb.ai" in url


def test_redirect_call_with_localhost_trace_server(monkeypatch):
    """Test redirect_call with WF_TRACE_SERVER_URL set to localhost."""
    monkeypatch.setenv("WF_TRACE_SERVER_URL", "http://localhost:9000")

    url = urls.redirect_call("test-entity", "test-project", "call-123")
    assert url == "http://localhost:9000/test-entity/test-project/weave/r/call/call-123"


def test_redirect_call_with_custom_host(monkeypatch):
    """Test redirect_call with WF_TRACE_SERVER_URL set to a custom host."""
    monkeypatch.setenv("WF_TRACE_SERVER_URL", "http://custom-host:8080/traces")

    url = urls.redirect_call("test-entity", "test-project", "call-123")
    assert (
        url == "http://custom-host:8080/test-entity/test-project/weave/r/call/call-123"
    )


def test_redirect_call_with_https_url(monkeypatch):
    """Test redirect_call with HTTPS trace server URL."""
    monkeypatch.setenv("WF_TRACE_SERVER_URL", "https://secure-host:443")

    url = urls.redirect_call("test-entity", "test-project", "call-123")
    assert (
        url == "https://secure-host:443/test-entity/test-project/weave/r/call/call-123"
    )


def test_redirect_call_with_no_port(monkeypatch):
    """Test redirect_call with trace server URL without explicit port."""
    monkeypatch.setenv("WF_TRACE_SERVER_URL", "http://myhost")

    url = urls.redirect_call("test-entity", "test-project", "call-123")
    assert url == "http://myhost/test-entity/test-project/weave/r/call/call-123"


def test_redirect_call_with_invalid_url_fallback(monkeypatch):
    """Test redirect_call falls back to localhost:9000 for invalid URLs."""
    # URL without scheme should fallback
    monkeypatch.setenv("WF_TRACE_SERVER_URL", "invalid-url-no-scheme")

    url = urls.redirect_call("test-entity", "test-project", "call-123")
    assert url == "http://localhost:9000/test-entity/test-project/weave/r/call/call-123"
