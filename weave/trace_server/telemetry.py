"""Telemetry primitives for weave.trace_server.

Owns two things:
  1. Span-attribute helpers (`set_current_span_attrs` / `set_root_span_attrs`)
     that stamp searchable attributes on the currently active or local-root
     OTel span.
  2. The `db_inserts` counter — an OTel Counter emitted over whatever
     `MeterProvider` the host installs via `init()`.

The library does not own a `MeterProvider`. The host installs one via
`init()` at process startup. Until `init()` is called, metric emissions
no-op via `NoOpMeterProvider`, so the library keeps working in test/dev
environments where no host is set up.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Callable, Generator
from contextvars import ContextVar
from functools import wraps
from typing import Any

from opentelemetry import trace as _otel_trace
from opentelemetry.metrics import Counter, MeterProvider, NoOpMeterProvider

from weave.trace_server.tracing_root import get_local_root

DB_INSERT_METRIC = "weave_trace_server.db_inserts"
DB_INSERT_PATH_UNKNOWN = "unknown"

_db_insert_path: ContextVar[str] = ContextVar(
    "_db_insert_path", default=DB_INSERT_PATH_UNKNOWN
)

_init_lock = threading.Lock()
_meter_provider: MeterProvider = NoOpMeterProvider()
_db_insert_counter: Counter | None = None


def init(meter_provider: MeterProvider) -> None:
    """Wire the host's MeterProvider into weave's telemetry.

    Idempotent — safe to call twice. Must be called before the first metric
    is emitted, otherwise samples flow through the no-op provider and are
    silently dropped.
    """
    global _meter_provider, _db_insert_counter  # noqa: PLW0603 — singleton install
    with _init_lock:
        _meter_provider = meter_provider
        meter = meter_provider.get_meter("weave.trace_server")
        _db_insert_counter = meter.create_counter(DB_INSERT_METRIC)


@contextlib.contextmanager
def db_insert_path_scope(path: str) -> Generator[None, None, None]:
    """Tag any DB inserts within this block with `path:<path>`.

    Outermost wins: nested re-entries are no-ops so the originating
    public-API entry point is what shows up on the metric, not whatever
    inner helper happens to call `self._insert`.
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
    """Decorator form of `db_insert_path_scope`.

    Coroutine-safe (tag spans awaits). `run_in_executor` does NOT carry
    the contextvar, so a caller handing CH writes to an executor must
    `copy_context().run`.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with db_insert_path_scope(path):
                    return await func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with db_insert_path_scope(path):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def record_db_insert(*, table: str, count: int, path: str | None = None) -> None:
    """Emit a counter sample for rows inserted into the trace-server DB.

    `path` falls back to the current `db_insert_path_scope` contextvar if
    not provided; pass explicitly from background flushers where the
    contextvar may not be set.

    Attributes: `table` is always attached; `path` is attached only when
    resolved (i.e. not `DB_INSERT_PATH_UNKNOWN`). `service`/`env`/`version`
    come from the host `MeterProvider`'s Resource.
    """
    if count <= 0:
        return
    if _db_insert_counter is None:
        return
    resolved_path = path if path is not None else _db_insert_path.get()
    attrs: dict[str, str] = {"table": table}
    if resolved_path != DB_INSERT_PATH_UNKNOWN:
        attrs["path"] = resolved_path
    _db_insert_counter.add(count, attrs)


def set_current_span_attrs(attrs: dict[str, str | float | int]) -> None:
    """Set attributes on the currently active OTel span. No-op if none recording."""
    span = _otel_trace.get_current_span()
    if span.is_recording():
        span.set_attributes(attrs)


def set_root_span_attrs(attrs: dict[str, str | float | int]) -> None:
    """Set attributes on the local root span (the entry-point span recorded
    by `local_root_scope` at the request / batch boundary).

    No-op if no `local_root_scope` is active.
    """
    span = get_local_root()
    if span is None:
        return
    span.set_attributes(attrs)
