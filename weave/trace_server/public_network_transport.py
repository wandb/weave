"""httpx transports that only connect to publicly routable addresses.

Used for requests to user-configured hosts such as custom runtime base URLs.
Each request resolves its hostname once, rejects it if any answer is not
publicly routable, and connects to a checked address while keeping the
original hostname for the Host header, TLS SNI, and certificate verification.
Because the check runs per request, every redirect hop is checked too.
"""

from __future__ import annotations

import ipaddress
import socket

import anyio
import httpx

from weave.shared.helpers.url_safety import is_publicly_routable_ip
from weave.trace_server.environment import (
    CUSTOM_RUNTIME_ALLOWED_PRIVATE_CIDRS_ENV,
    wf_custom_runtime_allowed_private_cidrs,
)

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

# Cloud metadata and fabric endpoints stay unreachable even inside an exempted network.
NEVER_REACHABLE_NETWORKS = (
    ipaddress.ip_network("169.254.0.0/16"),  # IPv4 link-local, incl. 169.254.169.254
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fd00:ec2::254/128"),  # AWS IPv6 metadata
    ipaddress.ip_network("fd20:ce::254/128"),  # GCP IPv6 metadata
    ipaddress.ip_network("168.63.129.16/32"),  # Azure WireServer, a public address
)


class NonPublicAddressError(httpx.ConnectError):
    pass


def _allowed_private_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks = []
    for entry in wf_custom_runtime_allowed_private_cidrs():
        try:
            networks.append(ipaddress.ip_network(entry))
        except ValueError as e:
            raise ValueError(
                f"{CUSTOM_RUNTIME_ALLOWED_PRIVATE_CIDRS_ENV} entry {entry!r} is not a CIDR network"
            ) from e
    return networks


def _checked_addresses(
    request: httpx.Request, host: str, answers: list[tuple]
) -> list[IPAddress]:
    addresses = list(
        dict.fromkeys(ipaddress.ip_address(answer[4][0]) for answer in answers)
    )
    if not addresses:
        raise httpx.ConnectError(f"No addresses found for {host}", request=request)
    allowed_networks = _allowed_private_networks()
    for address in addresses:
        # An IPv4-mapped IPv6 address reaches the embedded IPv4 host.
        target = getattr(address, "ipv4_mapped", None) or address
        if any(target in network for network in NEVER_REACHABLE_NETWORKS) or not (
            is_publicly_routable_ip(target)
            or any(target in network for network in allowed_networks)
        ):
            # The resolved address stays out of the message so errors don't map internal DNS.
            raise NonPublicAddressError(
                f"Refusing to connect to {host}: its address is not publicly routable",
                request=request,
            )
    return addresses


def _pinned(request: httpx.Request, host: str, address: IPAddress) -> httpx.Request:
    extensions = dict(request.extensions)
    if request.url.scheme == "https":
        extensions["sni_hostname"] = host
    # The Host header was set from the original URL when the request was built.
    return httpx.Request(
        request.method,
        request.url.copy_with(host=str(address)),
        headers=request.headers,
        stream=request.stream,
        extensions=extensions,
    )


# Connection failures that move on to the next checked address, as
# socket.create_connection does.
_UNREACHABLE = (httpx.ConnectError, httpx.ConnectTimeout)


class PublicNetworkTransport(httpx.HTTPTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        # The ASCII (IDNA) host is what the Host header carries; resolve the same name.
        host = request.url.raw_host.decode("ascii")
        try:
            answers = socket.getaddrinfo(
                host, request.url.port, type=socket.SOCK_STREAM
            )
        except OSError as e:
            raise httpx.ConnectError(str(e), request=request) from e
        *fallbacks, last = _checked_addresses(request, host, answers)
        for address in fallbacks:
            try:
                return super().handle_request(_pinned(request, host, address))
            except _UNREACHABLE:
                continue
        return super().handle_request(_pinned(request, host, last))


class AsyncPublicNetworkTransport(httpx.AsyncHTTPTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.raw_host.decode("ascii")
        # httpcore bounds its own lookup by the connect timeout; keep that bound.
        connect_timeout = request.extensions.get("timeout", {}).get("connect")
        try:
            with anyio.fail_after(connect_timeout):
                answers = await anyio.getaddrinfo(
                    host, request.url.port, type=socket.SOCK_STREAM
                )
        except TimeoutError as e:
            raise httpx.ConnectTimeout(
                f"DNS lookup for {host} timed out", request=request
            ) from e
        except OSError as e:
            raise httpx.ConnectError(str(e), request=request) from e
        *fallbacks, last = _checked_addresses(request, host, answers)
        for address in fallbacks:
            try:
                return await super().handle_async_request(
                    _pinned(request, host, address)
                )
            except _UNREACHABLE:
                continue
        return await super().handle_async_request(_pinned(request, host, last))
