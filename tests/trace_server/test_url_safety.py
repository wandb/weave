"""Tests for `weave.trace_server.helpers.url_safety.is_publicly_routable_url`."""

from __future__ import annotations

import pytest

from weave.trace_server.helpers.url_safety import is_publicly_routable_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # public http(s) urls -> accepted
        ("https://api.openai.com/v1", True),
        ("http://my-ollama-server.example.com:11434", True),
        ("https://cdn.openai.com/foo/bar.png", True),
        ("https://oaidalleapiprodscus.blob.core.windows.net/private/image.png", True),
        ("http://images.example.org/x.jpg", True),
        ("https://example.com:8443/path", True),
        ("https://example.com./trailing-dot", True),
        ("http://user:pass@example.com/", True),
        ("HTTPS://Example.Com/Path", True),
        ("https://evil.example.com/", True),
        # non-http schemes -> rejected
        ("ftp://files.example.com", False),
        ("file:///etc/passwd", False),
        ("gopher://internal.svc/", False),
        ("ws://example.com/", False),
        ("wss://example.com/", False),
        ("javascript:alert(1)", False),
        ("data:text/plain,hello", False),
        # malformed / hostless -> rejected
        ("", False),
        ("not a url", False),
        ("http:///no-host", False),
        ("http://", False),
        ("https://", False),
        # localhost variants -> rejected
        ("http://localhost/", False),
        ("http://localhost", False),
        ("http://LOCALHOST/path", False),
        ("http://localhost.localdomain/", False),
        ("http://ip6-localhost/", False),
        ("http://ip6-loopback/", False),
        ("http://foo.localhost/", False),
        ("http://a.b.localhost/", False),
        # cloud metadata hostnames -> rejected
        ("http://metadata.google.internal/", False),
        ("http://metadata.google.internal./", False),
        ("http://foo.metadata.google.internal/", False),
        ("http://metadata.goog/", False),
        ("http://metadata.internal/", False),
        ("http://metadata.azure.com/", False),
        ("http://METADATA.GOOGLE.INTERNAL/", False),
        # non-global ipv4 (loopback, RFC1918, link-local/IMDS, unspecified/multicast/broadcast)
        ("http://127.0.0.1/", False),
        ("http://127.0.0.1:6379/", False),
        ("http://10.0.0.1/", False),
        ("http://172.16.0.1/", False),
        ("http://192.168.1.1/", False),
        ("http://169.254.169.254/latest/meta-data/", False),
        ("http://0.0.0.0/", False),
        ("http://224.0.0.1/", False),
        ("http://255.255.255.255/", False),
        # non-global ipv6
        ("http://[::1]/", False),
        ("http://[fe80::1]/", False),
        ("http://[fc00::1]/", False),
        ("http://[ff00::1]/", False),
        ("http://[::ffff:169.254.169.254]/", False),
        ("http://[::ffff:10.0.0.1]/", False),
        # alternative ipv4 encodings: socket.inet_aton accepts hex/decimal forms that a
        # naive ipaddress.ip_address check would let through; they must not bypass the check.
        ("http://0x7f000001/", False),  # hex 127.0.0.1
        ("http://0xa9fea9fe/", False),  # hex 169.254.169.254
        ("http://2130706433/", False),  # decimal 127.0.0.1
        ("http://2852039166/", False),  # decimal 169.254.169.254
        ("http://0/", False),  # decimal 0.0.0.0
    ],
)
def test_is_publicly_routable_url(url: str, expected: bool) -> None:
    assert is_publicly_routable_url(url) is expected
