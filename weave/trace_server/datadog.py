"""Datadog integration utilities for trace server."""

import logging
from collections.abc import Callable, Generator, Iterator
from functools import wraps
from typing import Any

import ddtrace

logger = logging.getLogger(__name__)


def generator_trace(
    span_name: str,
) -> Callable[
    [Callable[..., Iterator[Any]]], Callable[..., Generator[Any, None, None]]
]:
    """Like @ddtrace.tracer.wrap but treats GeneratorExit as a normal completion.

    @ddtrace.tracer.wrap on a generator function marks the span as an error when
    the consumer closes the iterator early (e.g. explicit gen.close() call or client
    disconnect), because ddtrace propagates GeneratorExit through yield from and marks
    the span as errored. This decorator catches GeneratorExit and lets the span finish
    cleanly instead.
    """

    def decorator(
        func: Callable[..., Iterator[Any]],
    ) -> Callable[..., Generator[Any, None, None]]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Generator[Any, None, None]:
            with ddtrace.tracer.trace(span_name):
                try:
                    yield from func(*args, **kwargs)
                except GeneratorExit:
                    pass  # Normal early-close — not an application error

        return wrapper

    return decorator


def set_root_span_dd_tags(tags: dict[str, str | float | int]) -> None:
    """Set tags on the current root span for Datadog tracing.

    Args:
        tags: Dictionary of tags to set on the root span.
            Keys should be tag names and values can be strings, floats, or ints.

    Examples:
        Set performance metrics on the root span:
        >>> set_root_span_dd_tags({"query.duration_ms": 42.5, "query.rows": 100})

        Set status information:
        >>> set_root_span_dd_tags({"cache.hit": "true", "cache.key": "abc123"})
    """
    root_span = ddtrace.tracer.current_root_span()
    if root_span is None:
        logger.debug("No root span")
    else:
        root_span.set_tags(tags)


def set_current_span_dd_tags(tags: dict[str, str | float | int]) -> None:
    """Set tags on the current span for Datadog tracing.

    This sets tags on the current span (which may be nested), as opposed to
    the root span of the trace.

    Args:
        tags: Dictionary of tags to set on the current span.
            Keys should be tag names and values can be strings, floats, or ints.

    Examples:
        Set operation metadata on the current span:
        >>> set_current_span_dd_tags({"operation.count": 100, "operation.table": "calls"})
    """
    current_span = ddtrace.tracer.current_span()
    if current_span is not None:
        current_span.set_tags(tags)
