"""Datadog integration utilities for trace server."""

import json
import logging
from collections.abc import Callable, Generator, Iterator
from functools import wraps
from typing import Any

import ddtrace
from pydantic import BaseModel

DD_TAG_MAX_LEN = 500

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


def tag_request(
    req: BaseModel,
    tag_prefix: str,
) -> dict[str, str | float | int]:
    """Serialize a pydantic request model as DD span tags for debuggability.

    Builds tags one field at a time, dropping fields that would exceed the
    per-tag size limit so every emitted value is valid JSON.
    """
    tags: dict[str, str | float | int] = {}
    remaining = DD_TAG_MAX_LEN
    for key, value in req.model_dump().items():
        if isinstance(value, BaseModel):
            serialized = value.model_dump_json()
        else:
            serialized = json.dumps(value)
        if len(serialized) <= remaining:
            tags[f"{tag_prefix}.{key}"] = serialized
            remaining -= len(serialized)
    return tags
