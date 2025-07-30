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
    logger.info(
        "retry_attempt",
        extra={
            "fn": retry_state.fn,
            "retry_id": get_current_retry_id(),
            "attempt_number": retry_state.attempt_number,
            "exception": str(retry_state.outcome.exception()),
        },
    )


def _log_failure(retry_state: tenacity.RetryCallState) -> Any:
    logger.info(
        "retry_failed",
        extra={
            "fn": retry_state.fn,
            "retry_id": get_current_retry_id(),
            "attempt_number": retry_state.attempt_number,
            "exception": str(retry_state.outcome.exception()),
        },
    )
    return retry_state.outcome.result()
