"""Compatibility exports for weave.shared.url_safety."""

from weave.shared.url_safety import (
    ALLOWED_SCHEMES,
    BLOCKED_HOSTNAME_RE,
    LOCALHOST_LITERALS,
    ipaddress,
    is_publicly_routable_url,
    re,
    socket,
    urlparse,
)

__all__ = [
    "ALLOWED_SCHEMES",
    "BLOCKED_HOSTNAME_RE",
    "LOCALHOST_LITERALS",
    "ipaddress",
    "is_publicly_routable_url",
    "re",
    "socket",
    "urlparse",
]
