from enum import Enum

from pydantic import BaseModel

from weave.trace_server.interface.builtin_object_classes import base_object_def

"""
Data Model:
    inputs:
        inputs.model
            inputs.model.self
                Model Ref
            inputs.model.name: optional? (str)
            inputs.model.predict: Predict ref
        inputs.self: eval ref
        inputs.self.name: eval name
        inputs.self.dataset: dataset ref
        inputs.self.dataset.name: name (str)
        inputs.self.dataset.rows: rows (dataset ref)
        inputs.self.scorers: array of scorer refs (EMPTY IN IMPERATIVE EVALS)
        inputs.self.evaluate: Op ref - Evaluation.evaluate (EMPTY IN IMPERATIVE EVALS)
        inputs.self.predict_and_score : Op ref - Evaluation.predict_and_score (EMPTY IN IMPERATIVE EVALS)
        inputs.
    output:
        each key under output is either:
            A scorer name (imperative eval)
        each scorer 

What is a leaderboard:

each row is represented by a model
each column is an eval object
each eval object contains:
    dataset
    scorers (not for imperative evals)
    scorers contain metrics 
"""


class AggregationMethod(str, Enum):
    LATEST = "latest"
    AVERAGE = "average"


class VersionGroup(BaseModel):
    label: str  # label for the combination of the groups
    versions: list[str]
    method: AggregationMethod


class ObjectVersionGroups(BaseModel):
    group_mapping: list[
        VersionGroup
    ]  # List of versions of the object to group together
    base_ref: list[str]  # The unversioned ref


class ObjectConfig(BaseModel):
    version_groups: ObjectVersionGroups
    show_version_indicator: bool = True
    display_name_map: dict[
        str, str
    ] = {}  # ref/name -> display name (keys can use "*" wildcards)
    deselected: list[
        str
    ] = []  # List of dataset refs or patterns to exclude (can use "*" for wildcard matching)


class DynamicLeaderboardColumnConfig(BaseModel):
    evaluation_object_ref: base_object_def.RefStr
    scorer_name: str
    summary_metric_path: str
    should_minimize: bool = False
    deselected: bool = False  # If True, this metric is excluded from the leaderboard


class DynamicLeaderboard(base_object_def.BaseObject):
    calls_query: (
        str  # The query used by the UI to filter rows. If none, use all entries
    )
    model_configuration: ObjectConfig
    dataset_configuration: ObjectConfig
    scorer_configuration: ObjectConfig
    columns_configuration: list[DynamicLeaderboardColumnConfig] = []
