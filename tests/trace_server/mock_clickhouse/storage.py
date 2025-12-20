"""In-memory storage for mock ClickHouse backend."""

from __future__ import annotations

import copy
import threading
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TableSchema:
    """Schema definition for a table."""

    name: str
    columns: list[str] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)


@dataclass
class Table:
    """Represents a table with its data."""

    name: str
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)

    def get_column_index(self, column_name: str) -> int:
        """Get the index of a column by name."""
        try:
            return self.columns.index(column_name)
        except ValueError:
            raise KeyError(f"Column '{column_name}' not found in table '{self.name}'")

    def insert(self, data: Sequence[Sequence[Any]], column_names: list[str]) -> int:
        """Insert rows into the table.

        Args:
            data: List of rows, each row is a list of values
            column_names: Names of the columns being inserted

        Returns:
            Number of rows inserted
        """
        # Ensure all columns exist in the table
        for col in column_names:
            if col not in self.columns:
                self.columns.append(col)

        # Build a mapping from column_names to table column indices
        col_indices = [self.columns.index(col) for col in column_names]

        for row_data in data:
            # Create a new row with None for all columns
            new_row: list[Any] = [None] * len(self.columns)
            # Fill in the values at the correct positions
            for idx, col_idx in enumerate(col_indices):
                new_row[col_idx] = row_data[idx]
            self.rows.append(new_row)

        return len(data)


class MockClickHouseStorage:
    """In-memory storage that simulates ClickHouse databases and tables."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._databases: dict[str, dict[str, Table]] = {}
        self._current_database: str = "default"
        # Create default database
        self._databases["default"] = {}

    @property
    def current_database(self) -> str:
        """Get the current database name."""
        return self._current_database

    @current_database.setter
    def current_database(self, value: str) -> None:
        """Set the current database name."""
        with self._lock:
            self._current_database = value

    def create_database(self, name: str, if_not_exists: bool = True) -> None:
        """Create a new database."""
        with self._lock:
            if name in self._databases:
                if not if_not_exists:
                    raise ValueError(f"Database '{name}' already exists")
                return
            self._databases[name] = {}

    def drop_database(self, name: str, if_exists: bool = True) -> None:
        """Drop a database."""
        with self._lock:
            if name not in self._databases:
                if not if_exists:
                    raise ValueError(f"Database '{name}' does not exist")
                return
            del self._databases[name]

    def get_database(self, name: str | None = None) -> dict[str, Table]:
        """Get a database by name, or the current database if not specified."""
        db_name = name or self._current_database
        if db_name not in self._databases:
            raise ValueError(f"Database '{db_name}' does not exist")
        return self._databases[db_name]

    def create_table(
        self,
        name: str,
        columns: list[str] | None = None,
        if_not_exists: bool = True,
        database: str | None = None,
    ) -> None:
        """Create a new table in the current database."""
        with self._lock:
            db = self.get_database(database)
            if name in db:
                if not if_not_exists:
                    raise ValueError(f"Table '{name}' already exists")
                return
            db[name] = Table(name=name, columns=columns or [])

    def drop_table(
        self, name: str, if_exists: bool = True, database: str | None = None
    ) -> None:
        """Drop a table from the current database."""
        with self._lock:
            db = self.get_database(database)
            if name not in db:
                if not if_exists:
                    raise ValueError(f"Table '{name}' does not exist")
                return
            del db[name]

    def get_table(self, name: str, database: str | None = None) -> Table:
        """Get a table by name."""
        db = self.get_database(database)
        if name not in db:
            raise ValueError(f"Table '{name}' does not exist in database")
        return db[name]

    def insert(
        self,
        table_name: str,
        data: Sequence[Sequence[Any]],
        column_names: list[str],
        database: str | None = None,
    ) -> int:
        """Insert data into a table.

        Args:
            table_name: Name of the table
            data: List of rows to insert
            column_names: Column names for the data
            database: Database name (uses current if not specified)

        Returns:
            Number of rows inserted
        """
        with self._lock:
            # Auto-create table if it doesn't exist
            try:
                table = self.get_table(table_name, database)
            except ValueError:
                self.create_table(table_name, columns=column_names, database=database)
                table = self.get_table(table_name, database)

            return table.insert(data, column_names)

    def query(
        self,
        table_name: str,
        columns: list[str] | None = None,
        where: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> list[tuple]:
        """Simple query interface for testing.

        Args:
            table_name: Name of the table to query
            columns: Columns to select (all if None)
            where: Simple equality conditions
            database: Database name (uses current if not specified)

        Returns:
            List of matching rows as tuples
        """
        with self._lock:
            table = self.get_table(table_name, database)

            # Get column indices for selection
            if columns:
                col_indices = [table.get_column_index(c) for c in columns]
            else:
                col_indices = list(range(len(table.columns)))

            results: list[tuple] = []
            for row in table.rows:
                # Apply where conditions
                if where:
                    match = True
                    for col_name, expected_value in where.items():
                        col_idx = table.get_column_index(col_name)
                        if row[col_idx] != expected_value:
                            match = False
                            break
                    if not match:
                        continue

                # Select requested columns
                selected = tuple(row[i] for i in col_indices)
                results.append(selected)

            return results

    def query_stream(
        self,
        table_name: str,
        columns: list[str] | None = None,
        where: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> Iterator[tuple]:
        """Stream query results."""
        results = self.query(table_name, columns, where, database)
        yield from results

    def clear(self) -> None:
        """Clear all data from all databases."""
        with self._lock:
            for db in self._databases.values():
                for table in db.values():
                    table.rows.clear()

    def reset(self) -> None:
        """Reset to initial state with only the default database."""
        with self._lock:
            self._databases.clear()
            self._databases["default"] = {}
            self._current_database = "default"

    def get_all_rows(
        self, table_name: str, database: str | None = None
    ) -> list[dict[str, Any]]:
        """Get all rows from a table as dictionaries.

        This is a convenience method for testing that returns rows
        as dictionaries with column names as keys.
        """
        with self._lock:
            table = self.get_table(table_name, database)
            return [dict(zip(table.columns, row)) for row in table.rows]
