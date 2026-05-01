"""Prove that we can add a score to a finalized EvaluationLogger result.

Flow exercised:
1. Create an evaluation via EvaluationLogger; log a prediction with one initial
   score; finalize via log_summary.
2. "Reload" the eval — find the prediction call IDs purely from server queries
   (no in-memory handles).
3. Use the V2 trace-server APIs (scorer_create + score_create) to attach a new
   score to the existing prediction, with evaluation_run_id pointing at the
   finalized eval root.
4. Verify via eval_results_query that the new score appears in trial.scores
   and in summary.scorer_stats.
"""

from __future__ import annotations

import weave
from weave.evaluation.eval_imperative import EvaluationLogger
from weave.trace_server.trace_server_interface import (
    CallsFilter,
    CallsQueryReq,
    EvalResultsQueryReq,
    ScoreCreateReq,
    ScorerCreateReq,
)
from weave.utils.project_id import from_project_id


def _find_predict_and_score_call_id(server, project_id: str, eval_call_id: str) -> str:
    children = list(
        server.calls_query_stream(
            CallsQueryReq(
                project_id=project_id,
                filter=CallsFilter(parent_ids=[eval_call_id]),
            )
        )
    )
    for c in children:
        if "predict_and_score" in (c.op_name or ""):
            return c.id
    raise AssertionError(
        f"No predict_and_score call found under eval {eval_call_id}; "
        f"got op_names={[c.op_name for c in children]}"
    )


def _find_predict_call_id(server, project_id: str, p_and_s_id: str) -> str:
    children = list(
        server.calls_query_stream(
            CallsQueryReq(
                project_id=project_id,
                filter=CallsFilter(parent_ids=[p_and_s_id]),
            )
        )
    )
    for c in children:
        if "Model.predict" in (c.op_name or ""):
            return c.id
    raise AssertionError(
        f"No Model.predict call found under predict_and_score {p_and_s_id}; "
        f"got op_names={[c.op_name for c in children]}"
    )


def test_add_score_to_finalized_evaluation_logger(client):
    """End-to-end: EvaluationLogger -> finalize -> score_create -> eval_results_query."""
    project_id = client.project_id
    entity, project = from_project_id(project_id)
    server = client.server

    # ---------------------------------------------------------------
    # 1. Create the eval with one prediction and one initial score, finalize.
    # ---------------------------------------------------------------
    ev = EvaluationLogger(name="my_eval")
    pred = ev.log_prediction(inputs={"x": 1}, output="hello")
    pred.log_score(scorer="initial_correctness", score=0.5)
    pred.finish()
    ev.log_summary({"note": "initial"})
    client.flush()

    eval_call_id = ev._evaluate_call.id

    # ---------------------------------------------------------------
    # 2. Reload: find the prediction call purely from server queries.
    # ---------------------------------------------------------------
    p_and_s_id = _find_predict_and_score_call_id(server, project_id, eval_call_id)
    predict_call_id = _find_predict_call_id(server, project_id, p_and_s_id)

    # ---------------------------------------------------------------
    # 3. Create a new scorer and attach a score via V2 score_create.
    # ---------------------------------------------------------------
    scorer_res = server.scorer_create(
        ScorerCreateReq(
            project_id=project_id,
            name="late_added_scorer",
            op_source_code="def score(output):\n    return 0.9\n",
        )
    )
    scorer_ref = (
        f"weave:///{entity}/{project}/object/"
        f"{scorer_res.object_id}:{scorer_res.digest}"
    )

    score_res = server.score_create(
        ScoreCreateReq(
            project_id=project_id,
            prediction_id=predict_call_id,
            scorer=scorer_ref,
            value=0.9,
            evaluation_run_id=eval_call_id,
        )
    )
    assert score_res.score_id

    # ---------------------------------------------------------------
    # 4. Query eval_results_query and verify score appears.
    # ---------------------------------------------------------------
    res = server.eval_results_query(
        EvalResultsQueryReq(
            project_id=project_id,
            evaluation_call_ids=[eval_call_id],
            include_summary=True,
        )
    )

    assert res.total_rows == 1
    trial = res.rows[0].evaluations[0].trials[0]

    # The original score (logged through EvaluationLogger before log_summary)
    # is still present.
    assert "initial_correctness" in trial.scores
    assert trial.scores["initial_correctness"] == 0.5

    # ---- KEY ASSERTION (the late-added score) ---------------------
    # The score we just attached via score_create — AFTER the eval was
    # finalized by log_summary — appears in trial.scores under the scorer
    # name parsed from the scorer ref, with the value passed to score_create.
    assert "late_added_scorer" in trial.scores, (
        f"new score not in trial.scores; got keys={list(trial.scores)}"
    )
    assert trial.scores["late_added_scorer"] == 0.9

    # And its call id (the score_id returned by score_create) is wired into
    # trial.scorer_call_ids so callers can navigate from the trial back to
    # the score call in the trace.
    assert "late_added_scorer" in trial.scorer_call_ids
    assert trial.scorer_call_ids["late_added_scorer"] == score_res.score_id

    # ---------------------------------------------------------------
    # 5. Verify the summary aggregate picks up the late-added scorer too.
    #    Without the merge in eval_results_helpers, summary.scorer_stats
    #    would only show "initial_correctness" and the new scorer's stats
    #    would be silently missing.
    # ---------------------------------------------------------------
    summary = res.summary
    assert summary is not None
    assert summary.row_count == 1
    assert len(summary.evaluations) == 1
    eval_summary = summary.evaluations[0]
    assert eval_summary.evaluation_call_id == eval_call_id
    assert eval_summary.trial_count == 1

    scorer_keys = {s.scorer_key for s in eval_summary.scorer_stats}
    assert "initial_correctness" in scorer_keys

    # ---- KEY ASSERTION (late-added score in summary) --------------
    # The new scorer is present in summary.scorer_stats alongside the original.
    assert "late_added_scorer" in scorer_keys, (
        f"new score not in summary.scorer_stats; got keys={scorer_keys}"
    )

    # And its aggregate stats are computed correctly: continuous (because the
    # value 0.9 is a float), one trial seen, mean equals the value.
    late_stats = next(
        s for s in eval_summary.scorer_stats if s.scorer_key == "late_added_scorer"
    )
    assert late_stats.value_type == "continuous"
    assert late_stats.trial_count == 1
    assert late_stats.numeric_count == 1
    assert late_stats.numeric_mean == 0.9
