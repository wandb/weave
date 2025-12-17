from enum import Enum

from pydantic import BaseModel

from weave.trace_server.interface.builtin_object_classes import base_object_def
from typing import Literal


class AggregationMethod(str, Enum):
    LATEST = "latest"
    AVERAGE = "average"


class ObjectVersionGroup(BaseModel):
    label: str  # label for the combination of the groups
    base_ref: str
    versions: list[str] | Literal["*"]
    show_version_indicator: bool
    method: AggregationMethod


class ObjectConfig(BaseModel):
    version_groups: list[ObjectVersionGroup]
    display_name_map: dict[str, str]  # ref/name -> display name (keys can use "*" wildcards)
    deselected: list[str]  # List of dataset refs or patterns to exclude (can use "*" for wildcard matching)


class DynamicLeaderboardColumnConfig(BaseModel):
    evaluation_object_ref: base_object_def.RefStr
    scorer_name: str
    summary_metric_path: str
    should_minimize: bool
    deselected: bool  # If True, this metric is excluded from the leaderboard


class DynamicLeaderboard(base_object_def.BaseObject):
    calls_query: str
    model_configuration: ObjectConfig
    dataset_configuration: ObjectConfig
    scorer_configuration: ObjectConfig
    columns_configuration: list[DynamicLeaderboardColumnConfig]  # Empty by default
