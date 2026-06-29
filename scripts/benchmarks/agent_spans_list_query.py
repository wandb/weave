#!/usr/bin/env -S uv run --extra trace_server python
"""Benchmark the agents ungrouped spans list-read: master vs page-prefetch two-pass.

Reuses the real query builder (`make_spans_list_query`) so the SQL is exactly
what the server runs, and the real migrator so the `spans` schema (sort key,
skip indexes) matches prod. Seeds a synthetic project, then for each access
shape times the always-attribute path ("master") against the two-pass and
reports rows-read and p50 from each query's result summary.

The PR perf table omitted `include_costs`; this adds it. The cost path wraps the
page CTE around the per-span price JOIN, so the question is whether the LIMIT
still prunes the `spans` scan (read-in-order on `(project_id, started_at,
span_id)`) rather than materializing the whole project's costs first.

    uv run scripts/benchmarks/agent_spans_list_query.py --rows 600000

Runs against the ClickHouse at WF_CLICKHOUSE_HOST/WF_CLICKHOUSE_PORT (default
localhost:8123) into a throwaway database that is dropped on exit (--keep to
retain). Point it at a populated prod replica with --database <db> --no-seed to
reproduce the PR's prod numbers.
"""

from __future__ import annotations

import argparse
import os
import statistics
from contextlib import contextmanager

from weave.trace_server import clickhouse_trace_server_batched as ch_batched
from weave.trace_server import clickhouse_trace_server_migrator as wf_migrator
from weave.trace_server.agents.types import AgentSortBy, AgentSpansQueryReq
from weave.trace_server.interface.query import Query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder import agent_query_builder as aqb

PROJECT_ID = "bench_project"
SPANS_PER_TRACE = 3
WARMUP_RUNS = 2
TIMED_RUNS = 6


def _shapes() -> list[tuple[str, AgentSpansQueryReq]]:
    """The list-read shapes to compare, mirroring the PR perf table + costs."""
    opname_filter = Query.model_validate(
        {"$expr": {"$eq": [{"$getField": "operation_name"}, {"$literal": "chat"}]}}
    )
    trace_filter = Query.model_validate(
        {"$expr": {"$eq": [{"$getField": "trace_id"}, {"$literal": "trace_0"}]}}
    )
    return [
        ("list50", AgentSpansQueryReq(project_id=PROJECT_ID, limit=50)),
        ("list1000", AgentSpansQueryReq(project_id=PROJECT_ID, limit=1000)),
        (
            "deep_offset",
            AgentSpansQueryReq(project_id=PROJECT_ID, limit=50, offset=10000),
        ),
        (
            "filter_opname",
            AgentSpansQueryReq(project_id=PROJECT_ID, limit=50, query=opname_filter),
        ),
        (
            "include_costs",
            AgentSpansQueryReq(project_id=PROJECT_ID, limit=50, include_costs=True),
        ),
        # Controls: these gate out of the two-pass, so master == two-pass (1x).
        (
            "ctl_trace_id",
            AgentSpansQueryReq(project_id=PROJECT_ID, limit=50, query=trace_filter),
        ),
        (
            "ctl_agent_sort",
            AgentSpansQueryReq(
                project_id=PROJECT_ID,
                limit=50,
                sort_by=[AgentSortBy(field="agent_name", direction="asc")],
            ),
        ),
    ]


@contextmanager
def _force_master():
    """Force the always-attribute (pre-two-pass) path for the master baseline."""
    original = aqb._spans_list_two_pass_applies
    aqb._spans_list_two_pass_applies = lambda req: False
    try:
        yield
    finally:
        aqb._spans_list_two_pass_applies = original


def _build_sql(req: AgentSpansQueryReq) -> tuple[str, dict[str, object]]:
    pb = ParamBuilder("genai")
    sql = aqb.make_spans_list_query(pb, req)
    return sql, pb.get_params()


def _seed(client, database: str, n_rows: int) -> None:
    n_traces = max(1, n_rows // SPANS_PER_TRACE)
    # role 0 = agent root (own identity), roles 1/2 = unset children that inherit.
    client.command(
        f"""
        INSERT INTO {database}.spans
            (project_id, trace_id, span_id, parent_span_id, operation_name,
             agent_name, agent_version, agent_id, conversation_id,
             request_model, input_tokens, output_tokens, started_at, created_at)
        SELECT
            '{PROJECT_ID}',
            concat('trace_', toString(intDiv(number, {SPANS_PER_TRACE}))),
            concat('span_', toString(number)),
            '',
            if(number % {SPANS_PER_TRACE} = 0, 'invoke_agent', 'chat'),
            if(number % {SPANS_PER_TRACE} = 0, concat('agent_', toString(intDiv(number, {SPANS_PER_TRACE}) % 200)), ''),
            if(number % {SPANS_PER_TRACE} = 0, 'v1', ''),
            if(number % {SPANS_PER_TRACE} = 0, concat('id_', toString(intDiv(number, {SPANS_PER_TRACE}) % 200)), ''),
            if(number % {SPANS_PER_TRACE} = 0, concat('conv_', toString(intDiv(number, {SPANS_PER_TRACE}))), ''),
            'gpt-4o-mini',
            toUInt64(100 + number % 500),
            toUInt64(50 + number % 300),
            toDateTime64('2026-01-01 00:00:00', 6) + toIntervalMillisecond(number * 17),
            now64()
        FROM numbers({n_traces * SPANS_PER_TRACE})
        """
    )
    client.command(f"OPTIMIZE TABLE {database}.spans FINAL")


def _measure(client, sql: str, params: dict[str, object]) -> tuple[int, float]:
    """Return (rows_read, p50_ms) over warm runs, from each query's summary."""
    durations: list[float] = []
    rows_read = 0
    for i in range(WARMUP_RUNS + TIMED_RUNS):
        result = client.query(sql, parameters=params, settings={"use_query_cache": 0})
        if i >= WARMUP_RUNS:
            durations.append(int(result.summary["elapsed_ns"]) / 1e6)
            rows_read = int(result.summary["read_rows"])
    return rows_read, statistics.median(durations)


def _run(client, database: str) -> None:
    header = f"{'shape':<16}{'tp_rows':>14}{'m_rows':>14}{'rx':>7}{'tp_ms':>9}{'m_ms':>9}{'tx':>7}"
    print(header)
    print("-" * len(header))
    for name, req in _shapes():
        tp_sql, tp_params = _build_sql(req)
        with _force_master():
            m_sql, m_params = _build_sql(req)
        tp_rows, tp_ms = _measure(client, tp_sql, tp_params)
        m_rows, m_ms = _measure(client, m_sql, m_params)
        rx = (m_rows / tp_rows) if tp_rows else 0.0
        tx = (m_ms / tp_ms) if tp_ms else 0.0
        print(
            f"{name:<16}{tp_rows:>14,}{m_rows:>14,}{rx:>7.1f}"
            f"{tp_ms:>9.1f}{m_ms:>9.1f}{tx:>7.1f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rows", type=int, default=600_000, help="synthetic spans to seed"
    )
    parser.add_argument(
        "--database", default=None, help="reuse this db instead of a throwaway"
    )
    parser.add_argument(
        "--no-seed", action="store_true", help="skip seeding (db already populated)"
    )
    parser.add_argument(
        "--keep", action="store_true", help="do not drop the throwaway db"
    )
    args = parser.parse_args()

    host = os.environ.get("WF_CLICKHOUSE_HOST", "localhost")
    port = int(os.environ.get("WF_CLICKHOUSE_PORT", "8123"))
    database = args.database or "bench_agent_spans_list"
    management_db = f"db_management_{database}"

    server = ch_batched.ClickHouseTraceServer(host=host, port=port, database=database)
    client = server.ch_client

    if not args.no_seed:
        client.command(f"DROP DATABASE IF EXISTS {management_db} SYNC")
        client.command(f"DROP DATABASE IF EXISTS {database} SYNC")
        server._database_ensured = False
        migrator = wf_migrator.get_clickhouse_trace_server_migrator(
            server._mint_client(), management_db=management_db
        )
        migrator.apply_migrations(database)
        print(f"seeding {args.rows:,} spans into {database}.spans ...")
        _seed(client, database, args.rows)

    try:
        _run(client, database)
    finally:
        if not args.keep and not args.database:
            client.command(f"DROP DATABASE IF EXISTS {management_db} SYNC")
            client.command(f"DROP DATABASE IF EXISTS {database} SYNC")


if __name__ == "__main__":
    main()
