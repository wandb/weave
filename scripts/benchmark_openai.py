#!/usr/bin/env python3

import os
import statistics
import subprocess
import sys
import textwrap

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from rich.table import Table

# TODO: Add mock setup


def test_with_weave():
    cmd = textwrap.dedent(
        """
        import time

        start_import = time.perf_counter()
        import openai
        import weave
        end_import = time.perf_counter()
        print(end_import - start_import)

        start_init = time.perf_counter()
        weave.init('openai-benchmark')
        oaiclient = openai.OpenAI()
        end_init = time.perf_counter()
        print(end_init - start_init)

        start_call = time.perf_counter()
        response = oaiclient.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Tell me a short joke"}],
            max_tokens=60
        )
        end_call = time.perf_counter()
        print(end_call - start_call)
        """
    )

    res = subprocess.run(
        [sys.executable, "-c", cmd],
        capture_output=True,
        text=True,
        env=os.environ,
    )
    import_time, *_, init_time, _, call_time = res.stdout.strip().splitlines()
    return float(import_time), float(init_time), float(call_time)


def test_without_weave():
    cmd = textwrap.dedent(
        """
        import time

        start_import = time.perf_counter()
        import openai
        end_import = time.perf_counter()
        print(end_import - start_import)

        start_init = time.perf_counter()
        oaiclient = openai.OpenAI()
        end_init = time.perf_counter()
        print(end_init - start_init)

        start_call = time.perf_counter()
        response = oaiclient.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Tell me a short joke"}],
            max_tokens=60
        )
        end_call = time.perf_counter()
        print(end_call - start_call)
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", cmd],
        capture_output=True,
        text=True,
        env=os.environ,
    )
    import_time, init_time, call_time = result.stdout.strip().split("\n")
    return float(import_time), float(init_time), float(call_time)


def benchmark(iterations=5):
    console = Console()
    import_times_without_weave = []
    init_times_without_weave = []
    call_times_without_weave = []
    import_times_with_weave = []
    init_times_with_weave = []
    call_times_with_weave = []

    with Progress(
        SpinnerColumn(),
        *Progress.get_default_columns(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Running OpenAI API tests...", total=iterations)

        for _ in range(iterations):
            import_time, init_time, call_time = test_without_weave()
            import_times_without_weave.append(import_time)
            init_times_without_weave.append(init_time)
            call_times_without_weave.append(call_time)

            import_time, init_time, call_time = test_with_weave()
            import_times_with_weave.append(import_time)
            init_times_with_weave.append(init_time)
            call_times_with_weave.append(call_time)

            progress.advance(task)

    table = Table(title="OpenAI API Benchmark Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Component", style="yellow")
    table.add_column("Without Weave", style="green")
    table.add_column("With Weave", style="blue")
    table.add_column("Difference", style="red")
    table.add_column("% Increase", style="red")

    metrics = [
        ("Mean time", statistics.mean),
        ("Median time", statistics.median),
        ("Std dev", statistics.stdev),
        ("Min time", min),
        ("Max time", max),
    ]

    components = [
        ("Import", import_times_without_weave, import_times_with_weave),
        ("Init", init_times_without_weave, init_times_with_weave),
        ("API Call", call_times_without_weave, call_times_with_weave),
        (
            "Total",
            [
                sum(x)
                for x in zip(
                    import_times_without_weave,
                    init_times_without_weave,
                    call_times_without_weave,
                )
            ],
            [
                sum(x)
                for x in zip(
                    import_times_with_weave,
                    init_times_with_weave,
                    call_times_with_weave,
                )
            ],
        ),
    ]

    for name, func in metrics:
        for comp_name, without_times, with_times in components:
            without_val = func(without_times)
            with_val = func(with_times)
            diff = with_val - without_val
            pct_increase = (
                (diff / without_val) * 100 if without_val != 0 else float("inf")
            )

            table.add_row(
                name,
                comp_name,
                f"{without_val:.4f}s",
                f"{with_val:.4f}s",
                f"{diff:+.4f}s",
                f"{pct_increase:+.1f}%",
            )

    console.print("\n")
    console.print(table)

    times_table = Table(title="Individual API Call Times")
    times_table.add_column("Run #", style="cyan")
    times_table.add_column("Component", style="yellow")
    times_table.add_column("Without Weave (seconds)", style="green")
    times_table.add_column("With Weave (seconds)", style="blue")
    times_table.add_column("Difference (seconds)", style="red")
    times_table.add_column("% Increase", style="red")

    for i in range(iterations):
        for comp_name, without_times, with_times in components:
            without_val = without_times[i]
            with_val = with_times[i]
            diff = with_val - without_val
            pct_increase = (
                (diff / without_val) * 100 if without_val != 0 else float("inf")
            )

            times_table.add_row(
                str(i + 1),
                comp_name,
                f"{without_val:.4f}",
                f"{with_val:.4f}",
                f"{diff:+.4f}",
                f"{pct_increase:+.1f}%",
            )

    console.print("\n")
    console.print(times_table)


if __name__ == "__main__":
    benchmark()
