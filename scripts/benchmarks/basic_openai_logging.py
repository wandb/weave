#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "openai==1.97.1",
#     "weave==0.51.56",
#     "rich==14.0.0",
# ]
# ///
"""Benchmark Weave overhead on OpenAI API calls."""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from openai import OpenAI
from rich.console import Console
from rich.table import Table

import weave

# This is unfortunate, but needed to make the script runnable both as a uv
# script and as a helper in the test suite
sys.path.insert(0, str(Path(__file__).parent))
from utils import utils

console = Console()


def make_openai_call() -> str:
    """Make a simple OpenAI API call.

    Returns:
        str: The response content.
    """
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                # UUID added to avoid caching
                "content": f"Tell me a random greeting. {uuid.uuid4()}",
            }
        ],
        max_tokens=100,
        temperature=0,
    )
    return response.choices[0].message.content or ""


def time_function_calls(
    func: Callable[[], Any], iterations: int, warmup: int = 3
) -> list[float]:
    """Time function calls and return list of execution times.

    Args:
        func: Function to time.
        iterations: Number of iterations to run.
        warmup: Number of warm-up calls before timing.

    Returns:
        list[float]: List of execution times in seconds.
    """
    # Perform warm-up calls
    for _ in range(warmup):
        try:
            func()
        except Exception:
            pass

    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return times


def run_benchmark_without_weave(iterations: int, warmup: int = 3) -> dict[str, float]:
    """Run benchmark with Weave disabled."""
    console.print("Running without Weave...")
    os.environ["WEAVE_DISABLED"] = "true"
    times = time_function_calls(make_openai_call, iterations, warmup)
    return utils.calculate_stats(times)


def run_benchmark_with_weave(iterations: int, warmup: int = 3) -> dict[str, float]:
    """Run benchmark with Weave enabled."""
    console.print("Running with Weave enabled...")
    if "WEAVE_DISABLED" in os.environ:
        del os.environ["WEAVE_DISABLED"]

    weave.init("benchmark_openai", settings={"print_call_link": False})
    times = time_function_calls(make_openai_call, iterations, warmup)
    return utils.calculate_stats(times)


def run_multiple_rounds(
    iterations: int, rounds: int = 2, warmup: int = 3
) -> tuple[dict[str, float], dict[str, float]]:
    """Run multiple rounds of benchmarks with alternating order."""
    console.print(f"Running {rounds} rounds with alternating order...")

    with_weave_means = []
    without_weave_means = []

    for round_num in range(rounds):
        console.print(f"\n[bold]Round {round_num + 1}/{rounds}[/bold]")

        # Alternate order each round
        if round_num % 2 == 0:
            console.print("Order: Without Weave → With Weave")
            without_stats = run_benchmark_without_weave(iterations, warmup)
            time.sleep(1)
            with_stats = run_benchmark_with_weave(iterations, warmup)
        else:
            console.print("Order: With Weave → Without Weave")
            with_stats = run_benchmark_with_weave(iterations, warmup)
            time.sleep(1)
            without_stats = run_benchmark_without_weave(iterations, warmup)

        with_weave_means.append(with_stats["mean"])
        without_weave_means.append(without_stats["mean"])

    # Return aggregated stats
    return utils.calculate_stats(with_weave_means), utils.calculate_stats(
        without_weave_means
    )


def write_results_to_csv(
    with_weave_stats: dict[str, float],
    without_weave_stats: dict[str, float],
    filename: str,
) -> None:
    """Write benchmark results to CSV file."""
    headers = [
        "Metric",
        "With_Weave_Seconds",
        "Without_Weave_Seconds",
        "Overhead_Percent",
    ]
    rows = []

    for metric, label in [
        ("mean", "Mean"),
        ("median", "Median"),
        ("std_dev", "Std Dev"),
        ("min", "Min"),
        ("max", "Max"),
    ]:
        with_val = with_weave_stats[metric]
        without_val = without_weave_stats[metric]
        overhead_pct = (
            ((with_val - without_val) / without_val) * 100 if without_val > 0 else 0
        )
        rows.append(
            [label, f"{with_val:.6f}", f"{without_val:.6f}", f"{overhead_pct:.2f}"]
        )

    utils.write_csv_with_headers(filename, headers, rows)


def create_results_table(
    with_weave_stats: dict[str, float] | None = None,
    without_weave_stats: dict[str, float] | None = None,
    csv_data: list[dict[str, str]] | None = None,
) -> Table:
    """Create a Rich table from either stats or CSV data."""
    headers = ["Metric", "Without Weave", "With Weave", "Overhead"]
    column_styles = ["cyan", "red", "green", "yellow"]
    column_justifications = ["left", "right", "right", "right"]
    rows = []

    if csv_data:
        # Create from CSV data
        for row in csv_data:
            overhead_pct = float(row["Overhead_Percent"])
            rows.append(
                [
                    row["Metric"],
                    utils.format_seconds(float(row["Without_Weave_Seconds"])),
                    utils.format_seconds(float(row["With_Weave_Seconds"])),
                    utils.format_percentage(overhead_pct),
                ]
            )
    else:
        # Create from stats
        if with_weave_stats is None or without_weave_stats is None:
            raise ValueError(
                "with_weave_stats and without_weave_stats must be provided when csv_data is None"
            )

        for metric, label in [
            ("mean", "Mean"),
            ("median", "Median"),
            ("std_dev", "Std Dev"),
            ("min", "Min"),
            ("max", "Max"),
        ]:
            with_val = with_weave_stats[metric]
            without_val = without_weave_stats[metric]
            overhead_pct = (
                ((with_val - without_val) / without_val) * 100 if without_val > 0 else 0
            )

            rows.append(
                [
                    label,
                    utils.format_seconds(without_val),
                    utils.format_seconds(with_val),
                    utils.format_percentage(overhead_pct),
                ]
            )

    return utils.create_basic_table(
        "Weave Overhead Benchmark Results",
        headers,
        rows,
        column_styles,
        column_justifications,
    )


def main() -> None:
    """Benchmark OpenAI calls with and without Weave logging."""
    parser = argparse.ArgumentParser(
        description="Benchmark Weave overhead on OpenAI calls"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of API calls to make per round (default: 10)",
    )
    parser.add_argument(
        "--rounds", type=int, default=2, help="Number of rounds to run (default: 2)"
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=3,
        help="Number of warm-up calls before timing (default: 3)",
    )
    parser.add_argument(
        "--out_filetype", choices=["csv"], help="Output file type for results (csv)"
    )
    parser.add_argument(
        "--from_file",
        type=str,
        help="Read results from existing file instead of running benchmark",
    )

    args = parser.parse_args()

    if args.from_file:
        # Read and display results from file
        console.print(f"[bold]Reading results from: {args.from_file}[/bold]\n")
        if not os.path.exists(args.from_file):
            console.print(f"[red]Error: File {args.from_file} does not exist[/red]")
            return

        csv_data = utils.read_results_from_csv(args.from_file)
        table = create_results_table(csv_data=csv_data)
        console.print()
        console.print(table)

        mean_row = next(row for row in csv_data if row["Metric"] == "Mean")
        mean_overhead = float(mean_row["Overhead_Percent"])
        console.print(
            f"\n[bold]Summary:[/bold] Weave adds an average overhead of [yellow]{utils.format_percentage(mean_overhead)}[/yellow] per API call"
        )
        return

    # Run benchmark
    console.print("[bold]Weave Overhead Benchmark[/bold]")
    console.print(
        f"Running {args.rounds} rounds of {args.iterations} iterations each with {args.warmup} warm-up calls..."
    )
    console.print("Test order will alternate between rounds to eliminate bias.\n")

    with_weave_stats, without_weave_stats = run_multiple_rounds(
        args.iterations, args.rounds, args.warmup
    )

    if args.out_filetype == "csv":
        # Write to CSV and display from CSV
        script_dir = utils.get_script_dir_path(__file__)
        csv_filename = os.path.join(script_dir, "basic_openai_logging_results.csv")
        write_results_to_csv(with_weave_stats, without_weave_stats, csv_filename)

        csv_data = utils.read_results_from_csv(csv_filename)
        table = create_results_table(csv_data=csv_data)
        console.print()
        console.print(table)

        mean_row = next(row for row in csv_data if row["Metric"] == "Mean")
        mean_overhead = float(mean_row["Overhead_Percent"])
    else:
        # Display directly from stats
        table = create_results_table(with_weave_stats, without_weave_stats)
        console.print()
        console.print(table)

        mean_overhead = (
            (
                (with_weave_stats["mean"] - without_weave_stats["mean"])
                / without_weave_stats["mean"]
            )
            * 100
            if without_weave_stats["mean"] > 0
            else 0
        )

    console.print(
        f"\n[bold]Summary:[/bold] Weave adds an average overhead of [yellow]{utils.format_percentage(mean_overhead)}[/yellow] per API call"
    )


if __name__ == "__main__":
    main()
