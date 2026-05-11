import datetime
from typing import Any

from weave.trace_server import constants
from weave.trace_server import eval_results_helpers as eval_helpers
from weave.trace_server import trace_server_interface as tsi


def _call(
    *,
    call_id: str = "call-1",
    parent_id: str | None = "eval-1",
    op_name: str = constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
    attributes: dict[str, Any] | None = None,
    inputs: dict[str, Any] | None = None,
    output: Any | None = None,
) -> tsi.CallSchema:
    now = datetime.datetime.now(datetime.timezone.utc)
    return tsi.CallSchema(
        id=call_id,
        project_id="project-1",
        trace_id="trace-1",
        parent_id=parent_id,
        op_name=op_name,
        started_at=now,
        ended_at=now,
        attributes=attributes or {},
        inputs=inputs or {},
        output=output,
        summary={},
    )


def _genai_span_ref(trace_id: str = "agent-trace-1") -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "span_id": "span-1",
    }


def test_build_eval_rows_returns_genai_span_ref_without_children() -> None:
    predict_and_score_call = _call(
        call_id="pas-1",
        attributes={
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.GENAI_SPAN_REF_ATTR_KEY: _genai_span_ref(),
            }
        },
        inputs={"example": {"x": 1}, "model": "model://agent"},
        output={"output": "result", "scores": {}},
    )

    rows = eval_helpers.build_eval_rows(
        [predict_and_score_call],
        ["eval-1"],
        {"pas-1": "row-1"},
        include_raw_data_rows=False,
        include_predict_and_score_children=False,
    )

    trial = rows[0].evaluations[0].trials[0]
    assert trial.genai_span_ref == tsi.GenAISpanRef.model_validate(
        _genai_span_ref()
    )


def test_build_trial_prefers_prediction_genai_span_ref() -> None:
    predict_and_score_call = _call(
        call_id="pas-1",
        attributes={
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.GENAI_SPAN_REF_ATTR_KEY: _genai_span_ref("parent-trace"),
            }
        },
        inputs={"example": {"x": 1}, "model": "model://agent"},
        output={"output": "result", "scores": {}},
    )
    predict_call = _call(
        call_id="predict-1",
        parent_id="pas-1",
        op_name="Agent.predict",
        attributes={
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.GENAI_SPAN_REF_ATTR_KEY: _genai_span_ref("predict-trace"),
            }
        },
        inputs={"self": "model://agent", "inputs": {"x": 1}},
        output="result",
    )

    _, row_eval_map = eval_helpers.build_eval_rows_from_calls(
        [predict_and_score_call],
        {"pas-1": [predict_call]},
        include_raw_data_rows=False,
    )

    trial = next(iter(row_eval_map.values()))["eval-1"].trials[0]
    assert trial.genai_span_ref is not None
    assert trial.genai_span_ref.trace_id == "predict-trace"


def test_extract_genai_span_ref_ignores_malformed_refs() -> None:
    for raw_ref in (
        {"span_id": "missing-trace-id"},
        {"trace_id": "missing-span-id"},
    ):
        call = _call(
            attributes={
                constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                    constants.GENAI_SPAN_REF_ATTR_KEY: raw_ref,
                }
            }
        )

        assert eval_helpers.extract_genai_span_ref(call) is None
