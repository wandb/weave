from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable, TypedDict, TypeVar

import requests
import tenacity
from pydantic import ValidationError

logger = logging.getLogger(__name__)

RETRY_MAX_INTERVAL = 60 * 5  # 5 min
RETRY_MAX_ATTEMPTS = 3


T = TypeVar("T")


class RetryConfig(TypedDict):
    max_attempts: int
    max_time_between_retries: float


_retry_config = RetryConfig(
    max_attempts=RETRY_MAX_ATTEMPTS,
    max_time_between_retries=RETRY_MAX_INTERVAL,
)


def configure_retry(
    *,
    max_attempts: int | None = None,
    max_time_between_retries: float | None = None,
) -> None:
    global _retry_config
    _retry_config = RetryConfig(
        max_attempts=max_attempts or _retry_config["max_attempts"],
        max_time_between_retries=max_time_between_retries
        or _retry_config["max_time_between_retries"],
    )


def with_retry(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator that applies configurable retry logic to a function.
    The retry configuration can be changed at runtime using configure_retry().
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Create a retry object with the current configuration
        retry = tenacity.Retrying(
            stop=tenacity.stop_after_attempt(_retry_config["max_attempts"]),
            wait=tenacity.wait_exponential_jitter(
                initial=1, max=_retry_config["max_time_between_retries"]
            ),
            retry=tenacity.retry_if_exception(_is_retryable_exception),
            before_sleep=_log_retry,
            retry_error_callback=_log_failure,
            reraise=True,
        )

        # Use the retry object to call the function
        return retry(lambda: func(*args, **kwargs))

    return wrapper


def _is_retryable_exception(e: Exception) -> bool:
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
            "attempt_number": retry_state.attempt_number,
            "exception": str(retry_state.outcome.exception()),
        },
    )


def _log_failure(retry_state: tenacity.RetryCallState) -> Any:
    logger.info(
        "retry_failed",
        extra={
            "fn": retry_state.fn,
            "attempt_number": retry_state.attempt_number,
            "exception": str(retry_state.outcome.exception()),
        },
    )
    return retry_state.outcome.result()
