"""Helpers for printing HTTP requests and responses."""

from __future__ import annotations

import datetime
import json
import os
import threading
from time import time
from typing import Any

import httpx
from httpx import Request, Response

from weave.trace.display.display import Console, Text
from weave.trace.env import ssl_verify
from weave.trace.settings import http_timeout

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
    try:
        body_text = response.text
    except httpx.ResponseNotRead:
        console.print("  [stream not read]", style=STYLE_NONE)
        return

    if response.headers.get("Content-Type") == "application/json":
        pprint_json(body_text)
    elif body_text:
        console.print(Text(body_text, style=STYLE_BODY))
    else:
        console.print("  None", style=STYLE_NONE)


def _is_debug_http_enabled() -> bool:
    return os.environ.get("WEAVE_DEBUG_HTTP") == "1"


def _log_request(request: Request) -> None:
    if not _is_debug_http_enabled():
        return

    request.extensions["weave_start_time"] = time()
    console.print(Text("-" * 21, style=STYLE_DIVIDER_REQUEST))
    pprint_request(request)


def _log_response(response: Response) -> None:
    if not _is_debug_http_enabled():
        return

    console.print(Text("----- Response below -----", style=STYLE_DIVIDER_RESPONSE))
    start_time = response.request.extensions.get("weave_start_time")
    if isinstance(start_time, (int, float)):
        elapsed_time = time() - start_time
        console.print(
            Text("Elapsed Time: ", style=STYLE_LABEL),
            Text(f"{elapsed_time:.2f} seconds", style=STYLE_METADATA),
            sep="",
        )
    pprint_response(response)


# Shared httpx.Client lifecycle.
#
# The client is built lazily on first use so env-driven config such as
# ``WEAVE_INSECURE_DISABLE_SSL`` and ``WF_HTTP_TIMEOUT`` is read at first-use
# time, not at import time. The trade-off this design makes:
#
#   Config (verify=, timeout=, event_hooks) is captured when the client is
#   built, and frozen for the life of the process.
#
# This matches how httpx itself wants to be used — ``verify`` is a property of
# the connection pool and cannot be changed per-request (see encode/httpx#554).
# It also matches the openai/anthropic SDKs, which build their httpx.Client
# eagerly per SDK instance and do not reconfigure it. Callers who need to
# change SSL/timeout config must set the env var *before* the first HTTP
# call (typically before ``weave.init``).
_client: httpx.Client | None = None
_client_lock = threading.Lock()


def get_client() -> httpx.Client:
    """Return the shared httpx.Client, building it on first use.

    See module-level comment for the freeze-after-first-use contract.
    """
    global _client  # noqa: PLW0603
    with _client_lock:
        if _client is None:
            # Use HTTPX's default transport so env proxy handling
            # (including NO_PROXY) works natively.
            _client = httpx.Client(
                event_hooks={
                    "request": [_log_request],
                    "response": [_log_response],
                },
                timeout=http_timeout(),
                limits=CLIENT_LIMITS,
                verify=ssl_verify(),
            )
        return _client


def _reset_client_for_tests() -> None:
    """Close the cached client and clear it. Test seam only.

    Production code must not call this — the freeze-after-first-use contract
    is intentional. Tests use it to simulate a fresh process when asserting
    behavior tied to env vars read at client-construction time.
    """
    global _client  # noqa: PLW0603
    with _client_lock:
        if _client is not None:
            _client.close()
        _client = None


def get(
    url: str,
    params: dict[str, str] | None = None,
    *,
    stream: bool = False,
    **kwargs: Any,
) -> Response:
    """Send a GET request with optional logging."""
    client = get_client()
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
    client = get_client()
    if stream:
        # Extract auth since build_request doesn't accept it
        auth = kwargs.pop("auth", None)
        request = client.build_request("POST", url, data=data, json=json, **kwargs)
        return client.send(request, auth=auth, stream=True)
    return client.post(url, data=data, json=json, **kwargs)


def put(
    url: str,
    data: dict[str, Any] | str | bytes | None = None,
    json: dict[str, Any] | None = None,
    *,
    stream: bool = False,
    **kwargs: Any,
) -> Response:
    """Send a PUT request with optional logging."""
    client = get_client()
    if stream:
        # Extract auth since build_request doesn't accept it
        auth = kwargs.pop("auth", None)
        request = client.build_request("PUT", url, data=data, json=json, **kwargs)
        return client.send(request, auth=auth, stream=True)
    return client.put(url, data=data, json=json, **kwargs)


def delete(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    stream: bool = False,
    **kwargs: Any,
) -> Response:
    """Send a DELETE request with optional logging."""
    client = get_client()
    if stream:
        # Extract auth since build_request doesn't accept it
        auth = kwargs.pop("auth", None)
        request = client.build_request("DELETE", url, params=params, **kwargs)
        return client.send(request, auth=auth, stream=True)
    return client.delete(url, params=params, **kwargs)
