"""Helpers for printing HTTP requests and responses."""

import datetime
import json
import os
import threading
from typing import Any, Optional, Union

import httpx
from httpx import HTTPStatusError, Request, Response

from weave.trace.display.display import Console, Text


class HTTPError(HTTPStatusError):
    """Compatibility wrapper for requests.HTTPError API."""

    def __init__(
        self, message: str, response: Optional[Response] = None, **kwargs: Any
    ):
        """Initialize HTTPError with backwards compatibility for requests API.

        Args:
            message: Error message
            response: HTTP response object (optional for compatibility)
            **kwargs: Additional keyword arguments
        """
        if response is not None:
            # If response has a request attribute, use it
            if hasattr(response, "request") and response.request is not None:
                super().__init__(message, request=response.request, response=response)
            else:
                # Create a dummy request for compatibility
                dummy_request = Request("GET", "http://unknown")
                super().__init__(message, request=dummy_request, response=response)
            self.response = response
        else:
            # For cases where no response is provided
            dummy_request = Request("GET", "http://unknown")
            dummy_response = Response(500)
            super().__init__(message, request=dummy_request, response=dummy_response)
            self.response = None


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


def decode_str(string: Union[str, bytes]) -> str:
    """Decode a bytes object to a string."""
    return string if isinstance(string, str) else string.decode("utf-8")


def pprint_header(header: tuple[str, str]) -> None:
    """Pretty print a header, redacting Authorization headers."""
    key, value = header
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
    for header in request.headers.items():
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
    for header in response.headers.items():
        pprint_header(header)

    console.print(Text("Body:", style=STYLE_LABEL))
    if response.headers.get("Content-Type") == "application/json":
        pprint_json(response.text)
    elif response.text:
        console.print(Text(response.text, style=STYLE_BODY))
    else:
        console.print("  None", style=STYLE_NONE)


def log_request(request: Request) -> None:
    """Log HTTP request if debugging is enabled."""
    if os.environ.get("WEAVE_DEBUG_HTTP") != "1":
        return
    console.print(Text("-" * 21, style=STYLE_DIVIDER_REQUEST))
    pprint_request(request)


def log_response(response: Response) -> None:
    """Log HTTP response if debugging is enabled."""
    if os.environ.get("WEAVE_DEBUG_HTTP") != "1":
        return
    elapsed_time = response.elapsed.total_seconds() if response.elapsed else 0.0
    console.print(Text("----- Response below -----", style=STYLE_DIVIDER_RESPONSE))
    console.print(
        Text("Elapsed Time: ", style=STYLE_LABEL),
        Text(f"{elapsed_time:.2f} seconds", style=STYLE_METADATA),
        sep="",
    )
    pprint_response(response)


# Create a client with event hooks for logging
client = httpx.Client(
    event_hooks={
        "request": [log_request],
        "response": [log_response],
    }
)


def get(url: str, params: Optional[dict[str, str]] = None, **kwargs: Any) -> Response:
    """Send a GET request with optional logging."""
    return client.get(url, params=params, **kwargs)


def post(
    url: str,
    data: Optional[Union[dict[str, Any], str]] = None,
    json: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> Response:
    """Send a POST request with optional logging."""
    # httpx.Client.post() doesn't support stream parameter, so we need to use
    # the standalone httpx.post() function when streaming is requested.
    stream = kwargs.pop("stream", False)
    if stream:
        # Use standalone httpx.post() for streaming requests
        # Note: This bypasses the client's event hooks, but streaming requests
        # need the standalone function.
        return httpx.post(url, data=data, json=json, **kwargs)
    return client.post(url, data=data, json=json, **kwargs)
