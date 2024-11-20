from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from weave.trace.refs import TableRef


class Table:
    ref: TableRef | None

    def __init__(self, rows: list[dict]) -> None:
        if not isinstance(rows, list):
            try:
                import pandas as pd

                if isinstance(rows, pd.DataFrame):
                    rows = rows.to_dict(orient="records")
            except ImportError:
                pass
        self._validate_rows(rows)
        self._rows = rows
        self.ref = None

    def _validate_rows(self, rows: Any) -> None:
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("Rows must be a list of dicts")

    @property
    def rows(self) -> list[dict]:
        return self._rows

    @rows.setter
    def rows(self, value: list[dict]) -> None:
        self._validate_rows(value)
        self._rows = value

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, key: int) -> dict:
        return self.rows[key]

    def __iter__(self) -> Iterator:
        return iter(self.rows)

    def __eq__(self, other: Any) -> bool:
        return self.rows == other

    def append(self, row: dict) -> None:
        """Add a row to the table."""
        if not isinstance(row, dict):
            raise TypeError("Can only append dicts to tables")
        self.rows.append(row)

    def pop(self, index: int) -> None:
        """Remove a row at the given index from the table."""
        self.rows.pop(index)
