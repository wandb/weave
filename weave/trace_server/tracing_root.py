"""Contextvar-based "local root span" tracker for OpenTelemetry tracing.

Records the entry-point span so downstream helpers can attribute per-request
tags to the outer span. `opentelemetry.trace.get_current_span()` returns the
innermost active span, not the root, so we track the root explicitly.

A `local_root_scope(span)` context manager records `span` in a contextvar,
and `get_local_root()` reads it back. Application code enters a scope at
each entry point (FastAPI request middleware, Kafka batch handler,
scheduled-task entry); downstream helpers that need "the root for this unit
of work" call `get_local_root()`.

Python contextvars semantics — what callers need to know
---------------------------------------------------------
The tracker rides on `contextvars.ContextVar`, so its visibility follows
Python's context propagation rules:

- An `async def` route handler awaited via FastAPI inherits the middleware's
  context. The tracker is visible.
- `await run_in_threadpool(sync_fn)` (FastAPI/anyio) and `await
  asyncio.to_thread(sync_fn)` (stdlib >= 3.9) both copy the calling task's
  context into the worker thread. Visible.
- `asyncio.create_task(coro())` calls `Context.copy()` and runs the coroutine
  in the copy. Visible by default. To start a task with a fresh context, pass
  `context=contextvars.Context()` explicitly.
- `loop.run_in_executor(None, sync_fn)` does NOT copy contextvars to the
  worker thread. The tracker is NOT visible. Use `asyncio.to_thread` or
  manually `copy_context().run(...)` when executor work needs to see the
  local root.
- FastAPI `BackgroundTasks` run AFTER the response is sent — by then the
  request middleware's `local_root_scope` has exited. Background tasks do
  NOT see the local root. If you need root-span tagging on a background
  task, open a new `local_root_scope` inside the task itself.

Token discipline
----------------
`local_root_scope` returns a `contextvars.Token` from `var.set(...)` on
enter, and `var.reset(token)` on exit — including on exception, via
`finally`. This prevents a request handler that raises from leaking its
local root into whatever code reuses the same context next.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

    from opentelemetry import trace

_local_root: contextvars.ContextVar[trace.Span | None] = contextvars.ContextVar(
    "weave_trace_local_root", default=None
)


@contextmanager
def local_root_scope(span: trace.Span) -> Generator[None]:
    """Record `span` as the local root span for the duration of the block.

    Reset the contextvar on exit, including on exception, so callers that
    raise don't leak a stale root into the next user of this context.
    """
    token = _local_root.set(span)
    try:
        yield
    finally:
        _local_root.reset(token)


def get_local_root() -> trace.Span | None:
    """Return the span stored by the innermost active `local_root_scope`, or
    `None` if no scope is active or the stored span is not recording.

    Non-recording spans (e.g. `trace.INVALID_SPAN`, or spans created while no
    real provider was installed) are treated as "no local root".
    """
    span = _local_root.get()
    if span is None:
        return None
    if not span.is_recording():
        return None
    return span
