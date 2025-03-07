"""A simple component for tabular structured data, useful as an intermediate representation."""

from __future__ import annotations

import csv
import locale
import os
import sys
import termios
import tty
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from rich.console import Console
from rich.table import Table

from weave.trace import util
from weave.trace.rich import pydantic_util

if TYPE_CHECKING:
    import pandas as pd


# Set locale to user's default setting
locale.setlocale(locale.LC_ALL, "")

# TODO: Add support for other types, e.g. float, datetime, etc.
ColumnType = Literal["str", "int", "bool"]
ColumnValues = list[Any]
RowValues = list[Any]


@dataclass
class ColumnDefinition:
    id: str
    label: str | None = None
    type: ColumnType | None = None
    nullable: bool = True

    # TODO: Could add support for a default value.

    @property
    def display_name(self) -> str:
        return self.label or self.id


def display_value(value: Any) -> str:
    """String representation of a grid cell value for display."""
    if value is None:
        if util.is_notebook():
            # The unicode "Symbol For Null" messes up the column lines in notebooks
            return "[gray35]<None>[/]"
        return "[gray35]␀[/]"
    if isinstance(value, bool):
        # TODO: Should we use emoji like ✅ or ❌?
        return "[green]True[/]" if value else "[red]False[/]"
    if isinstance(value, int):
        return locale.format_string("%d", value, grouping=True)
    return str(value)


def get_terminal_height() -> int:
    """Returns the number of lines available in the terminal."""
    return os.get_terminal_size().lines - 5  # Adjust for headers & padding


def get_key() -> str:
    """Reads a single keypress from the user without requiring Enter."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        # Check if it might be an arrow key (starts with escape sequence)
        if ch == "\x1b":
            # Read the next two characters for arrow keys
            next_chars = sys.stdin.read(2)
            return ch + next_chars
        else:
            return ch
    except KeyboardInterrupt:
        return "q"  # Handle Ctrl+C gracefully
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


class Row:
    """Access to one row of a Grid."""

    grid: Grid
    index: int

    def __init__(self, grid: Grid, index: int) -> None:
        self.grid = grid
        self.index = index

    def to_list(self) -> RowValues:
        return self.grid.rows[self.index]

    def to_dict(self) -> dict[str, Any]:
        return {col.id: self[col.id] for col in self.grid.columns}

    def to_rich_table(self) -> Table:
        """Convert the row to a Rich table with key-value pairs."""
        d = {col.display_name: display_value(self[col.id]) for col in self.grid.columns}
        return pydantic_util.dict_to_table(d)

    def to_rich_table_str(self) -> Table:
        table = self.to_rich_table()
        return pydantic_util.table_to_str(table)

    def __getattr__(self, name: str) -> Any:
        """Allow accessing column values as attributes.

        Example:
            row.column_id instead of row['column_id']

        Args:
            name: The column id to access

        Returns:
            The value in the specified column

        Raises:
            AttributeError: If the column doesn't exist
        """
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"Row has no attribute or column '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        """Allow setting column values as attributes.

        Example:
            row.column_id = value instead of row['column_id'] = value

        Args:
            name: The column id to set
            value: The value to assign to the column
        """
        if name in ("grid", "index"):
            # These are actual attributes of the Row class
            object.__setattr__(self, name, value)
        else:
            try:
                self[name] = value
            except KeyError:
                object.__setattr__(self, name, value)

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, str):
            col_index = self.grid._column_id_to_index.get(key)
            if col_index is None:
                raise KeyError(f"Column '{key}' not found")
            return self.grid.rows[self.index][col_index]
        elif isinstance(key, int):
            if key < 0 or key >= len(self.grid.rows[self.index]):
                raise IndexError("Row index out of range")
            return self.grid.rows[self.index][key]
        else:
            raise TypeError("Key must be string or integer")

    def __setitem__(self, key: str | int, value: Any) -> None:
        """Set a value in the row using either column name or index.

        Args:
            key: Column id (str) or index (int)
            value: The value to set
        """
        if isinstance(key, (str, int)):
            self.grid.set_cell_value(self.index, key, value)
        else:
            raise TypeError("Key must be string or integer")

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:
        """Pretty representation for IPython."""
        if cycle:
            p.text("Row(...)")
        else:
            items = [
                f"{col.id}={display_value(self[col.id])}" for col in self.grid.columns
            ]
            p.text(f"Row({', '.join(items)})")


class Column:
    grid: Grid
    column_id: str

    def __init__(self, grid: Grid, column_id: str) -> None:
        self.grid = grid
        self.column_id = column_id

    def rename(self, label: str) -> Column:
        """Rename the column."""
        self.grid.rename_column(self.column_id, label)
        return self

    def to_list(self) -> ColumnValues:
        """Convert column values to a list.

        Returns:
            A list containing all values in this column.
        """
        col_index = self.grid._column_id_to_index.get(self.column_id)
        if col_index is None:
            raise KeyError(f"Column '{self.column_id}' not found")
        return [row[col_index] for row in self.grid.rows]

    def __getitem__(self, index: int | slice) -> Any | list[Any]:
        """Get the value(s) at the specified row index or slice for this column.

        Args:
            index: The row index or slice to retrieve the value(s) from

        Returns:
            The value at the specified row index or a list of values for a slice

        Raises:
            IndexError: If the row index is out of range
        """
        col_index = self.grid._column_id_to_index.get(self.column_id)
        if col_index is None:
            raise KeyError(f"Column '{self.column_id}' not found")

        num_rows = len(self.grid.rows)
        if isinstance(index, slice):
            # Handle slice by returning a list of values
            start, stop, step = index.indices(num_rows)
            return [self.grid.rows[i][col_index] for i in range(start, stop, step)]
        else:
            # Handle single index
            if index < 0 or index >= num_rows:
                raise IndexError("Row index out of range")
            return self.grid.rows[index][col_index]

    def __setitem__(self, index: int, value: Any) -> None:
        """Set the value at the specified row index for this column.

        Args:
            index: The row index to set the value at
            value: The value to set

        Raises:
            IndexError: If the row index is out of range
        """
        if index < 0 or index >= len(self.grid.rows):
            raise IndexError("Row index out of range")

        self.grid.set_cell_value(index, self.column_id, value)

    def to_rich_table(self) -> Table:
        """Convert the column to a rich Table for pretty display.

        Returns:
            A rich Table with a single column containing all values from this column.
        """
        table = Table()

        # Add a single column with the column name
        col_def = next(
            (col for col in self.grid.columns if col.id == self.column_id), None
        )
        display_name = col_def.display_name if col_def else self.column_id

        # Set justification based on column type
        if col_def and col_def.type == "int":
            table.add_column(display_name, justify="right")
        else:
            table.add_column(display_name)

        # Add all values from this column as rows
        for i in range(len(self.grid.rows)):
            try:
                value = self[i]
                # Convert value to string for display
                table.add_row(display_value(value))
            except (IndexError, KeyError):
                table.add_row("N/A")

        return table

    def to_rich_table_str(self) -> str:
        table = self.to_rich_table()
        return pydantic_util.table_to_str(table)

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:
        """Show a nicely formatted table in ipython."""
        if cycle:
            p.text("Column(...)")
        else:
            p.text(self.to_rich_table_str())


class Grid:
    columns: list[ColumnDefinition]
    rows: list[RowValues]
    _column_id_to_index: dict[str, int]

    def __init__(self, name: str | None = None) -> None:
        self.columns = []
        self.rows = []
        self._column_id_to_index = {}

    def set_cell_value(self, row_index: int, column: str | int, value: Any) -> Grid:
        """Set the value of a specific cell in the grid.

        Args:
            row_index: The index of the row to update
            column: The name or index of the column to update
            value: The new value to set

        Returns:
            The grid instance for method chaining
        """
        if row_index < 0 or row_index >= len(self.rows):
            raise IndexError("Row index out of range")

        column_index = None
        if isinstance(column, int):
            if column < 0 or column >= len(self.columns):
                raise IndexError("Column index out of range")
            column_index = column
        elif isinstance(column, str):
            for i, col in enumerate(self.columns):
                if col.id == column:
                    column_index = i
                    break
            if column_index is None:
                raise KeyError(f"Column '{column}' not found")
        else:
            raise TypeError("Column must be specified by name (str) or index (int)")

        # Check column type and coerce value if possible
        col = self.columns[column_index]
        if value is None and not col.nullable:
            raise ValueError(f"Column '{col.id}' is not nullable")
        elif col.type is not None:
            try:
                if col.type == "bool" and not isinstance(value, bool):
                    value = bool(value)
                elif col.type == "int" and not isinstance(value, int):
                    value = int(value)
                elif col.type == "str" and not isinstance(value, str):
                    value = str(value)
            except (ValueError, TypeError):
                raise ValueError(
                    f"Cannot coerce value '{value}' to type '{col.type}' for column '{col.id}'"
                )

        self.rows[row_index][column_index] = value
        return self

    def insert_column(
        self,
        column_index: int,
        name: str,
        label: str | None = None,
        type: ColumnType | None = None,
    ) -> Grid:
        """Insert a new column at the specified index in the grid."""
        self.columns.insert(
            column_index, ColumnDefinition(id=name, label=label, type=type)
        )
        self._column_id_to_index = {col.id: i for i, col in enumerate(self.columns)}
        for row_index in range(self.num_rows):
            self.rows[row_index].insert(column_index, None)
        return self

    def add_column(
        self, name: str, label: str | None = None, type: ColumnType | None = None
    ) -> Grid:
        """Add a new column to the grid."""
        return self.insert_column(len(self.columns), name, label, type)

    def _get_column_definition(self, column_id: int | str) -> ColumnDefinition:
        """Get the definition of a column by id."""
        if isinstance(column_id, int):
            if column_id < 0 or column_id >= len(self.columns):
                raise IndexError("Column index out of range")
            return self.columns[column_id]
        for col in self.columns:
            if col.id == column_id:
                return col
        raise KeyError(f"Column '{column_id}' not found")

    def rename_column(self, column_id: int | str, label: str) -> Grid:
        """Rename a column in the grid."""
        definition = self._get_column_definition(column_id)
        definition.label = label
        return self

    def add_row(self, values: RowValues) -> Grid:
        """Add a new row of values to the grid."""
        if len(values) != len(self.columns):
            raise ValueError(
                f"Row length ({len(values)}) does not match number of columns ({len(self.columns)})"
            )

        # Check column types and coerce values if possible
        processed_values: RowValues = []
        for i, (value, column) in enumerate(zip(values, self.columns)):
            if column.type is not None:
                try:
                    if column.type == "bool" and not isinstance(value, bool):
                        processed_values.append(bool(value))
                    elif column.type == "int" and not isinstance(value, int):
                        processed_values.append(int(value))
                    elif column.type == "str" and not isinstance(value, str):
                        processed_values.append(str(value))
                    else:
                        processed_values.append(value)
                except (ValueError, TypeError):
                    raise ValueError(
                        f"Cannot coerce value '{value}' to type '{column.type}' for column '{column.id}'"
                    )
            else:
                processed_values.append(value)

        self.rows.append(processed_values)
        return self

    def get_row(self, index: int) -> Row:
        """Get a row by index that allows access by column name or position."""
        if index < 0 or index >= len(self.rows):
            raise IndexError("Row index out of range")
        return Row(self, index)
        # return Row(self.rows[index], self.columns)

    def get_column_values(self, column: str | int) -> ColumnValues:
        """Get all values for a specific column by name or index."""
        if isinstance(column, str):
            # Find the column index by name
            for i, col in enumerate(self.columns):
                if col.id == column:
                    column_index = i
                    break
            else:
                raise KeyError(f"Column '{column}' not found")
        elif isinstance(column, int):
            if column < 0 or column >= len(self.columns):
                raise IndexError("Column index out of range")
            column_index = column
        else:
            raise TypeError(
                "Column must be specified by name (string) or index (integer)"
            )

        # Extract values for the specified column from all rows
        return [row[column_index] for row in self.rows]

    def get_column(self, key: str | int) -> Column:
        """Get a column by id."""
        if isinstance(key, int):
            if key < 0 or key >= len(self.columns):
                raise IndexError("Column index out of range")
            column_id = self.columns[key].id
        elif isinstance(key, str):
            if key not in self._column_id_to_index:
                raise KeyError(f"Column '{key}' not found")
            column_id = key
        else:
            raise TypeError(
                "Key must be a string (column name) or integer (column index)"
            )
        return Column(self, column_id)

    def __getitem__(self, key: str | int | slice) -> Column | Row | Grid:
        """
        Allow accessing column values using grid['column_name'] syntax,
        accessing a row using grid[row_index] syntax,
        or slicing rows using grid[start:end] syntax.
        """
        if isinstance(key, str):
            return self.get_column(key)
        elif isinstance(key, int):
            return self.get_row(key)
        elif isinstance(key, slice):
            # Create a new grid with just the sliced rows
            new_grid = Grid()
            new_grid.columns = self.columns.copy()
            new_grid._column_id_to_index = self._column_id_to_index.copy()
            start, stop, step = key.indices(len(self.rows))
            new_grid.rows = self.rows[start:stop:step]
            return new_grid
        else:
            raise TypeError(
                "Key must be a string (column name), integer (row index), or slice (row range)"
            )

    @property
    def num_rows(self) -> int:
        """Return the number of rows in the grid."""
        return len(self.rows)

    @property
    def num_columns(self) -> int:
        """Return the number of columns in the grid."""
        return len(self.columns)

    def to_rich_table(self, row_start: int = 0, row_end: int | None = None) -> Table:
        """Convert the grid spec (not calls) to a rich Table for pretty display."""
        table = Table()

        # Add columns to the table
        for col in self.columns:
            if col.type == "int":
                table.add_column(
                    col.display_name, justify="right", header_style="bold cyan"
                )
            else:
                table.add_column(col.display_name, header_style="bold cyan")

        # Add rows to the table
        for row_values in self.rows[row_start:row_end]:
            # Convert all values to strings for display
            str_values = [display_value(val) for val in row_values]
            table.add_row(*str_values)

        return table

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:
        """Show a nicely formatted table in ipython."""
        if cycle:
            p.text("Grid(...)")
        else:
            p.text(self.to_rich_table_str())

    def to_rich_table_str(self) -> str:
        table = self.to_rich_table()
        return pydantic_util.table_to_str(table)

    def show(self, rows_per_page: int | None = None) -> None:
        height = get_terminal_height()
        if self.num_rows < height:
            print(self.to_rich_table_str())
            return

        height -= 2  # Adjust for pagination and navigation instructions

        if rows_per_page is None:
            # Make rows_per_page a multiple of 5 with a minimum value of 5
            rows_per_page = max(5, (height // 5) * 5)
        page = 0
        total_pages = (self.num_rows // rows_per_page) + (
            1 if self.num_rows % rows_per_page else 0
        )

        console = Console()
        while True:
            console.clear()
            console.print(f"Page {page + 1}/{total_pages}", style="bold magenta")
            paginated_table = self.to_rich_table(
                page * rows_per_page, (page + 1) * rows_per_page
            )
            console.print(paginated_table)
            console.print(
                "\nUse ← (left) / → (right) to navigate, 'q' to quit",
                style="bold yellow",
            )

            key = get_key()
            if key == "\x1b[C" and page < total_pages - 1:  # Right arrow key
                page += 1
            elif key == "\x1b[D" and page > 0:  # Left arrow key
                page -= 1
            elif key.lower() == "q":  # Quit on 'q'
                break

    # TODO: Add additional methods for converting to CSV/TSV/JSON?

    def to_pandas(self) -> pd.DataFrame:
        """Convert the grid contents to a pandas DataFrame.

        Returns:
            A pandas DataFrame containing all the data from the grid.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to use this method")

        # Create a DataFrame directly from the grid data
        data: dict[str, list[Any]] = {col.id: [] for col in self.columns}

        # Populate the data dictionary with values from each row
        for row_values in self.rows:
            for i, col in enumerate(self.columns):
                data[col.id].append(row_values[i] if i < len(row_values) else None)

        return pd.DataFrame(data)

    @classmethod
    def from_pandas(cls, df: pd.DataFrame) -> Grid:
        """Create a Grid from a pandas DataFrame.

        Args:
            df: The pandas DataFrame to convert to a Grid

        Returns:
            A Grid instance containing the data from the DataFrame
        """
        grid = cls()

        # Add columns based on DataFrame columns
        for col_name in df.columns:
            # Try to determine column type
            col_type: ColumnType | None = None
            if df[col_name].dtype == "int64":
                col_type = "int"

            grid.add_column(str(col_name), type=col_type)

        # Add rows from DataFrame
        for _, row in df.iterrows():
            values = []
            for col in df.columns:
                values.append(row[col])
            grid.add_row(values)

        return grid

    @classmethod
    def load_csv(cls, file_path: str | os.PathLike, **kwargs: Any) -> Grid:
        """Create a Grid from a CSV file.

        Args:
            file_path: Path to the CSV file
            **kwargs: Additional arguments to pass to csv.reader (like delimiter, quotechar)

        Returns:
            A Grid instance containing the data from the CSV file

        Raises:
            FileNotFoundError: If the file does not exist
        """
        grid = cls()

        with open(file_path, newline="", encoding="utf-8") as csv_file:
            reader = csv.reader(csv_file, **kwargs)
            # Read header row for column names
            try:
                header = next(reader)
            except StopIteration:
                # Empty file
                return grid

            # Add columns based on header
            for col_name in header:
                grid.add_column(col_name)

            # Process data rows
            for row in reader:
                # Try to infer types for the first data row
                # TODO: Maybe should consider first N rows to infer types?
                if len(grid.rows) == 0:
                    # TODO: Ability to infer bool
                    for i, value in enumerate(row):
                        # Try to convert to int
                        try:
                            int(value)
                            # If successful, update column type to int
                            if i < len(grid.columns):
                                grid.columns[i].type = "int"
                        except (ValueError, TypeError):
                            pass

                # Add the row data
                processed_row: RowValues = []
                for i, value in enumerate(row):
                    # Convert to int if the column type is int
                    if i < len(grid.columns) and grid.columns[i].type == "int":
                        try:
                            processed_row.append(int(value) if value else None)
                        except (ValueError, TypeError):
                            processed_row.append(None)
                    else:
                        processed_row.append(value)

                # Pad row if needed
                while len(processed_row) < len(grid.columns):
                    processed_row.append(None)

                grid.add_row(processed_row)

        return grid
