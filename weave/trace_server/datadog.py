"""Datadog-integration utilities for trace server.

Historical name kept for backward compatibility — internally this module
no longer depends on `ddtrace`. The two things it provides are:

  1. `db_insert_path` / `tag_db_insert_path` / `record_db_insert` —
     emit DogStatsD counters for trace-server DB inserts. The wire
     format and metric name (`weave_trace_server.db_inserts`) are
     preserved so existing DD dashboards keep working.

  2. `set_root_span_dd_tags` / `set_current_span_dd_tags` —
     thin wrappers that set attributes on the current OTel span.
     "root span" semantics are NOT preserved exactly — OTel has no
     built-in current-root-span accessor; we use the currently-active
     span instead. See `services/weave-trace/docs/phase-b-weave-public-plan.md`
     §3.4 for the analysis: all three historical call sites only need
     "the span currently active when the helper is called," so this
     is NOT a semantic regression.

The DogStatsD client is inline (~30 lines, UDP socket) rather than via the
`datadog` PyPI package or an OTel Counter. Rationale (per design review):
inline keeps the wire format under our control, adds zero new deps, and
avoids entangling these counters with the isolated MeterProvider used
elsewhere for runtime metrics.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import socket
from collections.abc import Callable, Generator
from contextvars import ContextVar
from functools import lru_cache, wraps
from typing import Any

from opentelemetry import trace as _otel_trace

logger = logging.getLogger(__name__)

DB_INSERT_METRIC = "weave_trace_server.db_inserts"
DB_INSERT_PATH_UNKNOWN = "unknown"

_db_insert_path: ContextVar[str] = ContextVar(
    "_db_insert_path", default=DB_INSERT_PATH_UNKNOWN
)


class _StatsDClient:
    """Minimal DogStatsD client over UDP.

    Best-effort, non-blocking-ish. We open the socket lazily so importing
    this module is side-effect free, and swallow `OSError` on send so a
    stats hiccup never crashes the request path.

    Wire format: `metric.name:value|c|#tag1:val1,tag2:val2`. Multi-line
    payloads (one packet per metric) are supported by DD Agent; we send
    one packet per call.
    """

    def __init__(self, host: str, port: int) -> None:
        self._addr = (host, port)
        self._sock: socket.socket | None = None

    def _ensure_socket(self) -> socket.socket | None:
        if self._sock is None:
            try:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._sock.setblocking(False)
            except OSError:
                logger.debug(
                    "DogStatsD socket creation failed; metric emission disabled"
                )
                return None
        return self._sock

    def increment(
        self, metric: str, *, value: int = 1, tags: list[str] | None = None
    ) -> None:
        sock = self._ensure_socket()
        if sock is None:
            return
        tag_suffix = f"|#{','.join(tags)}" if tags else ""
        packet = f"{metric}:{value}|c{tag_suffix}".encode()
        try:
            sock.sendto(packet, self._addr)
        except OSError:
            # Don't let a transient stats failure interrupt the caller.
            pass


def _resolve_dogstatsd_addr() -> tuple[str, int]:
    """Resolve `DD_DOGSTATSD_URL` / `DD_AGENT_HOST` / defaults to (host, port).

    Honors `DD_DOGSTATSD_URL` (e.g. `udp://datadog.datadog:8125`) first,
    then falls back to `DD_AGENT_HOST:DD_DOGSTATSD_PORT`, then
    `localhost:8125`.
    """
    url = os.environ.get("DD_DOGSTATSD_URL")
    if url:
        # Strip optional `udp://` prefix.
        if url.startswith("udp://"):
            url = url[len("udp://") :]
        host, _, port_str = url.partition(":")
        port = int(port_str) if port_str else 8125
        return host, port
    host = os.environ.get("DD_AGENT_HOST", "localhost")
    port = int(os.environ.get("DD_DOGSTATSD_PORT", "8125"))
    return host, port


@lru_cache(maxsize=1)
def _dogstatsd_client() -> _StatsDClient:
    """Process-wide DogStatsd client; lazy so import is side-effect free."""
    host, port = _resolve_dogstatsd_addr()
    return _StatsDClient(host, port)


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


def set_root_span_dd_tags(tags: dict[str, str | float | int]) -> None:
    """Set attributes on the current OTel span.

    Args:
        tags: Dictionary of attributes to set. Keys are attribute names;
            values can be strings, floats, or ints.

    Note:
        "root span" in the original ddtrace sense is not exactly preserved
        — OTel has no built-in current-root-span accessor. We use the
        currently-active span, which is correct for all known historical
        call sites (they all want "the span currently active here", not
        literal trace-root semantics).
    """
    span = _otel_trace.get_current_span()
    if span.is_recording():
        span.set_attributes(tags)


def set_current_span_dd_tags(tags: dict[str, str | float | int]) -> None:
    """Set attributes on the current OTel span.

    Args:
        tags: Dictionary of attributes to set. Keys are attribute names;
            values can be strings, floats, or ints.
    """
    span = _otel_trace.get_current_span()
    if span.is_recording():
        span.set_attributes(tags)
