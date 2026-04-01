import json
from unittest import mock

import pytest

import weave
from tests.conftest import LATENCY_TOL
from tests.trace.util import client_is_sqlite
from tests.trace_server.completions_util import with_simple_mock_litellm_completion
from weave.trace.refs import ObjectRef
from weave.trace.weave_client import WeaveClient, generate_id
from weave.trace_server.trace_server_interface import (
    CallsQueryReq,
    EvalResultsQueryReq,
    EvaluateModelReq,
    EvaluateModelRes,
    EvaluationRunCreateReq,
    EvaluationStatusComplete,
    EvaluationStatusNotFound,
    EvaluationStatusReq,
    EvaluationStatusRunning,
    ObjCreateReq,
    PredictionCreateReq,
    PredictionFinishReq,
    ScoreCreateReq,
    ScorerCreateReq,
    TableCreateReq,
    TraceServerInterface,
    TraceStatus,
)
from weave.trace_server.workers.evaluate_model_worker import evaluate_model_worker
from weave.utils.project_id import from_project_id, to_project_id


@pytest.mark.asyncio
async def test_evaluation_status(client):
    is_sqlite = client_is_sqlite(client)
    if is_sqlite:
        # TODO: FIX ME, should work in sqlite, but get database lock error:
        # https://github.com/wandb/weave/actions/runs/16228542054/job/45826073140?pr=5069
        # `Task failed: OperationalError: database table is locked: calls`
        return

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
    is_sqlite = client_is_sqlite(client)
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
    # Mock the LLM completions for all the calls during evaluation
    # This is a simplified mock - in reality the evaluation would make multiple calls
    with with_simple_mock_litellm_completion(
        json.dumps({"score": 9})
    ):  # Mock score response
        eval_res = evaluate_model_fn(req)

    # Query for calls
    calls_res = client.server.calls_query(
        CallsQueryReq.model_validate(
            {
                "project_id": project_id,
            }
        )
    )

    # Here are the 9 calls that are expected:
    # evaluate
    # predict_and_score
    #    predict
    #       complete
    #    score
    #       predict
    #          complete
    # summary
    #    scorer summary
    # Note: SQLite does not support calling the LLM, so it is not correct.
    # I want to keep the sqlite tests here however as we are more interested
    # in testing the overal flow, not LLMs in particular.
    if is_sqlite:
        assert len(calls_res.calls) == 5
    else:
        assert len(calls_res.calls) == 9

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
    if is_sqlite:
        assert eval_call.summary["status_counts"] == {
            TraceStatus.SUCCESS: 4,
            TraceStatus.ERROR: 1,
        }
        assert eval_call.summary["weave"]["status"] == TraceStatus.DESCENDANT_ERROR
        assert eval_call.output == {
            "LLMAsAJudgeScorer": None,
            "model_latency": {"mean": pytest.approx(0, abs=LATENCY_TOL)},
        }
    else:
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
