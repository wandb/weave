#!/usr/bin/env python3

import statistics
import subprocess
import sys

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from rich.table import Table


def run_single_import():
    cmd = """
import time
start = time.perf_counter()
import weave
end = time.perf_counter()
print(end - start)
"""
    result = subprocess.run([sys.executable, "-c", cmd], capture_output=True, text=True)
    return float(result.stdout)


def benchmark(iterations=10):
    console = Console()
    times = []

    with Progress(
        SpinnerColumn(),
        *Progress.get_default_columns(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Running import tests...", total=iterations)

        for _ in range(iterations):
            times.append(run_single_import())
            progress.advance(task)

    # Display results in a nice table
    table = Table(title="Import Time Benchmark Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Mean import time", f"{statistics.mean(times):.4f}s")
    table.add_row("Median import time", f"{statistics.median(times):.4f}s")
    table.add_row("Std dev", f"{statistics.stdev(times):.4f}s")
    table.add_row("Min time", f"{min(times):.4f}s")
    table.add_row("Max time", f"{max(times):.4f}s")

    console.print("\n")
    console.print(table)

    # Show individual times
    times_table = Table(title="Individual Import Times")
    times_table.add_column("Run #", style="cyan")
    times_table.add_column("Time (seconds)", style="green")

    for i, t in enumerate(times, 1):
        times_table.add_row(str(i), f"{t:.4f}")

    console.print("\n")
    console.print(times_table)


if __name__ == "__main__":
    benchmark()
