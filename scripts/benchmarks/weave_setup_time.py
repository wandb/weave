#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "weave==0.51.56",
#     "rich==14.0.0",
# ]
# ///
"""Benchmark Weave import and initialization time."""

import argparse
import os
import subprocess
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

# This is unfortunate, but needed to make the script runnable both as a uv
# script and as a helper in the test suite
sys.path.insert(0, str(Path(__file__).parent))
from utils import utils

console = Console()


def _run_timing_script(
    script_content: str,
    test_name: str,
    parser_func: Callable[[str], Any],
) -> Any:
    """Run a timing script in a fresh process and parse the output.

    Args:
        script_content (str): The Python script content to execute.
        test_name (str): A name for the test (used in temp file naming and error messages).
        parser_func: Function to parse the stdout and return the desired result.

    Returns:
        The result from parser_func, or appropriate default on failure.
    """
    # Write to a temporary file
    temp_file = f"temp_{test_name}_{uuid.uuid4().hex[:8]}.py"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(script_content)

        # Run in a fresh Python process
        result = subprocess.run(
            [sys.executable, temp_file],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode == 0:
            return parser_func(result.stdout.strip())
        else:
            console.print(
                f"[red]{test_name.title()} test failed: {result.stderr}[/red]"
            )
            return parser_func("")  # Let parser_func handle the error case
    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)


def time_weave_import() -> float:
    """Time the import of weave module in a fresh process.

    Returns:
        float: Time taken to import weave in seconds.
    """
    # Create a temporary script to time weave import in isolation
    temp_script = """
import time
start_time = time.perf_counter()
import weave
end_time = time.perf_counter()
print(end_time - start_time)
"""

    def parse_import_time(output: str) -> float:
        if not output:
            return 0.0
        return float(output)

    return _run_timing_script(temp_script, "import", parse_import_time)


def time_total_weave_setup() -> tuple[float, float]:
    """Time both import and init of weave in a fresh process (complete setup).

    Returns:
        tuple[float, float]: (import_time, init_time) in seconds.
    """
    # Create a temporary script to time both import and init
    temp_script = f"""
import time
import sys

# Time import
import_start = time.perf_counter()
import weave
import_end = time.perf_counter()
import_time = import_end - import_start

# Time init
init_start = time.perf_counter()
weave.init(
    "benchmark_init_{uuid.uuid4().hex[:8]}",
    settings={{"print_call_link": False}},
)
init_end = time.perf_counter()
init_time = init_end - init_start

print(f"{{import_time}},{{init_time}}")
"""

    def parse_setup_times(output: str) -> tuple[float, float]:
        if not output:
            return 0.0, 0.0
        import_time, init_time = map(float, output.split(","))
        return import_time, init_time

    return _run_timing_script(temp_script, "full", parse_setup_times)


def run_benchmark_iterations(iterations: int) -> dict[str, list[float]]:
    """Run multiple iterations of weave setup timing.

    Args:
        iterations: Number of iterations to run.

    Returns:
        dict[str, list[float]]: Dictionary with timing results for import, init, and total.
    """
    console.print(f"Running {iterations} iterations of weave setup timing...")

    import_times = []
    init_times = []
    total_times = []

    for i in range(iterations):
        console.print(f"Iteration {i + 1}/{iterations}", end="")

        # Get timing for this iteration
        import_time, init_time = time_total_weave_setup()
        total_time = import_time + init_time

        import_times.append(import_time)
        init_times.append(init_time)
        total_times.append(total_time)

        console.print(
            f" - Import: {import_time:.3f}s, Init: {init_time:.3f}s, Total: {total_time:.3f}s"
        )

    return {"import": import_times, "init": init_times, "total": total_times}


def write_results_to_csv(results: dict[str, list[float]], filename: str) -> None:
    """Write benchmark results to CSV file.

    Args:
        results: Dictionary with timing results.
        filename: Output CSV filename.
    """
    # Calculate stats for each timing type
    stats = {
        timing_type: utils.calculate_stats(times)
        for timing_type, times in results.items()
    }

    # Prepare CSV data
    headers = ["Timing_Type", "Metric", "Value_Seconds"]
    rows = []

    metrics = ["mean", "median", "std_dev", "min", "max"]
    metric_labels = ["Mean", "Median", "Std Dev", "Min", "Max"]

    for timing_type in ["import", "init", "total"]:
        for metric, label in zip(metrics, metric_labels, strict=False):
            value = stats[timing_type][metric]
            rows.append([timing_type.title(), label, f"{value:.6f}"])

    utils.write_csv_with_headers(filename, headers, rows)


def create_results_table(stats: dict[str, dict[str, float]]) -> Table:
    """Create a Rich table from timing statistics.

    Args:
        stats: Dictionary with timing statistics for import, init, and total.

    Returns:
        Rich table with timing results.
    """
    headers = ["Component", "Metric", "Time (seconds)"]
    column_styles = ["cyan", "magenta", "green"]
    column_justifications = ["left", "left", "right"]

    rows = []
    metrics = ["mean", "median", "std_dev", "min", "max"]
    metric_labels = ["Mean", "Median", "Std Dev", "Min", "Max"]

    for timing_type in ["import", "init", "total"]:
        for metric, label in zip(metrics, metric_labels, strict=False):
            value = stats[timing_type][metric]
            rows.append([timing_type.title(), label, utils.format_seconds(value)])

    return utils.create_basic_table(
        "Weave Setup Timing Results",
        headers,
        rows,
        column_styles,
        column_justifications,
    )


def display_summary(stats: dict[str, dict[str, float]]) -> None:
    """Display summary statistics.

    Args:
        stats: Dictionary with timing statistics.
    """
    console.print("\n[bold]Summary:[/bold]")
    console.print(
        f"  • Import time: [yellow]{utils.format_seconds(stats['import']['mean'])}[/yellow]"
    )
    console.print(
        f"  • Init time: [yellow]{utils.format_seconds(stats['init']['mean'])}[/yellow]"
    )
    console.print(
        f"  • Total time: [yellow]{utils.format_seconds(stats['total']['mean'])}[/yellow]"
    )


def get_stats_from_csv(csv_data: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    """Extract statistics from CSV data.

    Args:
        csv_data: List of row dictionaries from CSV.

    Returns:
        Dictionary with timing statistics.
    """
    stats: dict[str, dict[str, float]] = {"import": {}, "init": {}, "total": {}}

    for row in csv_data:
        timing_type = row["Timing_Type"].lower()
        metric = row["Metric"].lower().replace(" ", "_")
        if timing_type in stats:
            stats[timing_type][metric] = float(row["Value_Seconds"])

    return stats


def main() -> None:
    """Benchmark weave setup time and log results."""
    parser = argparse.ArgumentParser(description="Benchmark Weave setup time")
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of setup iterations to run (default: 10)",
    )
    parser.add_argument(
        "--out_filetype",
        choices=["csv"],
        help="Output file type for results (csv)",
    )
    parser.add_argument(
        "--from_file",
        type=str,
        help="Read results from existing file instead of running benchmark",
    )

    args = parser.parse_args()

    if args.from_file:
        # Read results from existing file
        console.print(f"[bold]Reading results from: {args.from_file}[/bold]\n")
        if not os.path.exists(args.from_file):
            console.print(f"[red]Error: File {args.from_file} does not exist[/red]")
            return

        csv_data = utils.read_results_from_csv(args.from_file)
        stats = get_stats_from_csv(csv_data)
    else:
        # Run the benchmark
        console.print("[bold]Weave Setup Time Benchmark[/bold]")
        console.print(f"Running {args.iterations} iterations...\n")

        results = run_benchmark_iterations(args.iterations)
        stats = {
            timing_type: utils.calculate_stats(times)
            for timing_type, times in results.items()
        }

        if args.out_filetype == "csv":
            # Write results to CSV in the same directory as the script
            script_dir = utils.get_script_dir_path(__file__)
            csv_filename = os.path.join(script_dir, "weave_setup_time_results.csv")
            write_results_to_csv(results, csv_filename)

    # Display results
    console.print()
    table = create_results_table(stats)
    console.print(table)
    display_summary(stats)


if __name__ == "__main__":
    main()
