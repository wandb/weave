"""OpenTelemetry-backed tracing primitives for `weave.trace_server`.

This module is the OTel-equivalent of the `ddtrace`-flavored helpers in
`weave/trace_server/datadog.py`. It exists so call sites under
`weave/trace_server/` can decorate functions with `@traced(name=...)` without
importing `ddtrace` directly.

Contract for `@traced(name)`:
  - The span name is exactly `name` (no auto-derivation from `__qualname__`).
    Dashboards in DD are keyed on this name, so it MUST match the historical
    `@ddtrace.tracer.wrap(name="X")` value 1:1 during the migration.
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
  - Like `@traced` but iterates inside the span body so the span covers the
    full iteration lifetime. Both generator and async-generator shapes are
    supported.
  - `GeneratorExit` (consumer disconnect) is treated as normal completion.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Generator, Iterator
from contextlib import contextmanager
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast, overload

from opentelemetry import context as otel_context
from opentelemetry import trace

from weave.shared.otel_context_keys import WEAVE_SERVER_SPAN_KEY

F = TypeVar("F", bound=Callable[..., Any])
P = ParamSpec("P")
T = TypeVar("T")

# Module-scope tracer: re-resolving `get_tracer(...)` per wrapper call costs
# ~7us/span (measured), and these decorators run on hot CH-query paths with
# dozens of spans per request. Tests swap this binding via
# `monkeypatch.setattr(tracing, "_tracer", ...)`.
_tracer = trace.get_tracer("weave.trace_server")


@contextmanager
def _server_span(name: str) -> Iterator[None]:
    """Open the span and mark the context for the duration it is current.

    The mark is how the client SDK tells one of our spans from an agent's when
    it records the invoking span on a call; without it a call created under an
    in-process server would claim Weave's own telemetry as its caller.
    """
    with _tracer.start_as_current_span(name) as span:
        token = otel_context.attach(otel_context.set_value(WEAVE_SERVER_SPAN_KEY, span))
        try:
            yield
        finally:
            otel_context.detach(token)


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
    if inspect.isasyncgenfunction(fn) and "generator" not in allow:
        raise TypeError(
            f"{decorator_name} cannot decorate async generator function "
            f"{fn.__qualname__!r}: the span would end on generator-creation "
            "rather than on exhaustion. Use @traced_generator instead."
        )


def traced(name: str) -> Callable[[F], F]:
    """Wrap a function in an OTel span named `name`.

    Args:
        name: The span name. Becomes the DD APM `resource_name` via the
            OTel→DD bridge, so it MUST match the historical
            `@ddtrace.tracer.wrap(name="X")` value during the migration.

    Raises:
        TypeError: If applied to a generator or async-generator function.
            Use `traced_generator` for those.
    """

    def deco(fn: F) -> F:
        _reject_unsupported_shape(fn, "@traced", allow="sync, async")

        if asyncio.iscoroutinefunction(fn):

            @wraps(fn)
            async def awrap(*args: Any, **kwargs: Any) -> Any:
                with _server_span(name):
                    return await fn(*args, **kwargs)

            return cast(F, awrap)

        @wraps(fn)
        def swrap(*args: Any, **kwargs: Any) -> Any:
            with _server_span(name):
                return fn(*args, **kwargs)

        return cast(F, swrap)

    return deco


class _TracedGenerator:
    """The decorator `traced_generator(name)` returns; overloaded by shape."""

    def __init__(self, name: str) -> None:
        self._name = name

    @overload
    def __call__(
        self, fn: Callable[P, AsyncIterator[T]]
    ) -> Callable[P, AsyncGenerator[T, None]]: ...

    @overload
    def __call__(
        self, fn: Callable[P, Iterator[T]]
    ) -> Callable[P, Generator[T, None, None]]: ...

    def __call__(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        _reject_unsupported_shape(fn, "@traced_generator", allow="generator")
        name = self._name

        if inspect.isasyncgenfunction(fn):

            @wraps(fn)
            async def awrapper(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
                with _server_span(name):
                    async for item in fn(*args, **kwargs):
                        yield item

            return awrapper

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Generator[Any, None, None]:
            with _server_span(name):
                yield from fn(*args, **kwargs)

        return wrapper


def traced_generator(name: str) -> _TracedGenerator:
    """Wrap a generator function in an OTel span that spans the full iteration.

    Drop-in replacement for `weave.trace_server.datadog.generator_trace`. Use
    on streaming endpoints where the function `yield`s rows incrementally.
    Accepts generator and async-generator functions.

    `GeneratorExit` (consumer calling `gen.close()` or HTTP client disconnect)
    is treated as normal completion: OTel's `use_span` only catches
    `Exception`, not `BaseException`.
    """
    return _TracedGenerator(name)
