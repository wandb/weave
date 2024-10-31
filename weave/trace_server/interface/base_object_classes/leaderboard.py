from dataclasses import field
from typing import Any, Optional

from pydantic import BaseModel
from weave.trace_server.interface.base_object_classes import base_object_def

class LeaderboardColumn(BaseModel):
    evaluation_object_ref: base_object_def.RefStr
    scorer_name: str
    summary_metric_path_parts: list[str] = field(default_factory=list)
    should_minimize: Optional[bool] = None


class Leaderboard(base_object_def.BaseObject):
    columns: list[LeaderboardColumn]


class LeaderboardModelEvaluationResult(BaseModel):
    evaluate_call_ref: base_object_def.RefStr
    value: Any


class ModelScoresForColumn(BaseModel):
    scores: list[LeaderboardModelEvaluationResult]


class LeaderboardModelResult(BaseModel):
    model_ref: str
    column_scores: list[ModelScoresForColumn]
