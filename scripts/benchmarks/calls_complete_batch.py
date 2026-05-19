"""Microbench for `ClickHouseTraceServer.calls_complete` per-batch lookup hoisting.

Background: Datadog trace `6a0c7d9900000000975ce4fb10f7c246` shows, inside a
50-call batch to POST /traces/v2/.../calls/complete, 50 sequential
`table_routing.resolve_v2_write_target` and `ttl_settings.get_project_retention_days`
spans. Both lookups are L1-cached, but each call still pays the function-call +
lock + cachetools-get + ddtrace span overhead -> ~3-5ms per cached hit, ~450ms
wasted wall time per 50-call same-project batch.

This bench exercises `calls_complete` against a stubbed CH client (no DB
connection) so the only costs measured are the Python/ddtrace overhead of the
hoist path. It compares one run to itself; to compare branches, run the script
once on master and once on this branch and diff the median.

Usage:
    uv run python scripts/benchmarks/calls_complete_batch.py [--iterations 20] [--batch-size 50]
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import statistics
import time
import uuid
from unittest.mock import MagicMock, patch

import ddtrace

from weave.trace_server import clickhouse_trace_server_batched as chts
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.project_version import project_version
from weave.trace_server.project_version.types import CallsStorageServerMode
from weave.trace_server.ttl_settings import reset_ttl_cache

DEFAULT_ITERATIONS = 20
DEFAULT_BATCH_SIZE = 50


def _make_complete_call(project_id: str) -> tsi.CompletedCallSchemaForInsert:
    """Build a realistic-but-cheap complete-call payload."""
    now = dt.datetime.now(dt.timezone.utc)
    return tsi.CompletedCallSchemaForInsert(
        project_id=project_id,
        id=str(uuid.uuid4()),
        trace_id=str(uuid.uuid4()),
        op_name="bench_op",
        started_at=now,
        ended_at=now,
        attributes={"env": "bench", "version": 1},
        inputs={"prompt": "hello world", "n": 42},
        output={"text": "ok"},
        summary={"weave": {"latency_ms": 12}},
    )


def _make_mock_ch_client() -> MagicMock:
    """Mock CH client. Residence query -> COMPLETE_ONLY; TTL query -> no TTL."""
    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_ch_client.insert.return_value = MagicMock()

    residence_result = MagicMock()
    residence_result.result_rows = [(1, None)]  # COMPLETE_ONLY
    residence_result.row_count = 1
    residence_result.first_row = (1, None)

    ttl_result = MagicMock()
    ttl_result.result_rows = []
    ttl_result.row_count = 0
    ttl_result.first_row = None

    def _route_query(sql, *args, **kwargs):
        if "project_ttl_settings" in sql:
            return ttl_result
        return residence_result

    mock_ch_client.query.side_effect = _route_query
    return mock_ch_client


def _time_calls_complete(iterations: int, batch_size: int, mode: str) -> list[float]:
    """Run calls_complete `iterations` times against a same-project batch.

    `mode` controls cache state per iteration:
      - "warm":     populate L1 caches once before the loop (the steady-state
                    production case for an active project)
      - "cold":     clear L1 caches before each iteration (every batch's first
                    lookup goes through to CH)
    """
    mock_ch_client = _make_mock_ch_client()
    project_id = base64.b64encode(b"bench_entity/bench_project").decode()

    with patch.object(
        chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        server = chts.ClickHouseTraceServer(host="bench_host")
        server.table_routing_resolver._mode = CallsStorageServerMode.AUTO

        with (
            patch.object(chts.ClickHouseTraceServer, "_insert_call_complete"),
            patch.object(chts.ClickHouseTraceServer, "_insert_call_to_v1"),
            patch.object(chts, "maybe_enqueue_minimal_call_end", return_value=None),
        ):
            if mode == "warm":
                # Warm L1 caches so timed runs measure cached-hit overhead.
                server.table_routing_resolver.resolve_v2_write_target(
                    project_id, mock_ch_client
                )
                from weave.trace_server.ttl_settings import get_project_retention_days

                get_project_retention_days(project_id, mock_ch_client)

            timings_ms: list[float] = []
            for _ in range(iterations):
                if mode == "cold":
                    project_version.reset_project_residence_cache()
                    reset_ttl_cache()
                batch = [_make_complete_call(project_id) for _ in range(batch_size)]
                req = tsi.CallsUpsertCompleteReq(batch=batch)
                # Wrap in an active DD span so `set_current_span_dd_tags` does real
                # work (in prod each request has a parent HTTP span; without one
                # the tag calls early-return and underestimate per-call overhead).
                with ddtrace.tracer.trace("bench.calls_complete"):
                    t0 = time.perf_counter_ns()
                    server.calls_complete(req)
                    t1 = time.perf_counter_ns()
                timings_ms.append((t1 - t0) / 1_000_000.0)
            return timings_ms


def _summarize(label: str, timings_ms: list[float]) -> dict[str, str | float]:
    s = sorted(timings_ms)
    n = len(s)
    return {
        "label": label,
        "n": float(n),
        "min_ms": s[0],
        "median_ms": s[n // 2],
        "mean_ms": statistics.fmean(s),
        "p95_ms": s[min(n - 1, int(n * 0.95))],
        "max_ms": s[-1],
    }


def _print_markdown(rows: list[dict[str, str | float]]) -> None:
    print()
    print("| scenario | n | min ms | median ms | mean ms | p95 ms | max ms |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        print(
            f"| {r['label']} | {int(float(r['n']))} | {float(r['min_ms']):.2f} | "
            f"{float(r['median_ms']):.2f} | {float(r['mean_ms']):.2f} | "
            f"{float(r['p95_ms']):.2f} | {float(r['max_ms']):.2f} |"
        )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    rows: list[dict[str, str | float]] = []
    for mode in ("warm", "cold"):
        # Reset caches between scenarios so each starts fresh.
        project_version.reset_project_residence_cache()
        reset_ttl_cache()
        label = f"calls_complete x{args.batch_size} ({mode} cache)"
        print(f"[{label}] running {args.iterations} iterations...")
        timings = _time_calls_complete(args.iterations, args.batch_size, mode=mode)
        rows.append(_summarize(label, timings))

    _print_markdown(rows)


if __name__ == "__main__":
    main()
