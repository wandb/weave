"""Custom runtime requests reach only publicly routable addresses.

A custom runtime's base URL is user-configured, so every connection made for it
must land on a public address.
"""

from __future__ import annotations

import socket
from collections.abc import Callable

import httpx
import pytest

from weave.trace_server.environment import CUSTOM_RUNTIME_ALLOWED_PRIVATE_CIDRS_ENV
from weave.trace_server.public_network_transport import (
    AsyncPublicNetworkTransport,
    NonPublicAddressError,
    PublicNetworkTransport,
)


def _fake_getaddrinfo(*addresses: str) -> Callable[..., list]:
    def getaddrinfo(host, port, *args, **kwargs):
        return [
            (
                socket.AF_INET6 if ":" in address else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (address, port or 0),
            )
            for address in addresses
        ]

    return getaddrinfo


@pytest.fixture
def forwarded(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    """Requests the guard hands to the real transport, which never connects."""
    requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle_request)
    monkeypatch.setattr(
        httpx.AsyncHTTPTransport, "handle_async_request", handle_async_request
    )
    return requests


async def _send(url: str, *, use_async: bool) -> httpx.Response:
    if use_async:
        async with httpx.AsyncClient(transport=AsyncPublicNetworkTransport()) as c:
            return await c.get(url)
    with httpx.Client(transport=PublicNetworkTransport()) as c:
        return c.get(url)


@pytest.mark.asyncio
@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize(
    ("url", "resolved"),
    [
        ("https://internal.example.com/v1", ("10.32.0.1",)),
        ("https://mixed.example.com/v1", ("93.184.215.14", "127.0.0.1")),
        ("https://metadata.example.com/", ("169.254.169.254",)),
        ("https://mapped.example.com/", ("::ffff:169.254.169.254",)),
        ("https://cgnat.example.com/", ("100.100.100.200",)),
        ("http://127.0.0.1:8080/server_info", None),
    ],
    ids=[
        "dns-private",
        "dns-any-private-answer",
        "metadata",
        "ipv4-mapped",
        "cgnat",
        "literal",
    ],
)
async def test_rejects_non_public_destinations(
    monkeypatch, forwarded, url, resolved, use_async
):
    if resolved is not None:
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(*resolved))

    with pytest.raises(NonPublicAddressError, match="not publicly routable"):
        await _send(url, use_async=use_async)

    assert forwarded == []


@pytest.mark.asyncio
@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
async def test_connects_to_the_checked_address_and_keeps_the_hostname(
    monkeypatch, forwarded, use_async
):
    # Pinning the checked IP closes the gap where a second DNS lookup answers differently.
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("93.184.215.14"))

    await _send("https://runtime.example.com:8443/v1/models", use_async=use_async)

    (request,) = forwarded
    assert request.url == "https://93.184.215.14:8443/v1/models"
    assert request.headers["Host"] == "runtime.example.com:8443"
    assert request.extensions["sni_hostname"] == "runtime.example.com"


def test_operator_exempt_networks(monkeypatch, forwarded):
    # Operators may exempt their own networks, but never cloud metadata inside them.
    monkeypatch.setenv(
        CUSTOM_RUNTIME_ALLOWED_PRIVATE_CIDRS_ENV,
        "10.20.0.0/16, 169.254.0.0/16, ::ffff:0:0/96, fd00::/8, 100.64.0.0/10",
    )

    def get(url: str, answer: str) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(answer))
        with httpx.Client(transport=PublicNetworkTransport()) as c:
            c.get(url)

    get("http://vllm.corp.internal:8000/v1", "10.20.0.15")
    assert [str(r.url) for r in forwarded] == ["http://10.20.0.15:8000/v1"]

    never_reachable = (
        "169.254.169.254",
        "::ffff:169.254.169.254",
        "fd00:ec2::254",
        "fd00:ec2::23",
        "100.100.100.200",
        "::ffff:100.100.100.200",
    )
    for answer in ("10.21.0.15", *never_reachable, "168.63.129.16"):
        with pytest.raises(NonPublicAddressError):
            get("http://runtime.corp.internal/", answer)
    assert len(forwarded) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
async def test_resolves_the_ascii_host_and_skips_unreachable_addresses(
    monkeypatch, use_async
):
    # The IDNA form is what the Host header carries, so it is the name to resolve.
    # A first address that times out moves on to the next, as plain sockets do.
    lookups: list[str] = []

    def getaddrinfo(host, port, *args, **kwargs):
        # anyio passes the already-encoded name as bytes.
        lookups.append(host.decode() if isinstance(host, bytes) else host)
        return _fake_getaddrinfo("2606:4700::1111", "93.184.215.14")(host, port)

    sent: list[httpx.Request] = []

    def connect(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.url.host == "2606:4700::1111":
            raise httpx.ConnectTimeout("unreachable", request=request)
        return httpx.Response(200, request=request)

    async def connect_async(self, request: httpx.Request) -> httpx.Response:
        return connect(request)

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", lambda _, r: connect(r))
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", connect_async)

    await _send("https://bücher.example/v1", use_async=use_async)

    assert lookups == ["xn--bcher-kva.example"]
    assert [r.url.host for r in sent] == ["2606:4700::1111", "93.184.215.14"]
    assert sent[-1].extensions["sni_hostname"] == "xn--bcher-kva.example"


def test_invalid_exempt_network_fails_closed(monkeypatch, forwarded):
    monkeypatch.setenv(CUSTOM_RUNTIME_ALLOWED_PRIVATE_CIDRS_ENV, "10.0.0.1/8")
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("10.0.0.1"))

    with httpx.Client(transport=PublicNetworkTransport()) as c:
        with pytest.raises(ValueError, match=CUSTOM_RUNTIME_ALLOWED_PRIVATE_CIDRS_ENV):
            c.get("http://runtime.example.com/")

    assert forwarded == []
