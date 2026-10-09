"""httpx transports that only connect to publicly routable addresses.

Used for requests to user-configured hosts such as custom runtime base URLs.
Each request resolves its hostname once, rejects it if any resolved address is not
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
    ipaddress.ip_network("fd00:ec2::23/128"),  # AWS EKS Pod Identity agent, IPv6
    ipaddress.ip_network("fd20:ce::254/128"),  # GCP IPv6 metadata
    ipaddress.ip_network("168.63.129.16/32"),  # Azure WireServer (public IP)
    ipaddress.ip_network("100.100.100.200/32"),  # Alibaba Cloud metadata (CGNAT)
)


class NonPublicAddressError(httpx.ConnectError):
    pass


def _checked_addresses(
    request: httpx.Request, host: str, addrinfos: list[tuple]
) -> list[IPAddress]:
    # Each addrinfo is (family, type, proto, canonname, sockaddr); sockaddr[0] is the IP.
    addresses = list(
        dict.fromkeys(ipaddress.ip_address(addrinfo[4][0]) for addrinfo in addrinfos)
    )
    if not addresses:
        raise httpx.ConnectError(f"No addresses found for {host}", request=request)
    allowed_networks = []
    for entry in wf_custom_runtime_allowed_private_cidrs():
        try:
            allowed_networks.append(ipaddress.ip_network(entry))
        except ValueError as e:
            raise ValueError(
                f"{CUSTOM_RUNTIME_ALLOWED_PRIVATE_CIDRS_ENV} entry {entry!r} is not a CIDR network"
            ) from e
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


def _pinned_request(
    request: httpx.Request, host: str, address: IPAddress
) -> httpx.Request:
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
            addrinfos = socket.getaddrinfo(
                host, request.url.port, type=socket.SOCK_STREAM
            )
        except OSError as e:
            raise httpx.ConnectError(str(e), request=request) from e
        addresses = _checked_addresses(request, host, addrinfos)
        for address in addresses[:-1]:
            try:
                return super().handle_request(_pinned_request(request, host, address))
            except _UNREACHABLE:
                continue
        return super().handle_request(_pinned_request(request, host, addresses[-1]))


class AsyncPublicNetworkTransport(httpx.AsyncHTTPTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.raw_host.decode("ascii")
        # httpcore bounds its own lookup by the connect timeout; keep that bound.
        connect_timeout = request.extensions.get("timeout", {}).get("connect")
        try:
            with anyio.fail_after(connect_timeout):
                addrinfos = await anyio.getaddrinfo(
                    host, request.url.port, type=socket.SOCK_STREAM
                )
        except TimeoutError as e:
            raise httpx.ConnectTimeout(
                f"DNS lookup for {host} timed out", request=request
            ) from e
        except OSError as e:
            raise httpx.ConnectError(str(e), request=request) from e
        addresses = _checked_addresses(request, host, addrinfos)
        for address in addresses[:-1]:
            try:
                return await super().handle_async_request(
                    _pinned_request(request, host, address)
                )
            except _UNREACHABLE:
                continue
        return await super().handle_async_request(
            _pinned_request(request, host, addresses[-1])
        )
