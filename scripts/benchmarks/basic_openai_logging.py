"""Benchmark Weave overhead on OpenAI API calls."""

#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "openai==1.97.1",
#     "weave==0.51.56",
#     "rich==14.0.0",
# ]
# ///

import argparse
import csv
import os
import statistics
import time
import uuid

from openai import OpenAI
from rich.console import Console
from rich.table import Table

import weave

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


def warm_up_calls(num_warmup: int = 3) -> None:
    """Perform warm-up API calls to initialize network connections.

    Args:
        num_warmup: Number of warm-up calls to make.
    """
    for _ in range(num_warmup):
        try:
            make_openai_call()
        except Exception:
            # Ignore warm-up errors
            pass


def time_function_calls(func, iterations: int = 10, warmup: int = 3) -> list[float]:
    """Time function calls and return list of execution times.

    Args:
        func: Function to time.
        iterations: Number of iterations to run.
        warmup: Number of warm-up calls before timing.

    Returns:
        list[float]: List of execution times in seconds.
    """
    # Perform warm-up calls
    if warmup > 0:
        warm_up_calls(warmup)

    times = []
    for _ in range(iterations):
        start_time = time.perf_counter()
        func()
        end_time = time.perf_counter()
        times.append(end_time - start_time)
    return times


def calculate_stats(times: list[float]) -> dict[str, float]:
    """Calculate timing statistics.

    Args:
        times: List of execution times.

    Returns:
        dict[str, float]: Dictionary with statistical measures.
    """
    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
        "min": min(times),
        "max": max(times),
    }


def run_benchmark_without_weave(iterations: int, warmup: int = 3) -> list[float]:
    """Run benchmark with Weave disabled.

    Args:
        iterations: Number of iterations to run.
        warmup: Number of warm-up calls.

    Returns:
        list[float]: List of execution times.
    """
    console.print("Running without Weave...")
    # Use environment variable to completely disable Weave
    os.environ["WEAVE_DISABLED"] = "true"
    return time_function_calls(make_openai_call, iterations, warmup)


def run_benchmark_with_weave(iterations: int, warmup: int = 3) -> list[float]:
    """Run benchmark with Weave enabled.

    Args:
        iterations: Number of iterations to run.
        warmup: Number of warm-up calls.

    Returns:
        list[float]: List of execution times.
    """
    console.print("Running with Weave enabled...")
    # Remove the disable flag and initialize fresh
    if "WEAVE_DISABLED" in os.environ:
        del os.environ["WEAVE_DISABLED"]

    # Initialize Weave with minimal settings to reduce API calls
    weave.init(
        "benchmark_openai",
        settings={"print_call_link": False},
    )
    return time_function_calls(make_openai_call, iterations, warmup)


def run_multiple_rounds(
    iterations: int, rounds: int = 2, warmup: int = 3
) -> tuple[dict[str, float], dict[str, float]]:
    """Run multiple rounds of benchmarks with alternating order.

    Args:
        iterations: Number of iterations per round.
        rounds: Number of rounds to run.
        warmup: Number of warm-up calls per round.

    Returns:
        tuple: (with_weave_stats, without_weave_stats)
    """
    console.print(f"Running {rounds} rounds with alternating order...")

    with_weave_results = []
    without_weave_results = []

    for round_num in range(rounds):
        console.print(f"\n[bold]Round {round_num + 1}/{rounds}[/bold]")

        # Alternate the order: even rounds start with without_weave, odd rounds start with with_weave
        if round_num % 2 == 0:
            # Start with without_weave
            console.print("Order: Without Weave → With Weave")
            without_weave_times = run_benchmark_without_weave(iterations, warmup)
            time.sleep(1)  # Small delay between tests
            with_weave_times = run_benchmark_with_weave(iterations, warmup)
        else:
            # Start with with_weave
            console.print("Order: With Weave → Without Weave")
            with_weave_times = run_benchmark_with_weave(iterations, warmup)
            time.sleep(1)  # Small delay between tests
            without_weave_times = run_benchmark_without_weave(iterations, warmup)

        # Calculate stats for this round
        with_weave_stats = calculate_stats(with_weave_times)
        without_weave_stats = calculate_stats(without_weave_times)

        with_weave_results.append(with_weave_stats)
        without_weave_results.append(without_weave_stats)

    # Aggregate results across rounds
    def aggregate_stats(results_list):
        all_means = [r["mean"] for r in results_list]
        all_medians = [r["median"] for r in results_list]
        all_mins = [r["min"] for r in results_list]
        all_maxes = [r["max"] for r in results_list]

        return {
            "mean": statistics.mean(all_means),
            "median": statistics.median(all_medians),
            "std_dev": statistics.stdev(all_means) if len(all_means) > 1 else 0,
            "min": min(all_mins),
            "max": max(all_maxes),
        }

    with_weave_final = aggregate_stats(with_weave_results)
    without_weave_final = aggregate_stats(without_weave_results)

    return with_weave_final, without_weave_final


def write_results_to_csv(
    with_weave_stats: dict[str, float],
    without_weave_stats: dict[str, float],
    filename: str,
) -> None:
    """Write benchmark results to CSV file.

    Args:
        with_weave_stats: Statistics from Weave-enabled run.
        without_weave_stats: Statistics from Weave-disabled run.
        filename: Output CSV filename.
    """
    console.print(f"Writing results to {filename}...")

    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        # Write header
        writer.writerow(
            [
                "Metric",
                "With_Weave_Seconds",
                "Without_Weave_Seconds",
                "Overhead_Percent",
            ]
        )

        # Write data rows
        metrics = ["mean", "median", "std_dev", "min", "max"]
        metric_labels = ["Mean", "Median", "Std Dev", "Min", "Max"]

        for metric, label in zip(metrics, metric_labels):
            with_val = with_weave_stats[metric]
            without_val = without_weave_stats[metric]

            # Calculate overhead percentage
            if without_val > 0:
                overhead_pct = ((with_val - without_val) / without_val) * 100
            else:
                overhead_pct = 0

            writer.writerow(
                [label, f"{with_val:.6f}", f"{without_val:.6f}", f"{overhead_pct:.2f}"]
            )


def read_results_from_csv(filename: str) -> list[dict[str, str]]:
    """Read benchmark results from CSV file.

    Args:
        filename: Input CSV filename.

    Returns:
        list[dict[str, str]]: List of row dictionaries.
    """
    console.print(f"Reading results from {filename}...")

    results = []
    with open(filename, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            results.append(row)

    return results


def create_results_table_from_csv(csv_data: list[dict[str, str]]) -> Table:
    """Create a Rich table from CSV data.

    Args:
        csv_data: List of row dictionaries from CSV.

    Returns:
        Table: Rich table with comparison results.
    """
    table = Table(title="Weave Overhead Benchmark Results")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Without Weave", style="red", justify="right")
    table.add_column("With Weave", style="green", justify="right")
    table.add_column("Overhead", style="yellow", justify="right")

    for row in csv_data:
        metric = row["Metric"]
        with_val = float(row["With_Weave_Seconds"])
        without_val = float(row["Without_Weave_Seconds"])
        overhead_pct = float(row["Overhead_Percent"])

        # Format overhead display
        overhead_str = (
            f"+{overhead_pct:.1f}%" if overhead_pct > 0 else f"{overhead_pct:.1f}%"
        )

        table.add_row(metric, f"{without_val:.3f}s", f"{with_val:.3f}s", overhead_str)

    return table


def main():
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
        "--rounds",
        type=int,
        default=2,
        help="Number of rounds to run (default: 2)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=3,
        help="Number of warm-up calls before timing (default: 3)",
    )

    args = parser.parse_args()

    # Main orchestration mode
    console.print("[bold]Weave Overhead Benchmark[/bold]")
    console.print(
        f"Running {args.rounds} rounds of {args.iterations} iterations each with {args.warmup} warm-up calls..."
    )
    console.print("Test order will alternate between rounds to eliminate bias.\n")

    # Run multiple rounds with alternating order
    with_weave_stats, without_weave_stats = run_multiple_rounds(
        args.iterations, args.rounds, args.warmup
    )

    # Write results to CSV in the same directory as the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_filename = os.path.join(script_dir, "basic_openai_logging_results.csv")
    write_results_to_csv(with_weave_stats, without_weave_stats, csv_filename)

    # Read results back from CSV
    csv_data = read_results_from_csv(csv_filename)

    # Display results in a table
    console.print()
    table = create_results_table_from_csv(csv_data)
    console.print(table)

    # Show summary (calculate from CSV data)
    mean_row = next(row for row in csv_data if row["Metric"] == "Mean")
    mean_overhead = float(mean_row["Overhead_Percent"])
    console.print(
        f"\n[bold]Summary:[/bold] Weave adds an average overhead of [yellow]{mean_overhead:.1f}%[/yellow] per API call"
    )


if __name__ == "__main__":
    main()
