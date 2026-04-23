"""OpenTelemetry metrics for ClickHouse client operations.

Wraps the hot methods on a ``clickhouse_connect`` client (``query``,
``insert``, ``command``, ``query_rows_stream``) with no-op-safe OTEL
instruments. When no ``MeterProvider`` is registered by the host
service, ``opentelemetry.metrics.get_meter`` returns a no-op meter
and the wrappers add no measurable overhead beyond a function call.

The host service (e.g. weave-trace) is responsible for installing a
real MeterProvider + exporter. This module only produces the signal.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from opentelemetry import metrics

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client as CHClient

METER_NAME = "weave.trace_server.clickhouse"

WRAPPED_METHODS: tuple[str, ...] = (
    "query",
    "insert",
    "command",
    "query_rows_stream",
)

QUERY_DURATION_BUCKETS: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
)

_meter = metrics.get_meter(METER_NAME)

_query_duration = _meter.create_histogram(
    name="weave.clickhouse.query.duration",
    unit="s",
    description="ClickHouse query duration by operation",
    explicit_bucket_boundaries_advisory=list(QUERY_DURATION_BUCKETS),
)

_query_count = _meter.create_counter(
    name="weave.clickhouse.query.count",
    description="Total ClickHouse queries by operation",
)

_query_errors = _meter.create_counter(
    name="weave.clickhouse.query.errors",
    description="ClickHouse query errors by operation",
)


P = ParamSpec("P")
R = TypeVar("R")


def install_metrics(client: CHClient) -> CHClient:
    """Rebind hot ClickHouse client methods to record OTEL metrics.

    Must be called once per thread-local client. Idempotent per client:
    if the attribute is already wrapped (sentinel set), it is skipped.
    """
    for op in WRAPPED_METHODS:
        original = getattr(client, op, None)
        if original is None:
            continue
        if getattr(original, "_weave_metrics_wrapped", False):
            continue
        setattr(client, op, _wrap(op, original))
    return client


def _wrap(operation: str, func: Callable[P, R]) -> Callable[P, R]:
    attrs = {"operation": operation}

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        _query_count.add(1, attrs)
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        except Exception:
            _query_errors.add(1, attrs)
            raise
        finally:
            _query_duration.record(time.perf_counter() - start, attrs)

    wrapper._weave_metrics_wrapped = True  # type: ignore[attr-defined]
    return wrapper
