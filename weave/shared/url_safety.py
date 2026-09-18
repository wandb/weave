"""Server-side URL safety helpers.

Used to gate any place where the trace server fetches a URL whose host
could come from an untrusted source: provider base URLs, upstream image
generation responses, etc. Primary protection belongs at the network
layer (pod egress policy); this module is belt-and-suspenders.

`is_publicly_routable_url` rejects:
- non-http(s) schemes
- empty / missing host
- localhost variants and reserved cloud-metadata hostnames
- IP literals that are not globally routable, including alternative IPv4
  encodings (decimal, hex, octal) that bypass naive string checks
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = frozenset({"http", "https"})

LOCALHOST_LITERALS = frozenset(
    {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}
)

# Symbolic hostnames that resolve to cloud instance-metadata services.
# Bare-IP IMDS (169.254.169.254) is covered by the is_global check below;
# this regex catches the hostnames that resolve to it.
BLOCKED_HOSTNAME_RE = re.compile(
    r"(?:^|\.)"
    r"(?:metadata\.google\.internal"
    r"|metadata\.goog"
    r"|metadata\.internal"
    r"|metadata\.azure\.com"
    r")\.?$",
    re.IGNORECASE,
)


def is_publicly_routable_url(url: str) -> bool:
    """Return True if `url` is safe to fetch from a server context.

    A URL is considered safe when it parses cleanly, uses http or https,
    has a host that is neither a localhost literal nor a known cloud-
    metadata hostname, and (if the host is an IP literal in any common
    encoding) resolves to a globally routable address.

    Non-IP hostnames are accepted on the assumption that DNS resolution
    and further egress filtering happen downstream. DNS-rebinding attacks
    against hostnames are the egress policy's job, not this function's.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False

    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return False

    if host in LOCALHOST_LITERALS or host.endswith(".localhost"):
        return False

    if BLOCKED_HOSTNAME_RE.search(host):
        return False

    addr: ipaddress.IPv4Address | ipaddress.IPv6Address | None = None
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        try:
            packed = socket.inet_aton(host)
        except OSError:
            return True
        addr = ipaddress.ip_address(packed)

    # `is_global` alone is too permissive: it returns True for IPv4/IPv6
    # multicast (e.g. 224.0.0.1, ff00::/8). Enumerate the disallowed
    # categories explicitly.
    return not (
        addr.is_loopback
        or addr.is_link_local
        or addr.is_private
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )
