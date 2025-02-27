from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from weave.trace.traverse import PathElement
from weave.trace_server.interface.builtin_object_classes import base_object_def

# Compare with definitions in weave/trace_server/trace_server_interface.py


class CallsFilter(BaseModel):
    op_names: Optional[list[str]] = None
    input_refs: Optional[list[str]] = None
    output_refs: Optional[list[str]] = None
    parent_ids: Optional[list[str]] = None
    trace_ids: Optional[list[str]] = None
    call_ids: Optional[list[str]] = None
    trace_roots_only: Optional[bool] = None
    wb_user_ids: Optional[list[str]] = None
    wb_run_ids: Optional[list[str]] = None


class Filter(BaseModel):
    id: int
    field: str
    # Type of operator could be locked down more, but this is better for extensibility
    operator: str
    value: Any


class Filters(BaseModel):
    items: list[Filter] = []
    logicOperator: Literal["and"] = "and"


class Pin(BaseModel):
    # TODO: Make them optional? But one is required?
    left: list[str]
    right: list[str]


SortDirection = Literal["asc", "desc"]


# Note: This is intentionally similar to `SortBy` in `trace_server_interface.py`
# but duplicating because logically it shouldn't need to match the API interface.
class SortBy(BaseModel):
    # Field should be a key of `CallSchema`. For dictionary fields
    # (`attributes`, `inputs`, `outputs`, `summary`), the field can be
    # dot-separated.
    field: str
    direction: SortDirection


class Column(BaseModel):
    # Optional in case we want something like computed columns in the future.
    path: Optional[list[PathElement]] = Field(default=None)
    label: Optional[str] = Field(default=None)


class SavedViewDefinition(BaseModel):
    filter: Optional[CallsFilter] = Field(default=None)
    filters: Optional[Filters] = Field(default=None)

    # cols is legacy column visibility config
    cols: Optional[dict[str, bool]] = Field(default=None)

    # columns is specifying exactly which columns to include
    # including order.
    columns: Optional[list[Column]] = Field(default=None)

    pin: Optional[Pin] = Field(default=None)
    sort: Optional[list[SortBy]] = Field(default=None)
    page_size: Optional[int] = Field(default=None)


class SavedView(base_object_def.BaseObject):
    # TODO: Should we have a spec_version literal?

    # "traces" or "evaluations", type is str for extensibility
    table: str

    # Avoiding confusion around object_id + name
    label: str

    definition: SavedViewDefinition


__all__ = ["SavedView"]
