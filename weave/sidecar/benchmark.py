#!/usr/bin/env python3
"""Benchmark script comparing Weave tracing with and without the Go sidecar.

Usage:
    # First, build and start the sidecar in another terminal:
    # cd weave/sidecar && go build -o weave-sidecar . && ./weave-sidecar --backend https://trace.wandb.ai

    # Run benchmark without sidecar:
    python benchmark.py --project your-project --ops 1000

    # Run benchmark with sidecar:
    WEAVE_USE_SIDECAR=true python benchmark.py --project your-project --ops 1000

    # Run both and compare:
    python benchmark.py --project your-project --ops 1000 --compare
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass


@dataclass
class BenchmarkResult:
    """Results from a benchmark run."""

    name: str
    num_ops: int
    total_time: float
    ops_per_second: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float

    def __str__(self) -> str:
        return f"""
{self.name}
{'=' * len(self.name)}
  Operations:      {self.num_ops:,}
  Total time:      {self.total_time:.2f}s
  Throughput:      {self.ops_per_second:,.0f} ops/sec
  Avg latency:     {self.avg_latency_ms:.3f} ms
  Min latency:     {self.min_latency_ms:.3f} ms
  Max latency:     {self.max_latency_ms:.3f} ms
"""


def run_benchmark(project: str, num_ops: int, use_sidecar: bool) -> BenchmarkResult:
    """Run the benchmark with the specified configuration."""
    import weave
    from weave.trace.context import weave_client_context

    # Initialize weave
    weave.init(project)
    client = weave_client_context.get_weave_client()

    # Define a simple traced operation
    @weave.op
    def traced_operation(x: int) -> int:
        return x * 2

    # Warm up
    for i in range(10):
        traced_operation(i)

    # Flush warmup data: first Python-side queues, then sidecar if enabled
    if client:
        client.flush()
        if use_sidecar and hasattr(client.server, "flush"):
            client.server.flush()

    # Run benchmark
    latencies = []
    start_total = time.perf_counter()

    for i in range(num_ops):
        start = time.perf_counter()
        traced_operation(i)
        end = time.perf_counter()
        latencies.append((end - start) * 1000)  # Convert to ms

    # Flush all data and include flush time in total:
    # 1. Flush Python-side async batch processor (always)
    # 2. Flush sidecar to wait for HTTP requests to complete (if enabled)
    if client:
        client.flush()
        if use_sidecar and hasattr(client.server, "flush"):
            client.server.flush()

    end_total = time.perf_counter()
    total_time = end_total - start_total

    # Clean up
    weave.finish()

    name = "With Go Sidecar" if use_sidecar else "Without Sidecar (Python only)"

    return BenchmarkResult(
        name=name,
        num_ops=num_ops,
        total_time=total_time,
        ops_per_second=num_ops / total_time,
        avg_latency_ms=sum(latencies) / len(latencies),
        min_latency_ms=min(latencies),
        max_latency_ms=max(latencies),
    )


def run_subprocess_benchmark(
    project: str, num_ops: int, use_sidecar: bool
) -> BenchmarkResult:
    """Run benchmark in a subprocess to ensure clean state."""
    env = os.environ.copy()
    # Suppress call link output for cleaner benchmark results
    env["WEAVE_PRINT_CALL_LINK"] = "false"
    if use_sidecar:
        env["WEAVE_USE_SIDECAR"] = "true"
    else:
        env.pop("WEAVE_USE_SIDECAR", None)

    # Run this script in benchmark-only mode
    result = subprocess.run(
        [
            sys.executable,
            __file__,
            "--project",
            project,
            "--ops",
            str(num_ops),
            "--run-only",
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Subprocess failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Parse output
    lines = result.stdout.strip().split("\n")
    data = {}
    for line in lines:
        if "=" in line:
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()

    name = "With Go Sidecar" if use_sidecar else "Without Sidecar (Python only)"

    return BenchmarkResult(
        name=name,
        num_ops=int(data["num_ops"]),
        total_time=float(data["total_time"]),
        ops_per_second=float(data["ops_per_second"]),
        avg_latency_ms=float(data["avg_latency_ms"]),
        min_latency_ms=float(data["min_latency_ms"]),
        max_latency_ms=float(data["max_latency_ms"]),
    )


def print_comparison(without_sidecar: BenchmarkResult, with_sidecar: BenchmarkResult) -> None:
    """Print a comparison of the two benchmark results."""
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)

    throughput_improvement = with_sidecar.ops_per_second / without_sidecar.ops_per_second
    latency_improvement = without_sidecar.avg_latency_ms / with_sidecar.avg_latency_ms

    print(f"""
Throughput:
  Without sidecar: {without_sidecar.ops_per_second:,.0f} ops/sec
  With sidecar:    {with_sidecar.ops_per_second:,.0f} ops/sec
  Improvement:     {throughput_improvement:.1f}x

Average Latency:
  Without sidecar: {without_sidecar.avg_latency_ms:.3f} ms
  With sidecar:    {with_sidecar.avg_latency_ms:.3f} ms
  Improvement:     {latency_improvement:.1f}x
""")


def check_sidecar_running() -> bool:
    """Check if the sidecar socket exists."""
    socket_path = os.environ.get("WEAVE_SIDECAR_SOCKET", "/tmp/weave_sidecar.sock")
    return os.path.exists(socket_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark Weave tracing with and without Go sidecar"
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Weave project name (e.g., 'entity/project' or 'project')",
    )
    parser.add_argument(
        "--ops",
        type=int,
        default=1000,
        help="Number of operations to run (default: 1000)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run both with and without sidecar and compare",
    )
    parser.add_argument(
        "--run-only",
        action="store_true",
        help="Internal flag: just run benchmark and output raw results",
    )

    args = parser.parse_args()

    if args.run_only:
        # Internal mode: just run and output parseable results
        use_sidecar = os.environ.get("WEAVE_USE_SIDECAR", "").lower() == "true"
        result = run_benchmark(args.project, args.ops, use_sidecar)
        print(f"num_ops={result.num_ops}")
        print(f"total_time={result.total_time}")
        print(f"ops_per_second={result.ops_per_second}")
        print(f"avg_latency_ms={result.avg_latency_ms}")
        print(f"min_latency_ms={result.min_latency_ms}")
        print(f"max_latency_ms={result.max_latency_ms}")
        return

    if args.compare:
        print("Running benchmark comparison...")
        print(f"Project: {args.project}")
        print(f"Operations: {args.ops:,}")

        # Check if sidecar is running
        if not check_sidecar_running():
            print(
                "\nWARNING: Sidecar socket not found. Make sure to start the sidecar:"
            )
            print("  cd weave/sidecar")
            print("  go build -o weave-sidecar .")
            print("  ./weave-sidecar --backend https://trace.wandb.ai")
            print()

        print("\n--- Running without sidecar ---")
        without_result = run_subprocess_benchmark(args.project, args.ops, use_sidecar=False)
        print(without_result)

        print("\n--- Running with sidecar ---")
        with_result = run_subprocess_benchmark(args.project, args.ops, use_sidecar=True)
        print(with_result)

        print_comparison(without_result, with_result)
    else:
        # Single run
        use_sidecar = os.environ.get("WEAVE_USE_SIDECAR", "").lower() == "true"

        if use_sidecar and not check_sidecar_running():
            print("ERROR: WEAVE_USE_SIDECAR is set but sidecar socket not found.")
            print("Start the sidecar first:")
            print("  cd weave/sidecar")
            print("  go build -o weave-sidecar .")
            print("  ./weave-sidecar --backend https://trace.wandb.ai")
            sys.exit(1)

        print(f"Running benchmark {'with' if use_sidecar else 'without'} sidecar...")
        print(f"Project: {args.project}")
        print(f"Operations: {args.ops:,}")

        result = run_benchmark(args.project, args.ops, use_sidecar)
        print(result)


if __name__ == "__main__":
    main()
