"""Persisted "saved views" for the Agents panel.

This is the agents-panel analogue of `saved_view.SavedView`. The calls/evals
`SavedView` is deliberately call-table shaped (its definition is built around
`CallsFilter`, expandable ref columns, leaderboards, ...), so rather than bolt
mutually-exclusive agents fields onto it we model agents views with their own
builtin object class. Both classes are persisted through the same generic
`obj_create` / `obj_read` / `objs_query` endpoints — no agents-specific server
endpoint is involved.

The agents panel keeps its working state in the URL as a per-tab "diff from
default" (see `agentsUrlState.ts`). That works until the diff grows large
(many custom columns, a tuned time window, a long filter set), at which point
the URL becomes unwieldy and unshareable. A saved view persists that per-tab
configuration to the backend so it can be named, reloaded, and shared by a
short id instead of an exploding query string.

Backend is intentionally decoupled from the UI's tab structure. Mirroring the
calls `SavedView` (whose `view_type` is a free-form `str` "for extensibility"),
`tab` here is a plain string and `definition` is a single flat, all-optional
superset of every tab's fields. The set of tabs and which fields are valid for
each one live entirely in the frontend, which enforces them with a zod
discriminated union on `tab`. So adding, renaming, or removing a tab — or a
future dashboard tab — is a frontend-only change and never touches this schema.
Type-safety note: this module is the source of truth for field *shapes*;
`scripts/generate_base_object_schemas.py` turns it into JSON schema, which the
frontend compiles into zod leaf types.

What is (and isn't) persisted: a saved view captures the *configuration* of a
tab — filters, sort, numeric ranges, time window, column visibility, custom
columns, view mode — mirroring `agentsUrlState`'s tab-scoped params. It does
not capture transient navigation (the selected agent, a highlighted message,
chat pagination); those stay in the URL only, the same way the calls
`SavedView` persists filters/columns/sort but not the selected row.
"""

from typing import Literal

from pydantic import BaseModel, Field

from weave.trace_server.interface.builtin_object_classes import base_object_def

SortDirection = Literal["asc", "desc"]

# Layout of a table tab: `table` is the full-width grid, `split` puts a chart
# canvas alongside it. Mirrors `AgentTableView` in `agentsUrlState.ts`.
TableViewMode = Literal["table", "split"]

# Time-window units, mirroring `TimeWindowUnit` on the frontend.
TimeWindowUnit = Literal["second", "minute", "hour", "day", "week"]

# Aggregation modes a conversations-tab custom-attribute column can take,
# mirroring `CONVERSATION_CUSTOM_ATTR_MODES` in `agentsUrlState.ts`.
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
    """A single sort directive: a field and a direction.

    Field name (rather than `sort_by`) and the `sort` key match the frontend
    `AgentsSort` shape so the URL-state layer can round-trip it directly.
    """

    field: str
    sort: SortDirection


class ColsDiff(BaseModel):
    """Column-visibility diff from a tab's default hidden set.

    Mirrors the URL representation: `hide` lists columns hidden beyond the
    defaults, `show` lists default-hidden columns the user re-enabled. Storing
    the diff (not an absolute hidden list) keeps a saved view resilient to
    later changes in the page's default columns. Also used for the agents-tab
    `hidden_agents` selection, which is the same hide/show diff shape.
    """

    hide: list[str] = Field(default_factory=list)
    show: list[str] = Field(default_factory=list)


class NumericRange(BaseModel):
    """Inclusive `[min, max]` range for a numeric histogram filter."""

    min: float
    max: float


class TimeWindowSelection(BaseModel):
    """A brushed sub-selection within a time window, in epoch milliseconds."""

    start_ms: int
    end_ms: int


class TimeWindow(BaseModel):
    """The active time window for a tab, in epoch milliseconds.

    `unit` + `quantity` describe the window size (e.g. 24 hours); `start_ms`
    pins its left edge; `selection` is an optional brushed sub-range. Mirrors
    `TimeWindowState` on the frontend.
    """

    unit: TimeWindowUnit
    quantity: int = Field(ge=1)
    start_ms: int
    selection: TimeWindowSelection | None = None


class ConversationCustomAttr(BaseModel):
    """A conversations-tab custom-attribute column selection.

    `attr_id` is the `<source>:<key>` id used elsewhere in the agents panel;
    `mode` is how the column is aggregated across a conversation.
    """

    attr_id: str
    mode: ConversationCustomAttrMode


class AgentsSavedViewDefinition(BaseModel):
    """Flat, all-optional configuration for one agents-panel tab.

    Mirrors the calls `SavedViewDefinition`: a single superset bag whose fields
    are populated per tab by the frontend, rather than a backend-side
    discriminated union. The backend validates field *shapes*; the frontend
    enforces which fields are valid for which `tab`.
    """

    # Which agents-panel tab this view configures (e.g. "spans",
    # "conversations", "agents"). Free-form on purpose — like calls
    # `view_type`, the set of tabs is owned by the frontend so it can change
    # without a backend change.
    tab: str

    # --- shared table-tab config (spans, conversations) ---
    time_window: TimeWindow | None = Field(default=None)
    sort: ViewSort | None = Field(default=None)
    # Categorical filters keyed by column id (e.g. `agent_name`).
    filters: dict[str, str] | None = Field(default=None)
    # Numeric histogram filters keyed by column id.
    numeric_ranges: dict[str, NumericRange] | None = Field(default=None)
    cols: ColsDiff | None = Field(default=None)
    # Custom-attribute column ids added to the grid (`<source>:<key>`).
    custom_cols: list[str] | None = Field(default=None)
    view: TableViewMode | None = Field(default=None)
    # Whether the page-wide volume histogram is collapsed.
    volume_collapsed: bool | None = Field(default=None)

    # --- conversations tab ---
    conv_custom_attrs: list[ConversationCustomAttr] | None = Field(default=None)

    # --- agents list tab ---
    sort_field: str | None = Field(default=None)
    # Diff (hide/show) from the default set of excluded agents.
    hidden_agents: ColsDiff | None = Field(default=None)


class AgentsSavedView(base_object_def.BaseObject):
    """A persisted, named configuration of one agents-panel tab.

    Persisted as a generic Weave object (`builtin_object_class="AgentsSavedView"`)
    via `obj_create` / `obj_read` / `objs_query`. The tab lives in
    `definition.tab`, so listing one tab's views = filtering objects of this
    class by `definition.tab`.
    """

    # Human-facing title for the view (object_id is the stable id; label is the
    # editable display name, mirroring calls `SavedView.label`).
    label: str
    definition: AgentsSavedViewDefinition


__all__ = ["AgentsSavedView"]
