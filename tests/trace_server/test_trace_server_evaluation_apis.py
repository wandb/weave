import datetime
import json
import os
from unittest import mock
from unittest.mock import patch

import pytest

import weave
from tests.conftest import LATENCY_TOL
from tests.trace.util import FAKE_NOT_IMPLEMENTED
from tests.trace_server.completions_util import with_simple_mock_litellm_completion
from weave.trace.refs import ObjectRef
from weave.trace.serialization.custom_objs import UnsafeDeserializationError
from weave.trace.weave_client import WeaveClient, generate_id
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.interface.query import Query
from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallsDeleteReq,
    CallsQueryReq,
    CallStartReq,
    EndedCallSchemaForInsert,
    EvalResultsFilter,
    EvalResultsQueryReq,
    EvalResultsSortBy,
    EvaluateModelReq,
    EvaluateModelRes,
    EvaluationRunCreateReq,
    EvaluationStatusComplete,
    EvaluationStatusNotFound,
    EvaluationStatusReq,
    EvaluationStatusRunning,
    FileCreateReq,
    GenAISpanRef,
    ObjCreateReq,
    PredictionCreateReq,
    PredictionFinishReq,
    ScoreCreateReq,
    ScorerCreateReq,
    StartedCallSchemaForInsert,
    TableCreateReq,
    TraceServerInterface,
    TraceStatus,
)
from weave.trace_server.workers.evaluate_model_worker import evaluate_model_worker
from weave.utils.project_id import from_project_id, to_project_id


@pytest.mark.asyncio
async def test_evaluation_status(client):
    eval_call_id = generate_id()

    def get_status():
        client.flush()
        return client.server.evaluation_status(
            EvaluationStatusReq(project_id=client.project_id, call_id=eval_call_id)
        ).status

    @weave.op
    def model(a: int) -> int:
        status = get_status()
        assert status == EvaluationStatusRunning(completed_rows=a - 1, total_rows=3)
        return a + 1

    @weave.op
    def scorer(output: int, exp_output: int) -> float:
        return 1.0 if output == exp_output else 0.0

    dataset = [
        {"a": 1, "exp_output": 2},
        {"a": 2, "exp_output": 3},
        {"a": 3, "exp_output": 4},
    ]
    eval = weave.Evaluation(dataset=dataset, scorers=[scorer])

    assert get_status() == EvaluationStatusNotFound()

    # mock weave.trace.env.py::get_weave_parallelism to return 1 (allows for checking status deterministically)
    with mock.patch.dict("os.environ", {"WEAVE_PARALLELISM": "1"}):
        # Patch the first 2 calls to generate_id to return eval_call_id, then defer to the real function
        real_generate_id = generate_id

        def generate_id_side_effect():
            if generate_id_side_effect.calls < 2:
                generate_id_side_effect.calls += 1
                return eval_call_id
            return real_generate_id()

        generate_id_side_effect.calls = 0

        with mock.patch(
            "weave.trace.weave_client.generate_id", side_effect=generate_id_side_effect
        ):
            await eval.evaluate(model=model)

    assert get_status() == EvaluationStatusComplete(
        output={
            "output": {"mean": 3.0},
            "scorer": {"mean": 1.0},
            "model_latency": {"mean": pytest.approx(0, abs=LATENCY_TOL)},
        }
    )


def setup_test_objects(server: TraceServerInterface, entity: str, project: str):
    project_id = to_project_id(entity, project)

    def create_model() -> str:
        """Create a test model and return its reference URI."""
        model_object_id = "test_model_for_eval"
        llm_model_val = {
            "llm_model_id": "gpt-4o-mini",
            "default_params": {
                "messages_template": [
                    {
                        "role": "system",
                        "content": "You are a scorer. You will be given a user input and a model output. You will return a score from 0 to 10. Please return the score in a JSON object with the key 'score'.",
                    },
                ],
                "response_format": "json_object",
            },
        }
        model_create_res = server.obj_create(
            ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": project_id,
                        "object_id": model_object_id,
                        "val": llm_model_val,
                        "builtin_object_class": "LLMStructuredCompletionModel",
                    }
                }
            )
        )
        return ObjectRef(
            entity=entity,
            project=project,
            name=model_object_id,
            _digest=model_create_res.digest,
        ).uri

    def create_dataset() -> str:
        """Create a test dataset and return its reference URI."""
        dataset_table_val = [
            {"user_input": "How are you?", "expected": "I'm doing well, thank you!"}
        ]
        dataset_table_res = server.table_create(
            TableCreateReq.model_validate(
                {
                    "table": {
                        "project_id": project_id,
                        "rows": dataset_table_val,
                    }
                }
            )
        )
        dataset_object_id = "test_eval_dataset"
        dataset_val = {
            "_type": "Dataset",
            "_class_name": "Dataset",
            "_bases": ["BaseModel", "Object", "Dataset"],
            "rows": f"weave:///{project_id}/table/{dataset_table_res.digest}",
        }
        dataset_create_res = server.obj_create(
            ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": project_id,
                        "object_id": dataset_object_id,
                        "val": dataset_val,
                    }
                }
            )
        )
        return ObjectRef(
            entity=entity,
            project=project,
            name=dataset_object_id,
            _digest=dataset_create_res.digest,
        ).uri

    def create_scorer() -> str:
        """Create a test scorer and return its reference URI."""
        # First create the model for the scorer
        scorer_model_object_id = "test_eval_scorer_model"
        scorer_model_val = {
            "llm_model_id": "gpt-4o-mini",
            "default_params": {
                "messages_template": [
                    {
                        "role": "system",
                        "content": "You are an expert judge. Compare the model output to the expected output and return a score from 0 to 10. Please return the score in a JSON object with the key 'score'.",
                    },
                ],
                "response_format": "json_object",
            },
        }
        scorer_model_create_res = server.obj_create(
            ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": project_id,
                        "object_id": scorer_model_object_id,
                        "val": scorer_model_val,
                        "builtin_object_class": "LLMStructuredCompletionModel",
                    }
                }
            )
        )
        scorer_model_ref = ObjectRef(
            entity=entity,
            project=project,
            name=scorer_model_object_id,
            _digest=scorer_model_create_res.digest,
        ).uri

        # Then create the scorer
        scorer_object_id = "test_eval_llm_judge_scorer"
        scorer_val = {
            "_type": "LLMAsAJudgeScorer",
            "_class_name": "LLMAsAJudgeScorer",
            "_bases": ["BaseModel", "Scorer", "LLMAsAJudgeScorer"],
            "model": scorer_model_ref,
            "scoring_prompt": "User input: {user_input}\nModel output: {output}\nExpected output: {expected}\n\nScore the similarity (0-10).",
        }
        scorer_create_res = server.obj_create(
            ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": project_id,
                        "object_id": scorer_object_id,
                        "val": scorer_val,
                    }
                }
            )
        )
        return ObjectRef(
            entity=entity,
            project=project,
            name=scorer_object_id,
            _digest=scorer_create_res.digest,
        ).uri

    def create_evaluation(dataset_ref: str, scorer_ref: str) -> str:
        """Create a test evaluation and return its reference URI."""
        evaluation_object_id = "test_evaluation"
        evaluation_val = {
            "_type": "Evaluation",
            "_class_name": "Evaluation",
            "_bases": ["BaseModel", "Object", "Evaluation"],
            "dataset": dataset_ref,
            "scorers": [scorer_ref],
            # Note: You might need to add more fields depending on the Evaluation class structure
        }
        evaluation_create_res = server.obj_create(
            ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": project_id,
                        "object_id": evaluation_object_id,
                        "val": evaluation_val,
                    }
                }
            )
        )
        return ObjectRef(
            entity=entity,
            project=project,
            name=evaluation_object_id,
            _digest=evaluation_create_res.digest,
        ).uri

    model_ref_uri = create_model()
    evaluation_ref_uri = create_evaluation(create_dataset(), create_scorer())

    return model_ref_uri, evaluation_ref_uri


@pytest.mark.parametrize("direct_script_execution", [True, False])
def test_evaluate_model(client: WeaveClient, direct_script_execution):
    """Test the evaluate_model API endpoint with isolated execution.

    This test verifies that:
    1. Evaluations can be created and executed through the evaluate_model API
    2. Evaluation execution is properly traced (creates call records)
    3. Evaluations correctly run models against datasets and apply scorers
    4. Different projects are properly isolated from each other

    The test creates a model, dataset, scorer, and evaluation, then runs
    the evaluation through the evaluate_model API.
    """
    project_id = client.project_id
    entity, project = from_project_id(project_id)

    def evaluate_model_wrapped(req: EvaluateModelReq):
        call_id = generate_id()
        res = evaluate_model_worker.evaluate_model(
            evaluate_model_worker.EvaluateModelArgs(
                project_id=req.project_id,
                evaluation_ref=req.evaluation_ref,
                model_ref=req.model_ref,
                wb_user_id=entity,
                evaluation_call_id=call_id,
            )
        )
        return EvaluateModelRes(
            call_id=call_id,
        )

    evaluate_model_fn = (
        evaluate_model_wrapped
        if direct_script_execution
        else client.server.evaluate_model
    )
    model_ref_uri, evaluation_ref_uri = setup_test_objects(
        client.server,
        entity,
        "test_evaluate_model_" + ("local" if direct_script_execution else "remote"),
    )

    # Run the evaluation
    req = EvaluateModelReq.model_validate(
        {
            "project_id": project_id,
            "evaluation_ref": evaluation_ref_uri,
            "model_ref": model_ref_uri,
        }
    )
    # Mock the LLM completions for all the calls during evaluation.
    # Also provide a fake OPENAI_API_KEY so the secret fetcher finds a key.
    with (
        with_simple_mock_litellm_completion(json.dumps({"score": 9})),
        patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
    ):
        eval_res = evaluate_model_fn(req)

    # Query for calls
    calls_res = client.server.calls_query(
        CallsQueryReq.model_validate(
            {
                "project_id": project_id,
            }
        )
    )

    # Expected calls (completions write to spans table, not calls):
    # evaluate
    # predict_and_score
    #    predict
    #    score
    #       predict
    # summary
    #    scorer summary
    assert len(calls_res.calls) == 7

    # Query for the specific evaluation call
    eval_calls_res = client.server.calls_query(
        CallsQueryReq.model_validate(
            {
                "project_id": project_id,
                "filter": {
                    "call_ids": [eval_res.call_id],
                },
            }
        )
    )

    assert len(eval_calls_res.calls) == 1
    eval_call = eval_calls_res.calls[0]
    assert eval_call.op_name.startswith(
        f"weave:///{project_id}/op/Evaluation.evaluate:"
    )
    assert isinstance(eval_call.summary, dict)
    assert eval_call.summary["status_counts"] == {
        TraceStatus.SUCCESS: 7,
        TraceStatus.ERROR: 0,
    }
    assert eval_call.summary["weave"]["status"] == TraceStatus.SUCCESS
    assert eval_call.output == {
        "output": {"score": {"mean": 9.0}},
        "LLMAsAJudgeScorer": {"score": {"mean": 9.0}},
        "model_latency": {"mean": pytest.approx(0, abs=LATENCY_TOL)},
    }


# The guard raises inside the lazy row-decode threadpool, which logs the failure
# at ERROR before it propagates out of asyncio.run; that log is the expected path.
@pytest.mark.disable_logging_error_check
def test_evaluate_model_rejects_unsafe_dataset_row(client):
    """An Op node in a dataset row must be refused at decode time, not loaded and
    executed (WB-34909).

    The evaluation and dataset objects carry no custom types themselves; the Op
    CustomWeaveType lives in a table row that is only fetched and deserialized
    lazily during evaluation. The worker disables unsafe custom-object decode, so
    materializing that row raises instead of importing the code.
    """
    project_id = client.project_id
    entity, project = from_project_id(project_id)
    server = client.server

    def _obj(object_id: str, val: dict, builtin: str | None = None) -> str:
        obj = {"project_id": project_id, "object_id": object_id, "val": val}
        if builtin is not None:
            obj["builtin_object_class"] = builtin
        res = server.obj_create(ObjCreateReq.model_validate({"obj": obj}))
        return ObjectRef(
            entity=entity, project=project, name=object_id, _digest=res.digest
        ).uri

    # A real file so the lazy file fetch succeeds; the decode guard, not a missing
    # file, is what must stop the Op row from being reconstructed.
    file_res = server.file_create(
        FileCreateReq(project_id=project_id, name="obj.py", content=b"print('hi')")
    )
    table_res = server.table_create(
        TableCreateReq.model_validate(
            {
                "table": {
                    "project_id": project_id,
                    "rows": [
                        {"input": "ok"},
                        {
                            "input": {
                                "_type": "CustomWeaveType",
                                "weave_type": {"type": "Op"},
                                "files": {"obj.py": file_res.digest},
                                "load_op": None,
                            }
                        },
                    ],
                }
            }
        )
    )
    dataset_ref = _obj(
        "dataset_with_custom_row",
        {
            "_type": "Dataset",
            "_class_name": "Dataset",
            "_bases": ["BaseModel", "Object", "Dataset"],
            "rows": f"weave:///{project_id}/table/{table_res.digest}",
        },
    )
    evaluation_ref = _obj(
        "eval_with_custom_row",
        {
            "_type": "Evaluation",
            "_class_name": "Evaluation",
            "_bases": ["BaseModel", "Object", "Evaluation"],
            "dataset": dataset_ref,
            "scorers": None,
        },
    )
    model_ref = _obj(
        "valid_model",
        {"llm_model_id": "gpt-4o-mini", "default_params": {}},
        builtin="LLMStructuredCompletionModel",
    )

    with pytest.raises(UnsafeDeserializationError):
        evaluate_model_worker.evaluate_model(
            evaluate_model_worker.EvaluateModelArgs(
                project_id=project_id,
                evaluation_ref=evaluation_ref,
                model_ref=model_ref,
                wb_user_id=entity,
                evaluation_call_id=generate_id(),
            )
        )


@pytest.mark.parametrize("op_arg", ["evaluation_ref", "model_ref"])
def test_evaluate_model_rejects_op_ref_as_eval_or_model_ref(client, op_arg):
    """An op ref passed directly as the evaluation_ref/model_ref must be refused at
    decode time (WB-34909). This pins the guarantee that replaced the deleted
    `_assert_safe_ref` pre-check: `client.get` of an op ref reconstructs an `Op`
    CustomWeaveType, which the secure worker client refuses instead of importing.
    """
    project_id = client.project_id
    entity, project = from_project_id(project_id)
    server = client.server

    def _obj(object_id: str, val: dict, builtin: str | None = None) -> str:
        obj = {"project_id": project_id, "object_id": object_id, "val": val}
        if builtin is not None:
            obj["builtin_object_class"] = builtin
        res = server.obj_create(ObjCreateReq.model_validate({"obj": obj}))
        return ObjectRef(
            entity=entity, project=project, name=object_id, _digest=res.digest
        ).uri

    @weave.op
    def sneaky(a: int) -> int:
        return a + 1

    op_ref = weave.publish(sneaky).uri()

    table_res = server.table_create(
        TableCreateReq.model_validate(
            {"table": {"project_id": project_id, "rows": [{"input": "ok"}]}}
        )
    )
    dataset_ref = _obj(
        "valid_dataset",
        {
            "_type": "Dataset",
            "_class_name": "Dataset",
            "_bases": ["BaseModel", "Object", "Dataset"],
            "rows": f"weave:///{project_id}/table/{table_res.digest}",
        },
    )
    valid_evaluation_ref = _obj(
        "valid_eval",
        {
            "_type": "Evaluation",
            "_class_name": "Evaluation",
            "_bases": ["BaseModel", "Object", "Evaluation"],
            "dataset": dataset_ref,
            "scorers": None,
        },
    )
    valid_model_ref = _obj(
        "valid_model",
        {"llm_model_id": "gpt-4o-mini", "default_params": {}},
        builtin="LLMStructuredCompletionModel",
    )

    refs = {
        "evaluation_ref": valid_evaluation_ref,
        "model_ref": valid_model_ref,
        op_arg: op_ref,
    }
    with pytest.raises(UnsafeDeserializationError):
        evaluate_model_worker.evaluate_model(
            evaluate_model_worker.EvaluateModelArgs(
                project_id=project_id,
                evaluation_ref=refs["evaluation_ref"],
                model_ref=refs["model_ref"],
                wb_user_id=entity,
                evaluation_call_id=generate_id(),
            )
        )


def test_eval_results_query_basic(client):
    project_id = client.project_id
    entity, project = from_project_id(project_id)

    scorer_res = client.server.scorer_create(
        ScorerCreateReq(
            project_id=project_id,
            name="basic_scorer",
            op_source_code="def score(output):\n    return 1",
        )
    )
    scorer_ref = (
        f"weave:///{entity}/{project}/object/{scorer_res.object_id}:{scorer_res.digest}"
    )

    run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://basic",
            model="model://basic",
        )
    )
    pred = client.server.prediction_create(
        PredictionCreateReq(
            project_id=project_id,
            model="model://basic",
            inputs={"x": 1},
            output="result",
            evaluation_run_id=run.evaluation_run_id,
        )
    )
    client.server.score_create(
        ScoreCreateReq(
            project_id=project_id,
            prediction_id=pred.prediction_id,
            scorer=scorer_ref,
            value=0.9,
            evaluation_run_id=run.evaluation_run_id,
        )
    )
    client.server.prediction_finish(
        PredictionFinishReq(
            project_id=project_id,
            prediction_id=pred.prediction_id,
        )
    )

    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=project_id,
            evaluation_call_ids=[run.evaluation_run_id],
        )
    )

    assert res.total_rows == 1
    assert len(res.rows) == 1
    trial = res.rows[0].evaluations[0].trials[0]
    assert "basic_scorer" in trial.scores
    assert trial.scores["basic_scorer"] == 0.9


def test_eval_results_query_returns_genai_span_ref_without_children(client):
    project_id = client.project_id
    genai_span_ref = GenAISpanRef(
        trace_id="agent-trace-1",
        span_id="span-1",
    )

    run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://agent-ref",
            model="model://agent-ref",
        )
    )
    pred = client.server.prediction_create(
        PredictionCreateReq(
            project_id=project_id,
            model="model://agent-ref",
            inputs={"x": 1},
            output="result",
            evaluation_run_id=run.evaluation_run_id,
            genai_span_ref=[genai_span_ref],
        )
    )
    client.server.prediction_finish(
        PredictionFinishReq(
            project_id=project_id,
            prediction_id=pred.prediction_id,
        )
    )

    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=project_id,
            evaluation_call_ids=[run.evaluation_run_id],
            include_predict_and_score_children=False,
        )
    )

    assert res.total_rows == 1
    trial = res.rows[0].evaluations[0].trials[0]
    assert trial.predict_call_id is None
    assert trial.genai_span_ref == [genai_span_ref]


def test_eval_results_query_nonexistent_eval_root(client):
    project_id = client.project_id

    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=project_id,
            evaluation_call_ids=["00000000-0000-0000-0000-000000000000"],
        )
    )

    assert res.total_rows == 0
    assert res.rows == []


def test_eval_results_query_multiple_evals(client):
    project_id = client.project_id

    run_a = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://multi-a",
            model="model://multi-a",
        )
    )
    run_b = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://multi-b",
            model="model://multi-b",
        )
    )

    for run, model in [(run_a, "model://multi-a"), (run_b, "model://multi-b")]:
        pred = client.server.prediction_create(
            PredictionCreateReq(
                project_id=project_id,
                model=model,
                inputs={"x": "shared"},
                output="out",
                evaluation_run_id=run.evaluation_run_id,
            )
        )
        client.server.prediction_finish(
            PredictionFinishReq(
                project_id=project_id,
                prediction_id=pred.prediction_id,
            )
        )

    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=project_id,
            evaluation_call_ids=[run_a.evaluation_run_id, run_b.evaluation_run_id],
        )
    )

    assert res.total_rows == 1
    assert len(res.rows) == 1
    assert {e.evaluation_call_id for e in res.rows[0].evaluations} == {
        run_a.evaluation_run_id,
        run_b.evaluation_run_id,
    }


def test_eval_results_resolve_refs_only_for_paginated_rows(client):
    """Verify that resolve_row_refs only resolves refs for the paginated slice"""
    project_id = client.project_id

    # create an eval with 5 rows
    run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://ref-resolve-test",
            model="model://ref-resolve-test",
        )
    )
    for i in range(5):
        pred = client.server.prediction_create(
            PredictionCreateReq(
                project_id=project_id,
                model="model://ref-resolve-test",
                inputs={"x": f"input_{i}"},
                output=f"output_{i}",
                evaluation_run_id=run.evaluation_run_id,
            )
        )
        client.server.prediction_finish(
            PredictionFinishReq(
                project_id=project_id,
                prediction_id=pred.prediction_id,
            )
        )

    original_refs_read_batch = client.server.refs_read_batch
    refs_read_batch_calls = []

    def tracking_refs_read_batch(req):
        refs_read_batch_calls.append(req)
        return original_refs_read_batch(req)

    with mock.patch.object(
        client.server, "refs_read_batch", side_effect=tracking_refs_read_batch
    ):
        paginated_res = client.server.eval_results_query(
            EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[run.evaluation_run_id],
                include_raw_data_rows=True,
                resolve_row_refs=True,
                limit=2,
                offset=0,
            )
        )

    assert paginated_res.total_rows == 5
    assert len(paginated_res.rows) == 2

    for call in refs_read_batch_calls:
        # only resolve refs for the paginated slice, not all rows
        assert len(call.refs) <= 2


def test_eval_results_include_predict_and_score_children(client):
    """Verify include_predict_and_score_children controls child call data."""
    project_id = client.project_id
    entity, project = from_project_id(project_id)

    scorer_res = client.server.scorer_create(
        ScorerCreateReq(
            project_id=project_id,
            name="children_test_scorer",
            op_source_code="def score(output):\n    return 1",
        )
    )
    scorer_ref = (
        f"weave:///{entity}/{project}/object/{scorer_res.object_id}:{scorer_res.digest}"
    )

    run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://children-test",
            model="model://children-test",
        )
    )
    pred = client.server.prediction_create(
        PredictionCreateReq(
            project_id=project_id,
            model="model://children-test",
            inputs={"x": 1},
            output="result",
            evaluation_run_id=run.evaluation_run_id,
        )
    )
    client.server.score_create(
        ScoreCreateReq(
            project_id=project_id,
            prediction_id=pred.prediction_id,
            scorer=scorer_ref,
            value=0.8,
            evaluation_run_id=run.evaluation_run_id,
        )
    )
    client.server.prediction_finish(
        PredictionFinishReq(
            project_id=project_id,
            prediction_id=pred.prediction_id,
        )
    )

    # With children included (default) — predict_call_id and scorer_call_ids populated
    res_with = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=project_id,
            evaluation_call_ids=[run.evaluation_run_id],
            include_predict_and_score_children=True,
        )
    )
    trial_with = res_with.rows[0].evaluations[0].trials[0]
    assert trial_with.predict_call_id is not None
    assert trial_with.scorer_call_ids != {}
    assert trial_with.scores["children_test_scorer"] == 0.8

    # scores should still be present.
    res_without = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=project_id,
            evaluation_call_ids=[run.evaluation_run_id],
            include_predict_and_score_children=False,
        )
    )
    trial_without = res_without.rows[0].evaluations[0].trials[0]
    assert trial_without.predict_call_id is None
    assert trial_without.scorer_call_ids == {}
    assert trial_without.scores["children_test_scorer"] == 0.8


def test_eval_results_summary_predict_total_tokens(client):
    """Summary predict_total_tokens sums per-trial model tokens, excluding scorer tokens."""
    project_id = client.project_id
    model_ref = "model://predict-tokens"
    run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://predict-tokens",
            model=model_ref,
        )
    )

    # Two trials. Each has a model predict child (30 tokens) and an LLM-judge
    # scorer child (100 tokens); the predict_and_score rollup carries both (130).
    for i in range(2):
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        pas_id = generate_id()
        client.server.call_start(
            CallStartReq(
                start=StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=pas_id,
                    trace_id=run.evaluation_run_id,
                    parent_id=run.evaluation_run_id,
                    op_name="Evaluation.predict_and_score",
                    started_at=now,
                    attributes={},
                    inputs={"example": {"idx": i}, "model": model_ref},
                )
            )
        )
        predict_id = generate_id()
        client.server.call_start(
            CallStartReq(
                start=StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=predict_id,
                    trace_id=run.evaluation_run_id,
                    parent_id=pas_id,
                    op_name="Model.predict",
                    started_at=now,
                    attributes={},
                    inputs={"self": model_ref, "example": {"idx": i}},
                )
            )
        )
        client.server.call_end(
            CallEndReq(
                end=EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=predict_id,
                    ended_at=now + datetime.timedelta(seconds=1),
                    output=f"answer_{i}",
                    summary={"usage": {"gpt-4o-mini": {"total_tokens": 30}}},
                )
            )
        )
        scorer_id = generate_id()
        client.server.call_start(
            CallStartReq(
                start=StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=scorer_id,
                    trace_id=run.evaluation_run_id,
                    parent_id=pas_id,
                    op_name="my_scorer.score",
                    started_at=now + datetime.timedelta(seconds=1),
                    attributes={},
                    inputs={"output": f"answer_{i}"},
                )
            )
        )
        client.server.call_end(
            CallEndReq(
                end=EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=scorer_id,
                    ended_at=now + datetime.timedelta(seconds=2),
                    output={"score": 1},
                    summary={"usage": {"judge": {"total_tokens": 100}}},
                )
            )
        )
        client.server.call_end(
            CallEndReq(
                end=EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=pas_id,
                    ended_at=now + datetime.timedelta(seconds=3),
                    output={"output": f"answer_{i}", "scores": {"my_scorer": 1}},
                    summary={
                        "usage": {
                            "gpt-4o-mini": {"total_tokens": 30},
                            "judge": {"total_tokens": 100},
                        }
                    },
                )
            )
        )

    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=project_id,
            evaluation_call_ids=[run.evaluation_run_id],
            include_rows=False,
            include_summary=True,
            include_predict_and_score_children=True,
        )
    )
    assert res.summary is not None
    # 2 trials x 30 model tokens = 60; the 2 x 100 judge tokens are excluded.
    assert res.summary.evaluations[0].predict_total_tokens == 60


def test_eval_results_summary_predict_total_tokens_none_when_absent(client):
    """predict_total_tokens is None when no trial carries token usage (caller falls back)."""
    eval_id, _ = _create_eval_with_scores(
        client, [{"accuracy": 0.5}], eval_name="no-tokens"
    )
    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[eval_id],
            include_rows=False,
            include_summary=True,
        )
    )
    assert res.summary is not None
    assert res.summary.evaluations[0].predict_total_tokens is None


def test_eval_results_summary_predict_total_tokens_counts_zero(client):
    """A trial whose model usage is 0 still counts: the field is 0, not None."""
    project_id = client.project_id
    model_ref = "model://zero-tokens"
    run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://zero-tokens",
            model=model_ref,
        )
    )
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    pas_id = generate_id()
    client.server.call_start(
        CallStartReq(
            start=StartedCallSchemaForInsert(
                project_id=project_id,
                id=pas_id,
                trace_id=run.evaluation_run_id,
                parent_id=run.evaluation_run_id,
                op_name="Evaluation.predict_and_score",
                started_at=now,
                attributes={},
                inputs={"example": {"idx": 0}, "model": model_ref},
            )
        )
    )
    predict_id = generate_id()
    client.server.call_start(
        CallStartReq(
            start=StartedCallSchemaForInsert(
                project_id=project_id,
                id=predict_id,
                trace_id=run.evaluation_run_id,
                parent_id=pas_id,
                op_name="Model.predict",
                started_at=now,
                attributes={},
                inputs={"self": model_ref, "example": {"idx": 0}},
            )
        )
    )
    client.server.call_end(
        CallEndReq(
            end=EndedCallSchemaForInsert(
                project_id=project_id,
                id=predict_id,
                ended_at=now + datetime.timedelta(seconds=1),
                output="result",
                summary={"usage": {"gpt-4o-mini": {"total_tokens": 0}}},
            )
        )
    )
    client.server.call_end(
        CallEndReq(
            end=EndedCallSchemaForInsert(
                project_id=project_id,
                id=pas_id,
                ended_at=now + datetime.timedelta(seconds=2),
                output={"output": "result", "scores": {}},
                summary={},
            )
        )
    )
    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=project_id,
            evaluation_call_ids=[run.evaluation_run_id],
            include_rows=False,
            include_summary=True,
            include_predict_and_score_children=True,
        )
    )
    assert res.summary is not None
    assert res.summary.evaluations[0].predict_total_tokens == 0


def test_eval_results_resolved_inputs_inline(client):
    """Inline inputs should be available as dicts in raw_data_row."""
    project_id = client.project_id

    run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://inline-inputs",
            model="model://inline-inputs",
        )
    )
    pred = client.server.prediction_create(
        PredictionCreateReq(
            project_id=project_id,
            model="model://inline-inputs",
            inputs={"question": "What is 2+2?", "expected": "4"},
            output="4",
            evaluation_run_id=run.evaluation_run_id,
        )
    )
    client.server.prediction_finish(
        PredictionFinishReq(
            project_id=project_id,
            prediction_id=pred.prediction_id,
        )
    )

    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=project_id,
            evaluation_call_ids=[run.evaluation_run_id],
            include_raw_data_rows=True,
            resolve_row_refs=False,
        )
    )

    assert res.total_rows == 1
    row = res.rows[0]
    assert isinstance(row.raw_data_row, dict)
    assert row.raw_data_row["question"] == "What is 2+2?"


@pytest.mark.parametrize(
    "predict_and_score_op_name",
    [
        "Evaluation.predict_and_score",
        "Evaluation.predictAndScore",  # ts-sdk camelCase variant
    ],
)
def test_eval_results_dataset_backed_no_resolve(client, predict_and_score_op_name):
    """Dataset-backed inputs should remain as ref strings when resolve_row_refs=False."""
    project_id = client.project_id

    dataset_rows = [{"question": "What is 2+2?"}]
    table_res = client.server.table_create(
        TableCreateReq.model_validate(
            {"table": {"project_id": project_id, "rows": dataset_rows}}
        )
    )

    run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://no-resolve",
            model="model://no-resolve",
        )
    )

    digest = table_res.row_digests[0]
    ref_str = f"weave-trace-internal:///{project_id}/table/{table_res.digest}/attr/rows/id/{digest}"
    predict_and_score_id = generate_id()
    client.server.call_start(
        CallStartReq(
            start=StartedCallSchemaForInsert(
                project_id=project_id,
                id=predict_and_score_id,
                trace_id=run.evaluation_run_id,
                parent_id=run.evaluation_run_id,
                op_name=predict_and_score_op_name,
                started_at=datetime.datetime.now(tz=datetime.timezone.utc),
                attributes={},
                inputs={"example": ref_str, "model": "model://no-resolve"},
            )
        )
    )
    client.server.call_end(
        CallEndReq(
            end=EndedCallSchemaForInsert(
                project_id=project_id,
                id=predict_and_score_id,
                ended_at=datetime.datetime.now(tz=datetime.timezone.utc),
                output={"output": "4", "scores": {}},
                summary={},
            )
        )
    )

    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=project_id,
            evaluation_call_ids=[run.evaluation_run_id],
            include_raw_data_rows=True,
            resolve_row_refs=False,
        )
    )

    assert res.total_rows == 1
    row = res.rows[0]
    assert isinstance(row.raw_data_row, str)
    assert "/attr/rows/id/" in row.raw_data_row


def _create_eval_with_scores(client, scores_per_row, eval_name="eval"):
    """Helper: create an eval run with predict-and-score calls having given scores.

    scores_per_row: list of dicts, e.g. [{"accuracy": 0.9}, {"accuracy": 0.3}]
    Returns (evaluation_run_id, [pas_call_ids]).
    """
    project_id = client.project_id
    run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation=f"eval://{eval_name}",
            model=f"model://{eval_name}",
        )
    )
    predict_and_score_ids = []
    for i, scores in enumerate(scores_per_row):
        predict_and_score_id = generate_id()
        predict_and_score_ids.append(predict_and_score_id)
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        client.server.call_start(
            CallStartReq(
                start=StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=predict_and_score_id,
                    trace_id=run.evaluation_run_id,
                    parent_id=run.evaluation_run_id,
                    op_name="Evaluation.predict_and_score",
                    started_at=now,
                    attributes={},
                    inputs={
                        "example": {"question": f"q{i}", "idx": i},
                        "model": f"model://{eval_name}",
                    },
                )
            )
        )
        client.server.call_end(
            CallEndReq(
                end=EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=predict_and_score_id,
                    ended_at=now + datetime.timedelta(seconds=i + 1),
                    output={
                        "output": f"answer_{i}",
                        "scores": scores,
                        "model_latency": {"mean": float(i + 1)},
                    },
                    summary={},
                )
            )
        )
    return run.evaluation_run_id, predict_and_score_ids


def test_eval_results_row_order_is_stable(client):
    """Row order should be stable across repeated requests (default sort by row_digest)."""
    eval_id, _ = _create_eval_with_scores(
        client,
        [{"accuracy": 0.1}, {"accuracy": 0.5}, {"accuracy": 0.9}, {"accuracy": 0.3}],
        eval_name="order-stable",
    )
    digests_first = None
    for _ in range(3):
        res = client.server.eval_results_query(
            EvalResultsQueryReq(
                project_id=client.project_id,
                evaluation_call_ids=[eval_id],
            )
        )
        digests = [row.row_digest for row in res.rows]
        if digests_first is None:
            digests_first = digests
        else:
            assert digests == digests_first, "Row order changed between requests"


def test_eval_results_excludes_deleted_calls(client):
    """Deleted PAS calls should not appear in eval results."""
    eval_id, predict_and_score_ids = _create_eval_with_scores(
        client,
        [{"accuracy": 0.3}, {"accuracy": 0.9}, {"accuracy": 0.6}],
        eval_name="delete-test",
    )
    # Verify all 3 rows are present before deletion
    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[eval_id],
        )
    )
    assert res.total_rows == 3

    # verify we no longer see deleted calls
    client.server.calls_delete(
        CallsDeleteReq(
            project_id=client.project_id, call_ids=[predict_and_score_ids[0]]
        )
    )

    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[eval_id],
        )
    )
    assert res.total_rows == 2


def test_eval_results_sort_by_score_desc(client):
    """Sort by scores.accuracy DESC should return highest-scoring row first."""
    eval_id, _ = _create_eval_with_scores(
        client,
        [{"accuracy": 0.3}, {"accuracy": 0.9}, {"accuracy": 0.6}],
        eval_name="sort-desc",
    )
    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[eval_id],
            include_raw_data_rows=True,
            sort_by=[EvalResultsSortBy(field="scores.accuracy", direction="desc")],
        )
    )
    assert res.total_rows == 3
    accuracies = [row.evaluations[0].trials[0].scores["accuracy"] for row in res.rows]
    assert accuracies == [0.9, 0.6, 0.3]


def test_eval_results_sort_by_score_asc(client):
    """Sort by scores.accuracy ASC should return lowest-scoring row first."""
    eval_id, _ = _create_eval_with_scores(
        client,
        [{"accuracy": 0.3}, {"accuracy": 0.9}, {"accuracy": 0.6}],
        eval_name="sort-asc",
    )
    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[eval_id],
            include_raw_data_rows=True,
            sort_by=[EvalResultsSortBy(field="scores.accuracy", direction="asc")],
        )
    )
    accuracies = [row.evaluations[0].trials[0].scores["accuracy"] for row in res.rows]
    assert accuracies == [0.3, 0.6, 0.9]


def test_eval_results_filter_score_gte(client):
    """Filter scores.accuracy >= 0.5 should exclude rows below threshold."""
    eval_id, _ = _create_eval_with_scores(
        client,
        [{"accuracy": 0.3}, {"accuracy": 0.9}, {"accuracy": 0.6}],
        eval_name="filter-gte",
    )
    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[eval_id],
            include_raw_data_rows=True,
            filters=[
                EvalResultsFilter(
                    query=Query.model_validate(
                        {
                            "$expr": {
                                "$gte": [
                                    {
                                        "$convert": {
                                            "input": {"$getField": "scores.accuracy"},
                                            "to": "double",
                                        }
                                    },
                                    {"$literal": 0.5},
                                ]
                            }
                        }
                    ),
                )
            ],
        )
    )
    assert res.total_rows == 2
    accuracies = sorted(
        row.evaluations[0].trials[0].scores["accuracy"] for row in res.rows
    )
    assert accuracies == [0.6, 0.9]


def test_eval_results_sort_and_filter_combined(client):
    """Sort + filter together: filter first, then sort the remaining rows."""
    eval_id, _ = _create_eval_with_scores(
        client,
        [{"accuracy": 0.1}, {"accuracy": 0.5}, {"accuracy": 0.9}, {"accuracy": 0.7}],
        eval_name="sort-filter",
    )
    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[eval_id],
            include_raw_data_rows=True,
            sort_by=[EvalResultsSortBy(field="scores.accuracy", direction="desc")],
            filters=[
                EvalResultsFilter(
                    query=Query.model_validate(
                        {
                            "$expr": {
                                "$gte": [
                                    {
                                        "$convert": {
                                            "input": {"$getField": "scores.accuracy"},
                                            "to": "double",
                                        }
                                    },
                                    {"$literal": 0.4},
                                ]
                            }
                        }
                    ),
                )
            ],
        )
    )
    assert res.total_rows == 3
    accuracies = [row.evaluations[0].trials[0].scores["accuracy"] for row in res.rows]
    assert accuracies == [0.9, 0.7, 0.5]


def test_eval_results_filter_with_evaluation_call_id_scope(client):
    """Filter scoped to evaluation_call_id only tests that eval's scores."""
    eval_id, _ = _create_eval_with_scores(
        client,
        [{"accuracy": 0.9}, {"accuracy": 0.3}, {"accuracy": 0.7}],
        eval_name="scope-single",
    )
    res_unfiltered = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[eval_id],
            include_raw_data_rows=True,
        )
    )
    assert res_unfiltered.total_rows == 3

    res_filtered = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[eval_id],
            include_raw_data_rows=True,
            filters=[
                EvalResultsFilter(
                    evaluation_call_id=eval_id,
                    query=Query.model_validate(
                        {
                            "$expr": {
                                "$gte": [
                                    {
                                        "$convert": {
                                            "input": {"$getField": "scores.accuracy"},
                                            "to": "double",
                                        }
                                    },
                                    {"$literal": 0.5},
                                ]
                            }
                        }
                    ),
                )
            ],
        )
    )
    assert res_filtered.total_rows == 2
    accuracies = sorted(
        row.evaluations[0].trials[0].scores["accuracy"] for row in res_filtered.rows
    )
    assert accuracies == [0.7, 0.9]


def test_eval_results_sort_unsupported_field_returns_invalid_request(client):
    """Sorting on an unsupported field prefix returns InvalidRequest."""
    eval_id, _ = _create_eval_with_scores(
        client, [{"accuracy": 0.5}], eval_name="bad-field"
    )
    with pytest.raises(InvalidRequest, match="Unsupported sort field"):
        client.server.eval_results_query(
            EvalResultsQueryReq(
                project_id=client.project_id,
                evaluation_call_ids=[eval_id],
                sort_by=[EvalResultsSortBy(field="bogus.field", direction="asc")],
            )
        )


def test_eval_results_sort_by_output(client):
    """Sort by output.label orders rows by nested model output field."""
    project_id = client.project_id
    run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://output-sort",
            model="model://output-sort",
        )
    )
    labels = ["cherry", "apple", "banana"]
    for i, label in enumerate(labels):
        call_id = generate_id()
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        client.server.call_start(
            CallStartReq(
                start=StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    trace_id=run.evaluation_run_id,
                    parent_id=run.evaluation_run_id,
                    op_name="Evaluation.predict_and_score",
                    started_at=now,
                    attributes={},
                    inputs={
                        "example": {"idx": i},
                        "model": "model://output-sort",
                    },
                )
            )
        )
        client.server.call_end(
            CallEndReq(
                end=EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    ended_at=now + datetime.timedelta(seconds=1),
                    output={
                        "output": {"label": label},
                        "scores": {"accuracy": float(i)},
                    },
                    summary={},
                )
            )
        )
    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=project_id,
            evaluation_call_ids=[run.evaluation_run_id],
            include_raw_data_rows=True,
            sort_by=[EvalResultsSortBy(field="output.output.label", direction="asc")],
        )
    )
    assert res.total_rows == 3
    sorted_labels = [
        row.evaluations[0].trials[0].model_output["label"] for row in res.rows
    ]
    assert sorted_labels == ["apple", "banana", "cherry"]


# TODO: remove the skip once the in-memory fake sorts output/input numerically
# (it currently orders them lexicographically); ClickHouse already does.
@pytest.mark.skipif(
    FAKE_NOT_IMPLEMENTED,
    reason="fake: output/input sort is lexicographic, not numeric, yet",
)
def test_eval_results_sort_by_numeric_output(client):
    """Numeric output columns sort by value, not lexicographically.

    Regression test for the ClickHouse ORDER BY: previously `output.*` fields
    were ordered as the raw `JSON_VALUE` String, so e.g. 10 sorted before 2.
    Executed against ClickHouse so we exercise the actual generated SQL.
    """
    project_id = client.project_id
    run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://numeric-output-sort",
            model="model://numeric-output-sort",
        )
    )
    # Chosen so lexicographic and numeric orderings differ:
    # lexicographic asc -> [1, 10, 2]; numeric asc -> [1, 2, 10].
    values = [2, 10, 1]
    for i, value in enumerate(values):
        call_id = generate_id()
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        client.server.call_start(
            CallStartReq(
                start=StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    trace_id=run.evaluation_run_id,
                    parent_id=run.evaluation_run_id,
                    op_name="Evaluation.predict_and_score",
                    started_at=now,
                    attributes={},
                    inputs={
                        "example": {"idx": i},
                        "model": "model://numeric-output-sort",
                    },
                )
            )
        )
        client.server.call_end(
            CallEndReq(
                end=EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    ended_at=now + datetime.timedelta(seconds=1),
                    output={
                        "output": {"predicted": value},
                        "scores": {"accuracy": float(i)},
                    },
                    summary={},
                )
            )
        )

    def sorted_predictions(direction: str) -> list:
        res = client.server.eval_results_query(
            EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[run.evaluation_run_id],
                include_raw_data_rows=True,
                sort_by=[
                    EvalResultsSortBy(
                        field="output.output.predicted", direction=direction
                    )
                ],
            )
        )
        return [
            row.evaluations[0].trials[0].model_output["predicted"] for row in res.rows
        ]

    assert sorted_predictions("asc") == [1, 2, 10]
    assert sorted_predictions("desc") == [10, 2, 1]


# TODO: remove the skip once the in-memory fake sorts output/input numerically
# (it currently orders them lexicographically); ClickHouse already does.
@pytest.mark.skipif(
    FAKE_NOT_IMPLEMENTED,
    reason="fake: output/input sort is lexicographic, not numeric, yet",
)
def test_eval_results_sort_by_numeric_input(client):
    """Numeric input columns sort by value, not lexicographically.

    Inputs resolve via a different path than outputs (the `resolved_inputs`
    CTE / inline `example` fallback), so cover them separately. Executed
    against ClickHouse so we exercise the actual generated SQL.
    """
    project_id = client.project_id
    run = client.server.evaluation_run_create(
        EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://numeric-input-sort",
            model="model://numeric-input-sort",
        )
    )
    # Chosen so lexicographic and numeric orderings differ:
    # lexicographic asc -> [1, 10, 2]; numeric asc -> [1, 2, 10].
    values = [2, 10, 1]
    for value in values:
        call_id = generate_id()
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        client.server.call_start(
            CallStartReq(
                start=StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    trace_id=run.evaluation_run_id,
                    parent_id=run.evaluation_run_id,
                    op_name="Evaluation.predict_and_score",
                    started_at=now,
                    attributes={},
                    inputs={
                        "example": {"x": value},
                        "model": "model://numeric-input-sort",
                    },
                )
            )
        )
        client.server.call_end(
            CallEndReq(
                end=EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    ended_at=now + datetime.timedelta(seconds=1),
                    output={"output": {"label": "x"}, "scores": {"accuracy": 1.0}},
                    summary={},
                )
            )
        )

    def sorted_inputs(direction: str) -> list:
        res = client.server.eval_results_query(
            EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[run.evaluation_run_id],
                include_raw_data_rows=True,
                sort_by=[EvalResultsSortBy(field="inputs.x", direction=direction)],
            )
        )
        return [row.raw_data_row["x"] for row in res.rows]

    assert sorted_inputs("asc") == [1, 2, 10]
    assert sorted_inputs("desc") == [10, 2, 1]


def test_eval_results_summary_with_filter(client):
    """Summary reflects filtered rows, not all rows."""
    eval_id, _ = _create_eval_with_scores(
        client,
        [{"accuracy": 0.2}, {"accuracy": 0.6}, {"accuracy": 0.9}],
        eval_name="summary-filter",
    )
    res = client.server.eval_results_query(
        EvalResultsQueryReq(
            project_id=client.project_id,
            evaluation_call_ids=[eval_id],
            include_rows=False,
            include_summary=True,
            filters=[
                EvalResultsFilter(
                    query=Query.model_validate(
                        {
                            "$expr": {
                                "$gte": [
                                    {
                                        "$convert": {
                                            "input": {"$getField": "scores.accuracy"},
                                            "to": "double",
                                        }
                                    },
                                    {"$literal": 0.5},
                                ]
                            }
                        }
                    ),
                )
            ],
        )
    )
    assert res.summary is not None
    assert res.summary.row_count == 2
    # mean should be (0.6 + 0.9) / 2 = 0.75, not (0.2 + 0.6 + 0.9) / 3
    eval_summary = res.summary.evaluations[0]
    accuracy_stat = next(
        s for s in eval_summary.scorer_stats if s.scorer_key == "accuracy"
    )
    assert accuracy_stat.numeric_mean == pytest.approx(0.75, abs=0.01)
