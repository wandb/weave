"""Datadog integration utilities for trace server."""

import dataclasses
import logging
import time
from collections.abc import Callable, Generator, Iterator
from functools import wraps
from typing import Any

import ddtrace

from weave.trace_server import trace_server_interface as tsi

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class CallsQueryStreamMetrics:
    stream_start: float
    time_to_first_row_ms: float | None = None
    time_to_first_call_ms: float | None = None
    row_to_dict_ms: float = 0.0
    model_validate_ms: float = 0.0
    expand_ms: float = 0.0
    feedback_ms: float = 0.0
    rows_yielded: int = 0
    batches_processed: int = 0

    def mark_first_row(self) -> None:
        if self.time_to_first_row_ms is None:
            self.time_to_first_row_ms = round(
                (time.monotonic() - self.stream_start) * 1000,
                1,
            )

    def mark_yielded_call(self) -> None:
        self.rows_yielded += 1
        if self.time_to_first_call_ms is None:
            self.time_to_first_call_ms = round(
                (time.monotonic() - self.stream_start) * 1000,
                1,
            )

    def add_row_to_dict_ms(self, started_at: float) -> None:
        self.row_to_dict_ms += (time.monotonic() - started_at) * 1000

    def add_model_validate_ms(self, started_at: float) -> None:
        self.model_validate_ms += (time.monotonic() - started_at) * 1000

    def add_expand_ms(self, started_at: float) -> None:
        self.expand_ms += (time.monotonic() - started_at) * 1000

    def add_feedback_ms(self, started_at: float) -> None:
        self.feedback_ms += (time.monotonic() - started_at) * 1000

    def to_dd_tags(self) -> dict[str, str | float | int]:
        tags: dict[str, str | float | int] = {
            "calls_stream.rows_yielded": self.rows_yielded,
            "calls_stream.row_to_dict_ms": round(self.row_to_dict_ms, 1),
            "calls_stream.model_validate_ms": round(self.model_validate_ms, 1),
        }
        if self.time_to_first_row_ms is not None:
            tags["calls_stream.time_to_first_row_ms"] = self.time_to_first_row_ms
        if self.time_to_first_call_ms is not None:
            tags["calls_stream.time_to_first_call_ms"] = self.time_to_first_call_ms
        if self.batches_processed:
            tags["calls_stream.batches_processed"] = self.batches_processed
        if self.expand_ms:
            tags["calls_stream.expand_ms"] = round(self.expand_ms, 1)
        if self.feedback_ms:
            tags["calls_stream.feedback_ms"] = round(self.feedback_ms, 1)
        return tags


def iter_calls_query_stream_rows(
    raw_res: Iterator[tuple],
    metrics: CallsQueryStreamMetrics,
) -> Iterator[tuple]:
    for row in raw_res:
        metrics.mark_first_row()
        yield row


def validate_calls_query_stream_call(
    call_dict: dict[str, Any],
    metrics: CallsQueryStreamMetrics,
) -> tsi.CallSchema:
    model_validate_start = time.monotonic()
    call_schema = tsi.CallSchema.model_validate(call_dict)
    metrics.add_model_validate_ms(model_validate_start)
    metrics.mark_yielded_call()
    return call_schema


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
