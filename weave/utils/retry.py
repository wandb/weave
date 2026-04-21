from __future__ import annotations

import logging
from collections.abc import Callable
from contextvars import ContextVar
from functools import wraps
from typing import Any, TypeVar, cast, overload

import httpx
import tenacity
from pydantic import ValidationError
from typing_extensions import ParamSpec

from weave.trace.settings import retry_max_attempts, retry_max_interval
from weave.trace_server.ids import generate_id

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

# Context variable to store retry ID for correlation
_retry_id: ContextVar[str] = ContextVar("retry_id")


@overload
def with_retry(_func: Callable[P, R]) -> Callable[P, R]: ...
@overload
def with_retry(
    *,
    retry_if: Callable[[BaseException], bool] | None = None,
    wait: tenacity.wait.wait_base | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...
def with_retry(
    _func: Callable[P, R] | None = None,
    *,
    retry_if: Callable[[BaseException], bool] | None = None,
    wait: tenacity.wait.wait_base | None = None,
) -> Callable[P, R] | Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that applies configurable retry logic to a function.
    Retry configuration is determined by:
    1. Values from weave.trace.settings (if available)
    2. Values set via configure_retry().

    Automatically generates a retry ID for request correlation across all attempts.

    Pass `retry_if` to replace the default transport-error predicate with a
    caller-specific one (e.g. a 404-matcher for eventual-consistency races on
    write-then-read paths). Callers that want both transport retries and a
    domain retry should layer two `with_retry` calls.

    Pass `wait` to override the default exponential-jitter wait strategy. The
    override is resolved at decoration time, so callers that need the value to
    track a mutable module constant should wrap `with_retry` themselves.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Generate a retry ID for this request (shared across all attempts)
            retry_id = generate_id()
            retry_id_token = _retry_id.set(retry_id)

            predicate = retry_if if retry_if is not None else _is_retryable_exception

            retry = tenacity.Retrying(
                stop=tenacity.stop_after_attempt(retry_max_attempts()),
                wait=wait
                or tenacity.wait_exponential_jitter(
                    initial=1, max=retry_max_interval()
                ),
                retry=tenacity.retry_if_exception(predicate),
                before_sleep=_log_retry,
                retry_error_callback=_log_failure,
                reraise=True,
            )

            try:
                return cast(R, retry(func, *args, **kwargs))
            finally:
                # Always clean up the retry ID
                _retry_id.reset(retry_id_token)

        return wrapper

    if _func is not None:
        return decorator(_func)
    return decorator


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

    # Don't retry CallsCompleteModeRequired - should trigger immediate mode switch
    # Lazy import to avoid circular dependency (http_utils imports from this module)
    from weave.trace_server_bindings.http_utils import CallsCompleteModeRequired

    if isinstance(e, CallsCompleteModeRequired):
        return False

    # Don't retry on HTTP 4xx (except 429)
    if isinstance(e, httpx.HTTPStatusError) and e.response is not None:
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
