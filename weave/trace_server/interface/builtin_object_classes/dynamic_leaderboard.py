from enum import Enum

from pydantic import BaseModel

from weave.trace_server.interface.builtin_object_classes import base_object_def


class AggregationMethod(str, Enum):
    LATEST = "latest"
    AVERAGE = "average"


class VersionGroup(BaseModel):
    label: str  # label for the combination of the groups
    versions: list[str]  # Digests of the versions to group
    method: AggregationMethod


class ObjectVersionGroup(BaseModel):
    group_mapping: list[
        VersionGroup
    ]  # List of versions of the object to group together. Empty by default
    base_ref: str  # The object ref without a version suffix. Empty by default


class ObjectConfig(BaseModel):
    version_groups: list[ObjectVersionGroup]
    show_version_indicator: bool
    display_name_map: dict[
        str, str
    ]  # ref/name -> display name (keys can use "*" wildcards)
    deselected: list[
        str
    ]  # List of dataset refs or patterns to exclude (can use "*" for wildcard matching)


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
