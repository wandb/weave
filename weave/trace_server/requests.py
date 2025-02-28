"""Helpers for printing HTTP requests and responses."""

import datetime
import json
import os
import threading
from time import time
from typing import Any, Optional, Union

from requests import HTTPError as HTTPError
from requests import PreparedRequest, Response, Session
from requests.adapters import HTTPAdapter
from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text

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


def guess_content_type(request: PreparedRequest) -> str:
    """Guess the content type of a request."""
    content_type = request.headers.get("Content-Type")
    if content_type:
        return content_type
    # TODO: This is based on knowledge of our client.
    #       We should probably be sending a Content-Type header and also doing something more correct here
    if request.body:
        return "application/json"
    return "text/plain"


def pprint_json(text: str) -> None:
    """Pretty print JSON."""
    try:
        json_body = json.loads(text)
        pretty_json = json.dumps(json_body, indent=4)
        body_syntax = Syntax(pretty_json, "json", theme=THEME_JSON, line_numbers=True)
        console.print(body_syntax)
    except json.JSONDecodeError:
        console.print(Text("  Invalid JSON", style=STYLE_ERROR))
        console.print(Text(text, style=STYLE_ERROR))


def pprint_prepared_request(prepared_request: PreparedRequest) -> None:
    """Pretty print a PreparedRequest."""
    time_text = Text(
        datetime.datetime.now().strftime("%H:%M:%S.%f"), style=STYLE_METADATA
    )
    thread_text = Text(str(threading.get_ident()), style=STYLE_METADATA)
    method_text = Text(f"{prepared_request.method}", style=STYLE_METHOD)
    url_text = Text(f"{prepared_request.url}", style=STYLE_URL)
    console.print(Text("Time: ", style=STYLE_LABEL) + time_text)
    console.print(Text("Thread ID: ", style=STYLE_LABEL) + thread_text)
    console.print(Text("Method: ", style=STYLE_LABEL) + method_text)
    console.print(Text("URL: ", style=STYLE_LABEL) + url_text)

    console.print(Text("Headers:", style=STYLE_LABEL))
    for header in prepared_request.headers.items():
        pprint_header(header)

    console.print(Text("Body:", style=STYLE_LABEL))
    if prepared_request.body:
        content_type = guess_content_type(prepared_request)
        if content_type == "application/json":
            pprint_json(decode_str(prepared_request.body))
        elif content_type and content_type.startswith("multipart/form-data"):
            console.print(Text(decode_str(prepared_request.body), style=STYLE_BODY))
        elif isinstance(prepared_request.body, str):
            console.print(f"{prepared_request.body}", style=STYLE_BODY)
        else:
            # TODO: Can we do something safer?
            console.print(Text(decode_str(prepared_request.body), style=STYLE_BODY))
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
    reason_text = Text(f"{response.reason}", style=status_style)
    console.print(Text("Status Code: ", style=STYLE_LABEL) + status_code_text)
    console.print(Text("Reason: ", style=STYLE_LABEL) + reason_text)
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


class LoggingHTTPAdapter(HTTPAdapter):
    # Actual signature is:
    # self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None
    def send(self, request: PreparedRequest, **kwargs: Any) -> Response:  # type: ignore
        if os.environ.get("WEAVE_DEBUG_HTTP") != "1":
            return super().send(request, **kwargs)

        console.print(Text("-" * 21, style=STYLE_DIVIDER_REQUEST))
        pprint_prepared_request(request)
        start_time = time()
        response = super().send(request, **kwargs)
        elapsed_time = time() - start_time
        console.print(Text("----- Response below -----", style=STYLE_DIVIDER_RESPONSE))
        console.print(
            Text("Elapsed Time: ", style=STYLE_LABEL)
            + Text(f"{elapsed_time:.2f} seconds", style=STYLE_METADATA)
        )
        pprint_response(response)
        return response


session = Session()
adapter = LoggingHTTPAdapter()
session.mount("http://", adapter)
session.mount("https://", adapter)


def get(url: str, params: Optional[dict[str, str]] = None, **kwargs: Any) -> Response:
    """Send a GET request with optional logging."""
    return session.get(url, params=params, **kwargs)


def post(
    url: str,
    data: Optional[Union[dict[str, Any], str]] = None,
    json: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> Response:
    """Send a POST request with optional logging."""
    return session.post(url, data=data, json=json, **kwargs)
