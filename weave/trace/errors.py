"""Shared helpers for client-side error reporting."""

from typing import Any

import httpx


def response_error_message(response: httpx.Response) -> str:
    """Extract the most actionable message from an HTTP error response."""
    body: Any = response.text or "<empty response body>"
    try:
        parsed_body = response.json()
    except (UnicodeDecodeError, ValueError):
        return str(body)

    if isinstance(parsed_body, dict):
        for key in ("reason", "detail", "message"):
            if message := parsed_body.get(key):
                return str(message)
    return str(parsed_body)


def format_http_error(response: httpx.Response, context: str) -> str:
    """Add request context and status to an HTTP error response message."""
    return (
        f"{context} (status {response.status_code}): {response_error_message(response)}"
    )
