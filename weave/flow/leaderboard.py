from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from weave.trace.refs import OpRef
from weave.trace.weave_client import WeaveClient, get_ref
from weave.trace_server.interface.builtin_object_classes import leaderboard
from weave.trace_server.trace_server_interface import CallsFilter
from weave.utils.project_id import from_project_id


@dataclass
class LeaderboardModelEvaluationResult:
    evaluate_call_ref: str
    value: Any


@dataclass
class ModelScoresForColumn:
    scores: list[LeaderboardModelEvaluationResult]


@dataclass
class LeaderboardModelResult:
    model_ref: str
    column_scores: list[ModelScoresForColumn]


def get_leaderboard_results(
    spec: leaderboard.Leaderboard, client: WeaveClient
) -> list[LeaderboardModelResult]:
    entity, project = from_project_id(client._project_id())
    calls = client.get_calls(
        filter=CallsFilter(
            op_names=[
                OpRef(
                    entity=entity,
                    project=project,
                    name="Evaluation.evaluate",
                    _digest="*",
                ).uri()
            ],
            input_refs=[c.evaluation_object_ref for c in spec.columns],
        )
    )

    res_map: dict[str, LeaderboardModelResult] = {}
    for call in calls:
        # Frustrating that we have to get the ref like this. Since the
        # `Call` object auto-derefs the inputs (making a network request),
        # we have to manually get the ref here... waste of network calls.
        call_ref = get_ref(call)
        if call_ref is None:
            continue
        call_ref_uri = call_ref.uri()

        model_ref = get_ref(call.inputs["model"])
        if model_ref is None:
            continue
        model_ref_uri = model_ref.uri()
        if model_ref_uri not in res_map:
            res_map[model_ref_uri] = LeaderboardModelResult(
                model_ref=model_ref_uri,
                column_scores=[ModelScoresForColumn(scores=[]) for _ in spec.columns],
            )
        for col_idx, c in enumerate(spec.columns):
            eval_obj_ref = get_ref(call.inputs["self"])
            if eval_obj_ref is None:
                continue
            eval_obj_ref_uri = eval_obj_ref.uri()
            if c.evaluation_object_ref != eval_obj_ref_uri:
                continue
            if call.output is None:
                continue
            val = call.output.get(c.scorer_name)
            for part in c.summary_metric_path.split("."):
                if isinstance(val, dict):
                    val = val.get(part)
                elif isinstance(val, list):
                    val = val[int(part)]
                else:
                    break
            res_map[model_ref_uri].column_scores[col_idx].scores.append(
                LeaderboardModelEvaluationResult(
                    evaluate_call_ref=call_ref_uri, value=val
                )
            )
    return list(res_map.values())


# Re-export:
Leaderboard = leaderboard.Leaderboard
LeaderboardColumn = leaderboard.LeaderboardColumn
