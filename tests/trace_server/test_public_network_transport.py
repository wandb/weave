"""Custom runtime requests reach only publicly routable addresses.

A custom runtime's base URL is user-configured, so every connection made for it
must land on a public address, and redirects must not be followed.
"""

from __future__ import annotations

import http.server
import json
import socket
import threading
import uuid
from collections.abc import Callable, Iterator

import httpx
import pytest

from tests.trace_server.conftest import TEST_ENTITY
from weave.trace_server import llm_completion as llm_mod
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.environment import CUSTOM_RUNTIME_ALLOWED_PRIVATE_CIDRS_ENV
from weave.trace_server.public_network_transport import (
    AsyncPublicNetworkTransport,
    NonPublicAddressError,
    PublicNetworkTransport,
)
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context


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
    # Dedicated and self-managed deployments may host runtimes on their own network.
    # Exemptions never reach cloud metadata: link-local directly or IPv4-mapped,
    # AWS IPv6 metadata inside an exempted ULA range, Alibaba metadata inside an
    # exempted CGNAT range, or Azure's public fabric IP.
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


# ---------------------------------------------------------------------------
# Completion paths, against real local servers. Loopback is exempted so the
# guarded clients can reach the local runtime server at all.
# ---------------------------------------------------------------------------


def _serve(handler: type[http.server.BaseHTTPRequestHandler]) -> http.server.HTTPServer:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _url(server: http.server.HTTPServer, path: str) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}{path}"


@pytest.fixture
def redirecting_runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, list]]:
    """A runtime that answers every request with a 302 to an internal server."""
    monkeypatch.setenv(CUSTOM_RUNTIME_ALLOWED_PRIVATE_CIDRS_ENV, "127.0.0.0/8")
    internal_hits: list[str] = []

    class Internal(http.server.BaseHTTPRequestHandler):
        def _handle(self) -> None:
            internal_hits.append(f"{self.command} {self.path}")
            body = json.dumps({"gitVersion": "v1.35.8"}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = _handle

        def log_message(self, *args) -> None:
            pass

    internal = _serve(Internal)

    class Redirect(http.server.BaseHTTPRequestHandler):
        def _handle(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(302)
            self.send_header("Location", _url(internal, "/version"))
            self.send_header("Content-Length", "0")
            self.end_headers()

        do_GET = do_POST = _handle

        def log_message(self, *args) -> None:
            pass

    runtime = _serve(Redirect)
    try:
        yield _url(runtime, "/v1"), internal_hits
    finally:
        for server in (internal, runtime):
            server.shutdown()
            server.server_close()


@pytest.fixture
def working_runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, list]]:
    """A runtime that answers OpenAI chat completions and Ollama generate."""
    monkeypatch.setenv(CUSTOM_RUNTIME_ALLOWED_PRIVATE_CIDRS_ENV, "127.0.0.0/8")
    tenant_headers: list[str] = []

    class Runtime(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            tenant_headers.append(self.headers.get("X-Tenant", ""))
            if self.path.endswith("/api/generate"):
                lines = [{"response": "ok", "done": False}, {"done": True}]
                payload = (
                    "".join(json.dumps(line) + "\n" for line in lines)
                    if body.get("stream")
                    else json.dumps({"response": "ok", "done": True})
                )
            elif body.get("stream"):
                delta = {
                    "index": 0,
                    "delta": {"content": "ok"},
                    "finish_reason": "stop",
                }
                chunk = {"id": "c", "object": "chat.completion.chunk", "created": 0}
                chunk |= {"model": "test-model", "choices": [delta]}
                payload = f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n"
            else:
                message = {"role": "assistant", "content": "ok"}
                choice = {"index": 0, "message": message, "finish_reason": "stop"}
                payload = json.dumps(
                    {"id": "c", "object": "chat.completion", "created": 0}
                    | {"model": "test-model", "choices": [choice]}
                )
            encoded = payload.encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *args) -> None:
            pass

    server = _serve(Runtime)
    try:
        yield _url(server, "/v1"), tenant_headers
    finally:
        server.shutdown()
        server.server_close()


async def _complete(mode: str, model: str, api_key: str | None, base_url: str) -> str:
    kwargs = {
        "api_key": api_key,
        "inputs": tsi.CompletionsCreateRequestInputs(
            model=model, messages=[{"role": "user", "content": "hi"}]
        ),
        "provider": "custom",
        "base_url": base_url,
        "extra_headers": {"X-Tenant": "customer"},
        "public_network_only": True,
    }
    if mode == "sync":
        return json.dumps(llm_mod.lite_llm_completion(**kwargs).response)
    if mode == "async":
        return json.dumps((await llm_mod.lite_llm_acompletion(**kwargs)).response)
    return json.dumps(list(llm_mod.lite_llm_completion_stream(**kwargs)))


MODES = pytest.mark.parametrize("mode", ["sync", "async", "stream"])
CLIENTS = [
    pytest.param("openai/test-model", None, id="keyless"),
    pytest.param("openai/test-model", "runtime-secret", id="keyed"),
    pytest.param("ollama/llama3", None, id="ollama"),
]


@pytest.mark.asyncio
@MODES
@pytest.mark.parametrize(
    ("model", "api_key"),
    [
        *CLIENTS,
        # LiteLLM sends these names to its Responses API bridge, which builds its
        # own HTTP client, so custom runtimes must never reach LiteLLM with them.
        pytest.param("openai/responses/test-model", "runtime-secret", id="responses"),
        pytest.param("openai/o1-pro", "runtime-secret", id="o1-pro"),
    ],
)
async def test_custom_runtime_completions_do_not_follow_redirects(
    redirecting_runtime, mode, model, api_key
):
    runtime_url, internal_hits = redirecting_runtime

    result = await _complete(mode, model, api_key, runtime_url)

    assert internal_hits == []
    assert '"error"' in result, result
    assert "gitVersion" not in result


@pytest.mark.asyncio
@MODES
@pytest.mark.parametrize(("model", "api_key"), CLIENTS)
async def test_custom_runtime_completions_still_reach_allowed_runtimes(
    working_runtime, mode, model, api_key
):
    runtime_url, tenant_headers = working_runtime

    result = await _complete(mode, model, api_key, runtime_url)

    assert '"error"' not in result, result
    assert '"ok"' in result, result
    assert tenant_headers == ["customer"]


class _NoSecrets:
    def fetch(self, secret_name: str) -> dict:
        return {"secrets": {}}


@pytest.mark.parametrize("stream", [False, True], ids=["create", "stream"])
def test_registered_runtime_cannot_resolve_to_internal_address(
    trace_server, monkeypatch, stream
):
    # `runtime.test` passes the save-time URL check because it is a hostname,
    # then resolves to loopback when the completion connects.
    real_getaddrinfo = socket.getaddrinfo

    def getaddrinfo(host, *args, **kwargs):
        host = "127.0.0.1" if host == "runtime.test" else host
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    project_id = f"{TEST_ENTITY}/custom-runtime-network"
    runtime_name = f"runtime-{uuid.uuid4().hex[:8]}"
    trace_server.custom_runtime_apply(
        tsi.CustomRuntimeApplyReq(
            project_id=project_id,
            runtime_name=runtime_name,
            base_url="http://runtime.test:9/v1",
            api_key_secret=None,
            headers={},
            runtime_ids=[tsi.CustomRuntimeID(id="model", max_tokens=16)],
        )
    )
    req = tsi.CompletionsCreateReq(
        project_id=project_id,
        inputs=tsi.CompletionsCreateRequestInputs(
            model=f"custom::{runtime_name}::model",
            messages=[{"role": "user", "content": "hi"}],
        ),
        track_llm_call=False,
    )

    token = _secret_fetcher_context.set(_NoSecrets())
    try:
        if stream:
            result = json.dumps(list(trace_server.completions_create_stream(req)))
        else:
            result = json.dumps(trace_server.completions_create(req).response)
    finally:
        _secret_fetcher_context.reset(token)

    assert "Refusing to connect to runtime.test" in result, result
