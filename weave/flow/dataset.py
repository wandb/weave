from typing import Union, Any

from pydantic import field_validator
import weave

from weave.flow.obj import Object


class Dataset(Object):
    rows: weave.Table

    @field_validator("rows", mode="before")
    def convert_to_table(cls, rows: Any) -> weave.Table:
        if not isinstance(rows, weave.Table):
            return weave.Table(rows)
        return rows
