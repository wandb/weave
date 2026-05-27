"""Benchmark `make_file_content_read_query` master vs this PR.

Measures the read-query latency at the SQL layer against a local ClickHouse
container. Seeds a freshly-created `files` table with realistic data
(single-row PKs and duplicate-PK rows) and times each query variant over
many iterations.

Usage:
    python scripts/perf/bench_file_content_read.py

Env:
    CH_HOST (default localhost), CH_PORT (default 8123),
    BENCH_DIGESTS (default 200), BENCH_ITERS (default 500).

The script is self-contained -> safe to run from either branch and compare
output. The two query variants are inlined so master/PR diff doesn't change
the script itself.
"""

from __future__ import annotations

import os
import secrets
import statistics
import time

import clickhouse_connect

CH_HOST = os.environ.get("CH_HOST", "localhost")
CH_PORT = int(os.environ.get("CH_PORT", "8123"))
BENCH_DIGESTS = int(os.environ.get("BENCH_DIGESTS", "200"))
BENCH_ITERS = int(os.environ.get("BENCH_ITERS", "500"))
DB = f"bench_files_{int(time.time())}"
PROJECT_ID = "bench/project"

# Master: window without ORDER BY (non-deterministic on duplicate PKs).
QUERY_MASTER = """
SELECT n_chunks, val_bytes, file_storage_uri
FROM (
    SELECT *
    FROM (
            SELECT *,
                row_number() OVER (PARTITION BY project_id, digest, chunk_index) AS rn
            FROM {db}.files
            WHERE project_id = {{p:String}} AND digest = {{d:String}}
        )
    WHERE rn = 1
    ORDER BY project_id, digest, chunk_index
)
WHERE project_id = {{p:String}} AND digest = {{d:String}}
"""

# PR: window ORDER BY file_storage_uri IS NULL DESC (inline-CH wins ties).
QUERY_PR = """
SELECT n_chunks, val_bytes, file_storage_uri
FROM (
    SELECT *
    FROM (
            SELECT *,
                row_number() OVER (
                    PARTITION BY project_id, digest, chunk_index
                    ORDER BY file_storage_uri IS NULL DESC
                ) AS rn
            FROM {db}.files
            WHERE project_id = {{p:String}} AND digest = {{d:String}}
        )
    WHERE rn = 1
    ORDER BY project_id, digest, chunk_index
)
WHERE project_id = {{p:String}} AND digest = {{d:String}}
"""


def setup_table(client) -> list[str]:
    """Create a `files`-shaped table and seed BENCH_DIGESTS digests.

    Half the digests are single-row (typical prod). The other half are
    duplicate-PK (the race the PR fixes): one inline-CH row + one
    bucket-URI row at the same (project_id, digest, chunk_index).
    """
    client.command(f"CREATE DATABASE IF NOT EXISTS {DB}")
    client.command(f"""
        CREATE TABLE {DB}.files (
            project_id String,
            digest String,
            chunk_index UInt32,
            n_chunks UInt32,
            name String,
            val_bytes String,
            bytes_stored UInt64 DEFAULT 0,
            file_storage_uri Nullable(String),
            created_at DateTime64(3) DEFAULT now64(3)
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (project_id, digest, chunk_index)
    """)

    digests = [secrets.token_hex(16) for _ in range(BENCH_DIGESTS)]
    payload = b"x" * 50_000

    # Single-row half (typical case).
    single_rows = [
        [PROJECT_ID, d, 0, 1, "inline.bin", payload, len(payload), None]
        for d in digests[: BENCH_DIGESTS // 2]
    ]
    client.insert(
        f"{DB}.files",
        single_rows,
        column_names=[
            "project_id",
            "digest",
            "chunk_index",
            "n_chunks",
            "name",
            "val_bytes",
            "bytes_stored",
            "file_storage_uri",
        ],
    )

    # Duplicate-PK half: insert inline + bucket rows as separate INSERTs
    # so they land in different parts (mirrors the production race).
    columns = [
        "project_id",
        "digest",
        "chunk_index",
        "n_chunks",
        "name",
        "val_bytes",
        "bytes_stored",
        "file_storage_uri",
    ]
    for d in digests[BENCH_DIGESTS // 2 :]:
        client.insert(
            f"{DB}.files",
            [[PROJECT_ID, d, 0, 1, "inline.bin", payload, len(payload), None]],
            column_names=columns,
        )
        client.insert(
            f"{DB}.files",
            [
                [
                    PROJECT_ID,
                    d,
                    0,
                    1,
                    "bucket.bin",
                    b"",
                    len(payload),
                    f"gs://bench/{d}",
                ]
            ],
            column_names=columns,
        )

    return digests


def time_query(
    client, sql_template: str, digests: list[str], iters: int
) -> list[float]:
    """Run the templated query `iters` times against random digests."""
    sql = sql_template.format(db=DB)
    timings = []
    for i in range(iters):
        d = digests[i % len(digests)]
        t0 = time.perf_counter()
        client.query(sql, parameters={"p": PROJECT_ID, "d": d})
        timings.append((time.perf_counter() - t0) * 1000.0)
    return timings


def report(label: str, timings: list[float]) -> None:
    timings_sorted = sorted(timings)
    p = lambda q: timings_sorted[int(len(timings_sorted) * q)]
    print(
        f"{label:>8}  "
        f"n={len(timings):>5}  "
        f"mean={statistics.mean(timings):.3f}ms  "
        f"p50={p(0.50):.3f}ms  "
        f"p95={p(0.95):.3f}ms  "
        f"p99={p(0.99):.3f}ms  "
        f"max={timings_sorted[-1]:.3f}ms"
    )


def bench_variant(
    label: str,
    client,
    sql_template: str,
    digests: list[str],
) -> None:
    # Warmup so the first iteration doesn't dominate.
    time_query(client, sql_template, digests[:5], iters=20)
    timings = time_query(client, sql_template, digests, iters=BENCH_ITERS)
    report(label, timings)


def main() -> None:
    print(f"connecting to clickhouse at {CH_HOST}:{CH_PORT}")
    client = clickhouse_connect.get_client(
        host=CH_HOST, port=CH_PORT, username="default"
    )
    print(
        f"seeding {DB}.files with {BENCH_DIGESTS} digests "
        f"({BENCH_DIGESTS // 2} single-row, {BENCH_DIGESTS // 2} duplicate-PK)"
    )
    digests = setup_table(client)
    try:
        # Two splits so we can see the PR's impact on each shape separately.
        single_digests = digests[: BENCH_DIGESTS // 2]
        dup_digests = digests[BENCH_DIGESTS // 2 :]

        print()
        print("=== single-row PK (typical prod read) ===")
        bench_variant("master", client, QUERY_MASTER, single_digests)
        bench_variant("PR", client, QUERY_PR, single_digests)

        print()
        print("=== duplicate-PK (the race the PR fixes) ===")
        bench_variant("master", client, QUERY_MASTER, dup_digests)
        bench_variant("PR", client, QUERY_PR, dup_digests)
    finally:
        client.command(f"DROP DATABASE {DB}")


if __name__ == "__main__":
    main()
