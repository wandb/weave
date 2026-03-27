#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "weave==0.51.56",
#     "rich==14.0.0",
# ]
# ///
"""Benchmark granular Weave tracing overhead: init, decoration, call tracing, nesting."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# This is unfortunate, but needed to make the script runnable both as a uv
# script and as a helper in the test suite
sys.path.insert(0, str(Path(__file__).parent))
from utils import utils

console = Console()

# Benchmark registry: name → (runner_func_name, description)
# The order here is the default execution order.
BENCHMARKS: dict[str, str] = {
    "init": "weave.init() startup cost",
    "decoration": "@weave.op decoration overhead",
    "call": "traced vs untraced call overhead",
    "nested": "nested op call overhead (3 levels)",
    "throughput": "high-throughput per-call amortised cost",
}
ALL_BENCHMARK_NAMES = list(BENCHMARKS.keys())


# ---------------------------------------------------------------------------
# 1. weave.init() overhead (measured in subprocess for isolation)
# ---------------------------------------------------------------------------


def _run_subprocess_timing(script_content: str, label: str) -> float:
    """Run a timing script in a fresh subprocess and return the elapsed time."""
    temp_file = f"temp_{label}_{uuid.uuid4().hex[:8]}.py"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(script_content)
        result = subprocess.run(
            [sys.executable, temp_file],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
        console.print(f"[red]{label} failed: {result.stderr[:200]}[/red]")
        return 0.0
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)


def time_weave_import() -> float:
    """Time the import of weave module in a fresh process.

    Returns:
        float: Time taken to import weave in seconds.
    """
    script = """
import time
start_time = time.perf_counter()
import weave
end_time = time.perf_counter()
print(end_time - start_time)
"""
    return _run_subprocess_timing(script, "import")


def bench_init(iterations: int) -> list[float]:
    """Measure weave.init() time in fresh processes (excludes import)."""
    console.print(f"  weave.init() — {iterations} iterations (subprocess each)")
    times: list[float] = []
    script = f"""
import weave, time
start = time.perf_counter()
weave.init("bench_init_{uuid.uuid4().hex[:8]}", settings={{"print_call_link": False}})
elapsed = time.perf_counter() - start
print(elapsed)
"""
    for i in range(iterations):
        t = _run_subprocess_timing(script, f"init_{i}")
        times.append(t)
        console.print(f"    [{i+1}/{iterations}] {t:.4f}s")
    return times


# ---------------------------------------------------------------------------
# 2. @weave.op decoration overhead (in-process, no network)
# ---------------------------------------------------------------------------


def bench_decoration(iterations: int) -> list[float]:
    """Measure the cost of applying @weave.op to a function."""
    import weave

    console.print(f"  @weave.op decoration — {iterations} iterations")
    times: list[float] = []
    for _i in range(iterations):

        def _fn(x: int) -> int:
            return x + 1

        start = time.perf_counter()
        weave.op(_fn)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    console.print(f"    done — median {utils.format_seconds(sorted(times)[len(times)//2], 6)}")
    return times


# ---------------------------------------------------------------------------
# 3. Traced vs untraced call overhead
# ---------------------------------------------------------------------------


def bench_traced_call(iterations: int, warmup: int) -> tuple[list[float], list[float]]:
    """Compare calling a plain function vs a @weave.op-wrapped function."""
    import weave

    weave.init(f"bench_call_{uuid.uuid4().hex[:8]}", settings={"print_call_link": False})

    def plain_fn(x: int) -> int:
        return x * 2 + 1

    @weave.op
    def traced_fn(x: int) -> int:
        return x * 2 + 1

    console.print(f"  traced call — {iterations} iterations ({warmup} warmup)")

    # Warmup
    for j in range(warmup):
        plain_fn(j)
        traced_fn(j)

    plain_times: list[float] = []
    traced_times: list[float] = []
    for i in range(iterations):
        # Plain
        start = time.perf_counter()
        plain_fn(i)
        plain_times.append(time.perf_counter() - start)

        # Traced
        start = time.perf_counter()
        traced_fn(i)
        traced_times.append(time.perf_counter() - start)

    console.print(
        f"    plain median {utils.format_seconds(sorted(plain_times)[len(plain_times)//2], 6)}"
        f"  |  traced median {utils.format_seconds(sorted(traced_times)[len(traced_times)//2], 6)}"
    )
    return plain_times, traced_times


# ---------------------------------------------------------------------------
# 4. Nested op call overhead
# ---------------------------------------------------------------------------


def bench_nested_calls(iterations: int, warmup: int) -> tuple[list[float], list[float]]:
    """Compare flat traced call vs 3-level nested traced calls."""
    import weave

    weave.init(f"bench_nest_{uuid.uuid4().hex[:8]}", settings={"print_call_link": False})

    @weave.op
    def flat_fn(x: int) -> int:
        return x + 1

    @weave.op
    def inner(x: int) -> int:
        return x + 1

    @weave.op
    def middle(x: int) -> int:
        return inner(x)

    @weave.op
    def outer(x: int) -> int:
        return middle(x)

    console.print(f"  nested calls (3 levels) — {iterations} iterations ({warmup} warmup)")

    for j in range(warmup):
        flat_fn(j)
        outer(j)

    flat_times: list[float] = []
    nested_times: list[float] = []
    for i in range(iterations):
        start = time.perf_counter()
        flat_fn(i)
        flat_times.append(time.perf_counter() - start)

        start = time.perf_counter()
        outer(i)
        nested_times.append(time.perf_counter() - start)

    console.print(
        f"    flat median {utils.format_seconds(sorted(flat_times)[len(flat_times)//2], 6)}"
        f"  |  nested median {utils.format_seconds(sorted(nested_times)[len(nested_times)//2], 6)}"
    )
    return flat_times, nested_times


# ---------------------------------------------------------------------------
# 5. High-throughput (many rapid calls, amortised per-call cost)
# ---------------------------------------------------------------------------


def bench_throughput(batch_size: int, iterations: int, warmup: int) -> tuple[list[float], list[float]]:
    """Time a batch of N calls and report per-call cost."""
    import weave

    weave.init(f"bench_tp_{uuid.uuid4().hex[:8]}", settings={"print_call_link": False})

    def plain_fn(x: int) -> int:
        return x + 1

    @weave.op
    def traced_fn(x: int) -> int:
        return x + 1

    console.print(
        f"  throughput ({batch_size} calls/batch) — {iterations} batches ({warmup} warmup)"
    )

    # Warmup
    for _ in range(warmup):
        for j in range(batch_size):
            plain_fn(j)
            traced_fn(j)

    plain_batch_times: list[float] = []
    traced_batch_times: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        for j in range(batch_size):
            plain_fn(j)
        plain_batch_times.append(time.perf_counter() - start)

        start = time.perf_counter()
        for j in range(batch_size):
            traced_fn(j)
        traced_batch_times.append(time.perf_counter() - start)

    plain_per_call = [t / batch_size for t in plain_batch_times]
    traced_per_call = [t / batch_size for t in traced_batch_times]

    console.print(
        f"    per-call plain {utils.format_seconds(sorted(plain_per_call)[len(plain_per_call)//2], 6)}"
        f"  |  traced {utils.format_seconds(sorted(traced_per_call)[len(traced_per_call)//2], 6)}"
    )
    return plain_per_call, traced_per_call


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _overhead_pct(base: float, measured: float) -> float:
    return ((measured - base) / base) * 100 if base > 0 else 0.0


def build_results_table(all_stats: dict[str, dict[str, dict[str, float]]]) -> Table:
    """Build a single Rich table summarising all benchmarks."""
    headers = ["Benchmark", "Variant", "Iterations", "Mean", "Median", "Std Dev", "Min", "Max", "Overhead"]
    styles = ["cyan", "magenta", "dim", "green", "green", "yellow", "white", "white", "red"]
    justifications = ["left", "left", "right", "right", "right", "right", "right", "right", "right"]
    rows: list[list[str]] = []

    for bench_name, variants in all_stats.items():
        variant_names = list(variants.keys())
        base_stats = variants[variant_names[0]]  # first variant is the baseline
        for vname, stats in variants.items():
            overhead = _overhead_pct(base_stats["mean"], stats["mean"]) if vname != variant_names[0] else 0.0
            overhead_str = utils.format_percentage(overhead) if vname != variant_names[0] else "—"
            iters = int(stats.get("iterations", 0))
            iters_str = str(iters) if iters > 0 else "—"
            rows.append([
                bench_name,
                vname,
                iters_str,
                utils.format_seconds(stats["mean"], 6),
                utils.format_seconds(stats["median"], 6),
                utils.format_seconds(stats["std_dev"], 6),
                utils.format_seconds(stats["min"], 6),
                utils.format_seconds(stats["max"], 6),
                overhead_str,
            ])

    return utils.create_basic_table(
        "Weave Tracing Overhead — Granular Results",
        headers,
        rows,
        styles,
        justifications,
    )


def write_results_to_csv(
    all_stats: dict[str, dict[str, dict[str, float]]], filename: str
) -> None:
    """Write all benchmark results to a CSV file."""
    headers = ["Benchmark", "Variant", "Iterations", "Mean", "Median", "Std_Dev", "Min", "Max", "Overhead_Percent"]
    rows: list[list[str]] = []

    for bench_name, variants in all_stats.items():
        variant_names = list(variants.keys())
        base_stats = variants[variant_names[0]]
        for vname, stats in variants.items():
            overhead = _overhead_pct(base_stats["mean"], stats["mean"]) if vname != variant_names[0] else 0.0
            rows.append([
                bench_name,
                vname,
                str(int(stats.get("iterations", 0))),
                f"{stats['mean']:.6f}",
                f"{stats['median']:.6f}",
                f"{stats['std_dev']:.6f}",
                f"{stats['min']:.6f}",
                f"{stats['max']:.6f}",
                f"{overhead:.2f}",
            ])

    utils.write_csv_with_headers(filename, headers, rows)


def display_summary(all_stats: dict[str, dict[str, dict[str, float]]]) -> None:
    """Print a compact summary panel."""
    lines: list[str] = []

    if "weave.init()" in all_stats:
        s = all_stats["weave.init()"]["init"]
        n = int(s.get("iterations", 0))
        lines.append(f"weave.init()        : [yellow]{utils.format_seconds(s['mean'])}[/yellow]  [dim](n={n})[/dim]")

    if "@weave.op decorate" in all_stats:
        s = all_stats["@weave.op decorate"]["decorate"]
        n = int(s.get("iterations", 0))
        lines.append(f"@weave.op decorate  : [yellow]{utils.format_seconds(s['mean'], 6)}[/yellow]  [dim](n={n})[/dim]")

    if "traced call" in all_stats:
        plain_s = all_stats["traced call"]["plain"]
        traced_s = all_stats["traced call"]["traced"]
        n = int(traced_s.get("iterations", 0))
        overhead = _overhead_pct(plain_s["mean"], traced_s["mean"])
        lines.append(
            f"traced call overhead : [yellow]{utils.format_percentage(overhead)}[/yellow]"
            f"  (plain {utils.format_seconds(plain_s['mean'], 6)} → traced {utils.format_seconds(traced_s['mean'], 6)})"
            f"  [dim](n={n})[/dim]"
        )

    if "nested calls" in all_stats:
        flat_s = all_stats["nested calls"]["flat (1 level)"]
        nested_s = all_stats["nested calls"]["nested (3 levels)"]
        n = int(nested_s.get("iterations", 0))
        overhead = _overhead_pct(flat_s["mean"], nested_s["mean"])
        lines.append(
            f"nested 3-level cost : [yellow]{utils.format_percentage(overhead)}[/yellow] vs flat"
            f"  ({utils.format_seconds(flat_s['mean'], 6)} → {utils.format_seconds(nested_s['mean'], 6)})"
            f"  [dim](n={n})[/dim]"
        )

    if "throughput" in all_stats:
        plain_s = all_stats["throughput"]["plain/call"]
        traced_s = all_stats["throughput"]["traced/call"]
        n = int(traced_s.get("iterations", 0))
        batch = int(plain_s.get("iterations", 0))
        overhead = _overhead_pct(plain_s["mean"], traced_s["mean"])
        lines.append(
            f"throughput per-call  : [yellow]{utils.format_percentage(overhead)}[/yellow] overhead"
            f"  (plain {utils.format_seconds(plain_s['mean'], 6)} → traced {utils.format_seconds(traced_s['mean'], 6)})"
            f"  [dim](n={n}, batch={batch})[/dim]"
        )

    console.print(Panel("\n".join(lines), title="Summary", border_style="bold"))


# ---------------------------------------------------------------------------
# CSV read-back
# ---------------------------------------------------------------------------


def get_stats_from_csv(csv_data: list[dict[str, str]]) -> dict[str, dict[str, dict[str, float]]]:
    """Reconstruct the all_stats structure from CSV rows."""
    all_stats: dict[str, dict[str, dict[str, float]]] = {}
    for row in csv_data:
        bench = row["Benchmark"]
        variant = row["Variant"]
        if bench not in all_stats:
            all_stats[bench] = {}
        all_stats[bench][variant] = {
            "iterations": float(row.get("Iterations", 0)),
            "mean": float(row["Mean"]),
            "median": float(row["Median"]),
            "std_dev": float(row["Std_Dev"]),
            "min": float(row["Min"]),
            "max": float(row["Max"]),
        }
    return all_stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    bench_list = ", ".join(ALL_BENCHMARK_NAMES)
    parser = argparse.ArgumentParser(
        description="Granular Weave tracing overhead benchmarks",
        epilog=f"Available benchmarks: {bench_list}",
    )
    parser.add_argument(
        "--benchmarks",
        type=str,
        default=None,
        help=f"Comma-separated list of benchmarks to run (default: all). Choices: {bench_list}",
    )
    parser.add_argument("--list", action="store_true", help="List available benchmarks and exit")
    parser.add_argument("--iterations", type=int, default=20, help="Iterations per benchmark (default: 20)")
    parser.add_argument("--warmup", type=int, default=5, help="Warm-up calls (default: 5)")
    parser.add_argument("--batch-size", type=int, default=100, help="Calls per batch in throughput test (default: 100)")
    parser.add_argument("--init-iterations", type=int, default=5, help="Iterations for init benchmark — slower due to subprocess (default: 5)")
    parser.add_argument("--out_filetype", choices=["csv"], help="Output file type for results")
    parser.add_argument("--from_file", type=str, help="Read results from existing file instead of running")

    args = parser.parse_args()

    # --list: show available benchmarks and exit
    if args.list:
        console.print("[bold]Available benchmarks:[/bold]\n")
        for name, desc in BENCHMARKS.items():
            console.print(f"  [cyan]{name:<14}[/cyan] {desc}")
        console.print(f"\nRun all:  [dim]--benchmarks {','.join(ALL_BENCHMARK_NAMES)}[/dim]")
        return

    if args.from_file:
        console.print(f"[bold]Reading results from: {args.from_file}[/bold]\n")
        if not os.path.exists(args.from_file):
            console.print(f"[red]Error: File {args.from_file} does not exist[/red]")
            return
        csv_data = utils.read_results_from_csv(args.from_file)
        all_stats = get_stats_from_csv(csv_data)
        console.print()
        console.print(build_results_table(all_stats))
        display_summary(all_stats)
        return

    # Parse --benchmarks flag
    if args.benchmarks:
        selected = [b.strip() for b in args.benchmarks.split(",")]
        unknown = [b for b in selected if b not in BENCHMARKS]
        if unknown:
            console.print(f"[red]Unknown benchmark(s): {', '.join(unknown)}[/red]")
            console.print(f"[dim]Available: {bench_list}[/dim]")
            return
    else:
        selected = ALL_BENCHMARK_NAMES

    total = len(selected)
    console.print("[bold]Weave Tracing Overhead — Granular Benchmarks[/bold]")
    console.print(f"Running {total} benchmark(s): [cyan]{', '.join(selected)}[/cyan]\n")

    all_stats: dict[str, dict[str, dict[str, float]]] = {}
    step = 0

    # 1. weave.init()
    if "init" in selected:
        step += 1
        console.print(f"[bold cyan]{step}/{total}[/bold cyan] weave.init()")
        init_times = bench_init(args.init_iterations)
        init_stats = utils.calculate_stats(init_times)
        init_stats["iterations"] = args.init_iterations
        all_stats["weave.init()"] = {"init": init_stats}

    # 2. @weave.op decoration
    if "decoration" in selected:
        step += 1
        console.print(f"[bold cyan]{step}/{total}[/bold cyan] @weave.op decoration")
        dec_times = bench_decoration(args.iterations)
        dec_stats = utils.calculate_stats(dec_times)
        dec_stats["iterations"] = args.iterations
        all_stats["@weave.op decorate"] = {"decorate": dec_stats}

    # 3. Traced vs untraced call
    if "call" in selected:
        step += 1
        console.print(f"[bold cyan]{step}/{total}[/bold cyan] Traced vs untraced call")
        plain_times, traced_times = bench_traced_call(args.iterations, args.warmup)
        plain_stats = utils.calculate_stats(plain_times)
        plain_stats["iterations"] = args.iterations
        traced_stats = utils.calculate_stats(traced_times)
        traced_stats["iterations"] = args.iterations
        all_stats["traced call"] = {
            "plain": plain_stats,
            "traced": traced_stats,
        }

    # 4. Nested calls
    if "nested" in selected:
        step += 1
        console.print(f"[bold cyan]{step}/{total}[/bold cyan] Nested op calls")
        flat_times, nested_times = bench_nested_calls(args.iterations, args.warmup)
        flat_stats = utils.calculate_stats(flat_times)
        flat_stats["iterations"] = args.iterations
        nested_stats = utils.calculate_stats(nested_times)
        nested_stats["iterations"] = args.iterations
        all_stats["nested calls"] = {
            "flat (1 level)": flat_stats,
            "nested (3 levels)": nested_stats,
        }

    # 5. Throughput
    if "throughput" in selected:
        step += 1
        console.print(f"[bold cyan]{step}/{total}[/bold cyan] Throughput")
        plain_per, traced_per = bench_throughput(args.batch_size, args.iterations, args.warmup)
        plain_tp_stats = utils.calculate_stats(plain_per)
        plain_tp_stats["iterations"] = args.batch_size
        traced_tp_stats = utils.calculate_stats(traced_per)
        traced_tp_stats["iterations"] = args.iterations
        all_stats["throughput"] = {
            "plain/call": plain_tp_stats,
            "traced/call": traced_tp_stats,
        }

    # Output
    if args.out_filetype == "csv":
        script_dir = utils.get_script_dir_path(__file__)
        csv_filename = os.path.join(script_dir, "tracing_overhead_results.csv")
        write_results_to_csv(all_stats, csv_filename)

    console.print()
    console.print(build_results_table(all_stats))
    display_summary(all_stats)


if __name__ == "__main__":
    main()
