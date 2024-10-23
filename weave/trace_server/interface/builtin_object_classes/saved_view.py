from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from weave.trace_server.interface.builtin_object_classes import base_object_def


class LegacyFilter(BaseModel):
    op_version_refs: Optional[list[str]] = Field(default=None)
    input_object_version_refs: Optional[list[str]] = Field(default=None)
    output_object_version_refs: Optional[list[str]] = Field(default=None)


class Filter(BaseModel):
    id: int
    field: str
    # Type of operator could be locked down more, but this is better for extensibility
    operator: str
    value: Any


class Filters(BaseModel):
    items: list[Filter]
    logicOperator: Literal["and"]


class Pin(BaseModel):
    # TODO: Make them optional? But one is required?
    left: list[str]
    right: list[str]


SortDirection = Literal["asc", "desc"]


class SortClause(BaseModel):
    field: str
    sort: SortDirection


class SavedViewDefinition(BaseModel):
    filter: Optional[LegacyFilter] = Field(default=None)
    filters: Optional[Filters] = Field(default=None)
    cols: Optional[dict[str, bool]] = Field(default=None)
    pin: Optional[Pin] = Field(default=None)
    sort: Optional[list[SortClause]] = Field(default=None)
    page_size: Optional[int] = Field(default=None)


class SavedView(base_object_def.BaseObject):
    # "traces" or "evaluations"
    table: str

    # Avoiding confusion around object_id + name
    label: str

    definition: SavedViewDefinition


__all__ = ["SavedView"]
