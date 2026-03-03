"""Helpers for printing HTTP requests and responses."""

from __future__ import annotations

import datetime
import json
import os
import threading
from time import time
from typing import Any
from urllib import request as urllib_request

import httpx
from httpx import Request, Response

from weave.trace.display.display import Console, Text

console = Console()

# See https://rich.readthedocs.io/en/stable/appendix/colors.html
STYLE_LABEL = "bold slate_blue3"
STYLE_METHOD = "bold cyan"
STYLE_URL = "bold bright_cyan"
STYLE_STATUS_SUCCESS = "bold green"
STYLE_STATUS_ERROR = "bold bright_red"
STYLE_STATUS_OTHER = "bold cyan"
STYLE_METADATA = "white"
STYLE_HEADER_KEY = "bright_yellow"
STYLE_HEADER_VALUE = "yellow"
STYLE_BODY = "dark_magenta"
STYLE_NONE = "dark_magenta italic"
STYLE_ERROR = "red"
STYLE_DIVIDER_REQUEST = "white"
STYLE_DIVIDER_RESPONSE = "bright_black"
THEME_JSON = "ansi_dark"
CLIENT_LIMITS = httpx.Limits(max_connections=None, max_keepalive_connections=None)


def decode_str(string: str | bytes) -> str:
    """Decode a bytes object to a string."""
    return string if isinstance(string, str) else string.decode("utf-8")


def pprint_header(header: tuple[bytes | str, bytes | str]) -> None:
    """Pretty print a header, redacting Authorization headers."""
    key, value = header
    key = decode_str(key)
    value = decode_str(value)
    if key == "Authorization":
        value = "<Redacted>"
    console.print(f"  {key}: ", end="", style=STYLE_HEADER_KEY)
    console.print(Text(value, style=STYLE_HEADER_VALUE))


def guess_content_type(request: Request) -> str:
    """Guess the content type of a request."""
    content_type = request.headers.get("Content-Type")
    if content_type:
        return content_type
    # TODO: This is based on knowledge of our client.
    #       We should probably be sending a Content-Type header and also doing something more correct here
    if request.content:
        return "application/json"
    return "text/plain"


def pprint_json(text: str) -> None:
    """Pretty print JSON."""
    try:
        json_body = json.loads(text)
        pretty_json = json.dumps(json_body, indent=4)
        lines = pretty_json.splitlines()
        for i, line in enumerate(lines, 1):
            line_num = Text(f"{i:>3} ", style="dim")
            console.print(line_num, line, sep="", end="\n")
    except json.JSONDecodeError:
        console.print(Text("  Invalid JSON", style=STYLE_ERROR))
        console.print(Text(text, style=STYLE_ERROR))


def pprint_request(request: Request) -> None:
    """Pretty print a Request."""
    time_text = Text(
        datetime.datetime.now().strftime("%H:%M:%S.%f"), style=STYLE_METADATA
    )
    thread_text = Text(str(threading.get_ident()), style=STYLE_METADATA)
    method_text = Text(f"{request.method}", style=STYLE_METHOD)
    url_text = Text(f"{request.url}", style=STYLE_URL)
    console.print(Text("Time: ", style=STYLE_LABEL), time_text, sep="")
    console.print(Text("Thread ID: ", style=STYLE_LABEL), thread_text, sep="")
    console.print(Text("Method: ", style=STYLE_LABEL), method_text, sep="")
    console.print(Text("URL: ", style=STYLE_LABEL), url_text, sep="")

    console.print(Text("Headers:", style=STYLE_LABEL))
    for header in request.headers.raw:
        pprint_header(header)

    console.print(Text("Body:", style=STYLE_LABEL))
    if request.content:
        content_type = guess_content_type(request)
        if content_type == "application/json":
            pprint_json(decode_str(request.content))
        elif content_type and content_type.startswith("multipart/form-data"):
            console.print(Text(decode_str(request.content), style=STYLE_BODY))
        elif isinstance(request.content, str):
            console.print(f"{request.content}", style=STYLE_BODY)
        else:
            # TODO: Can we do something safer?
            console.print(Text(decode_str(request.content), style=STYLE_BODY))
    else:
        console.print(Text("  None", style=STYLE_NONE))


def pprint_response(response: Response) -> None:
    """Pretty print a Response."""
    status_style = STYLE_STATUS_OTHER
    if 200 <= response.status_code < 300:
        status_style = STYLE_STATUS_SUCCESS
    elif response.status_code >= 400:
        status_style = STYLE_STATUS_ERROR
    status_code_text = Text(f"{response.status_code}", style=status_style)
    reason_text = Text(f"{response.reason_phrase}", style=status_style)
    console.print(Text("Status Code: ", style=STYLE_LABEL), status_code_text, sep="")
    console.print(Text("Reason: ", style=STYLE_LABEL), reason_text, sep="")
    console.print(Text("Headers:", style=STYLE_LABEL))
    for key, value in response.headers.items():
        pprint_header((key, value))

    console.print(Text("Body:", style=STYLE_LABEL))
    if response.headers.get("Content-Type") == "application/json":
        pprint_json(response.text)
    elif response.text:
        console.print(Text(response.text, style=STYLE_BODY))
    else:
        console.print("  None", style=STYLE_NONE)


def _get_proxy_for_url(url: httpx.URL) -> str | None:
    """Resolve proxy URL from environment for this request URL."""
    host = url.host
    if host and urllib_request.proxy_bypass_environment(host):
        return None

    proxies = urllib_request.getproxies()
    return proxies.get(url.scheme) or proxies.get("all")


class LoggingHTTPTransport(httpx.BaseTransport):
    def __init__(self, *, limits: httpx.Limits) -> None:
        self._limits = limits
        self._lock = threading.Lock()
        self._transports: dict[str | None, httpx.HTTPTransport] = {}

    def _get_transport_for_request(self, request: httpx.Request) -> httpx.HTTPTransport:
        proxy = _get_proxy_for_url(request.url)
        with self._lock:
            transport = self._transports.get(proxy)
            if transport is None:
                transport = httpx.HTTPTransport(proxy=proxy, limits=self._limits)
                self._transports[proxy] = transport
            return transport

    def handle_request(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        transport = self._get_transport_for_request(request)
        if os.environ.get("WEAVE_DEBUG_HTTP") != "1":
            return transport.handle_request(request)

        console.print(Text("-" * 21, style=STYLE_DIVIDER_REQUEST))
        pprint_request(request)
        start_time = time()
        response = transport.handle_request(request)
        elapsed_time = time() - start_time
        console.print(Text("----- Response below -----", style=STYLE_DIVIDER_RESPONSE))
        console.print(
            Text("Elapsed Time: ", style=STYLE_LABEL),
            Text(f"{elapsed_time:.2f} seconds", style=STYLE_METADATA),
            sep="",
        )
        pprint_response(response)
        return response

    def close(self) -> None:
        with self._lock:
            transports = list(self._transports.values())
            self._transports = {}

        for transport in transports:
            transport.close()


def _get_http_timeout() -> float:
    """Get the HTTP timeout from settings."""
    # Import here to avoid circular imports
    from weave.trace.settings import http_timeout

    return http_timeout()


client = httpx.Client(
    # HTTPX doesn't read proxy env vars when a custom transport is provided,
    # so proxy routing is handled in LoggingHTTPTransport per request URL.
    transport=LoggingHTTPTransport(limits=CLIENT_LIMITS),
    timeout=_get_http_timeout(),
)


def get(
    url: str,
    params: dict[str, str] | None = None,
    *,
    stream: bool = False,
    **kwargs: Any,
) -> Response:
    """Send a GET request with optional logging."""
    if stream:
        # Extract auth since build_request doesn't accept it
        auth = kwargs.pop("auth", None)
        request = client.build_request("GET", url, params=params, **kwargs)
        return client.send(request, auth=auth, stream=True)
    return client.get(url, params=params, **kwargs)


def post(
    url: str,
    data: dict[str, Any] | str | bytes | None = None,
    json: dict[str, Any] | None = None,
    *,
    stream: bool = False,
    **kwargs: Any,
) -> Response:
    """Send a POST request with optional logging."""
    if stream:
        # Extract auth since build_request doesn't accept it
        auth = kwargs.pop("auth", None)
        request = client.build_request("POST", url, data=data, json=json, **kwargs)
        return client.send(request, auth=auth, stream=True)
    return client.post(url, data=data, json=json, **kwargs)


def delete(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    stream: bool = False,
    **kwargs: Any,
) -> Response:
    """Send a DELETE request with optional logging."""
    if stream:
        # Extract auth since build_request doesn't accept it
        auth = kwargs.pop("auth", None)
        request = client.build_request("DELETE", url, params=params, **kwargs)
        return client.send(request, auth=auth, stream=True)
    return client.delete(url, params=params, **kwargs)
