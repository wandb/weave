#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "clickhouse-connect==0.11.0",
#     "rich==14.0.0",
# ]
# ///
"""Benchmark ClickHouse client performance: sync baseline and (future) async.

Measures latency and throughput for the core I/O patterns used by the Weave
trace server — simple queries, parameterized queries, batch inserts, streaming
reads, and concurrent workloads.

Run against a local ClickHouse (default localhost:8123):

    uv run scripts/benchmarks/clickhouse_client.py

Override host/port:

    uv run scripts/benchmarks/clickhouse_client.py --host ch.example.com --port 8443

When clickhouse-connect ships a stable async client (>= 0.12.0), add
``clickhouse-connect[async]`` to the dependencies above and pass ``--async``
to compare sync vs async side-by-side.

    uv run scripts/benchmarks/clickhouse_client.py --async
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.client import Client
from rich.console import Console
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent))
from utils import utils

console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DB_NAME = "weave_benchmark"
TABLE_NAME = "bench_calls"

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id          String,
    project_id  String,
    op_name     String,
    started_at  DateTime64(6),
    ended_at    Nullable(DateTime64(6)),
    status      String DEFAULT 'running',
    payload     String DEFAULT ''
) ENGINE = MergeTree()
ORDER BY (project_id, id)
"""

DROP_TABLE_SQL = f"DROP TABLE IF EXISTS {TABLE_NAME}"


def timed(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, float]:
    """Run *fn* and return (result, elapsed_seconds)."""
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - start


def make_insert_rows(n: int) -> list[list[Any]]:
    """Generate *n* fake call rows."""
    now = "2025-01-01 00:00:00.000000"
    return [
        [str(uuid.uuid4()), "proj_bench", f"op_{i}", now, now, "success", f'{{"i": {i}}}']
        for i in range(n)
    ]


INSERT_COLUMNS = ["id", "project_id", "op_name", "started_at", "ended_at", "status", "payload"]


# ---------------------------------------------------------------------------
# Benchmark scenarios
# ---------------------------------------------------------------------------


def bench_simple_query(client: Client, iterations: int) -> list[float]:
    """SELECT 1 — measures round-trip latency."""
    times = []
    for _ in range(iterations):
        _, elapsed = timed(client.query, "SELECT 1")
        times.append(elapsed)
    return times


def bench_parameterized_query(client: Client, iterations: int) -> list[float]:
    """Parameterized SELECT — typical read path."""
    # Insert a few rows first
    client.insert(TABLE_NAME, data=make_insert_rows(10), column_names=INSERT_COLUMNS)
    times = []
    for _ in range(iterations):
        _, elapsed = timed(
            client.query,
            f"SELECT id, op_name, status FROM {TABLE_NAME} WHERE project_id = {{pid:String}} LIMIT 5",
            parameters={"pid": "proj_bench"},
        )
        times.append(elapsed)
    return times


def bench_batch_insert(client: Client, iterations: int, batch_size: int = 100) -> list[float]:
    """Batch INSERT — the primary write path."""
    times = []
    for _ in range(iterations):
        rows = make_insert_rows(batch_size)
        _, elapsed = timed(
            client.insert,
            TABLE_NAME,
            data=rows,
            column_names=INSERT_COLUMNS,
        )
        times.append(elapsed)
    return times


def bench_large_insert(client: Client, iterations: int, batch_size: int = 5000) -> list[float]:
    """Large batch INSERT — stress test."""
    times = []
    for _ in range(iterations):
        rows = make_insert_rows(batch_size)
        _, elapsed = timed(
            client.insert,
            TABLE_NAME,
            data=rows,
            column_names=INSERT_COLUMNS,
        )
        times.append(elapsed)
    return times


def bench_streaming_query(client: Client, iterations: int) -> list[float]:
    """Streaming SELECT — used for calls_query_stream."""
    # Ensure there's data to stream
    client.insert(TABLE_NAME, data=make_insert_rows(500), column_names=INSERT_COLUMNS)

    times = []
    for _ in range(iterations):

        def stream_all() -> int:
            count = 0
            with client.query_rows_stream(
                f"SELECT * FROM {TABLE_NAME} WHERE project_id = {{pid:String}}",
                parameters={"pid": "proj_bench"},
            ) as stream:
                for _ in stream:
                    count += 1
            return count

        _, elapsed = timed(stream_all)
        times.append(elapsed)
    return times


def bench_concurrent_queries(
    client: Client, iterations: int, concurrency: int = 8
) -> list[float]:
    """Concurrent SELECTs from a thread pool — simulates production load."""

    def single_query() -> float:
        _, elapsed = timed(
            client.query,
            f"SELECT count() FROM {TABLE_NAME} WHERE project_id = {{pid:String}}",
            parameters={"pid": "proj_bench"},
        )
        return elapsed

    all_times: list[float] = []
    for _ in range(iterations):
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(single_query) for _ in range(concurrency)]
            batch_times = [f.result() for f in as_completed(futures)]
        all_times.extend(batch_times)
    return all_times


# ---------------------------------------------------------------------------
# Async benchmarks (enabled when clickhouse-connect[async] >= 0.12.0)
# ---------------------------------------------------------------------------


def has_async_client() -> bool:
    """Check if the native async client is available."""
    return hasattr(clickhouse_connect, "get_async_client")


async def _run_async_benchmarks(
    host: str, port: int, user: str, password: str, iterations: int
) -> dict[str, list[float]]:
    """Run the async counterparts of key benchmarks."""
    import asyncio

    async with await clickhouse_connect.get_async_client(
        host=host, port=port, user=user, password=password, database=DB_NAME
    ) as client:
        results: dict[str, list[float]] = {}

        # Simple query
        times: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            await client.query("SELECT 1")
            times.append(time.perf_counter() - start)
        results["async_simple_query"] = times

        # Parameterized query
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            await client.query(
                f"SELECT id, op_name, status FROM {TABLE_NAME} WHERE project_id = {{pid:String}} LIMIT 5",
                parameters={"pid": "proj_bench"},
            )
            times.append(time.perf_counter() - start)
        results["async_param_query"] = times

        # Batch insert
        times = []
        for _ in range(iterations):
            rows = make_insert_rows(100)
            start = time.perf_counter()
            await client.insert(TABLE_NAME, data=rows, column_names=INSERT_COLUMNS)
            times.append(time.perf_counter() - start)
        results["async_batch_insert_100"] = times

        # Concurrent queries (async gather instead of threads)
        concurrency = 8
        all_times: list[float] = []
        for _ in range(iterations):
            async def single() -> float:
                start = time.perf_counter()
                await client.query(
                    f"SELECT count() FROM {TABLE_NAME} WHERE project_id = {{pid:String}}",
                    parameters={"pid": "proj_bench"},
                )
                return time.perf_counter() - start

            batch_times = await asyncio.gather(*(single() for _ in range(concurrency)))
            all_times.extend(batch_times)
        results["async_concurrent_8"] = all_times

        return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def format_stats(times: list[float]) -> dict[str, str]:
    """Format timing stats for display."""
    stats = utils.calculate_stats(times)
    return {
        "mean": utils.format_seconds(stats["mean"]),
        "median": utils.format_seconds(stats["median"]),
        "std": utils.format_seconds(stats["std_dev"]),
        "min": utils.format_seconds(stats["min"]),
        "max": utils.format_seconds(stats["max"]),
        "n": str(len(times)),
    }


def build_results_table(
    all_results: dict[str, list[float]], title: str
) -> Table:
    """Build a rich Table from benchmark results."""
    table = Table(title=title, show_lines=True)
    table.add_column("Benchmark", style="cyan", no_wrap=True)
    table.add_column("n", justify="right")
    table.add_column("Mean", justify="right", style="green")
    table.add_column("Median", justify="right", style="green")
    table.add_column("Std Dev", justify="right")
    table.add_column("Min", justify="right")
    table.add_column("Max", justify="right")

    for name, times in all_results.items():
        s = format_stats(times)
        table.add_row(name, s["n"], s["mean"], s["median"], s["std"], s["min"], s["max"])

    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="localhost", help="ClickHouse host (default: localhost)")
    parser.add_argument("--port", type=int, default=8123, help="ClickHouse HTTP port (default: 8123)")
    parser.add_argument("--user", default="default")
    parser.add_argument("--password", default="")
    parser.add_argument("--iterations", type=int, default=50, help="Iterations per benchmark (default: 50)")
    parser.add_argument("--async", dest="run_async", action="store_true", help="Also run async benchmarks (requires clickhouse-connect[async] >= 0.12.0)")
    args = parser.parse_args()

    console.rule("[bold]ClickHouse Client Benchmark[/bold]")
    console.print(f"Host: {args.host}:{args.port}  Iterations: {args.iterations}")

    # --- setup ---
    client = clickhouse_connect.get_client(
        host=args.host, port=args.port, user=args.user, password=args.password
    )
    client.command(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    client.database = DB_NAME
    client.command(DROP_TABLE_SQL)
    client.command(CREATE_TABLE_SQL)

    # --- sync benchmarks ---
    sync_results: dict[str, list[float]] = {}
    benchmarks = [
        ("simple_query", bench_simple_query),
        ("param_query", bench_parameterized_query),
        ("batch_insert_100", lambda c, n: bench_batch_insert(c, n, batch_size=100)),
        ("large_insert_5000", lambda c, n: bench_large_insert(c, n, batch_size=5000)),
        ("streaming_query", bench_streaming_query),
        ("concurrent_8", bench_concurrent_queries),
    ]

    for name, fn in benchmarks:
        console.print(f"  Running [cyan]{name}[/cyan] ...", end=" ")
        times = fn(client, args.iterations)
        sync_results[name] = times
        stats = utils.calculate_stats(times)
        console.print(f"[green]{utils.format_seconds(stats['mean'])}[/green] mean")

    console.print()
    console.print(build_results_table(sync_results, "Sync Client Results"))

    # --- async benchmarks ---
    if args.run_async:
        if not has_async_client():
            console.print(
                "\n[red]Async client not available.[/red] "
                "Install clickhouse-connect[async] >= 0.12.0 to enable async benchmarks."
            )
            sys.exit(1)

        import asyncio

        console.print("\n[bold]Running async benchmarks...[/bold]")
        async_results = asyncio.run(
            _run_async_benchmarks(args.host, args.port, args.user, args.password, args.iterations)
        )
        console.print(build_results_table(async_results, "Async Client Results"))

        # --- comparison table ---
        comparison = Table(title="Sync vs Async Comparison", show_lines=True)
        comparison.add_column("Benchmark", style="cyan")
        comparison.add_column("Sync Mean", justify="right")
        comparison.add_column("Async Mean", justify="right")
        comparison.add_column("Speedup", justify="right", style="bold")

        pairs = [
            ("simple_query", "async_simple_query"),
            ("param_query", "async_param_query"),
            ("batch_insert_100", "async_batch_insert_100"),
            ("concurrent_8", "async_concurrent_8"),
        ]
        for sync_name, async_name in pairs:
            if sync_name in sync_results and async_name in async_results:
                s_mean = statistics.mean(sync_results[sync_name])
                a_mean = statistics.mean(async_results[async_name])
                speedup = s_mean / a_mean if a_mean > 0 else float("inf")
                comparison.add_row(
                    sync_name,
                    utils.format_seconds(s_mean),
                    utils.format_seconds(a_mean),
                    f"{speedup:.2f}x",
                )
        console.print()
        console.print(comparison)

    # --- cleanup ---
    client.command(DROP_TABLE_SQL)
    console.print("\n[dim]Cleanup complete.[/dim]")


if __name__ == "__main__":
    main()
