import datetime
from typing import Any

from tests.trace_server.helpers import make_project_id
from weave.trace_server import constants
from weave.trace_server import eval_results_helpers as eval_helpers
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.helpers import genai_span_to_row
from weave.trace_server.agents.schema import (
    ALL_SPAN_INSERT_COLUMNS,
    AgentSpanCHInsertable,
)
from weave.trace_server.agents.types import AgentSpanSchema


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


def test_build_eval_rows_returns_genai_span_ref_list_without_children() -> None:
    predict_and_score_call = _call(
        call_id="pas-1",
        attributes={
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.GENAI_SPAN_REF_ATTR_KEY: [
                    _genai_span_ref("agent-trace-1"),
                    _genai_span_ref("agent-trace-2"),
                ],
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
    assert trial.genai_span_ref is not None
    assert [ref.trace_id for ref in trial.genai_span_ref] == [
        "agent-trace-1",
        "agent-trace-2",
    ]


def test_build_trial_combines_prediction_and_parent_genai_span_refs() -> None:
    predict_and_score_call = _call(
        call_id="pas-1",
        attributes={
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.GENAI_SPAN_REF_ATTR_KEY: [
                    _genai_span_ref("parent-trace"),
                ],
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
                constants.GENAI_SPAN_REF_ATTR_KEY: [
                    _genai_span_ref("predict-trace"),
                ],
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
    assert [ref.trace_id for ref in trial.genai_span_ref] == [
        "predict-trace",
        "parent-trace",
    ]


def test_extract_genai_span_refs_ignores_malformed_refs() -> None:
    for raw_refs in (
        [
            {"span_id": "missing-trace-id"},
        ],
        [
            {"trace_id": "missing-span-id"},
        ],
    ):
        call = _call(
            attributes={
                constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                    constants.GENAI_SPAN_REF_ATTR_KEY: raw_refs,
                }
            }
        )

        assert eval_helpers.extract_genai_span_refs(call) is None


def test_extract_genai_span_refs_skips_invalid_items() -> None:
    call = _call(
        attributes={
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.GENAI_SPAN_REF_ATTR_KEY: [
                    _genai_span_ref("valid-trace"),
                    "not-a-ref",
                    {"span_id": "missing-trace-id"},
                    {"trace_id": "missing-span-id"},
                ],
            }
        }
    )

    assert eval_helpers.extract_genai_span_refs(call) == [
        tsi.GenAISpanRef.model_validate(_genai_span_ref("valid-trace"))
    ]


def test_merge_eval_agent_span_refs_links_stamped_span_tree_root() -> None:
    rows = [
        tsi.EvalResultsRow(
            row_digest="row-1",
            evaluations=[
                tsi.EvalResultsRowEvaluation(
                    evaluation_call_id="eval-1",
                    trials=[tsi.EvalResultsTrial(predict_and_score_call_id="pas-1")],
                )
            ],
        )
    ]
    now = datetime.datetime.now(datetime.timezone.utc)
    spans = [
        AgentSpanSchema(
            project_id="project-1",
            trace_id="agent-trace-1",
            span_id="child",
            parent_span_id="root",
            started_at=now + datetime.timedelta(seconds=1),
            eval_run_id="eval-1",
            eval_predict_and_score_call_id="pas-1",
        ),
        AgentSpanSchema(
            project_id="project-1",
            trace_id="agent-trace-1",
            span_id="root",
            started_at=now,
            eval_run_id="eval-1",
            eval_predict_and_score_call_id="pas-1",
        ),
        AgentSpanSchema(
            project_id="project-1",
            trace_id="unrelated-trace",
            span_id="unrelated",
            eval_run_id="eval-2",
            eval_predict_and_score_call_id="pas-2",
        ),
    ]

    eval_helpers.merge_eval_agent_span_refs(rows, spans)

    assert rows[0].evaluations[0].trials[0].genai_span_ref == [
        tsi.GenAISpanRef(trace_id="agent-trace-1", span_id="root")
    ]


def test_merge_eval_agent_span_refs_preserves_explicit_ref_for_same_trace() -> None:
    explicit_ref = tsi.GenAISpanRef(trace_id="agent-trace-1", span_id="model-span")
    rows = [
        tsi.EvalResultsRow(
            row_digest="row-1",
            evaluations=[
                tsi.EvalResultsRowEvaluation(
                    evaluation_call_id="eval-1",
                    trials=[
                        tsi.EvalResultsTrial(
                            predict_and_score_call_id="pas-1",
                            genai_span_ref=[explicit_ref],
                        )
                    ],
                )
            ],
        )
    ]
    spans = [
        AgentSpanSchema(
            project_id="project-1",
            trace_id="agent-trace-1",
            span_id="root",
            eval_run_id="eval-1",
            eval_predict_and_score_call_id="pas-1",
        ),
        AgentSpanSchema(
            project_id="project-1",
            trace_id="agent-trace-2",
            span_id="other-root",
            eval_run_id="eval-1",
            eval_predict_and_score_call_id="pas-1",
        ),
    ]

    eval_helpers.merge_eval_agent_span_refs(rows, spans)

    assert rows[0].evaluations[0].trials[0].genai_span_ref == [
        explicit_ref,
        tsi.GenAISpanRef(trace_id="agent-trace-2", span_id="other-root"),
    ]


def test_hydrate_eval_agent_span_refs_queries_promoted_columns(ch_server) -> None:
    project_id = make_project_id("eval_results_agent_spans")
    span = AgentSpanCHInsertable(
        project_id=project_id,
        trace_id="agent-trace-1",
        span_id="agent-span-1",
        span_name="agent-run",
        started_at=datetime.datetime.now(datetime.timezone.utc),
        eval_run_id="eval-1",
        eval_predict_and_score_call_id="pas-1",
    )
    ch_server.ch_client.insert(
        "spans",
        data=[genai_span_to_row(span)],
        column_names=ALL_SPAN_INSERT_COLUMNS,
    )
    rows = [
        tsi.EvalResultsRow(
            row_digest="row-1",
            evaluations=[
                tsi.EvalResultsRowEvaluation(
                    evaluation_call_id="eval-1",
                    trials=[tsi.EvalResultsTrial(predict_and_score_call_id="pas-1")],
                )
            ],
        )
    ]

    warnings = eval_helpers.hydrate_eval_agent_span_refs(ch_server, project_id, rows)

    assert warnings == []
    assert rows[0].evaluations[0].trials[0].genai_span_ref == [
        tsi.GenAISpanRef(trace_id="agent-trace-1", span_id="agent-span-1")
    ]
