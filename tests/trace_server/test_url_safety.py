"""Tests for `weave.trace_server.url_safety.is_publicly_routable_url`."""

from __future__ import annotations

import pytest

from weave.trace_server.url_safety import is_publicly_routable_url


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "http://my-ollama-server.example.com:11434",
        "https://cdn.openai.com/foo/bar.png",
        "https://oaidalleapiprodscus.blob.core.windows.net/private/image.png",
        "http://images.example.org/x.jpg",
        "https://example.com:8443/path",
        "https://example.com./trailing-dot",
        "http://user:pass@example.com/",
        "HTTPS://Example.Com/Path",
        "https://evil.example.com/",
    ],
)
def test_accepts_public_http_urls(url: str) -> None:
    assert is_publicly_routable_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "ftp://files.example.com",
        "file:///etc/passwd",
        "gopher://internal.svc/",
        "ws://example.com/",
        "wss://example.com/",
        "javascript:alert(1)",
        "data:text/plain,hello",
    ],
)
def test_rejects_non_http_schemes(url: str) -> None:
    assert is_publicly_routable_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not a url",
        "http:///no-host",
        "http://",
        "https://",
    ],
)
def test_rejects_malformed_or_hostless(url: str) -> None:
    assert is_publicly_routable_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://localhost",
        "http://LOCALHOST/path",
        "http://localhost.localdomain/",
        "http://ip6-localhost/",
        "http://ip6-loopback/",
        "http://foo.localhost/",
        "http://a.b.localhost/",
    ],
)
def test_rejects_localhost_variants(url: str) -> None:
    assert is_publicly_routable_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "http://metadata.google.internal/",
        "http://metadata.google.internal./",
        "http://foo.metadata.google.internal/",
        "http://metadata.goog/",
        "http://metadata.internal/",
        "http://metadata.azure.com/",
        "http://METADATA.GOOGLE.INTERNAL/",
    ],
)
def test_rejects_cloud_metadata_hostnames(url: str) -> None:
    assert is_publicly_routable_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        # loopback
        "http://127.0.0.1/",
        "http://127.0.0.1:6379/",
        # private RFC1918
        "http://10.0.0.1/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        # link-local (incl. IMDS)
        "http://169.254.169.254/latest/meta-data/",
        # unspecified / multicast / broadcast
        "http://0.0.0.0/",
        "http://224.0.0.1/",
        "http://255.255.255.255/",
    ],
)
def test_rejects_non_global_ipv4(url: str) -> None:
    assert is_publicly_routable_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "http://[::1]/",
        "http://[fe80::1]/",
        "http://[fc00::1]/",
        "http://[ff00::1]/",
        "http://[::ffff:169.254.169.254]/",
        "http://[::ffff:10.0.0.1]/",
    ],
)
def test_rejects_non_global_ipv6(url: str) -> None:
    assert is_publicly_routable_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "http://0x7f000001/",  # hex 127.0.0.1
        "http://0xa9fea9fe/",  # hex 169.254.169.254
        "http://2130706433/",  # decimal 127.0.0.1
        "http://2852039166/",  # decimal 169.254.169.254
        "http://0/",  # decimal 0.0.0.0
    ],
)
def test_rejects_alt_ipv4_encodings(url: str) -> None:
    """Alternative IPv4 encodings (hex/decimal) must not bypass the IP check.

    socket.inet_aton accepts these forms; a naive ipaddress.ip_address check
    would let them through.
    """
    assert is_publicly_routable_url(url) is False
