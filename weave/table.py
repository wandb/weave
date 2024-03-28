import typing


class Table:
    def __init__(self, rows: typing.List) -> None:
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

    def __iter__(self) -> typing.Iterator:
        return iter(self.rows)
