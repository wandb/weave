from enum import Enum

from pydantic import BaseModel

from weave.trace_server.interface.builtin_object_classes import base_object_def


class ColorScheme(str, Enum):
    DIVERGING = "diverging"
    SEQUENTIAL = "sequential"
    CATEGORICAL = "categorical"


class GroupingStrategy(str, Enum):
    MODEL = "model"
    DATASET = "dataset"
    SCORER = "scorer"


class ScoreSelectionStrategy(str, Enum):
    LATEST = "latest"
    AVERAGE = "average"
    MANUAL = "manual"


class AggregationMethod(str, Enum):
    LATEST = "latest"
    AVERAGE = "average"
    MAX = "max"
    MIN = "min"


class MetricConfig(BaseModel):
    dataset_name: str  # "*" to match all datasets
    scorer_name: str  # "*" to match all scorers
    metric_path: str  # "*" to match all metric paths
    should_minimize: bool
    selected: bool
    # Wildcard matching rules:
    # - dataset_name="*" applies to all datasets with matching scorer_name and metric_path
    # - scorer_name="*" applies to all scorers with matching dataset_name and metric_path
    # - metric_path="*" applies to all metric paths with matching dataset_name and scorer_name
    # - Any combination of wildcards can be used (e.g., "*", "*", "true_count" matches all datasets/scorers with metric "true_count")
    # This ensures configurations automatically apply to new evaluation runs


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
    # Legacy fields
    columns: list[LeaderboardColumn]  # For legacy leaderboards
    calls_query: str | None = None  # The query used by the UI to filter rows. If none, use all entries

    # New configuration fields
    color_scheme: ColorScheme | None = None
    grouping_by: GroupingStrategy | None = None

    # Model configuration
    models_use_version_grouping: bool | None = None
    models_show_version_indicator: bool | None = None
    selected_models: list[str] | None = None  # List of model refs or patterns (can use "*" for wildcard matching)
    model_display_names: dict[str, str] | None = None  # ref/pattern -> display name (keys can use "*" wildcards)

    # Dataset/Scorer configuration
    datasets_use_version_grouping: bool | None = None
    datasets_show_version_indicator: bool | None = None
    dataset_display_names: dict[str, str] | None = None  # ref/pattern -> display name (keys can use "*" wildcards)
    dataset_version_aggregation: AggregationMethod | None = None
    score_selection_strategy: ScoreSelectionStrategy | None = None
    manual_version_selections: dict[str, str] | None = None  # entity_ref -> selected version digest

    # Metric configuration
    # Use wildcards ("*") in MetricConfig fields to apply configs to multiple entries
    # This ensures new evaluation runs automatically inherit the configuration
    metric_configs: list[MetricConfig] | None = None

