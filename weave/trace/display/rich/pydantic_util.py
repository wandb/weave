"""Helper methods for displaying pydantic models."""

from typing import Any

from pydantic import BaseModel

from weave.trace import util
from weave.trace.display import display


def dict_to_table(
    d: dict[str, Any], *, filter_none_values: bool = False
) -> display.Table:
    """Create a two-column table from a dictionary."""
    table = display.Table(show_header=False)
    table.add_column("Key", justify="right", style="bold cyan")
    table.add_column("Value")
    for k, v in d.items():
        if filter_none_values and v is None:
            continue
        table.add_row(k, str(v))
    return table


def table_to_str(table: display.Table) -> str:
    """Render a Table to a string."""
    use_emojis = not util.is_notebook()
    console = display.Console(emoji=use_emojis)
    return table.to_string(console)


def model_to_table(
    model: BaseModel, *, filter_none_values: bool = False
) -> display.Table:
    """Create a two-column table from a Pydantic model."""
    return dict_to_table(model.model_dump(), filter_none_values=filter_none_values)


def model_to_str(model: BaseModel) -> str:
    """Create a string representation of a Pydantic model."""
    return table_to_str(model_to_table(model))
