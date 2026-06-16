"""OpenTelemetry-backed tracing primitives for `weave.trace_server`.

This module is the OTel-equivalent of the `ddtrace`-flavored helpers in
`weave/trace_server/datadog.py`. It exists so call sites under
`weave/trace_server/` can decorate functions with `@traced(name=...)` without
importing `ddtrace` directly.

Why a new module instead of editing `datadog.py`:
  - The historical name `datadog.py` is misleading once we're using OTel — DD
    is just the backend; the SDK is OpenTelemetry.
  - Existing public symbols in `datadog.py` (`record_db_insert`,
    `set_root_span_dd_tags`, etc.) stay where they are. Only the *tracing*
    surface moves here, scoped as a pure addition so reviewers can see the
    new decorator contract without scanning for changes elsewhere.

Contract for `@traced(name)`:
  - The span name is exactly `name` (no auto-derivation from `__qualname__`).
    Dashboards in DD are keyed on this name, so it MUST match the historical
    `@ddtrace.tracer.wrap(name="X")` value 1:1 during the migration.
  - Both `def` and `async def` shapes are supported; detected via
    `asyncio.iscoroutinefunction`.
  - A raised `Exception` propagates and marks the span ERROR with
    description `"{ExcType}: {msg}"`. OTel's `start_as_current_span`
    handles this on `__exit__`; the decorator does not.
  - `BaseException` subclasses (`GeneratorExit`, `asyncio.CancelledError`,
    `KeyboardInterrupt`, `SystemExit`) pass through without marking the
    span errored. Cancellation is normal control flow, not an application
    error.
  - Generator / async-generator functions are refused at decoration time:
    a `with start_as_current_span(...)` block ends the span when the wrapper
    returns the generator object (before iteration begins), not when the
    generator is exhausted. A silently-wrong span duration is worse than a
    loud `TypeError`. For streaming generators, use `traced_generator(...)`.

Contract for `traced_generator(name)`:
  - Like `@traced` but `yield from`s inside the span body so the span covers
    the full iteration lifetime.
  - `GeneratorExit` (client disconnects mid-stream) is treated as normal
    completion. Same `BaseException` pass-through as `@traced`.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Generator, Iterator
from functools import wraps
from typing import Any, TypeVar

from opentelemetry import trace

T = TypeVar("T")

# Hoisted to module scope — re-resolving `get_tracer(...)` inside every wrapper
# call costs ~7us per span open (measured), and these decorators run on hot
# CH-query paths with dozens of spans per request. `get_tracer` returns a
# `ProxyTracer` that lazy-resolves the real TracerProvider on first
# `start_span`/`start_as_current_span` call and caches it. Tests that need to
# observe a different TracerProvider should call `reset_tracer_cache()` after
# swapping `trace._TRACER_PROVIDER`.
_tracer = trace.get_tracer("weave.trace_server")


def reset_tracer_cache() -> None:
    """Drop the cached real-tracer reference inside this module's ProxyTracer.

    Only intended for tests that swap the global TracerProvider mid-process.
    Production code should never need to call this — there is exactly one
    TracerProvider per process and it is set during application startup
    before any span is opened.
    """
    # `_real_tracer` is a private attr on `opentelemetry.trace.ProxyTracer`.
    # If a future OTel release renames it, we'd rather tests silently lose
    # isolation than crash with AttributeError mid-suite.
    try:
        _tracer._real_tracer = None  # type: ignore[attr-defined]  # noqa: SLF001
    except AttributeError:
        pass


def traced(name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Wrap a function in an OTel span named `name`.

    Args:
        name: The span name. This becomes the DD APM `resource_name` via DD's
            auto-derivation, so it MUST match the historical
            `@ddtrace.tracer.wrap(name="X")` value during the migration so
            existing dashboards keep resolving.

    Raises:
        TypeError: If applied to a generator or async-generator function. Use
            `traced_generator` for those.

    Examples:
        Sync function:
        >>> @traced(name="my_op")
        ... def my_op(x: int) -> int:
        ...     return x * 2

        Async function:
        >>> @traced(name="my_async_op")
        ... async def my_async_op(x: int) -> int:
        ...     return x * 2
    """

    def deco(fn: Callable[..., T]) -> Callable[..., T]:
        if inspect.isgeneratorfunction(fn):
            raise TypeError(
                f"@traced cannot decorate generator function {fn.__qualname__!r}: "
                "the span would end on first generator-creation rather than on "
                "exhaustion. Use @traced_generator instead, which `yield from`s "
                "inside the span body."
            )
        if inspect.isasyncgenfunction(fn):
            raise TypeError(
                f"@traced cannot decorate async generator function "
                f"{fn.__qualname__!r}: the span would end on first "
                "generator-creation rather than on exhaustion."
            )

        if asyncio.iscoroutinefunction(fn):

            @wraps(fn)
            async def awrap(*args: Any, **kwargs: Any) -> Any:
                with _tracer.start_as_current_span(name):
                    return await fn(*args, **kwargs)

            return awrap  # type: ignore[return-value]

        @wraps(fn)
        def swrap(*args: Any, **kwargs: Any) -> Any:
            with _tracer.start_as_current_span(name):
                return fn(*args, **kwargs)

        return swrap  # type: ignore[return-value]

    return deco


def traced_generator(
    name: str,
) -> Callable[
    [Callable[..., Iterator[Any]]], Callable[..., Generator[Any, None, None]]
]:
    """Wrap a generator function in an OTel span that spans the full iteration.

    Drop-in replacement for `weave.trace_server.datadog.generator_trace`. Use
    on streaming endpoints where the function `yield`s rows incrementally and
    the consumer may disconnect early.

    `GeneratorExit` (consumer calling `gen.close()` or HTTP client disconnect)
    is treated as normal completion: OTel's `use_span` only catches
    `Exception`, not `BaseException`, so `GeneratorExit` propagates without
    marking the span errored.

    Examples:
        >>> @traced_generator(name="stream_calls")
        ... def stream_calls(limit: int) -> Iterator[dict]:
        ...     for i in range(limit):
        ...         yield {"id": i}
    """

    def decorator(
        fn: Callable[..., Iterator[Any]],
    ) -> Callable[..., Generator[Any, None, None]]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Generator[Any, None, None]:
            with _tracer.start_as_current_span(name):
                yield from fn(*args, **kwargs)

        return wrapper

    return decorator
