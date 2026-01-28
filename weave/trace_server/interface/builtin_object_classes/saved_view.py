from typing import Literal

from pydantic import BaseModel, Field

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.common_interface import SortBy
from weave.trace_server.interface.builtin_object_classes import base_object_def

PathElement = str | int


class Pin(BaseModel):
    left: list[str]
    right: list[str]


class Column(BaseModel):
    # Optional in case we want something like computed columns in the future.
    path: list[PathElement] | None = Field(default=None)
    label: str | None = Field(default=None)


class ChartConfig(BaseModel):
    x_axis: str = Field(title="XAxis")
    y_axis: str = Field(title="YAxis")
    plot_type: Literal["scatter", "line", "bar"] | None = Field(
        default=None,
    )
    bin_count: int | None = Field(default=None)
    aggregation: Literal["average", "sum", "min", "max", "p95", "p99"] | None = Field(
        default=None
    )
    group_keys: list[str] | None = Field(default=None)
    custom_name: str | None = Field(default=None)


class ObjectVersionGroup(BaseModel):
    label: str  # label for the combination of the groups
    base_ref: str
    versions: list[str] | Literal["*"]
    show_version_indicator: bool


class ObjectConfig(BaseModel):
    version_groups: list[ObjectVersionGroup] | None = Field(default=None)
    display_name_map: dict[str, str] | None = Field(
        default=None
    )  # obj -> display name (keys can use "*" wildcards)
    deselected: list[str] | None = Field(
        default=None
    )  # List of dataset refs or patterns to exclude


class DynamicLeaderboardColumnConfig(BaseModel):
    evaluation_object_ref: base_object_def.RefStr | None = Field(default=None)
    scorer_name: str | None = Field(default=None)
    display_name: str | None = Field(default=None)
    summary_metric_path: str | None = Field(default=None)
    should_minimize: bool | None = Field(default=None)
    deselected: bool | None = Field(
        default=None
    )  # If True, this metric is excluded from the leaderboard


class DynamicLeaderboardConfig(BaseModel):
    # These are initialized to empty lists and dicts by default (show everything)
    model_configuration: ObjectConfig | None = Field(default=None)
    dataset_configuration: ObjectConfig | None = Field(default=None)
    scorer_configuration: ObjectConfig | None = Field(default=None)
    # Only has entries when a column is marked as deselected or minimized
    columns_configuration: list[DynamicLeaderboardColumnConfig] | None = Field(
        default=None
    )


class SavedViewDefinition(BaseModel):
    filter: tsi.CallsFilter | None = Field(default=None)

    query: tsi.Query | None = Field(default=None)

    # cols is the current UI column visibility config that
    # doesn't allow specifying column order - prefer use of
    # explicit columns list which is what we should work towards.
    cols: dict[str, bool] | None = Field(default=None)

    # columns is specifying exactly which columns to include
    # including order.
    columns: list[Column] | None = Field(default=None)
    header_depth: int | None = Field(default=None)

    pin: Pin | None = Field(default=None)
    sort_by: list[SortBy] | None = Field(default=None)
    page: int | None = Field(default=None)
    page_size: int | None = Field(default=None)
    charts: list[ChartConfig] | None = Field(default=None)

    # Evaluations calls table has dataset and evaluation object
    # selectors that can be used to filter down evals to those using these objects.
    # The selector is an object ref where the version can either be a digest or `*`
    # to match all versions.
    dataset_selector: str | None = Field(default=None)
    evaluation_selector: str | None = Field(default=None)

    # Dynamic leaderboards are populated by the evals in a saved view
    dynamic_leaderboard_config: DynamicLeaderboardConfig | None = Field(default=None)


class SavedView(base_object_def.BaseObject):
    # "traces" or "evaluations", type is str for extensibility
    view_type: str

    # Avoiding confusion around object_id + name
    label: str

    definition: SavedViewDefinition


__all__ = ["SavedView"]
