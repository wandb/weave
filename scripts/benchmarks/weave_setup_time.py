"""Benchmark Weave import and initialization time."""

#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "weave==0.51.56",
#     "rich==14.0.0",
# ]
# ///

import argparse
import os
import subprocess
import sys
import time
import uuid

from rich.console import Console
from utils import (
    calculate_stats,
    create_basic_table,
    format_seconds,
    get_script_dir_path,
    read_results_from_csv,
    write_csv_with_headers,
)

console = Console()


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

    # Write to a temporary file
    temp_file = f"temp_import_test_{uuid.uuid4().hex[:8]}.py"
    try:
        with open(temp_file, "w") as f:
            f.write(temp_script)

        # Run in a fresh Python process
        result = subprocess.run(
            [sys.executable, temp_file], capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            return float(result.stdout.strip())
        else:
            console.print(f"[red]Import test failed: {result.stderr}[/red]")
            return 0.0
    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)


def time_weave_init() -> float:
    """Time the weave.init() call.

    Returns:
        float: Time taken to initialize weave in seconds.
    """
    # Force a fresh import by removing from cache if it exists
    if "weave" in sys.modules:
        del sys.modules["weave"]

    # Import weave fresh
    import weave

    # Time the init call
    start_time = time.perf_counter()
    weave.init(
        f"benchmark_init_{uuid.uuid4().hex[:8]}",
        settings={"print_call_link": False},
    )
    end_time = time.perf_counter()

    return end_time - start_time


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

    # Write to a temporary file
    temp_file = f"temp_full_test_{uuid.uuid4().hex[:8]}.py"
    try:
        with open(temp_file, "w") as f:
            f.write(temp_script)

        # Run in a fresh Python process
        result = subprocess.run(
            [sys.executable, temp_file], capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            import_time, init_time = map(float, result.stdout.strip().split(","))
            return import_time, init_time
        else:
            console.print(f"[red]Full test failed: {result.stderr}[/red]")
            return 0.0, 0.0
    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)


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
    stats = {}
    for timing_type, times in results.items():
        stats[timing_type] = calculate_stats(times)

    # Prepare CSV data
    headers = ["Timing_Type", "Metric", "Value_Seconds"]
    rows = []

    metrics = ["mean", "median", "std_dev", "min", "max"]
    metric_labels = ["Mean", "Median", "Std Dev", "Min", "Max"]

    for timing_type in ["import", "init", "total"]:
        for metric, label in zip(metrics, metric_labels):
            value = stats[timing_type][metric]
            rows.append([timing_type.title(), label, f"{value:.6f}"])

    write_csv_with_headers(filename, headers, rows)


def create_results_table_from_csv(csv_data: list[dict[str, str]]):
    """Create a Rich table from CSV data.

    Args:
        csv_data: List of row dictionaries from CSV.

    Returns:
        Rich table with timing results.
    """
    headers = ["Component", "Metric", "Time (seconds)"]
    column_styles = ["cyan", "magenta", "green"]
    column_justifications = ["left", "left", "right"]

    rows = []
    for row in csv_data:
        timing_type = row["Timing_Type"]
        metric = row["Metric"]
        value = float(row["Value_Seconds"])
        rows.append([timing_type, metric, format_seconds(value)])

    return create_basic_table(
        "Weave Setup Timing Results",
        headers,
        rows,
        column_styles,
        column_justifications,
    )


def main():
    """Benchmark weave setup time and log results."""
    parser = argparse.ArgumentParser(description="Benchmark Weave setup time")
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of setup iterations to run (default: 10)",
    )

    args = parser.parse_args()

    console.print("[bold]Weave Setup Time Benchmark[/bold]")
    console.print(f"Running {args.iterations} iterations...\n")

    # Run the benchmark
    results = run_benchmark_iterations(args.iterations)

    # Write results to CSV in the same directory as the script
    script_dir = get_script_dir_path(__file__)
    csv_filename = os.path.join(script_dir, "weave_setup_time_results.csv")
    write_results_to_csv(results, csv_filename)

    # Read results back from CSV and display
    csv_data = read_results_from_csv(csv_filename)

    console.print()
    table = create_results_table_from_csv(csv_data)
    console.print(table)

    # Show summary
    import_mean = None
    init_mean = None
    total_mean = None

    for row in csv_data:
        if row["Timing_Type"] == "Import" and row["Metric"] == "Mean":
            import_mean = float(row["Value_Seconds"])
        elif row["Timing_Type"] == "Init" and row["Metric"] == "Mean":
            init_mean = float(row["Value_Seconds"])
        elif row["Timing_Type"] == "Total" and row["Metric"] == "Mean":
            total_mean = float(row["Value_Seconds"])

    if import_mean is not None and init_mean is not None and total_mean is not None:
        console.print("\n[bold]Summary:[/bold]")
        console.print(
            f"  • Import time: [yellow]{format_seconds(import_mean)}[/yellow]"
        )
        console.print(f"  • Init time: [yellow]{format_seconds(init_mean)}[/yellow]")
        console.print(f"  • Total time: [yellow]{format_seconds(total_mean)}[/yellow]")


if __name__ == "__main__":
    main()
