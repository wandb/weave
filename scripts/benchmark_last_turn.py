"""Benchmark Last Turn queries against an isolated local ClickHouse instance."""

import argparse
import json
import statistics
import time
import uuid
from pathlib import Path

import clickhouse_connect

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server.calls_query_builder.calls_query_builder import CallsQuery
from weave.trace_server.calls_query_builder.last_turn import (
    LAST_TURN_FIELD,
    LAST_TURN_MAX_BLOCK_SIZE,
)
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=18124)
    parser.add_argument("--rows", type=int, nargs="+", default=[0, 1000, 10000])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--workload", choices=["ordinary", "mixed"], default="ordinary")
    args = parser.parse_args()
    client = clickhouse_connect.get_client(host=args.host, port=args.port)
    table = f"last_turn_benchmark_{uuid.uuid4().hex}"
    fixtures = json.loads(
        (
            Path(__file__).parents[1]
            / "tests/trace_server/fixtures/last_turn_frontend.json"
        ).read_text()
    )["cases"]
    client.command(f"""CREATE TABLE {table} (
        project_id String, id String, inputs_dump String, output_dump String,
        attributes_dump String, otel_dump String, deleted_at DateTime64(3)
    ) ENGINE=MergeTree ORDER BY (project_id, id)""")
    try:
        for count in args.rows:
            client.command(f"TRUNCATE TABLE {table}")
            rows = []
            for index in range(count):
                if args.workload == "mixed":
                    fixture = fixtures[index % len(fixtures)]
                    call = (
                        json.loads(fixture["raw_call"])
                        if "raw_call" in fixture
                        else fixture["call"]
                    )
                else:
                    call = {
                        "inputs": {
                            "messages": [
                                *[
                                    {"role": "user", "content": "old context " * 10}
                                    for _ in range(20)
                                ],
                                {
                                    "role": "user",
                                    "content": f"{'refund' if index % 10 == 0 else 'question'} {index}",
                                },
                            ]
                        },
                        "output": {},
                        "attributes": {},
                    }
                rows.append(
                    [
                        "benchmark",
                        str(index),
                        *[
                            json.dumps(
                                call[key], ensure_ascii=False, separators=(",", ":")
                            )
                            for key in ("inputs", "output", "attributes")
                        ],
                        "",
                        0,
                    ]
                )
            if rows:
                client.insert(table, rows)
            for operation in ("select", "filter", "sort"):
                cq = CallsQuery(
                    project_id="benchmark", read_table=ReadTable.CALLS_COMPLETE
                )
                cq.add_field("id")
                cq.add_field(LAST_TURN_FIELD)
                if operation == "filter":
                    cq.add_condition(
                        tsi_query.ContainsOperation.model_validate(
                            {
                                "$contains": {
                                    "input": {"$getField": LAST_TURN_FIELD},
                                    "substr": {"$literal": "refund"},
                                }
                            }
                        )
                    )
                if operation == "sort":
                    cq.add_order(LAST_TURN_FIELD, "asc")
                cq.set_limit(25)
                pb = ParamBuilder()
                sql = cq.as_sql(pb, table_alias=table)
                measurements = []
                for _ in range(args.repeats):
                    start = time.monotonic()
                    result = client.query(
                        sql,
                        parameters=pb.get_params(),
                        settings=ch_settings.update_settings_for_calls_complete_read(
                            {
                                "max_threads": 2,
                                "max_block_size": LAST_TURN_MAX_BLOCK_SIZE,
                                "use_query_cache": 0,
                            }
                        ),
                    )
                    measurements.append(
                        {
                            "wall_seconds": time.monotonic() - start,
                            "server_seconds": int(result.summary["elapsed_ns"]) / 1e9,
                            "peak_bytes": int(result.summary["memory_usage"]),
                            "read_rows": int(result.summary["read_rows"]),
                        }
                    )
                print(
                    json.dumps(
                        {
                            "clickhouse": client.server_version,
                            "workload": args.workload,
                            "rows": count,
                            "operation": operation,
                            "median_seconds": round(
                                statistics.median(
                                    m["server_seconds"] for m in measurements
                                ),
                                4,
                            ),
                            "peak_bytes": max(m["peak_bytes"] for m in measurements),
                            "runs": measurements,
                        }
                    ),
                    flush=True,
                )
    finally:
        client.command(f"DROP TABLE {table}")
        client.close()


if __name__ == "__main__":
    main()
