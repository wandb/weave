"""Unit tests for `weave.trace_server.tracing`.

These tests use an isolated `TracerProvider` with an in-memory exporter so
they don't depend on (or interfere with) any process-global tracer state.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace.status import StatusCode

from weave.trace_server import tracing
from weave.trace_server.tracing import traced, traced_generator


@pytest.fixture
def exporter(monkeypatch: pytest.MonkeyPatch) -> InMemorySpanExporter:
    """Install an isolated TracerProvider + in-memory exporter for the test.

    Swaps the module-level `_tracer` binding directly so the decorators
    under test emit through our isolated provider. No process-global state
    is mutated.
    """
    provider = TracerProvider()
    exp = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exp))
    monkeypatch.setattr(tracing, "_tracer", provider.get_tracer("test"))
    return exp


def _single_span(exporter: InMemorySpanExporter) -> ReadableSpan:
    spans = exporter.get_finished_spans()
    assert len(spans) == 1, f"expected one span, got {len(spans)}: {spans!r}"
    return spans[0]


# ---------------------------------------------------------------------------
# @traced — sync function shape
# ---------------------------------------------------------------------------


def test_sync_function_span_name(exporter: InMemorySpanExporter) -> None:
    @traced(name="my_sync_op")
    def my_sync_op(x: int) -> int:
        return x * 2

    assert my_sync_op(3) == 6
    span = _single_span(exporter)
    assert span.name == "my_sync_op"
    assert span.status.status_code == StatusCode.UNSET


def test_sync_function_marks_error_and_reraises(
    exporter: InMemorySpanExporter,
) -> None:
    @traced(name="raises_op")
    def raises_op() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        raises_op()

    span = _single_span(exporter)
    assert span.name == "raises_op"
    assert span.status.status_code == StatusCode.ERROR
    # OTel's start_as_current_span sets description to "{ExcType}: {msg}".
    assert span.status.description == "RuntimeError: boom"
    # An exception event should be recorded on the span.
    event_names = [e.name for e in span.events]
    assert "exception" in event_names


def test_sync_function_preserves_metadata() -> None:
    """`functools.wraps` should preserve __name__, __doc__, __module__."""

    @traced(name="span_name_unrelated_to_fn_name")
    def some_fn(x: int) -> int:
        """Docstring."""
        return x

    assert some_fn.__name__ == "some_fn"
    assert some_fn.__doc__ == "Docstring."
    assert some_fn.__wrapped__(5) == 5  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# @traced — async function shape
# ---------------------------------------------------------------------------


def test_async_function_span_name(exporter: InMemorySpanExporter) -> None:
    @traced(name="my_async_op")
    async def my_async_op(x: int) -> int:
        return x * 2

    assert asyncio.run(my_async_op(3)) == 6
    span = _single_span(exporter)
    assert span.name == "my_async_op"
    assert span.status.status_code == StatusCode.UNSET


def test_async_function_marks_error_and_reraises(
    exporter: InMemorySpanExporter,
) -> None:
    @traced(name="async_raises_op")
    async def async_raises_op() -> None:
        raise ValueError("async-boom")

    with pytest.raises(ValueError, match="async-boom"):
        asyncio.run(async_raises_op())

    span = _single_span(exporter)
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description == "ValueError: async-boom"


def test_async_function_cancellation_not_marked_error(
    exporter: InMemorySpanExporter,
) -> None:
    """`asyncio.CancelledError` is normal control flow, not an application error.

    OTel's `use_span` catches `except Exception` (not `BaseException`), so
    `CancelledError` propagates through `start_as_current_span` without
    marking the span errored. We pin this here so a future change to the
    SDK or our wrapper that breaks this guarantee gets caught.
    """

    @traced(name="cancellable_op")
    async def cancellable_op() -> None:
        await asyncio.sleep(10)

    async def runner() -> None:
        task = asyncio.create_task(cancellable_op())
        # Let the task enter the sleep.
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(runner())
    span = _single_span(exporter)
    # NOT marked as error — cancellation is not an application error.
    assert span.status.status_code == StatusCode.UNSET


# ---------------------------------------------------------------------------
# @traced — refuses generator / async-generator functions at decoration time
# ---------------------------------------------------------------------------


def test_traced_refuses_generator_function() -> None:
    with pytest.raises(TypeError, match="generator function"):

        @traced(name="bad")
        def gen_fn() -> Iterator[int]:
            yield 1


def test_traced_refuses_async_generator_function() -> None:
    with pytest.raises(TypeError, match="async generator function"):

        @traced(name="bad")
        async def agen_fn() -> Any:
            yield 1


# ---------------------------------------------------------------------------
# traced_generator — covers full iteration, handles client disconnect
# ---------------------------------------------------------------------------


def test_traced_generator_span_covers_full_iteration(
    exporter: InMemorySpanExporter,
) -> None:
    @traced_generator(name="stream_op")
    def stream_op(n: int) -> Iterator[int]:
        yield from range(n)

    result = list(stream_op(5))
    assert result == [0, 1, 2, 3, 4]

    span = _single_span(exporter)
    assert span.name == "stream_op"
    assert span.status.status_code == StatusCode.UNSET


def test_traced_generator_client_disconnect_not_marked_error(
    exporter: InMemorySpanExporter,
) -> None:
    """A consumer abandoning the generator (e.g. HTTP client disconnect)
    raises `GeneratorExit` inside the generator. The wrapper must NOT mark
    the span as errored.
    """

    @traced_generator(name="abandoned_op")
    def abandoned_op() -> Iterator[int]:
        i = 0
        while True:
            yield i
            i += 1

    gen = abandoned_op()
    next(gen)
    next(gen)
    gen.close()  # triggers GeneratorExit inside the generator

    span = _single_span(exporter)
    assert span.name == "abandoned_op"
    assert span.status.status_code == StatusCode.UNSET


def test_traced_generator_marks_error_on_exception(
    exporter: InMemorySpanExporter,
) -> None:
    @traced_generator(name="stream_raises_op")
    def stream_raises_op() -> Iterator[int]:
        yield 1
        raise RuntimeError("stream-boom")

    with pytest.raises(RuntimeError, match="stream-boom"):
        list(stream_raises_op())

    span = _single_span(exporter)
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description == "RuntimeError: stream-boom"


def test_traced_generator_refuses_async_generator_function() -> None:
    """`yield from` does not work on async generators; refuse at decoration."""
    with pytest.raises(TypeError, match="async generator function"):

        @traced_generator(name="bad")
        async def agen_fn() -> Any:
            yield 1


# ---------------------------------------------------------------------------
# Idempotency — re-resolving the tracer on each call doesn't break nesting
# ---------------------------------------------------------------------------


def test_nested_traced_calls_produce_parent_child_spans(
    exporter: InMemorySpanExporter,
) -> None:
    @traced(name="inner")
    def inner() -> int:
        return 1

    @traced(name="outer")
    def outer() -> int:
        return inner()

    assert outer() == 1

    spans = exporter.get_finished_spans()
    assert len(spans) == 2
    # SimpleSpanProcessor exports in finish-order, so inner finishes first.
    inner_span = next(s for s in spans if s.name == "inner")
    outer_span = next(s for s in spans if s.name == "outer")
    assert inner_span.parent is not None
    assert inner_span.parent.span_id == outer_span.context.span_id
