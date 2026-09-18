"""Compatibility imports; definitions live in weave.shared.trace_server."""

from weave.shared.trace_server.helpers.url_safety import (
    ALLOWED_SCHEMES,
    BLOCKED_HOSTNAME_RE,
    LOCALHOST_LITERALS,
    annotations,
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
    "annotations",
    "ipaddress",
    "is_publicly_routable_url",
    "re",
    "socket",
    "urlparse",
]
