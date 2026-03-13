#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "weave",
#     "rich>=14.0.0",
#     "viztracer>=1.0.3",
# ]
# ///
"""Benchmark client-side digest computation vs server-side (legacy) path.

Measures the performance difference between:
- Fast path: client computes digests locally, constructs refs immediately
- Fallback path: client defers digest computation to server, blocks on response

Usage:
    uv run scripts/benchmarks/client_side_digests.py
    uv run scripts/benchmarks/client_side_digests.py --iterations 5 --rows 100
    uv run scripts/benchmarks/client_side_digests.py --out_filetype csv
"""

from __future__ import annotations

import argparse
import csv
import os
import statistics
import time
from typing import Any

from rich.console import Console
from rich.table import Table

import weave

console = Console()


def _calc_stats(times: list[float]) -> dict[str, float]:
    if not times:
        return {"mean": 0, "median": 0, "std_dev": 0, "min": 0, "max": 0}
    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
        "min": min(times),
        "max": max(times),
    }


def _make_dataset_rows(n: int) -> list[dict[str, Any]]:
    """Generate n dataset rows with varying data shapes."""
    rows = []
    for i in range(n):
        rows.append(
            {
                "id": i,
                "question": f"What is {i} + {i}?",
                "expected": str(i + i),
                "metadata": {
                    "source": "benchmark",
                    "index": i,
                    "tags": [f"tag_{i % 5}"],
                },
            }
        )
    return rows


def _make_nested_object() -> dict[str, Any]:
    """Create a non-trivial nested object for publishing."""
    return {
        "config": {
            "model_name": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 1024,
            "system_prompt": "You are a helpful assistant." * 10,
        },
        "metadata": {
            "version": "1.0.0",
            "author": "benchmark",
            "tags": ["test", "benchmark", "perf"],
        },
    }


def benchmark_publish_dataset(
    project_name: str,
    n_rows: int,
    enable_client_digests: bool,
    tracer: Any | None = None,
) -> dict[str, float]:
    """Benchmark publishing a dataset.

    Returns dict with:
        - init_time: time to call weave.init()
        - publish_time: time from publish() call to ref available
        - finish_time: time for client.finish() (flush all background work)
        - total_time: init + publish + finish
    """
    rows = _make_dataset_rows(n_rows)

    # Init
    t0 = time.perf_counter()
    client = weave.init(
        project_name,
        settings={
            "print_call_link": False,
            "enable_client_side_digests": enable_client_digests,
        },
    )
    t_init = time.perf_counter()

    # Publish dataset (profiled region)
    ds = weave.Dataset(name="bench_dataset", rows=rows)
    if tracer:
        tracer.start()
    t_pub_start = time.perf_counter()
    ref = weave.publish(ds)
    t_pub_end = time.perf_counter()

    # Finish (flush background tasks)
    t_finish_start = time.perf_counter()
    client.finish()
    t_finish_end = time.perf_counter()
    if tracer:
        tracer.stop()

    init_time = t_init - t0
    publish_time = t_pub_end - t_pub_start
    finish_time = t_finish_end - t_finish_start
    total_time = t_finish_end - t0

    return {
        "init_time": init_time,
        "publish_time": publish_time,
        "finish_time": finish_time,
        "total_time": total_time,
    }


def benchmark_publish_objects(
    project_name: str,
    n_objects: int,
    enable_client_digests: bool,
    tracer: Any | None = None,
) -> dict[str, float]:
    """Benchmark publishing multiple individual objects.

    Returns dict with:
        - init_time: time to call weave.init()
        - publish_time: time to publish all objects
        - finish_time: time for client.finish()
        - total_time: init + publish + finish
    """
    objects = [_make_nested_object() for _ in range(n_objects)]

    # Init
    t0 = time.perf_counter()
    client = weave.init(
        project_name,
        settings={
            "print_call_link": False,
            "enable_client_side_digests": enable_client_digests,
        },
    )
    t_init = time.perf_counter()

    # Publish objects (profiled region)
    if tracer:
        tracer.start()
    t_pub_start = time.perf_counter()
    for i, obj in enumerate(objects):
        weave.publish(obj, name=f"bench_obj_{i}")
    t_pub_end = time.perf_counter()

    # Finish
    t_finish_start = time.perf_counter()
    client.finish()
    t_finish_end = time.perf_counter()
    if tracer:
        tracer.stop()

    init_time = t_init - t0
    publish_time = t_pub_end - t_pub_start
    finish_time = t_finish_end - t_finish_start
    total_time = t_finish_end - t0

    return {
        "init_time": init_time,
        "publish_time": publish_time,
        "finish_time": finish_time,
        "total_time": total_time,
    }


def run_comparison(
    iterations: int,
    n_rows: int,
    n_objects: int,
    profile: bool = False,
) -> dict[str, dict[str, list[float]]]:
    """Run the full benchmark comparison.

    Returns nested dict: results[scenario][metric] = [times...]
    where scenario is like "dataset_fast", "dataset_fallback", etc.
    """
    tracers: dict[str, Any] = {}
    if profile:
        from viztracer import VizTracer

    results: dict[str, dict[str, list[float]]] = {}
    scenarios = [
        ("dataset_fast", True, "dataset"),
        ("dataset_fallback", False, "dataset"),
        ("objects_fast", True, "objects"),
        ("objects_fallback", False, "objects"),
    ]

    for scenario_name, _enable_digests, _bench_type in scenarios:
        results[scenario_name] = {
            "init_time": [],
            "publish_time": [],
            "finish_time": [],
            "total_time": [],
        }
        if profile:
            tracers[scenario_name] = VizTracer(
                output_file=f"profile_{scenario_name}.json",
                tracer_entries=5_000_000,
                verbose=0,
            )

    for i in range(iterations):
        console.print(f"\n[bold]Iteration {i + 1}/{iterations}[/bold]")

        for scenario_name, enable_digests, bench_type in scenarios:
            path_label = "fast" if enable_digests else "fallback"
            project = f"bench_{bench_type}_{path_label}_{i}"
            tracer = tracers.get(scenario_name)

            if bench_type == "dataset":
                timings = benchmark_publish_dataset(
                    project,
                    n_rows,
                    enable_digests,
                    tracer=tracer,
                )
            else:
                timings = benchmark_publish_objects(
                    project,
                    n_objects,
                    enable_digests,
                    tracer=tracer,
                )

            for metric, value in timings.items():
                results[scenario_name][metric].append(value)

            console.print(
                f"  {scenario_name:25s}  "
                f"pub={timings['publish_time']:.3f}s  "
                f"finish={timings['finish_time']:.3f}s  "
                f"total={timings['total_time']:.3f}s"
            )

    # Save profile traces
    if profile:
        for scenario_name, tracer in tracers.items():
            tracer.save()
            console.print(f"  Profile saved: profile_{scenario_name}.json")

    return results


def create_comparison_table(
    all_stats: dict[str, dict[str, dict[str, float]]],
) -> Table:
    """Create a rich table comparing fast vs fallback path."""
    table = Table(title="Client-Side Digests Benchmark Results")

    table.add_column("Scenario", style="cyan", justify="left")
    table.add_column("Path", style="magenta", justify="left")
    table.add_column("Publish (mean)", style="green", justify="right")
    table.add_column("Finish (mean)", style="green", justify="right")
    table.add_column("Total (mean)", style="yellow", justify="right")
    table.add_column("Total (median)", style="yellow", justify="right")

    for scenario_name, stats in all_stats.items():
        bench_type = "Dataset" if "dataset" in scenario_name else "Objects"
        path = "Fast" if "fast" in scenario_name else "Fallback"

        table.add_row(
            bench_type,
            path,
            f"{stats['publish_time']['mean']:.3f}s",
            f"{stats['finish_time']['mean']:.3f}s",
            f"{stats['total_time']['mean']:.3f}s",
            f"{stats['total_time']['median']:.3f}s",
        )

    return table


def create_speedup_table(
    all_stats: dict[str, dict[str, dict[str, float]]],
) -> Table:
    """Create a table showing speedup of fast path over fallback."""
    table = Table(title="Speedup (Fast Path vs Fallback)")

    table.add_column("Scenario", style="cyan", justify="left")
    table.add_column("Metric", style="magenta", justify="left")
    table.add_column("Fast (mean)", style="green", justify="right")
    table.add_column("Fallback (mean)", style="yellow", justify="right")
    table.add_column("Speedup", style="bold red", justify="right")

    pairs = [
        ("Dataset", "dataset_fast", "dataset_fallback"),
        ("Objects", "objects_fast", "objects_fallback"),
    ]

    for label, fast_key, fallback_key in pairs:
        if fast_key not in all_stats or fallback_key not in all_stats:
            continue

        for metric in ["publish_time", "finish_time", "total_time"]:
            fast_mean = all_stats[fast_key][metric]["mean"]
            fallback_mean = all_stats[fallback_key][metric]["mean"]

            if fast_mean > 0:
                speedup = fallback_mean / fast_mean
                speedup_str = f"{speedup:.2f}x"
            else:
                speedup_str = "N/A"

            metric_label = metric.replace("_", " ").title()
            table.add_row(
                label,
                metric_label,
                f"{fast_mean:.3f}s",
                f"{fallback_mean:.3f}s",
                speedup_str,
            )

    return table


def write_results_to_csv(
    all_stats: dict[str, dict[str, dict[str, float]]],
    filename: str,
) -> None:
    """Write benchmark results to CSV."""
    headers = ["Scenario", "Path", "Metric", "Mean", "Median", "StdDev", "Min", "Max"]
    rows = []

    for scenario_name, stats in all_stats.items():
        bench_type = "dataset" if "dataset" in scenario_name else "objects"
        path = "fast" if "fast" in scenario_name else "fallback"

        for metric_name, metric_stats in stats.items():
            rows.append(
                [
                    bench_type,
                    path,
                    metric_name,
                    f"{metric_stats['mean']:.6f}",
                    f"{metric_stats['median']:.6f}",
                    f"{metric_stats['std_dev']:.6f}",
                    f"{metric_stats['min']:.6f}",
                    f"{metric_stats['max']:.6f}",
                ]
            )

    console.print(f"Writing results to {filename}...")
    with open(filename, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark client-side digest computation"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of iterations per scenario (default: 3)",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=50,
        help="Number of dataset rows (default: 50)",
    )
    parser.add_argument(
        "--objects",
        type=int,
        default=10,
        help="Number of objects to publish (default: 10)",
    )
    parser.add_argument(
        "--out_filetype",
        choices=["csv"],
        help="Output file type for results",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Enable viztracer profiling (saves .json trace files)",
    )
    args = parser.parse_args()

    console.print("[bold]Client-Side Digests Benchmark[/bold]")
    console.print(f"  Iterations: {args.iterations}")
    console.print(f"  Dataset rows: {args.rows}")
    console.print(f"  Objects: {args.objects}")
    console.print()

    results = run_comparison(
        args.iterations, args.rows, args.objects, profile=args.profile
    )

    # Calculate stats
    all_stats = {
        scenario: {metric: _calc_stats(times) for metric, times in metrics.items()}
        for scenario, metrics in results.items()
    }

    # Display
    console.print()
    console.print(create_comparison_table(all_stats))
    console.print()
    console.print(create_speedup_table(all_stats))

    if args.out_filetype == "csv":
        script_dir = os.path.dirname(os.path.abspath(__file__))
        csv_filename = os.path.join(script_dir, "client_side_digests_results.csv")
        write_results_to_csv(all_stats, csv_filename)


if __name__ == "__main__":
    main()
