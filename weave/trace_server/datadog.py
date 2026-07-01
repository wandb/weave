"""DogStatsD counter emission + DD-flavored OTel span-tag helpers.

Emits a single counter (`weave_trace_server.db_inserts`) over UDP or a Unix
domain socket. Wire format: `metric.name:value|c|#tag1:val1,tag2:val2`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import socket
import threading
from collections.abc import Callable, Generator
from contextvars import ContextVar
from functools import wraps
from typing import Any
from urllib.parse import urlparse

from opentelemetry import trace as _otel_trace

from weave.trace_server.tracing_root import get_local_root

logger = logging.getLogger(__name__)

DB_INSERT_METRIC = "weave_trace_server.db_inserts"
DB_INSERT_PATH_UNKNOWN = "unknown"

_DEFAULT_HOST = "localhost"
_DEFAULT_PORT = 8125
# DD_DOGSTATSD_URL schemes that denote a Unix domain socket (the SaaS-prod
# Agent form); anything else is treated as UDP host:port.
_UDS_SCHEMES = frozenset({"unix", "unixgram", "uds"})

_db_insert_path: ContextVar[str] = ContextVar(
    "_db_insert_path", default=DB_INSERT_PATH_UNKNOWN
)


def _parse_port(raw: str | None, *, default: int = _DEFAULT_PORT) -> int:
    """Parse a port string, falling back to `default` for missing or invalid.

    A non-numeric `DD_DOGSTATSD_PORT` must not crash the process at import
    time — this module is imported by ~11 callers, and one bad env var
    would take the whole trace server down.
    """
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid port %r; falling back to %d", raw, default)
        return default


def _resolve_dogstatsd_target() -> tuple[int, str | tuple[str, int]]:
    """Resolve the DogStatsD socket family + address.

    Honors `DD_DOGSTATSD_URL` (`unix://`/`unixgram://`/`uds://` path for a
    Unix domain socket, else `udp://host:port`), then `DD_AGENT_HOST` +
    `DD_DOGSTATSD_PORT`, then `localhost:8125`. SaaS-prod Agents expose
    DogStatsD over a Unix socket, so UDS support is load-bearing.
    """
    url = os.environ.get("DD_DOGSTATSD_URL")
    if url:
        try:
            parsed = urlparse(url if "://" in url else f"udp://{url}")
            if parsed.scheme in _UDS_SCHEMES and parsed.path:
                return socket.AF_UNIX, parsed.path
            if parsed.hostname:
                return socket.AF_INET, (parsed.hostname, parsed.port or _DEFAULT_PORT)
        except ValueError:
            logger.warning(
                "Could not parse DD_DOGSTATSD_URL=%r; falling back to host/port env",
                url,
            )
    host = os.environ.get("DD_AGENT_HOST", _DEFAULT_HOST)
    port = _parse_port(os.environ.get("DD_DOGSTATSD_PORT"))
    return socket.AF_INET, (host, port)


def format_packet(metric: str, value: int, tags: list[str]) -> bytes:
    """Format a DogStatsD counter packet. Public so tests can pin the wire format."""
    tag_suffix = f"|#{','.join(tags)}" if tags else ""
    return f"{metric}:{value}|c{tag_suffix}".encode()


class _StatsDClient:
    """Best-effort, fire-and-forget DogStatsD client over UDP or a Unix socket.

    Resolves the target once and connects the socket, so each `emit` is a
    single non-blocking `send()` — no per-call DNS or address lookup. A
    failed `connect()` (bad host, missing socket file) disables the client;
    subsequent emits are no-ops.
    """

    def __init__(self, family: int, addr: str | tuple[str, int]) -> None:
        self._family = family
        self._addr = addr
        self._sock: socket.socket | None = None
        self._init_failed = False
        self._lock = threading.Lock()

    def _ensure_socket(self) -> socket.socket | None:
        # Fast path: already initialized.
        if self._sock is not None:
            return self._sock
        if self._init_failed:
            return None
        with self._lock:
            # Re-check under lock — another thread may have set it up.
            if self._sock is not None:
                return self._sock
            if self._init_failed:
                return None
            try:
                sock = socket.socket(self._family, socket.SOCK_DGRAM)
                sock.setblocking(False)
                # `connect()` binds the datagram socket's default
                # destination once (resolving the host for UDP), so each
                # `emit` is a bare non-blocking `send()` with no per-call
                # lookup.
                sock.connect(self._addr)
            except OSError as exc:
                logger.warning(
                    "DogStatsD init failed for %r (%s); metrics disabled",
                    self._addr,
                    exc,
                )
                self._init_failed = True
                return None
            self._sock = sock
            return sock

    def emit(self, metric: str, value: int, tags: list[str]) -> None:
        sock = self._ensure_socket()
        if sock is None:
            return
        try:
            sock.send(format_packet(metric, value, tags))
        except OSError:
            # Transient send failures don't interrupt the caller. We do
            # not log here — a noisy agent restart would flood logs.
            pass


_client = _StatsDClient(*_resolve_dogstatsd_target())


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
    """Decorator form of `db_insert_path`.

    Coroutine-safe (tag spans awaits). `run_in_executor` does NOT carry
    the contextvar, so a caller handing CH writes to an executor must
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
    """Emit a counter for rows inserted into the trace-server DB.

    `path` falls back to the current `db_insert_path()` contextvar if
    not provided; pass explicitly from background flushers where the
    contextvar may not be set.
    """
    if count <= 0:
        return
    resolved_path = path if path is not None else _db_insert_path.get()
    _client.emit(
        DB_INSERT_METRIC,
        count,
        [f"table:{table}", f"path:{resolved_path}"],
    )


def set_current_span_dd_tags(tags: dict[str, str | float | int]) -> None:
    """Set attributes on the currently active OTel span. No-op if none recording."""
    span = _otel_trace.get_current_span()
    if span.is_recording():
        span.set_attributes(tags)


def set_root_span_dd_tags(tags: dict[str, str | float | int]) -> None:
    """Set attributes on the local root span (the entry-point span recorded
    by `local_root_scope` at the request / batch boundary).

    No-op if no `local_root_scope` is active.
    """
    span = get_local_root()
    if span is None:
        return
    span.set_attributes(tags)
