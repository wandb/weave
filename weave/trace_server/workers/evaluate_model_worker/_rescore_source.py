"""Internal dataclass for the rescore worker — uniform shape across both
standard and imperative source-eval branches.

The downstream loop (apply_scorer + score_create) consumes ``_RescoreSource``;
it does NOT consume ``PredictionReadRes`` directly. This keeps the contract
between the per-branch fetcher and the loop minimal and explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class _RescoreSource:
    """One source-eval row to be rescored.

    Field semantics across branches:

    Standard branch (Evaluation.evaluate):
        prediction_id   = prediction call id (the call with op_name "prediction")
        parent_call_id  = prediction.parent_id = predict_and_score.call_id
        inputs          = prediction.inputs["inputs"]
        output          = prediction.output

    Imperative branch (weave.EvaluationLogger):
        prediction_id   = predict_and_score.call_id (no separate prediction)
        parent_call_id  = predict_and_score.call_id (same — score attaches here)
        inputs          = predict_and_score.inputs["example"]
        output          = predict_and_score.output["output"] if dict else output

    The rescore loop must use ``parent_call_id`` for score attachment via
    ``ScoreCreateReq.parent_id`` (the explicit override added in Task 1.2).
    Never re-derive parenting from ``prediction_id`` — that's the silent
    failure mode where standard passes CI because the values happen to align
    there but imperative misroutes scores.
    """

    prediction_id: str
    parent_call_id: str
    inputs: dict[str, Any]
    output: Any
