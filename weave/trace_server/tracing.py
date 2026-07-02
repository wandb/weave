"""OpenTelemetry-backed tracing primitives for `weave.trace_server`.

Contract for `@traced(name)`:
  - The span name is exactly `name` (no auto-derivation from `__qualname__`).
    Dashboards key on this name, so span-name literals are load-bearing.
  - Both `def` and `async def` shapes are supported.
  - A raised `Exception` propagates and marks the span ERROR. OTel's
    `start_as_current_span` handles this on `__exit__`; the decorator does
    not. `BaseException` subclasses (`GeneratorExit`, `CancelledError`,
    `KeyboardInterrupt`, `SystemExit`) pass through without marking the
    span errored — cancellation is normal control flow.
  - Generator / async-generator functions are refused at decoration time
    because `with start_as_current_span(...)` would end the span when the
    wrapper returns the generator object, not when iteration ends. Use
    `traced_generator` for streaming.

Contract for `traced_generator(name)`:
  - Like `@traced` but `yield from`s inside the span body so the span covers
    the full iteration lifetime.
  - `GeneratorExit` (consumer disconnect) is treated as normal completion.
  - Async generators are refused — `yield from` doesn't work on them and we
    don't have a streaming-async use case today.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Generator, Iterator
from functools import wraps
from typing import Any, TypeVar, cast

from opentelemetry import trace

F = TypeVar("F", bound=Callable[..., Any])

# Module-scope tracer: re-resolving `get_tracer(...)` per wrapper call costs
# ~7us/span (measured), and these decorators run on hot CH-query paths with
# dozens of spans per request. Tests swap this binding via
# `monkeypatch.setattr(tracing, "_tracer", ...)`.
_tracer = trace.get_tracer("weave.trace_server")


def _reject_unsupported_shape(
    fn: Callable[..., Any], decorator_name: str, *, allow: str
) -> None:
    """Raise `TypeError` at decoration time for function shapes we can't trace.

    `allow` describes what shape IS accepted, included in the error message
    so the user knows which decorator to reach for instead.
    """
    if inspect.isgeneratorfunction(fn) and "generator" not in allow:
        raise TypeError(
            f"{decorator_name} cannot decorate generator function "
            f"{fn.__qualname__!r}: the span would end on generator-creation "
            "rather than on exhaustion. Use @traced_generator instead."
        )
    if inspect.isasyncgenfunction(fn):
        raise TypeError(
            f"{decorator_name} cannot decorate async generator function "
            f"{fn.__qualname__!r}: `yield from` does not work on async "
            "generators. No streaming-async use case is supported today."
        )


def traced(name: str) -> Callable[[F], F]:
    """Wrap a function in an OTel span named `name`.

    Args:
        name: The span name. Becomes the DD APM `resource_name` via the
            OTel→DD bridge; dashboards key on this literal.

    Raises:
        TypeError: If applied to a generator or async-generator function.
            Use `traced_generator` for those.
    """

    def deco(fn: F) -> F:
        _reject_unsupported_shape(fn, "@traced", allow="sync, async")

        if asyncio.iscoroutinefunction(fn):

            @wraps(fn)
            async def awrap(*args: Any, **kwargs: Any) -> Any:
                with _tracer.start_as_current_span(name):
                    return await fn(*args, **kwargs)

            return cast(F, awrap)

        @wraps(fn)
        def swrap(*args: Any, **kwargs: Any) -> Any:
            with _tracer.start_as_current_span(name):
                return fn(*args, **kwargs)

        return cast(F, swrap)

    return deco


def traced_generator(
    name: str,
) -> Callable[
    [Callable[..., Iterator[Any]]], Callable[..., Generator[Any, None, None]]
]:
    """Wrap a generator function in an OTel span that spans the full iteration.

    Use on streaming endpoints where the function `yield`s rows incrementally.

    `GeneratorExit` (consumer calling `gen.close()` or HTTP client disconnect)
    is treated as normal completion: OTel's `use_span` only catches
    `Exception`, not `BaseException`.
    """

    def decorator(
        fn: Callable[..., Iterator[Any]],
    ) -> Callable[..., Generator[Any, None, None]]:
        _reject_unsupported_shape(fn, "@traced_generator", allow="generator")

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Generator[Any, None, None]:
            with _tracer.start_as_current_span(name):
                yield from fn(*args, **kwargs)

        return wrapper

    return decorator
