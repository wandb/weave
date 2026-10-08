"""Synthetic cost-stage benchmark against a local ClickHouse instance."""

import argparse
import datetime
import json
import tempfile
import time
import uuid
from pathlib import Path

import clickhouse_connect

from weave.trace_server.orm import ParamBuilder
from weave.trace_server.token_costs import (
    LLM_TOKEN_PRICES_COLUMNS,
    build_cost_ctes,
    get_compact_cost_final_select,
    get_cost_final_select,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=64)
    parser.add_argument("--compact-only", action="store_true")
    parser.add_argument("--port", type=int, default=18129)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    out = args.output_dir or Path(tempfile.mkdtemp(prefix="compact-cost-bench-"))
    out.mkdir(parents=True, exist_ok=True)
    client = clickhouse_connect.get_client(host="127.0.0.1", port=args.port)
    database = "compact_cost_bench_" + uuid.uuid4().hex
    client.command(f"CREATE DATABASE {database}")
    client = clickhouse_connect.get_client(
        host="127.0.0.1", port=args.port, database=database
    )
    project = "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc="
    fields = ["id", "started_at", "inputs_dump", "output_dump", "summary_dump"]
    types = {"string": "String", "float": "Float64", "datetime": "DateTime64(3)"}
    try:
        client.command(
            "CREATE TABLE base_calls (id String, started_at DateTime64(3), inputs_dump String, output_dump String, summary_dump String) ENGINE=MergeTree ORDER BY id"
        )
        price_cols = ", ".join(
            f"{c.name} {types[c.type]}" for c in LLM_TOKEN_PRICES_COLUMNS
        )
        client.command(
            f"CREATE TABLE llm_token_prices ({price_cols}) ENGINE=MergeTree ORDER BY llm_id"
        )
        now = datetime.datetime(2025, 1, 1)
        prices = []
        for model in ["bench-a", "bench-b"]:
            for i in range(24):
                values = {
                    c.name: (
                        ""
                        if c.type == "string"
                        else now
                        if c.type == "datetime"
                        else 0.001
                    )
                    for c in LLM_TOKEN_PRICES_COLUMNS
                }
                values.update(
                    id=f"{model}-{i}",
                    llm_id=model,
                    pricing_level="project",
                    pricing_level_id=project,
                    effective_date=now - datetime.timedelta(days=i + 1),
                )
                prices.append([values[c.name] for c in LLM_TOKEN_PRICES_COLUMNS])
        client.insert(
            "llm_token_prices",
            prices,
            column_names=[c.name for c in LLM_TOKEN_PRICES_COLUMNS],
        )
        usage = json.dumps(
            {
                "large_summary": "s" * 65536,
                "usage": {
                    m: {"input_tokens": 100, "output_tokens": 50, "requests": 1}
                    for m in ["bench-a", "bench-b"]
                },
            }
        )
        rows = [
            [str(i), now, "i" * 65536, "o" * 65536, usage] for i in range(args.rows)
        ]
        client.insert("base_calls", rows, column_names=fields)
        measurements = []
        results = {}
        for compact in (
            [True, True] if args.compact_only else [False, True, False, True]
        ):
            pb = ParamBuilder("pb")
            ctes = build_cost_ctes(pb, "all_calls", project, compact=compact)
            sql = (
                "WITH all_calls AS (SELECT * FROM base_calls ORDER BY id), "
                + ", ".join(cte.to_sql() for cte in ctes)
            )
            if compact:
                sql += (
                    ", call_costs AS ("
                    + get_cost_final_select(pb, ["id"], [], project, compact=True)
                    + ") "
                    + get_compact_cost_final_select(pb, "all_calls", fields, [])
                )
            else:
                sql += " " + get_cost_final_select(pb, fields, [], project)
            start = time.monotonic()
            result = client.query(
                sql,
                parameters=pb.get_params(),
                settings={"log_queries": 1, "max_threads": 4},
            )
            elapsed = time.monotonic() - start
            client.command("SYSTEM FLUSH LOGS")
            metrics = client.query(
                "SELECT memory_usage, read_rows, read_bytes, query_duration_ms FROM system.query_log WHERE query_id = {query_id:String} AND type = 'QueryFinish'",
                parameters={"query_id": result.query_id},
            ).result_rows[0]
            measurements.append(
                {
                    "compact": compact,
                    "elapsed_seconds": elapsed,
                    "peak_memory_bytes": metrics[0],
                    "read_rows": metrics[1],
                    "read_bytes": metrics[2],
                    "query_duration_ms": metrics[3],
                }
            )
            results[compact] = sorted(
                [
                    tuple(
                        json.loads(v) if col == "summary_dump" else v
                        for col, v in zip(result.column_names, row, strict=True)
                    )
                    for row in result.result_rows
                ],
                key=lambda row: row[0],
            )
            mode = "compact" if compact else "baseline"
            out.joinpath(f"bench-{mode}.sql").write_text(sql)
            out.joinpath(f"bench-{mode}-explain.txt").write_text(
                "\n".join(
                    row[0]
                    for row in client.query(
                        "EXPLAIN actions=1 " + sql, parameters=pb.get_params()
                    ).result_rows
                )
            )
        if not args.compact_only:
            assert results[False] == results[True]
        evidence = {
            "clickhouse_version": client.command("SELECT version()"),
            "rows": args.rows,
            "payload_bytes_per_call": 131072,
            "non_usage_summary_bytes_per_call": 65536,
            "models_per_call": 2,
            "price_rows_per_model": 24,
            "full_results_equal": None if args.compact_only else True,
            "measurements": measurements,
        }
        out.joinpath(f"structural-benchmark-{args.rows}.json").write_text(
            json.dumps(evidence, indent=2) + "\n"
        )
        print(json.dumps(evidence, indent=2))
    finally:
        client.command(f"DROP DATABASE {database}")


if __name__ == "__main__":
    main()
