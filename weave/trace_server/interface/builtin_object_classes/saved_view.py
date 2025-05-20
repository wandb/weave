from typing import Optional, Union

from pydantic import BaseModel, Field

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface.builtin_object_classes import base_object_def

PathElement = Union[str, int]


class Pin(BaseModel):
    left: list[str]
    right: list[str]


class Column(BaseModel):
    # Optional in case we want something like computed columns in the future.
    path: Optional[list[PathElement]] = Field(default=None)
    label: Optional[str] = Field(default=None)


class SavedViewDefinition(BaseModel):
    filter: Optional[tsi.CallsFilter] = Field(default=None)

    query: Optional[tsi.Query] = Field(default=None)

    # cols is the current UI column visibility config that
    # doesn't allow specifying column order - prefer use of
    # explicit columns list which is what we should work towards.
    cols: Optional[dict[str, bool]] = Field(default=None)

    # columns is specifying exactly which columns to include
    # including order.
    columns: Optional[list[Column]] = Field(default=None)

    pin: Optional[Pin] = Field(default=None)
    sort_by: Optional[list[tsi.SortBy]] = Field(default=None)
    page_size: Optional[int] = Field(default=None)


class SavedView(base_object_def.BaseObject):
    # "traces" or "evaluations", type is str for extensibility
    view_type: str

    # Avoiding confusion around object_id + name
    label: str

    definition: SavedViewDefinition


__all__ = ["SavedView"]
