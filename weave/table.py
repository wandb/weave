from typing import Iterator, Optional

from weave.trace.refs import TableRef


class Table:
    ref: Optional[TableRef]

    def __init__(self, rows: list) -> None:
        if not isinstance(rows, list):
            try:
                import pandas as pd

                if isinstance(rows, pd.DataFrame):
                    rows = rows.to_dict(orient="records")
            except ImportError:
                pass
        if not isinstance(rows, list):
            raise ValueError(
                "Attempted to construct a Table with a non-list object. Found: "
                + str(type(rows))
            )
        self.rows = rows
        self.ref = None

    def __getitem__(self, key: int) -> dict:
        return self.rows[key]

    def __iter__(self) -> Iterator:
        return iter(self.rows)
