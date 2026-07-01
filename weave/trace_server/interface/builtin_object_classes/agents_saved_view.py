"""Saved views for the Agents panel: a generic Weave object with a free-form
`view_type` and a flat, all-optional `definition`.
"""

from typing import Literal

from pydantic import BaseModel, Field

from weave.trace_server.interface.builtin_object_classes import base_object_def

SortDirection = Literal["asc", "desc"]
TableViewMode = Literal["table", "split"]
TimeWindowUnit = Literal["second", "minute", "hour", "day", "week"]
ConversationCustomAttrMode = Literal[
    "distribution",
    "avg",
    "min",
    "max",
    "count",
    "count_true",
    "count_false",
    "count_distinct",
]


class ViewSort(BaseModel):
    field: str
    sort: SortDirection


class ColsDiff(BaseModel):
    """Column-visibility diff from a view's default hidden set."""

    hide: list[str] = Field(
        default_factory=list, description="Columns hidden beyond the defaults."
    )
    show: list[str] = Field(
        default_factory=list,
        description="Default-hidden columns the user re-enabled.",
    )


class NumericRange(BaseModel):
    min: float
    max: float


class TimeWindowSelection(BaseModel):
    start_ms: int
    end_ms: int


class TimeWindow(BaseModel):
    unit: TimeWindowUnit
    quantity: int = Field(ge=1, description="Number of units in the window.")
    start_ms: int = Field(description="Left edge of the window, epoch ms.")
    selection: TimeWindowSelection | None = Field(
        default=None, description="Optional brushed sub-range."
    )


class ConversationCustomAttr(BaseModel):
    attr_id: str = Field(description="The `<source>:<key>` custom-attribute id.")
    mode: ConversationCustomAttrMode = Field(
        description="How the attribute is aggregated across a conversation."
    )


class AgentsSavedViewDefinition(BaseModel):
    """Flat, all-optional config for one agents-panel view (per `view_type`)."""

    view_type: str = Field(
        description="Which view this configures (e.g. 'spans'). Free-form; the "
        "set of views is owned by the frontend, so it can change without a "
        "backend change."
    )
    time_window: TimeWindow | None = Field(
        default=None, description="Active time window."
    )
    sort: ViewSort | None = Field(default=None, description="Sort directive.")
    filters: dict[str, str] | None = Field(
        default=None, description="Categorical filters keyed by column id."
    )
    numeric_ranges: dict[str, NumericRange] | None = Field(
        default=None, description="Numeric histogram filters keyed by column id."
    )
    cols: ColsDiff | None = Field(default=None, description="Column-visibility diff.")
    custom_cols: list[str] | None = Field(
        default=None,
        description="Custom-attribute column ids (`<source>:<key>`) on the grid.",
    )
    view: TableViewMode | None = Field(
        default=None, description="Table layout (full table vs split chart view)."
    )
    volume_collapsed: bool | None = Field(
        default=None, description="Whether the volume histogram is collapsed."
    )
    conv_custom_attrs: list[ConversationCustomAttr] | None = Field(
        default=None,
        description="Conversations view: custom-attribute column selections.",
    )
    sort_field: str | None = Field(
        default=None, description="Agents view: single sort field."
    )
    hidden_agents: ColsDiff | None = Field(
        default=None,
        description="Agents view: diff from the default excluded-agents set.",
    )


class AgentsSavedView(base_object_def.BaseObject):
    """A persisted, named configuration of one agents-panel view."""

    label: str = Field(description="Editable display name for the view.")
    definition: AgentsSavedViewDefinition


__all__ = ["AgentsSavedView"]
