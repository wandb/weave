#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "rich==14.0.0",
#     "typer==0.16.0",
# ]
# ///
"""Weave Benchmark Runner.

A typer app for selecting and running benchmarks from the benchmarks/ directory.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

app = typer.Typer(
    name="benchmark",
    help="🔬 Weave Benchmark Runner - Select and run performance benchmarks",
    rich_markup_mode="rich",
)
console = Console()


def find_benchmarks(benchmarks_dir: Path) -> list[Path]:
    """Find all Python benchmark files in the benchmarks directory.

    Args:
        benchmarks_dir (Path): Path to the benchmarks directory.

    Returns:
        list[Path]: List of benchmark file paths.
    """
    if not benchmarks_dir.exists():
        console.print(
            f"[red]Error:[/red] Benchmarks directory not found: {benchmarks_dir}"
        )
        return []

    benchmarks = []
    for file_path in benchmarks_dir.glob("*.py"):
        if file_path.is_file() and file_path.name != "utils.py":
            benchmarks.append(file_path)

    return sorted(benchmarks)


def get_benchmark_description(benchmark_path: Path) -> str:
    """Extract a description from the benchmark file's header docstring.

    Args:
        benchmark_path (Path): Path to the benchmark file.

    Returns:
        str: Description of the benchmark.
    """
    try:
        with open(benchmark_path, encoding="utf-8") as f:
            content = f.read()

        # Look for the very first docstring at the top of the file
        # This should be the main description of what the benchmark does
        if content.startswith('"""'):
            # Find the closing triple quotes
            end_pos = content.find('"""', 3)
            if end_pos != -1:
                description = content[3:end_pos].strip()
                # Clean up the description - remove extra whitespace and newlines
                description = " ".join(description.split())
                return description if description else "No description available"

    except Exception:
        return "Error reading description"
    else:
        return "No description available"


def display_benchmarks_table(benchmarks: list[Path]) -> None:
    """Display available benchmarks in a rich table.

    Args:
        benchmarks (list[Path]): List of benchmark file paths.
    """
    table = Table(
        title="📊 Available Benchmarks", box=box.ROUNDED, title_style="bold magenta"
    )

    table.add_column("#", style="cyan", no_wrap=True, width=3)
    table.add_column("Benchmark", style="bright_blue", no_wrap=True)
    table.add_column("Description", style="dim white")

    for i, benchmark in enumerate(benchmarks, 1):
        name = benchmark.stem
        description = get_benchmark_description(benchmark)
        table.add_row(str(i), name, description)

    console.print()
    console.print(table)
    console.print()


def execute_benchmark(
    benchmark_path: Path, extra_args: list[str] | None = None
) -> bool:
    """Execute the selected benchmark using uv run.

    Args:
        benchmark_path (Path): Path to the benchmark file to run.
        extra_args (list[str]): Additional arguments to pass to the benchmark script.

    Returns:
        bool: True if benchmark completed successfully, False otherwise.
    """
    console.print(
        f"[green]🚀 Running benchmark:[/green] [bold]{benchmark_path.name}[/bold]"
    )

    # Build command with extra arguments
    cmd = ["uv", "run", str(benchmark_path)]
    if extra_args:
        cmd.extend(extra_args)

    # Show the full command being executed
    cmd_display = " ".join(cmd)
    console.print(f"[dim]Command: {cmd_display}[/dim]")
    console.print()

    try:
        # Change to the benchmark directory and run with uv
        result = subprocess.run(cmd, cwd=benchmark_path.parent, check=False)

        console.print()
        if result.returncode == 0:
            console.print("[green]✅ Benchmark completed successfully![/green]")
            return True
        else:
            console.print(
                f"[red]❌ Benchmark failed with exit code {result.returncode}[/red]"
            )
            return False

    except FileNotFoundError:
        console.print(
            "[red]❌ Error: 'uv' command not found. Please install uv first.[/red]"
        )
        console.print(
            "Install with: [dim]curl -LsSf https://astral.sh/uv/install.sh | sh[/dim]"
        )
        return False
    except Exception as e:
        console.print(f"[red]❌ Error running benchmark:[/red] {e}")
        return False


@app.command("list")
def list_benchmarks() -> None:
    """📋 List all available benchmarks."""
    script_dir = Path(__file__).parent
    benchmarks_dir = script_dir / "benchmarks"
    benchmarks = find_benchmarks(benchmarks_dir)

    if not benchmarks:
        console.print(
            "[red]No benchmark files found in the benchmarks/ directory.[/red]"
        )
        console.print(f"[dim]Looked in: {benchmarks_dir}[/dim]")
        return

    display_benchmarks_table(benchmarks)


@app.command("run")
def run_benchmark(
    benchmark_name: Annotated[
        str | None,
        typer.Argument(help="Name of the benchmark to run (without .py extension)"),
    ] = None,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive", "-i", help="Run in interactive mode to select benchmark"
        ),
    ] = False,
    out_filetype: Annotated[
        str | None,
        typer.Option("--out_filetype", help="Output file type for results (csv)"),
    ] = None,
    from_file: Annotated[
        str | None,
        typer.Option(
            "--from_file",
            help="Read results from existing file instead of running benchmark",
        ),
    ] = None,
) -> None:
    """🚀 Run a specific benchmark or select interactively."""
    script_dir = Path(__file__).parent
    benchmarks_dir = script_dir / "benchmarks"
    benchmarks = find_benchmarks(benchmarks_dir)

    if not benchmarks:
        console.print(
            "[red]No benchmark files found in the benchmarks/ directory.[/red]"
        )
        console.print(f"[dim]Looked in: {benchmarks_dir}[/dim]")
        raise typer.Exit(1)

    selected_benchmark = None

    # If benchmark name is provided, find it
    if benchmark_name and not interactive:
        for benchmark in benchmarks:
            if benchmark.stem == benchmark_name:
                selected_benchmark = benchmark
                break

        if not selected_benchmark:
            console.print(f"[red]❌ Benchmark '{benchmark_name}' not found.[/red]")
            console.print("\n[yellow]Available benchmarks:[/yellow]")
            for benchmark in benchmarks:
                console.print(f"  • {benchmark.stem}")
            raise typer.Exit(1)

    # Interactive mode or no benchmark specified
    else:
        # Print header
        header_text = Text("🔬 Weave Benchmark Runner", style="bold bright_blue")
        header_panel = Panel(
            header_text, box=box.DOUBLE, padding=(1, 2), style="bright_blue"
        )
        console.print(header_panel)

        # Display available benchmarks
        display_benchmarks_table(benchmarks)

        # Get user selection
        try:
            while True:
                choice = Prompt.ask(
                    f"[bright_yellow]Select a benchmark to run[/bright_yellow] [dim](1-{len(benchmarks)}, or 'q' to quit)[/dim]",
                    default="q",
                )

                if choice.lower() in ["q", "quit", "exit"]:
                    console.print("[dim]👋 Goodbye![/dim]")
                    raise typer.Exit(0)

                try:
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(benchmarks):
                        selected_benchmark = benchmarks[choice_num - 1]
                        break
                    else:
                        console.print(
                            f"[red]Please enter a number between 1 and {len(benchmarks)}[/red]"
                        )
                except ValueError:
                    console.print(
                        "[red]Please enter a valid number or 'q' to quit[/red]"
                    )

        except KeyboardInterrupt:
            console.print("\n[dim]👋 Goodbye![/dim]")
            raise typer.Exit(0) from None

    # Build extra arguments for the benchmark script
    extra_args = []
    if out_filetype:
        extra_args.extend(["--out_filetype", out_filetype])
    if from_file:
        extra_args.extend(["--from_file", from_file])

    # Run the selected benchmark
    console.print()
    success = execute_benchmark(selected_benchmark, extra_args)
    if not success:
        raise typer.Exit(1)


@app.command("all")
def run_all_benchmarks(
    continue_on_failure: Annotated[
        bool,
        typer.Option(
            "--continue", "-c", help="Continue running other benchmarks if one fails"
        ),
    ] = False,
    out_filetype: Annotated[
        str | None,
        typer.Option("--out_filetype", help="Output file type for results (csv)"),
    ] = None,
    from_file: Annotated[
        str | None,
        typer.Option(
            "--from_file",
            help="Read results from existing file instead of running benchmark",
        ),
    ] = None,
) -> None:
    """🚀 Run all available benchmarks sequentially."""
    script_dir = Path(__file__).parent
    benchmarks_dir = script_dir / "benchmarks"
    benchmarks = find_benchmarks(benchmarks_dir)

    if not benchmarks:
        console.print(
            "[red]No benchmark files found in the benchmarks/ directory.[/red]"
        )
        console.print(f"[dim]Looked in: {benchmarks_dir}[/dim]")
        raise typer.Exit(1)

    # Print header
    header_text = Text(
        f"🔬 Running All {len(benchmarks)} Benchmarks", style="bold bright_blue"
    )
    header_panel = Panel(
        header_text, box=box.DOUBLE, padding=(1, 2), style="bright_blue"
    )
    console.print(header_panel)

    # Build extra arguments for the benchmark script
    extra_args = []
    if out_filetype:
        extra_args.extend(["--out_filetype", out_filetype])
    if from_file:
        extra_args.extend(["--from_file", from_file])

    results = []
    for i, benchmark in enumerate(benchmarks, 1):
        console.print(f"\n[cyan]═══ Benchmark {i}/{len(benchmarks)} ═══[/cyan]")
        success = execute_benchmark(benchmark, extra_args)
        results.append((benchmark.stem, success))

        if not success and not continue_on_failure:
            console.print(
                f"\n[red]❌ Stopping execution due to failure in {benchmark.stem}[/red]"
            )
            console.print(
                "[dim]Use --continue to run all benchmarks regardless of failures[/dim]"
            )
            break

    # Show summary
    console.print("\n" + "═" * 50)
    console.print("[bold]📊 Benchmark Results Summary[/bold]")

    passed = sum(1 for _, success in results if success)
    failed = len(results) - passed

    for name, success in results:
        status = "[green]✅ PASSED[/green]" if success else "[red]❌ FAILED[/red]"
        console.print(f"  {name}: {status}")

    console.print(
        f"\n[bold]Total: {len(results)} | [green]Passed: {passed}[/green] | [red]Failed: {failed}[/red][/bold]"
    )

    if failed > 0:
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """🔬 Weave Benchmark Runner.

    A rich CLI app for selecting and running benchmarks from the benchmarks/ directory.
    """
    if ctx.invoked_subcommand is None:
        # Default to run command in interactive mode when no command is specified
        run_benchmark(benchmark_name=None, interactive=True)


if __name__ == "__main__":
    app()
