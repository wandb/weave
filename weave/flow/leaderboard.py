from dataclasses import field
from typing import Any, Optional

from pydantic import BaseModel

import weave
from weave.trace.refs import OpRef
from weave.trace.weave_client import Call, WeaveClient, get_ref
from weave.trace_server.trace_server_interface import CallsFilter


class LeaderboardColumn(BaseModel):
    evaluation_object_ref: str
    scorer_name: str
    summary_metric_path_parts: list[str] = field(default_factory=list)
    should_minimize: Optional[bool] = None

class LeaderboardSpec(weave.Object):
    columns: list[LeaderboardColumn]

class LeaderboardModelEvaluationResult(BaseModel):
    evaluate_call_ref: str
    value: Any

class ModelScoresForColumn(BaseModel):
    scores: list[LeaderboardModelEvaluationResult]

class LeaderboardModelResult(BaseModel):
    model_ref: str
    column_scores: list[ModelScoresForColumn]


def get_leaderboard_results(spec: LeaderboardSpec, client: WeaveClient) -> list[LeaderboardModelResult]:
    entity, project = client._project_id().split("/")
    calls = client.get_calls(filter=CallsFilter(
        op_names=[OpRef(
            entity=entity,
            project=project,
            name="Evaluation.evaluate",
            _digest="*"
        ).uri()],
        input_refs=[c.evaluation_object_ref for c  in spec.columns]
    ))
    def get_scores(call: Call) -> list[float]:
        res = []
        for c in spec.columns:
            val = call.output.get(c.scorer_name)
            for part in c.summary_metric_path_parts:
                if isinstance(val, dict):
                    val = val.get(part)
                elif isinstance(val, list):
                    val = val[int(part)]
                else:
                    break
            res.append(val)
        return res
    
    res_map: dict[str, LeaderboardModelResult] = {}
    for call in calls:
        # Frustrating that we have to get the ref like this (such a waste of network calls)
        model_ref = get_ref(call.inputs["model"]).uri()
        if model_ref not in res_map:
            res_map[model_ref] = LeaderboardModelResult(model_ref=model_ref, column_scores=[ModelScoresForColumn(scores=[]) for _ in spec.columns])
        for col_idx, c in enumerate(spec.columns):
            eval_obj_ref = get_ref(call.inputs["self"]).uri()
            if c.evaluation_object_ref != eval_obj_ref:
                continue
            val = call.output.get(c.scorer_name)
            for part in c.summary_metric_path_parts:
                if isinstance(val, dict):
                    val = val.get(part)
                elif isinstance(val, list):
                    val = val[int(part)]
                else:
                    break
            res_map[model_ref].column_scores[col_idx].scores.append(LeaderboardModelEvaluationResult(
                evaluate_call_ref=get_ref(call).uri(),
                value=val
            ))
    return list(res_map.values())
