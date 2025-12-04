from pydantic import BaseModel

from weave.trace_server.interface.builtin_object_classes import base_object_def


class LeaderboardColumn(BaseModel):
    evaluation_object_ref: base_object_def.RefStr
    scorer_name: str
    summary_metric_path: str
    should_minimize: bool | None = None


# class FilterAndGroupSourceEvaluationSpec(BaseModel):
#     name: str
#     version: str  # "*" means all
#
#
# class FilterAndGroupDatasetScorerMetricSpec(BaseModel):
#     path: str  # "*" means all
#     should_minimize: bool | None = None
#
#
# class FilterAndGroupDatasetScorerSpec(BaseModel):
#     name: str  # "*" means all
#     version: str  # "*" means all
#     group_all_versions: bool | None = None
#     metrics: list[FilterAndGroupDatasetScorerMetricSpec] | None = None  # None means all
#
#
# class FilterAndGroupDatasetSpec(BaseModel):
#     name: str  # "*" means all
#     version: str  # "*" means all
#     group_all_versions: bool | None = None
#     scorers: list[FilterAndGroupDatasetScorerSpec] | None = None  # None means all
#
#
# class FilterAndGroupModelSpec(BaseModel):
#     name: str  # "*" means all
#     version: str  # "*" means all
#     group_all_versions: bool | None = None
#
#
# class FilterAndGroupSpec(BaseModel):
#     source_evaluations: list[FilterAndGroupSourceEvaluationSpec] | None = None  # None means all
#     datasets: list[FilterAndGroupDatasetSpec] | None = None  # None means all
#     models: list[FilterAndGroupModelSpec] | None = None  # None means all


class Leaderboard(base_object_def.BaseObject):
    columns: list[LeaderboardColumn] # For legacy leaderboards
    calls_query: str | None = None  # The query used by the UI to filter rows. If none, use all entries

