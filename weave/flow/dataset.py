from typing import Any

from pydantic import field_validator
import weave

from weave.flow.obj import Object
from weave.trace.vals import TraceTable


class Dataset(Object):
    rows: weave.Table

    @field_validator("rows", mode="before")
    def convert_to_table(cls, rows: Any) -> weave.Table:
        if not isinstance(rows, weave.Table):
            if isinstance(rows, TraceTable):
                rows = list(rows)
            return weave.Table(rows)
        return rows
