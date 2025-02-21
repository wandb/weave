from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import httpx
from weave_trace import DefaultHttpxClient

logger = logging.getLogger(__name__)


class VerboseClient(DefaultHttpxClient):
    """A debugging-focused HTTP client that logs detailed request/response information."""

    def __init__(
        self,
        log_headers: bool = False,
        log_body: bool = True,
        log_level: int = logging.DEBUG,
        max_body_length: int | None = 1000,
    ):
        """Initialize the verbose client with configurable logging options.

        Args:
            log_headers: Whether to log HTTP headers
            log_body: Whether to log request/response bodies
            log_level: Logging level to use (default: logging.DEBUG)
            max_body_length: Maximum length of body to log before truncating. None means no truncation.
        """
        super().__init__()
        self.log_headers = log_headers
        self.log_body = log_body
        self.log_level = log_level
        self.max_body_length = max_body_length

    def _format_body(self, content: bytes | None) -> str:
        """Format body content for logging, with optional truncation."""
        if not content:
            return "<empty>"

        try:
            # Try to parse and format as JSON
            body = json.loads(content)
            formatted = json.dumps(body, indent=2)
        except json.JSONDecodeError:
            # If not JSON, use raw content
            formatted = content.decode()

        if self.max_body_length is not None and len(formatted) > self.max_body_length:
            return formatted[: self.max_body_length] + "... [truncated]"
        return formatted

    def _log_headers(self, headers: httpx.Headers, prefix: str = "") -> None:
        """Log headers in a clean format."""
        if not self.log_headers:
            return

        for name, value in headers.items():
            # Skip sensitive headers
            if name.lower() in {"authorization", "cookie", "set-cookie"}:
                logger.log(self.log_level, f"{prefix}{name}: <redacted>")
            else:
                logger.log(self.log_level, f"{prefix}{name}: {value}")

    def send(self, request: httpx.Request, **kwargs: Any) -> httpx.Response:
        start_time = datetime.now()

        # Log request details
        logger.log(self.log_level, f"\n{'='*50}")
        logger.log(self.log_level, f"Request: {request.method} {request.url}")
        logger.log(self.log_level, f"Timestamp: {start_time.isoformat()}")

        if self.log_headers:
            logger.log(self.log_level, "Request Headers:")
            self._log_headers(request.headers, "  ")

        if self.log_body and request.content:
            logger.log(self.log_level, "Request Body:")
            logger.log(self.log_level, self._format_body(request.content))

        # Send the actual request
        response = super().send(request, **kwargs)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Log response details
        logger.log(
            self.log_level,
            f"\nResponse: {response.status_code} {response.reason_phrase}",
        )
        logger.log(self.log_level, f"Duration: {duration:.3f}s")

        if self.log_headers:
            logger.log(self.log_level, "Response Headers:")
            self._log_headers(response.headers, "  ")

        if self.log_body:
            logger.log(self.log_level, "Response Body:")
            logger.log(self.log_level, self._format_body(response.content))

        logger.log(self.log_level, f"{'='*50}\n")

        return response
