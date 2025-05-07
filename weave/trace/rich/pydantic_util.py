"""Helper methods for displaying pydantic models."""

from typing import Any

from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from weave.trace import util


def dict_to_table(d: dict[str, Any], *, filter_none_values: bool = False) -> Table:
    """Create a two-column table from a dictionary."""
    table = Table(show_header=False)
    table.add_column("Key", justify="right", style="bold cyan")
    table.add_column("Value")
    for k, v in d.items():
        if filter_none_values and v is None:
            continue
        table.add_row(k, str(v))
    return table


def table_to_str(table: Table) -> str:
    """Render a Rich Table to a string."""
    use_emojis = not util.is_notebook()
    console = Console(emoji=use_emojis)
    with console.capture() as capture:
        console.print(table)
    return capture.get().strip()


def model_to_table(model: BaseModel, *, filter_none_values: bool = False) -> Table:
    """Create a two-column table from a Pydantic model."""
    return dict_to_table(model.model_dump(), filter_none_values=filter_none_values)


def model_to_str(model: BaseModel) -> Table:
    """Create a string representation of a Pydantic model."""
    return table_to_str(model_to_table(model))
