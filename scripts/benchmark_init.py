#!/usr/bin/env python3

import argparse
import statistics
import subprocess
import sys
from datetime import datetime

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from rich.table import Table

from weave.trace.autopatch import AutopatchSettings


def today() -> str:
    return datetime.today().date().strftime("%Y-%m-%d")


def run_single_init(disable_autopatch: bool = False):
    projname = today() + "_benchmark_init"
    cmd = rf"""
import time
import weave
start = time.perf_counter()
weave.init("{projname}", autopatch_settings={{"disable_autopatch": {disable_autopatch}}})
end = time.perf_counter()
print(end - start)
"""
    result = subprocess.run([sys.executable, "-c", cmd], capture_output=True, text=True)
    # Get the last line of output (Skipping "Logged in as Weights & Biases user...")
    output = result.stdout.strip().split("\n")[-1]
    print(output)
    return float(output)


def benchmark(iterations: int = 10, disable_autopatch: bool = False):
    projname = today() + "_benchmark_init"
    # Ensure project exists
    import weave

    weave.init(projname, autopatch_settings=AutopatchSettings(disable_autopatch=True))

    console = Console()
    times = []

    with Progress(
        SpinnerColumn(),
        *Progress.get_default_columns(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Running init tests...", total=iterations)

        for _ in range(iterations):
            times.append(run_single_init(disable_autopatch))
            progress.advance(task)

    # Display results in a nice table
    table = Table(title="Init Time Benchmark Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Mean init time", f"{statistics.mean(times):.4f}s")
    table.add_row("Median init time", f"{statistics.median(times):.4f}s")
    table.add_row("Std dev", f"{statistics.stdev(times):.4f}s")
    table.add_row("Min time", f"{min(times):.4f}s")
    table.add_row("Max time", f"{max(times):.4f}s")

    console.print("\n")
    console.print(table)

    # Show individual times
    times_table = Table(title="Individual Init Times")
    times_table.add_column("Run #", style="cyan")
    times_table.add_column("Time (seconds)", style="green")

    for i, t in enumerate(times, 1):
        times_table.add_row(str(i), f"{t:.4f}")

    console.print("\n")
    console.print(times_table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark weave.init performance")
    parser.add_argument(
        "--disable-autopatch", action="store_true", help="Disable autopatching"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of iterations to run (default: 10)",
    )
    args = parser.parse_args()

    benchmark(iterations=args.iterations, disable_autopatch=args.disable_autopatch)
