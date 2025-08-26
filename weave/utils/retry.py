from __future__ import annotations

import contextvars
import logging
from functools import wraps
from typing import Any, Callable, TypeVar

import requests
import tenacity
from pydantic import ValidationError

from weave.trace.settings import retry_max_attempts, retry_max_interval
from weave.trace_server.ids import generate_id

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Context variable to store retry ID for correlation
_retry_id: contextvars.ContextVar[str] = contextvars.ContextVar("retry_id")

# Track whether we've warned about server being down
_server_down_warning_shown = False


def with_retry(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator that applies configurable retry logic to a function.
    Retry configuration is determined by:
    1. Values from weave.trace.settings (if available)
    2. Values set via configure_retry()

    Automatically generates a retry ID for request correlation across all attempts.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        # Generate a retry ID for this request (shared across all attempts)
        retry_id = generate_id()
        retry_id_token = _retry_id.set(retry_id)

        retry = tenacity.Retrying(
            stop=tenacity.stop_after_attempt(retry_max_attempts()),
            wait=tenacity.wait_exponential_jitter(initial=1, max=retry_max_interval()),
            retry=tenacity.retry_if_exception(_is_retryable_exception),
            before_sleep=_log_retry,
            retry_error_callback=_log_failure,
            reraise=True,
        )

        try:
            return retry(func, *args, **kwargs)
        finally:
            # Always clean up the retry ID
            _retry_id.reset(retry_id_token)

    return wrapper


def get_current_retry_id() -> str | None:
    """Get the current retry ID from context, if available."""
    try:
        return _retry_id.get()
    except LookupError:
        return None


def _is_retryable_exception(e: BaseException) -> bool:
    # Don't retry pydantic validation errors
    if isinstance(e, ValidationError):
        return False

    # Don't retry on HTTP 4xx (except 429)
    if isinstance(e, requests.HTTPError) and e.response is not None:
        code_class = e.response.status_code // 100

        # Bad request, not rate-limiting
        if code_class == 4 and e.response.status_code != 429:
            return False

    # Otherwise, retry: 5xx, OSError, ConnectionError, ConnectionResetError, IOError, etc...
    return True


def _log_retry(retry_state: tenacity.RetryCallState) -> None:
    global _server_down_warning_shown
    exception = retry_state.outcome.exception()
    
    # For server errors, log a more user-friendly message
    if isinstance(exception, requests.HTTPError) and exception.response is not None:
        status_code = exception.response.status_code
        if status_code == 502:
            # Show a user-friendly warning only once per session
            if not _server_down_warning_shown:
                logger.warning(
                    "Weave server appears to be unavailable. Will retry connection..."
                )
                _server_down_warning_shown = True
            logger.debug(
                f"Server unavailable (attempt {retry_state.attempt_number}). Retrying..."
            )
        elif status_code >= 500:
            logger.debug(
                f"Server error {status_code} (attempt {retry_state.attempt_number}). Retrying..."
            )
        else:
            logger.debug(
                f"HTTP {status_code} error (attempt {retry_state.attempt_number}). Retrying..."
            )
    else:
        # For non-HTTP errors, preserve original INFO level logging for compatibility
        logger.info(
            "retry_attempt",
            extra={
                "fn": retry_state.fn,
                "retry_id": get_current_retry_id(),
                "attempt_number": retry_state.attempt_number,
                "exception": str(exception),
            },
        )


def _log_failure(retry_state: tenacity.RetryCallState) -> Any:
    exception = retry_state.outcome.exception()
    
    # For server errors after all retries, log a clear user-friendly message
    if isinstance(exception, requests.HTTPError) and exception.response is not None:
        status_code = exception.response.status_code
        if status_code == 502:
            logger.error(
                f"Unable to connect to Weave server after {retry_state.attempt_number} attempts. "
                "The server may be down or experiencing issues. Please try again later."
            )
        elif status_code >= 500:
            logger.error(
                f"Server error (HTTP {status_code}) persists after {retry_state.attempt_number} attempts. "
                "Please check server status or try again later."
            )
        else:
            logger.warning(
                f"HTTP {status_code} error after {retry_state.attempt_number} attempts."
            )
    else:
        # For non-HTTP errors, log with more details
        logger.info(
            "retry_failed",
            extra={
                "fn": retry_state.fn,
                "retry_id": get_current_retry_id(),
                "attempt_number": retry_state.attempt_number,
                "exception": str(exception),
            },
        )
    return retry_state.outcome.result()
