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

Type-safety note: this module is the single source of truth for the persisted
shape. `scripts/generate_base_object_schemas.py` turns every registered
builtin object class into JSON schema, which the frontend's
`generate-schemas.sh` compiles into zod (`generatedBuiltinObjectClasses.zod.ts`).
So adding a field here flows automatically into a zod-validated frontend type;
the agents URL-state layer should consume that generated type rather than
re-declaring the shape by hand.

What is (and isn't) persisted: a saved view captures the *configuration* of a
tab — filters, sort, numeric ranges, time window, column visibility, custom
columns, view mode — mirroring `agentsUrlState`'s tab-scoped params. It does
not capture transient navigation (the selected agent, a highlighted message,
chat pagination); those stay in the URL only, the same way the calls
`SavedView` persists filters/columns/sort but not the selected row.

Future dashboards: the dashboard tab is hard-set today, but users will
eventually be able to compose their own dashboards (choose charts, drag/drop,
resize). The discriminated-union-on-`tab` design below is exactly the seam for
that: a `DashboardViewDefinition` member (carrying widget specs + grid
geometry) can be added to `AgentsSavedViewDefinition` later without touching
any existing tab variant or the persistence/codegen plumbing. We intentionally
do not model any dashboard/chart shapes yet.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from weave.trace_server.interface.builtin_object_classes import base_object_def

# The agents-panel tabs that support saved views today. `dashboard` and
# `signals` are intentionally absent: `dashboard` is hard-set pending the
# custom-dashboards work (see the module docstring) and `signals` has no
# user-configurable view state yet. Both slot in as new union members later.
AgentsViewTab = Literal["spans", "conversations", "agents"]

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


class _TableTabViewBase(BaseModel):
    """Shared configuration for the table-style tabs (spans, conversations).

    Holds the subset of `agentsUrlState` that is genuinely *view config*. All
    fields are optional so a saved view stores only the user's diff from the
    tab defaults — an empty definition means "the default view".
    """

    time_window: TimeWindow | None = Field(default=None)
    sort: ViewSort | None = Field(default=None)
    # Categorical filters keyed by column id (e.g. `agent_name`), mirroring the
    # URL `filters` record.
    filters: dict[str, str] | None = Field(default=None)
    # Numeric histogram filters keyed by column id.
    numeric_ranges: dict[str, NumericRange] | None = Field(default=None)
    cols: ColsDiff | None = Field(default=None)
    # Custom-attribute column ids added to the grid (`<source>:<key>`).
    custom_cols: list[str] | None = Field(default=None)
    view: TableViewMode | None = Field(default=None)
    # Whether the page-wide volume histogram is collapsed.
    volume_collapsed: bool | None = Field(default=None)


class SpansViewDefinition(_TableTabViewBase):
    """Saved view for the spans tab."""

    tab: Literal["spans"] = "spans"


class ConversationsViewDefinition(_TableTabViewBase):
    """Saved view for the conversations tab."""

    tab: Literal["conversations"] = "conversations"
    conv_custom_attrs: list[ConversationCustomAttr] | None = Field(default=None)


class AgentsListViewDefinition(BaseModel):
    """Saved view for the agents list tab.

    The agents tab sorts by a single field name (a fixed dropdown), not a
    `{field, dir}` object, and carries a `hidden_agents` diff rather than a
    column-visibility diff — hence its own variant rather than the table base.
    """

    tab: Literal["agents"] = "agents"
    time_window: TimeWindow | None = Field(default=None)
    sort_field: str | None = Field(default=None)
    filters: dict[str, str] | None = Field(default=None)
    numeric_ranges: dict[str, NumericRange] | None = Field(default=None)
    # Diff (hide/show) from the default set of excluded agents.
    hidden_agents: ColsDiff | None = Field(default=None)


# Discriminated on `tab` so each tab gets exactly the fields it can use and so
# new tabs (notably a future `dashboard` variant) can be added without
# disturbing existing members. See the module docstring.
AgentsSavedViewDefinition = Annotated[
    SpansViewDefinition | ConversationsViewDefinition | AgentsListViewDefinition,
    Field(discriminator="tab"),
]


class AgentsSavedView(base_object_def.BaseObject):
    """A persisted, named configuration of one agents-panel tab.

    Persisted as a generic Weave object (`builtin_object_class="AgentsSavedView"`)
    via `obj_create` / `obj_read` / `objs_query`. The active tab lives in
    `definition.tab` (the union discriminator), so listing "all spans views"
    means filtering objects of this class by `definition.tab == "spans"`.
    """

    # Human-facing title for the view (object_id is the stable id; label is the
    # editable display name, mirroring calls `SavedView.label`).
    label: str
    definition: AgentsSavedViewDefinition


__all__ = ["AgentsSavedView"]
