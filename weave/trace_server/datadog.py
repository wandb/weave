"""Trace-server observability helpers (DogStatsD counters + OTel span tags).

Historical name `datadog.py` kept because 11 internal modules import from
it; renaming is a mechanical follow-up. The module no longer depends on
ddtrace — it provides:

  1. `db_insert_path` / `tag_db_insert_path` / `record_db_insert` —
     emit DogStatsD counters for trace-server DB inserts. The wire
     format `weave_trace_server.db_inserts:N|c|#table:T,path:P` and the
     metric name are preserved so existing DD dashboards keep working.

  2. `set_current_span_dd_tags` — set attributes on the current OTel span.

Why inline DogStatsD instead of the `datadog` PyPI package or an OTel
Counter: keeps the wire format under our control, adds zero new deps, and
avoids entangling these counters with the isolated OTel MeterProvider
used elsewhere for runtime metrics.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import socket
from collections.abc import Callable, Generator
from contextvars import ContextVar
from functools import wraps
from typing import Any
from urllib.parse import urlparse

from opentelemetry import trace as _otel_trace

logger = logging.getLogger(__name__)

DB_INSERT_METRIC = "weave_trace_server.db_inserts"
DB_INSERT_PATH_UNKNOWN = "unknown"

_db_insert_path: ContextVar[str] = ContextVar(
    "_db_insert_path", default=DB_INSERT_PATH_UNKNOWN
)


def _resolve_dogstatsd_addr() -> tuple[str, int]:
    """Resolve `DD_DOGSTATSD_URL` / `DD_AGENT_HOST` / defaults to (host, port).

    Honors `DD_DOGSTATSD_URL` (e.g. `udp://datadog.datadog:8125`) first,
    then falls back to `DD_AGENT_HOST:DD_DOGSTATSD_PORT`, then
    `localhost:8125`. A malformed URL falls back to localhost rather than
    crashing the process at import time.
    """
    url = os.environ.get("DD_DOGSTATSD_URL")
    if url:
        try:
            parsed = urlparse(url if "://" in url else f"udp://{url}")
            if parsed.hostname:
                return parsed.hostname, parsed.port or 8125
        except ValueError:
            logger.warning(
                "Could not parse DD_DOGSTATSD_URL=%r; falling back to "
                "localhost:8125",
                url,
            )
    host = os.environ.get("DD_AGENT_HOST", "localhost")
    port = int(os.environ.get("DD_DOGSTATSD_PORT", "8125"))
    return host, port


_ADDR: tuple[str, int] = _resolve_dogstatsd_addr()
_SOCK: socket.socket | None = None
_SOCK_FAILED: bool = False  # don't retry creation after one failure


def _emit_statsd(metric: str, value: int, tags: list[str]) -> None:
    """Send a single DogStatsD counter packet.

    Best-effort: a socket-creation or send failure never interrupts the
    caller. We lazy-create the UDP socket on first emission so importing
    this module has zero side effects.
    """
    global _SOCK, _SOCK_FAILED  # noqa: PLW0603 — lazy singleton init
    if _SOCK_FAILED:
        return
    if _SOCK is None:
        try:
            _SOCK = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            _SOCK.setblocking(False)
        except OSError:
            logger.warning(
                "DogStatsD socket creation failed; metric emission disabled"
            )
            _SOCK_FAILED = True
            return
    tag_suffix = f"|#{','.join(tags)}" if tags else ""
    packet = f"{metric}:{value}|c{tag_suffix}".encode()
    try:
        _SOCK.sendto(packet, _ADDR)
    except OSError:
        # Don't let a transient stats failure interrupt the caller.
        pass


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

    Coroutine-safe (tag spans awaits). `run_in_executor` does NOT carry the
    contextvar, so a caller handing CH writes to an executor must
    `copy_context().run`.
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
    _emit_statsd(
        DB_INSERT_METRIC,
        count,
        [f"table:{table}", f"path:{resolved_path}"],
    )


def set_current_span_dd_tags(tags: dict[str, str | float | int]) -> None:
    """Set attributes on the current OTel span.

    No-op if no span is recording. Replaces the historical
    `ddtrace.tracer.current_span().set_tags(...)` and
    `ddtrace.tracer.current_root_span().set_tags(...)` — OTel has no
    built-in root-span accessor, but every historical call site only needs
    the span currently active when the helper is called.
    """
    span = _otel_trace.get_current_span()
    if span.is_recording():
        span.set_attributes(tags)
