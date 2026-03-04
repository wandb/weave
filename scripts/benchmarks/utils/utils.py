"""Shared utilities for benchmark scripts."""

from __future__ import annotations

import csv
import os
import statistics
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


def calculate_stats(times: list[float]) -> dict[str, float]:
    """Calculate timing statistics.

    Args:
        times: List of execution times.

    Returns:
        dict[str, float]: Dictionary with statistical measures.

    Examples:
        >>> times = [1.0, 2.0, 3.0, 4.0, 5.0]
        >>> stats = calculate_stats(times)
        >>> stats['mean']
        3.0
        >>> stats['median']
        3.0
    """
    if not times:
        return {"mean": 0, "median": 0, "std_dev": 0, "min": 0, "max": 0}

    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
        "min": min(times),
        "max": max(times),
    }


def read_results_from_csv(filename: str) -> list[dict[str, str]]:
    """Read benchmark results from CSV file.

    Args:
        filename: Input CSV filename.

    Returns:
        list[dict[str, str]]: List of row dictionaries.

    Examples:
        >>> data = read_results_from_csv("results.csv")
        >>> len(data) > 0  # doctest: +SKIP
        True
    """
    if not os.path.exists(filename):
        console.print(f"[red]Results file {filename} not found[/red]")
        return []

    console.print(f"Reading results from {filename}...")

    results = []
    with open(filename, encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            results.append(row)

    return results


def write_csv_with_headers(
    filename: str,
    headers: list[str],
    rows: list[list[Any]],
) -> None:
    """Write data to CSV file with given headers and rows.

    Args:
        filename: Output CSV filename.
        headers: List of column headers.
        rows: List of data rows.

    Examples:
        >>> headers = ["Name", "Value"]
        >>> rows = [["Test", "123"], ["Example", "456"]]
        >>> write_csv_with_headers("test.csv", headers, rows)  # doctest: +SKIP
    """
    console.print(f"Writing results to {filename}...")

    with open(filename, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        writer.writerows(rows)


def create_basic_table(
    title: str,
    headers: list[str],
    rows: list[list[str]],
    column_styles: list[str] | None = None,
    column_justifications: list[str] | None = None,
) -> Table:
    """Create a basic Rich table with given configuration.

    Args:
        title: Table title.
        headers: Column headers.
        rows: Data rows.
        column_styles: Optional list of column styles (e.g., ["cyan", "green"]).
        column_justifications: Optional list of column justifications (e.g., ["left", "right"]).

    Returns:
        Table: Rich table with the data.

    Examples:
        >>> headers = ["Name", "Value"]
        >>> rows = [["Test", "123"]]
        >>> table = create_basic_table("Results", headers, rows)
        >>> table.title
        'Results'
    """
    table = Table(title=title)

    # Set defaults if not provided
    if column_styles is None:
        column_styles = ["cyan"] * len(headers)
    if column_justifications is None:
        column_justifications = ["left"] * len(headers)

    # Add columns
    for i, header in enumerate(headers):
        style = column_styles[i] if i < len(column_styles) else "cyan"
        justify = column_justifications[i] if i < len(column_justifications) else "left"
        table.add_column(header, style=style, justify=justify)

    # Add rows
    for row in rows:
        table.add_row(*row)

    return table


def get_script_dir_path(script_file: str) -> str:
    """Get the directory path of a script file.

    Args:
        script_file: The __file__ variable from the calling script.

    Returns:
        str: The directory path of the script.

    Examples:
        >>> import os
        >>> path = get_script_dir_path(__file__)
        >>> os.path.basename(path)
        'benchmarks'
    """
    return os.path.dirname(os.path.abspath(script_file))


def format_seconds(seconds: float, precision: int = 3) -> str:
    """Format seconds with appropriate precision and unit suffix.

    Args:
        seconds: Time in seconds.
        precision: Number of decimal places.

    Returns:
        str: Formatted time string.

    Examples:
        >>> format_seconds(1.234567)
        '1.235s'
        >>> format_seconds(0.001234, 6)
        '0.001234s'
    """
    return f"{seconds:.{precision}f}s"


def format_percentage(value: float, precision: int = 1) -> str:
    """Format percentage with appropriate sign and precision.

    Args:
        value: Percentage value.
        precision: Number of decimal places.

    Returns:
        str: Formatted percentage string.

    Examples:
        >>> format_percentage(15.7)
        '+15.7%'
        >>> format_percentage(-5.2)
        '-5.2%'
        >>> format_percentage(0.0)
        '0.0%'
    """
    if value > 0:
        return f"+{value:.{precision}f}%"
    else:
        return f"{value:.{precision}f}%"
