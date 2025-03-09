from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import datetime
from typing import Any

import httpx
from weave_server_sdk import DefaultHttpxClient

logger = logging.getLogger(__name__)


class StreamingResponseWrapper:
    """Wraps a streaming response to log content as it's yielded."""

    def __init__(
        self,
        response: httpx.Response,
        log_level: int,
        max_body_length: int | None = None,
    ):
        self._response = response
        self._log_level = log_level
        self._max_body_length = max_body_length
        self._chunk_count = 0

    def _format_chunk(self, chunk: bytes) -> str:
        try:
            # Try to parse and format as JSON
            body = json.loads(chunk)
            formatted = json.dumps(body, indent=2)
        except json.JSONDecodeError:
            # If not JSON, use raw content
            formatted = chunk.decode()

        if self._max_body_length is not None and len(formatted) > self._max_body_length:
            return formatted[: self._max_body_length] + "... [truncated]"
        return formatted

    def iter_bytes(self, *, chunk_size: int | None = None) -> Iterator[bytes]:
        for chunk in self._response.iter_bytes(chunk_size=chunk_size):
            self._chunk_count += 1
            logger.log(
                self._log_level,
                f"Streaming chunk #{self._chunk_count}:\n{self._format_chunk(chunk)}\n",
            )
            yield chunk

    def iter_lines(
        self, *, decode_unicode: bool = True, chunk_size: int | None = None
    ) -> Iterator[bytes]:
        for line in self._response.iter_lines(
            decode_unicode=decode_unicode, chunk_size=chunk_size
        ):
            self._chunk_count += 1
            logger.log(
                self._log_level,
                f"Streaming line #{self._chunk_count}:\n{self._format_chunk(line)}\n",
            )
            yield line

    def iter_text(
        self, *, chunk_size: int | None = None, encoding: str | None = None
    ) -> Iterator[str]:
        for text in self._response.iter_text(chunk_size=chunk_size, encoding=encoding):
            self._chunk_count += 1
            logger.log(
                self._log_level,
                f"Streaming text #{self._chunk_count}:\n{text}\n",
            )
            yield text

    def __getattr__(self, name: str) -> Any:
        return getattr(self._response, name)


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
        logger.log(self.log_level, f"\n{'=' * 50}")
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

        if self.log_body and not kwargs.get("stream", False):
            logger.log(self.log_level, "Response Body:")
            logger.log(self.log_level, self._format_body(response.content))
        elif self.log_body:
            logger.log(self.log_level, "Response Body: <streaming>")
            # Wrap the response to log streaming content
            response = StreamingResponseWrapper(
                response, self.log_level, self.max_body_length
            )

        logger.log(self.log_level, f"{'=' * 50}\n")

        return response
