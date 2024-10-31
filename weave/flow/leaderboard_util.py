from weave.trace.refs import OpRef
from weave.trace.weave_client import WeaveClient, get_ref
from weave.trace_server.interface.base_object_classes import leaderboard
from weave.trace_server.trace_server_interface import CallsFilter


def get_leaderboard_results(
    spec: leaderboard.Leaderboard, client: WeaveClient
) -> list[leaderboard.LeaderboardModelResult]:
    entity, project = client._project_id().split("/")
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

    res_map: dict[str, leaderboard.LeaderboardModelResult] = {}
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
            res_map[model_ref_uri] = leaderboard.LeaderboardModelResult(
                model_ref=model_ref_uri,
                column_scores=[
                    leaderboard.ModelScoresForColumn(scores=[]) for _ in spec.columns
                ],
            )
        for col_idx, c in enumerate(spec.columns):
            eval_obj_ref = get_ref(call.inputs["self"])
            if eval_obj_ref is None:
                continue
            eval_obj_ref_uri = eval_obj_ref.uri()
            if c.evaluation_object_ref != eval_obj_ref_uri:
                continue
            val = call.output.get(c.scorer_name)
            for part in c.summary_metric_path_parts:
                if isinstance(val, dict):
                    val = val.get(part)
                elif isinstance(val, list):
                    val = val[int(part)]
                else:
                    break
            res_map[model_ref_uri].column_scores[col_idx].scores.append(
                leaderboard.LeaderboardModelEvaluationResult(
                    evaluate_call_ref=call_ref_uri, value=val
                )
            )
    return list(res_map.values())
