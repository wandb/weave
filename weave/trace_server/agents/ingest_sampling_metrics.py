"""Counters for the spans-model ingest sampler.

Emitted through the DogStatsD helper in ``weave.trace_server.datadog``, the
only counter transport available to this package. The calls-model sampler's
counters live in the trace-server service under different metric names; the
two families deliberately stay separate -- these count *spans* while those
count ingest messages, so summing them would be meaningless. Every emit is
best-effort: a metrics failure never breaks ingest.
"""

from __future__ import annotations

from weave.trace_server.datadog import emit_counter

_PREFIX = "weave_trace_server.ingest_sampling.spans"
_METRIC_SEEN = f"{_PREFIX}.seen"
_METRIC_PARSE_FAILURES = f"{_PREFIX}.parse_failures"
_METRIC_EVALS_KEPT = f"{_PREFIX}.evals_kept"
_METRIC_DROPPED = f"{_PREFIX}.dropped"
_METRIC_DROPPED_BYTES = f"{_PREFIX}.dropped_bytes"

_ROUTE_TAG = "route:agents_otel"


def seen(count: int) -> None:
    """Count spans the sampler inspected (the denominator for the rest)."""
    emit_counter(_METRIC_SEEN, count, [_ROUTE_TAG])


def parse_failures(count: int) -> None:
    """Count spans kept fail-open because their trace_id cannot key the hash."""
    emit_counter(_METRIC_PARSE_FAILURES, count, [_ROUTE_TAG])


def evals_kept(count: int) -> None:
    """Count spans kept by the eval carve-out."""
    emit_counter(_METRIC_EVALS_KEPT, count, [_ROUTE_TAG])


def dropped(count: int, byte_size: int, dry_run: bool) -> None:
    """Count dropped spans and their serialized protobuf size.

    Emitted in dry-run too (tagged ``dry_run:true``) -- observing would-drops
    is the whole point of dry-run, whereas the rate stamp is deliberately NOT
    written in dry-run (nothing was actually sampled). Same metric name for
    both real and would-drops, so dashboards MUST split this by the ``dry_run``
    tag; the tag, not a separate metric, is what keeps parity with the
    calls-model sampler.
    """
    tags = [_ROUTE_TAG, f"dry_run:{str(dry_run).lower()}"]
    emit_counter(_METRIC_DROPPED, count, tags)
    emit_counter(_METRIC_DROPPED_BYTES, byte_size, tags)
