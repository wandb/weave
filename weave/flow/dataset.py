from typing import Any

from pydantic import field_validator
import weave

from weave.flow.obj import Object
from weave.trace.vals import TraceTable


def short_str(obj: Any, limit: int = 25) -> str:
    str_val = str(obj)
    if len(str_val) > limit:
        return str_val[:limit] + "..."
    return str_val


class Dataset(Object):
    """Datasets enable you to collect examples for evaluation and automatically track versions for accurate comparisons. Easily update datasets with the UI and download the latest version locally with a simple API.

    When constructing a Dataset, you can pass in a list of dictionaries. Each dictionary represents a row in the dataset. The keys of the dictionary represent the column names, and the values represent the data in the row.
    """

    rows: weave.Table

    @field_validator("rows", mode="before")
    def convert_to_table(cls, rows: Any) -> weave.Table:
        if not isinstance(rows, weave.Table):
            table_ref = getattr(rows, "table_ref", None)
            if isinstance(rows, TraceTable):
                rows = list(rows)
            rows = weave.Table(rows)
            if table_ref:
                rows.table_ref = table_ref
        if len(rows.rows) == 0:
            raise ValueError("Attempted to construct a Dataset with an empty list.")
        for row in rows.rows:
            if not isinstance(row, dict):
                raise ValueError(
                    "Attempted to construct a Dataset with a non-dict object. Found type: "
                    + str(type(row))
                    + " of row: "
                    + short_str(row)
                )
            if len(row) == 0:
                raise ValueError(
                    "Attempted to construct a Dataset row with an empty dict."
                )
        return rows
