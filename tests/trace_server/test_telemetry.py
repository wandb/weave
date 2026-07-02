"""Tests for `weave.trace_server.telemetry`.

Covers the OTel Counter emission, `db_insert_path_scope` context propagation,
`init()` idempotency, and the span-attribute helpers.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from opentelemetry import trace as _otel_trace
from opentelemetry.metrics import NoOpMeterProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider

from weave.trace_server import telemetry
from weave.trace_server.tracing_root import local_root_scope

# ---------------------------------------------------------------------------
# init() + counter emission
# ---------------------------------------------------------------------------


@pytest.fixture
def reader_and_provider() -> Iterator[tuple[InMemoryMetricReader, MeterProvider]]:
    """Install a fresh in-memory MeterProvider for the test, restore afterward."""
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    prev_provider = telemetry._meter_provider
    prev_counter = telemetry._db_insert_counter
    telemetry.init(provider)
    try:
        yield reader, provider
    finally:
        telemetry._meter_provider = prev_provider
        telemetry._db_insert_counter = prev_counter


def _read_db_insert_samples(
    reader: InMemoryMetricReader,
) -> list[tuple[int, dict[str, Any]]]:
    """Return `[(value, attributes), ...]` for the `db_inserts` counter."""
    data = reader.get_metrics_data()
    if data is None:
        return []
    samples: list[tuple[int, dict[str, Any]]] = []
    for resource_metric in data.resource_metrics:
        for scope_metric in resource_metric.scope_metrics:
            for metric in scope_metric.metrics:
                if metric.name != telemetry.DB_INSERT_METRIC:
                    continue
                for point in metric.data.data_points:
                    samples.append((point.value, dict(point.attributes)))
    return samples


def test_init_is_idempotent() -> None:
    """Calling init twice must not raise; second call replaces the counter."""
    reader1 = InMemoryMetricReader()
    provider1 = MeterProvider(metric_readers=[reader1])
    reader2 = InMemoryMetricReader()
    provider2 = MeterProvider(metric_readers=[reader2])

    prev_provider = telemetry._meter_provider
    prev_counter = telemetry._db_insert_counter
    try:
        telemetry.init(provider1)
        first_counter = telemetry._db_insert_counter
        telemetry.init(provider2)
        second_counter = telemetry._db_insert_counter
        assert first_counter is not None
        assert second_counter is not None
        # Second init replaces the counter with one bound to provider2.
        assert first_counter is not second_counter

        telemetry.record_db_insert(table="calls", count=1)
        # First reader saw nothing (counter is now on provider2).
        assert _read_db_insert_samples(reader1) == []
        samples = _read_db_insert_samples(reader2)
        assert samples == [(1, {"table": "calls"})]
    finally:
        telemetry._meter_provider = prev_provider
        telemetry._db_insert_counter = prev_counter


def test_record_db_insert_before_init_is_noop() -> None:
    """Without init(), record_db_insert must not raise (counter is None)."""
    prev_provider = telemetry._meter_provider
    prev_counter = telemetry._db_insert_counter
    telemetry._meter_provider = NoOpMeterProvider()
    telemetry._db_insert_counter = None
    try:
        # Must not raise.
        telemetry.record_db_insert(table="calls", count=5)
    finally:
        telemetry._meter_provider = prev_provider
        telemetry._db_insert_counter = prev_counter


def test_record_db_insert_zero_count_is_noop(
    reader_and_provider: tuple[InMemoryMetricReader, MeterProvider],
) -> None:
    reader, _ = reader_and_provider
    telemetry.record_db_insert(table="calls", count=0)
    telemetry.record_db_insert(table="calls", count=-1)
    assert _read_db_insert_samples(reader) == []


def test_record_db_insert_table_only(
    reader_and_provider: tuple[InMemoryMetricReader, MeterProvider],
) -> None:
    """No path scope → only `table` attribute is emitted."""
    reader, _ = reader_and_provider
    telemetry.record_db_insert(table="calls_complete", count=3)
    samples = _read_db_insert_samples(reader)
    assert samples == [(3, {"table": "calls_complete"})]


def test_record_db_insert_with_scope(
    reader_and_provider: tuple[InMemoryMetricReader, MeterProvider],
) -> None:
    """Path scope populates the `path` attribute."""
    reader, _ = reader_and_provider
    with telemetry.db_insert_path_scope("otel_export"):
        telemetry.record_db_insert(table="calls_complete", count=7)
    samples = _read_db_insert_samples(reader)
    assert samples == [(7, {"table": "calls_complete", "path": "otel_export"})]


def test_record_db_insert_explicit_path_overrides_contextvar(
    reader_and_provider: tuple[InMemoryMetricReader, MeterProvider],
) -> None:
    """Explicit `path=` kwarg wins over the contextvar."""
    reader, _ = reader_and_provider
    with telemetry.db_insert_path_scope("outer"):
        telemetry.record_db_insert(table="calls", count=1, path="explicit")
    samples = _read_db_insert_samples(reader)
    assert samples == [(1, {"table": "calls", "path": "explicit"})]


def test_db_insert_path_scope_outermost_wins(
    reader_and_provider: tuple[InMemoryMetricReader, MeterProvider],
) -> None:
    """Nested `db_insert_path_scope` calls are no-ops — the outer path is preserved."""
    reader, _ = reader_and_provider
    with telemetry.db_insert_path_scope("outer"):
        with telemetry.db_insert_path_scope("inner"):
            telemetry.record_db_insert(table="calls", count=1)
    samples = _read_db_insert_samples(reader)
    assert samples == [(1, {"table": "calls", "path": "outer"})]


def test_tag_db_insert_path_sync_decorator(
    reader_and_provider: tuple[InMemoryMetricReader, MeterProvider],
) -> None:
    reader, _ = reader_and_provider

    @telemetry.tag_db_insert_path("sync_path")
    def do_insert() -> None:
        telemetry.record_db_insert(table="calls", count=2)

    do_insert()
    samples = _read_db_insert_samples(reader)
    assert samples == [(2, {"table": "calls", "path": "sync_path"})]


@pytest.mark.asyncio
async def test_tag_db_insert_path_async_decorator(
    reader_and_provider: tuple[InMemoryMetricReader, MeterProvider],
) -> None:
    reader, _ = reader_and_provider

    @telemetry.tag_db_insert_path("async_path")
    async def do_insert() -> None:
        telemetry.record_db_insert(table="calls", count=4)

    await do_insert()
    samples = _read_db_insert_samples(reader)
    assert samples == [(4, {"table": "calls", "path": "async_path"})]


# ---------------------------------------------------------------------------
# Span-attribute helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def tracer_provider() -> Iterator[TracerProvider]:
    """Install an SDK TracerProvider so `is_recording()` returns True."""
    provider = TracerProvider()
    prev = _otel_trace.get_tracer_provider()
    _otel_trace.set_tracer_provider(provider)
    try:
        yield provider
    finally:
        # `set_tracer_provider` warns on re-install; leave the SDK provider
        # in place — tests are isolated by fresh spans.
        _ = prev


def test_set_current_span_attrs_on_recording_span(
    tracer_provider: TracerProvider,
) -> None:
    tracer = tracer_provider.get_tracer("test")
    with tracer.start_as_current_span("op") as span:
        telemetry.set_current_span_attrs({"k": "v", "n": 42})
        assert span.attributes is not None
        assert span.attributes.get("k") == "v"
        assert span.attributes.get("n") == 42


def test_set_current_span_attrs_noop_without_recording_span() -> None:
    """No active span → no-op, no raise."""
    # Must not raise.
    telemetry.set_current_span_attrs({"k": "v"})


def test_set_root_span_attrs_populates_local_root(
    tracer_provider: TracerProvider,
) -> None:
    tracer = tracer_provider.get_tracer("test")
    with tracer.start_as_current_span("root") as root_span:
        with local_root_scope(root_span):
            with tracer.start_as_current_span("child"):
                telemetry.set_root_span_attrs({"root_key": "root_val"})
        assert root_span.attributes is not None
        assert root_span.attributes.get("root_key") == "root_val"


def test_set_root_span_attrs_noop_without_local_root() -> None:
    """No `local_root_scope` active → no-op, no raise."""
    telemetry.set_root_span_attrs({"k": "v"})
