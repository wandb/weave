"""Tests for ClickHouse OTEL metrics instrumentation."""

from __future__ import annotations

from typing import Any

import pytest
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from weave.trace_server.clickhouse import metrics as ch_metrics
from weave.trace_server.clickhouse.metrics import (
    WRAPPED_METHODS,
    install_metrics,
)


class FakeClient:
    """Minimal stand-in for clickhouse_connect.driver.client.Client.

    Only exposes the methods we expect to wrap plus one we don't, so we
    can verify unwrapped methods remain untouched.
    """

    def __init__(self) -> None:
        self.query_calls = 0
        self.insert_calls = 0
        self.command_calls = 0
        self.query_rows_stream_calls = 0
        self.untouched_calls = 0

    def query(self, *args: Any, **kwargs: Any) -> str:
        self.query_calls += 1
        return "ok"

    def insert(self, *args: Any, **kwargs: Any) -> int:
        self.insert_calls += 1
        return 1

    def command(self, *args: Any, **kwargs: Any) -> None:
        self.command_calls += 1

    def query_rows_stream(self, *args: Any, **kwargs: Any) -> list:
        self.query_rows_stream_calls += 1
        return []

    def untouched(self) -> None:
        self.untouched_calls += 1

    def raise_boom(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("boom")


@pytest.fixture
def reader_and_provider(monkeypatch: pytest.MonkeyPatch):
    """Install an InMemoryMetricReader-backed MeterProvider and rebind the
    module-level instruments so they feed into it.

    Required because the instruments are created at import time against
    whatever global MeterProvider is active then (typically the default
    no-op provider).
    """
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    set_meter_provider(provider)
    meter = provider.get_meter(ch_metrics.METER_NAME)
    monkeypatch.setattr(
        ch_metrics,
        "_query_duration",
        meter.create_histogram(
            name="weave.clickhouse.query.duration",
            unit="s",
        ),
    )
    monkeypatch.setattr(
        ch_metrics,
        "_query_count",
        meter.create_counter(name="weave.clickhouse.query.count"),
    )
    monkeypatch.setattr(
        ch_metrics,
        "_query_errors",
        meter.create_counter(name="weave.clickhouse.query.errors"),
    )
    return reader


def _metric_points(reader: InMemoryMetricReader, name: str) -> list[Any]:
    data = reader.get_metrics_data()
    out = []
    if data is None:
        return out
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                if metric.name == name:
                    out.extend(metric.data.data_points)
    return out


def test_install_metrics_wraps_all_hot_methods(reader_and_provider: InMemoryMetricReader) -> None:
    """install_metrics rebinds every hot method, records success metrics,
    leaves unrelated methods alone, and is idempotent. Errors increment
    the error counter and the exception still propagates.
    """
    client = FakeClient()
    install_metrics(client)  # type: ignore[arg-type]

    for op in WRAPPED_METHODS:
        assert getattr(getattr(client, op), "_weave_metrics_wrapped", False), op

    assert client.query("SELECT 1") == "ok"
    assert client.insert("tbl", [[1]]) == 1
    client.command("OPTIMIZE TABLE foo")
    assert client.query_rows_stream("SELECT 1") == []
    client.untouched()

    assert client.query_calls == 1
    assert client.insert_calls == 1
    assert client.command_calls == 1
    assert client.query_rows_stream_calls == 1
    assert client.untouched_calls == 1

    install_metrics(client)  # type: ignore[arg-type]
    client.query("SELECT 2")
    assert client.query_calls == 2

    reader_and_provider.collect()
    count_points = _metric_points(reader_and_provider, "weave.clickhouse.query.count")
    ops_seen = {p.attributes["operation"]: p.value for p in count_points}
    assert ops_seen == {
        "query": 2,
        "insert": 1,
        "command": 1,
        "query_rows_stream": 1,
    }

    duration_points = _metric_points(
        reader_and_provider, "weave.clickhouse.query.duration"
    )
    assert {p.attributes["operation"] for p in duration_points} == set(WRAPPED_METHODS)
    assert all(p.count >= 1 for p in duration_points)

    client.query = client.raise_boom  # type: ignore[method-assign]
    install_metrics(client)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="boom"):
        client.query()

    reader_and_provider.collect()
    error_points = _metric_points(reader_and_provider, "weave.clickhouse.query.errors")
    assert {p.attributes["operation"]: p.value for p in error_points} == {"query": 1}


def test_install_metrics_is_a_noop_when_no_provider_registered() -> None:
    """Without an SDK MeterProvider, wrapped methods still work and do not
    error. This is the operator-v2 'OTEL SDK not installed' path.
    """
    client = FakeClient()
    install_metrics(client)  # type: ignore[arg-type]
    assert client.query("SELECT 1") == "ok"
    with pytest.raises(RuntimeError, match="boom"):
        client.raise_boom()
