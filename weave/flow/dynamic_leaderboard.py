from typing import Any

from pydantic import BaseModel

from weave.trace.refs import OpRef
from weave.trace.weave_client import WeaveClient, get_ref
from weave.trace_server.interface.builtin_object_classes import dynamic_leaderboard
from weave.trace_server.trace_server_interface import CallsFilter
from weave.utils.project_id import from_project_id
import json


class LeaderboardModelEvaluationResult(BaseModel):
    evaluate_call_ref: str
    value: Any


class ModelScoresForColumn(BaseModel):
    scores: list[LeaderboardModelEvaluationResult]


class LeaderboardModelResult(BaseModel):
    model_ref: str
    column_scores: list[ModelScoresForColumn]


def get_leaderboard_results(
    spec: dynamic_leaderboard.DynamicLeaderboard, client: WeaveClient
) -> list[LeaderboardModelResult]:
    entity, project = from_project_id(client._project_id())
    query = json.loads(spec.calls_query)
    calls = client.get_calls(
        query=query
    )
    # implement here
    pass


# Re-export:
DynamicLeaderboard = dynamic_leaderboard.DynamicLeaderboard
ObjectConfig = dynamic_leaderboard.ObjectConfig
ObjectVersionGroups = dynamic_leaderboard.ObjectVersionGroups
VersionGroup = dynamic_leaderboard.VersionGroup
DynamicLeaderboardColumnConfig = dynamic_leaderboard.DynamicLeaderboardColumnConfig
