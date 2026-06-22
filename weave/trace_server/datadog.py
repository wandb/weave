"""Datadog integration utilities for trace server."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable, Generator, Iterator
from contextvars import ContextVar
from functools import lru_cache, wraps
from typing import TYPE_CHECKING, Any

import ddtrace
from ddtrace.internal.agent import config as _agent_config
from ddtrace.internal.dogstatsd import get_dogstatsd_client

if TYPE_CHECKING:
    from ddtrace.vendor.dogstatsd.base import DogStatsd

logger = logging.getLogger(__name__)

DB_INSERT_METRIC = "weave_trace_server.db_inserts"
DB_INSERT_PATH_UNKNOWN = "unknown"

_db_insert_path: ContextVar[str] = ContextVar(
    "_db_insert_path", default=DB_INSERT_PATH_UNKNOWN
)


@lru_cache(maxsize=1)
def _dogstatsd_client() -> DogStatsd:
    """Process-wide DogStatsd client; lazy so import is side-effect free.

    URL resolves from `DD_DOGSTATSD_URL` via ddtrace's agent config, so
    Helm-injected env vars flow through without extra wiring.
    """
    return get_dogstatsd_client(str(_agent_config.dogstatsd_url))


@contextlib.contextmanager
def db_insert_path(path: str) -> Generator[None, None, None]:
    """Tag any DB inserts within this block with `path:<path>`.

    Why: APM span tags get sampled away, so we mirror insert counts as
    dogstatsd counters. The `path` dimension distinguishes ingestion
    routes (otel vs native vs batch) that share the same destination table.

    Outermost wins: nested re-entries are no-ops so the originating
    public-API entry point is what shows up on the metric, not whatever
    inner helper happens to call self._insert.
    """
    if _db_insert_path.get() != DB_INSERT_PATH_UNKNOWN:
        yield
        return
    token = _db_insert_path.set(path)
    try:
        yield
    finally:
        _db_insert_path.reset(token)


def tag_db_insert_path(
    path: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator: tag DB inserts done inside `func` with `path:<path>`.

    Convenience over `db_insert_path` for decorating public API methods
    whose entire body should be attributed to a single ingestion path.

    Coroutine-safe (tag spans awaits). `run_in_executor` does NOT carry the
    contextvar, so a caller handing CH writes to an executor must `copy_context().run`.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with db_insert_path(path):
                    return await func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with db_insert_path(path):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def record_db_insert(*, table: str, count: int, path: str | None = None) -> None:
    """Emit a dogstatsd counter for rows inserted into the trace-server DB.

    `path` falls back to the current `db_insert_path()` contextvar if
    not provided; pass it explicitly from background flushers where the
    contextvar may not be set.
    """
    if count <= 0:
        return
    resolved_path = path if path is not None else _db_insert_path.get()
    _dogstatsd_client().increment(
        DB_INSERT_METRIC,
        value=count,
        tags=[f"table:{table}", f"path:{resolved_path}"],
    )


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
