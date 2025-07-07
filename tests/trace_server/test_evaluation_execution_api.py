import json

import pytest

from tests.trace_server.completions_util import with_simple_mock_litellm_completion
from weave.trace.refs import ObjectRef
from weave.trace_server.execution_runner.run_as_user import with_client_bound_to_project
from weave.trace_server.execution_runner.user_scripts.apply_scorer import apply_scorer
from weave.trace_server.execution_runner.user_scripts.evaluate_model import (
    evaluate_model,
)
from weave.trace_server.execution_runner.user_scripts.run_model import run_model
from weave.trace_server.trace_server_interface import (
    ApplyScorerReq,
    ApplyScorerRes,
    CallsQueryReq,
    EvaluateModelReq,
    EvaluateModelRes,
    ObjCreateReq,
    ObjQueryReq,
    RunModelReq,
    RunModelRes,
    TableCreateReq,
    TraceServerInterface,
)


@pytest.mark.asyncio
async def test_run_model(ch_only_trace_server: TraceServerInterface, client_creator):
    """
    Test the run_model API endpoint with isolated execution.

    This test verifies that:
    1. Models can be created and executed through the run_model API
    2. Model execution is properly traced (creates call records)
    3. Different projects are properly isolated from each other

    The test creates models in two different projects and executes them,
    ensuring that calls and objects are properly scoped to each project.
    """
    entity = "shawn"

    def create_model(entity: str, project: str) -> str:
        project_id = f"{entity}/{project}"
        model_object_id = "test_run_model"
        llm_model_val = {
            "llm_model_id": "gpt-4o-mini",
            "default_params": {
                "messages_template": [
                    {"role": "system", "content": "You are a helpful assistant."},
                ],
                "response_format": "text",
            },
        }
        model_create_res = ch_only_trace_server.obj_create(
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
        model_digest = model_create_res.digest
        return ObjectRef(
            entity=entity,
            project=project,
            name=model_object_id,
            _digest=model_digest,
        ).uri()

    async def run_model_harness(
        entity: str,
        project: str,
        model_ref_uri: str,
        user_input: str,
        expected_output: str,
        # Running with local mode true directly calls the underlying user script
        # allowing for easier debugging of the user script
        run_mode_local: bool = False,
    ) -> RunModelRes:
        project_id = f"{entity}/{project}"
        req = RunModelReq.model_validate(
            {
                "project_id": project_id,
                "model_ref": model_ref_uri,
                "inputs": {"user_input": user_input},
            }
        )
        with with_simple_mock_litellm_completion(expected_output):
            if run_mode_local:
                with with_client_bound_to_project(
                    entity, project, ch_only_trace_server
                ):
                    model_run_res = await run_model(req)
            else:
                model_run_res = await ch_only_trace_server.run_model(req)
        return model_run_res

    async def do_test(
        entity: str,
        project: str,
        expected_output: str,
        user_input: str,
        run_mode_local: bool = False,
    ):
        project_id = f"{entity}/{project}"
        model_ref_uri = create_model(entity, project)
        model_run_res = await run_model_harness(
            entity, project, model_ref_uri, user_input, expected_output, run_mode_local
        )

        assert model_run_res.output == expected_output

        calls_res = ch_only_trace_server.calls_query(
            CallsQueryReq.model_validate(
                {
                    "project_id": project_id,
                }
            )
        )

        # Completion call and predict call
        assert len(calls_res.calls) == 2

        objs_res = ch_only_trace_server.objs_query(
            ObjQueryReq.model_validate(
                {
                    "project_id": project_id,
                }
            )
        )

        # Model definition & predict object
        assert len(objs_res.objs) == 2

        calls_res = ch_only_trace_server.calls_query(
            CallsQueryReq.model_validate(
                {
                    "project_id": project_id,
                    "filter": {
                        "call_ids": [model_run_res.call_id],
                    },
                }
            )
        )

        assert len(calls_res.calls) == 1
        call = calls_res.calls[0]
        assert call.output == expected_output
        assert call.inputs["user_input"] == user_input
        assert call.op_name.startswith(
            f"weave:///{project_id}/op/LLMStructuredCompletionModel.predict:"
        )

    for run_mode_local in [False, True]:
        local_suffix = "_local" if run_mode_local else ""
        # First, do the test with the first project
        await do_test(
            entity=entity,
            project="test_run_model_1" + local_suffix,
            expected_output="Fantastic - how are you?",
            user_input="Hello, how are you?",
            run_mode_local=run_mode_local,
        )

        # Perform the test with a different project
        # Internal assertions ensure that the calls and objects are isolated
        await do_test(
            entity=entity,
            project="test_run_model_2" + local_suffix,
            expected_output="Hi friend",
            user_input="Hey there!",
            run_mode_local=run_mode_local,
        )


@pytest.mark.asyncio
async def test_apply_scorer(ch_only_trace_server: TraceServerInterface, client_creator):
    """
    Test the apply_scorer API endpoint with isolated execution.

    This test verifies that:
    1. Scorers can be created and executed through the apply_scorer API
    2. Scorer execution is properly traced (creates call records)
    3. Scorers can correctly score model outputs
    4. Different projects are properly isolated from each other

    The test creates a model, executes it to get a call to score,
    then creates a scorer and applies it to the call.
    """
    entity = "shawn"

    def create_model(entity: str, project: str) -> str:
        """Create a test model and return its reference URI."""
        project_id = f"{entity}/{project}"
        model_object_id = "test_model_for_scorer"
        llm_model_val = {
            "llm_model_id": "gpt-4o-mini",
            "default_params": {
                "messages_template": [
                    {"role": "system", "content": "You are a helpful assistant."},
                ],
                "response_format": "text",
            },
        }
        model_create_res = ch_only_trace_server.obj_create(
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
        ).uri()

    def create_scorer(entity: str, project: str) -> str:
        """Create a test scorer and return its reference URI."""
        project_id = f"{entity}/{project}"

        # First create the model for the scorer
        scorer_model_object_id = "test_scorer_model"
        scorer_model_val = {
            "llm_model_id": "gpt-4o-mini",
            "default_params": {
                "messages_template": [
                    {
                        "role": "system",
                        "content": "You are an expert judge. Evaluate the response and return a score from 0 to 10.",
                    },
                ],
                "response_format": "text",
            },
        }
        scorer_model_create_res = ch_only_trace_server.obj_create(
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
        ).uri()

        # Then create the scorer
        scorer_object_id = "test_llm_judge_scorer"
        scorer_val = {
            "_type": "LLMAsAJudgeScorer",
            "_class_name": "LLMAsAJudgeScorer",
            "_bases": ["BaseModel", "Scorer", "LLMAsAJudgeScorer"],
            "model": scorer_model_ref,
            "scoring_prompt": "User input: {user_input}\nModel output: {output}\n\nScore the quality of the response (0-10).",
        }
        scorer_create_res = ch_only_trace_server.obj_create(
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
        ).uri()

    async def run_model_and_get_call_id(
        entity: str,
        project: str,
        model_ref_uri: str,
        user_input: str,
        expected_output: str,
    ) -> str:
        """Run a model and return the call ID."""
        project_id = f"{entity}/{project}"
        req = RunModelReq.model_validate(
            {
                "project_id": project_id,
                "model_ref": model_ref_uri,
                "inputs": {"user_input": user_input},
            }
        )
        with with_simple_mock_litellm_completion(expected_output):
            model_run_res = await ch_only_trace_server.run_model(req)
        return model_run_res.call_id

    async def apply_scorer_harness(
        entity: str,
        project: str,
        scorer_ref_uri: str,
        target_call_id: str,
        expected_score: str,
        run_mode_local: bool = False,
    ) -> ApplyScorerRes:
        """Apply a scorer to a call."""
        project_id = f"{entity}/{project}"
        req = ApplyScorerReq.model_validate(
            {
                "project_id": project_id,
                "scorer_ref": scorer_ref_uri,
                "target_call_id": target_call_id,
                "additional_inputs": None,
            }
        )
        with with_simple_mock_litellm_completion(expected_score):
            if run_mode_local:
                with with_client_bound_to_project(
                    entity, project, ch_only_trace_server
                ):
                    scorer_res = await apply_scorer(req)
            else:
                scorer_res = await ch_only_trace_server.apply_scorer(req)
        return scorer_res

    async def do_test(
        entity: str,
        project: str,
        model_output: str,
        user_input: str,
        expected_score: str,
        run_mode_local: bool = False,
    ):
        project_id = f"{entity}/{project}"

        # Create model and scorer
        model_ref_uri = create_model(entity, project)
        scorer_ref_uri = create_scorer(entity, project)

        # Run the model to get a call to score
        call_id = await run_model_and_get_call_id(
            entity, project, model_ref_uri, user_input, model_output
        )

        # Apply the scorer to the call
        scorer_res = await apply_scorer_harness(
            entity, project, scorer_ref_uri, call_id, expected_score, run_mode_local
        )

        # Verify the scorer output (convert to string since mock returns strings)
        assert str(scorer_res.output) == expected_score

        # Query for calls
        calls_res = ch_only_trace_server.calls_query(
            CallsQueryReq.model_validate(
                {
                    "project_id": project_id,
                }
            )
        )

        # Should have 5 calls: model predict, model completion, scorer score, scorer model predict, scorer completion
        assert len(calls_res.calls) == 5

        # Query for objects
        objs_res = ch_only_trace_server.objs_query(
            ObjQueryReq.model_validate(
                {
                    "project_id": project_id,
                }
            )
        )

        # Should have 5 objects: model, model predict op, scorer model, scorer, scorer score op
        assert len(objs_res.objs) == 5

        # Query for the specific scorer call
        scorer_calls_res = ch_only_trace_server.calls_query(
            CallsQueryReq.model_validate(
                {
                    "project_id": project_id,
                    "filter": {
                        "call_ids": [scorer_res.call_id],
                    },
                }
            )
        )

        assert len(scorer_calls_res.calls) == 1
        scorer_call = scorer_calls_res.calls[0]
        assert str(scorer_call.output) == expected_score
        # The scorer call should be for the LLMAsAJudgeScorer.score op
        assert scorer_call.op_name.startswith(
            f"weave:///{project_id}/op/LLMAsAJudgeScorer.score:"
        )

    # Test both local and non-local modes
    for run_mode_local in [False, True]:
        local_suffix = "_local" if run_mode_local else ""

        # Test with first project
        await do_test(
            entity=entity,
            project="test_apply_scorer_1" + local_suffix,
            model_output="I'm doing great, thanks for asking!",
            user_input="How are you?",
            expected_score="8",
            run_mode_local=run_mode_local,
        )

        # Test with second project to ensure isolation
        await do_test(
            entity=entity,
            project="test_apply_scorer_2" + local_suffix,
            model_output="The weather is nice today.",
            user_input="What's the weather like?",
            expected_score="7",
            run_mode_local=run_mode_local,
        )


@pytest.mark.asyncio
async def test_evaluate_model(
    ch_only_trace_server: TraceServerInterface, client_creator
):
    """
    Test the evaluate_model API endpoint with isolated execution.

    This test verifies that:
    1. Evaluations can be created and executed through the evaluate_model API
    2. Evaluation execution is properly traced (creates call records)
    3. Evaluations correctly run models against datasets and apply scorers
    4. Different projects are properly isolated from each other

    The test creates a model, dataset, scorer, and evaluation, then runs
    the evaluation through the evaluate_model API.
    """
    entity = "shawn"

    def create_model(entity: str, project: str) -> str:
        """Create a test model and return its reference URI."""
        project_id = f"{entity}/{project}"
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
        model_create_res = ch_only_trace_server.obj_create(
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
        ).uri()

    def create_dataset(entity: str, project: str) -> str:
        """Create a test dataset and return its reference URI."""
        project_id = f"{entity}/{project}"
        dataset_table_val = [
            {"user_input": "How are you?", "expected": "I'm doing well, thank you!"},
            # {"user_input": "What's 2+2?", "expected": "4"},
            # {
            #     "user_input": "Tell me a joke",
            #     "expected": "Why did the chicken cross the road?",
            # },
        ]
        dataset_table_res = ch_only_trace_server.table_create(
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
        dataset_create_res = ch_only_trace_server.obj_create(
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
        ).uri()

    def create_scorer(entity: str, project: str) -> str:
        """Create a test scorer and return its reference URI."""
        project_id = f"{entity}/{project}"

        # First create the model for the scorer
        scorer_model_object_id = "test_eval_scorer_model"
        scorer_model_val = {
            "llm_model_id": "gpt-4o-mini",
            "default_params": {
                "messages_template": [
                    {
                        "role": "system",
                        "content": "You are an expert judge. Compare the model output to the expected output and return a score from 0 to 10.",
                    },
                ],
                "response_format": "text",
            },
        }
        scorer_model_create_res = ch_only_trace_server.obj_create(
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
        ).uri()

        # Then create the scorer
        scorer_object_id = "test_eval_llm_judge_scorer"
        scorer_val = {
            "_type": "LLMAsAJudgeScorer",
            "_class_name": "LLMAsAJudgeScorer",
            "_bases": ["BaseModel", "Scorer", "LLMAsAJudgeScorer"],
            "model": scorer_model_ref,
            "scoring_prompt": "User input: {user_input}\nModel output: {output}\nExpected output: {expected}\n\nScore the similarity (0-10).",
        }
        scorer_create_res = ch_only_trace_server.obj_create(
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
        ).uri()

    def create_evaluation(
        entity: str, project: str, dataset_ref: str, scorer_ref: str
    ) -> str:
        """Create a test evaluation and return its reference URI."""
        project_id = f"{entity}/{project}"
        evaluation_object_id = "test_evaluation"
        evaluation_val = {
            "_type": "Evaluation",
            "_class_name": "Evaluation",
            "_bases": ["BaseModel", "Object", "Evaluation"],
            "dataset": dataset_ref,
            "scorers": [scorer_ref],
            # Note: You might need to add more fields depending on the Evaluation class structure
        }
        evaluation_create_res = ch_only_trace_server.obj_create(
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
        ).uri()

    async def evaluate_model_harness(
        entity: str,
        project: str,
        evaluation_ref: str,
        model_ref: str,
        run_mode_local: bool = False,
    ) -> EvaluateModelRes:
        """Run an evaluation on a model."""
        project_id = f"{entity}/{project}"
        req = EvaluateModelReq.model_validate(
            {
                "project_id": project_id,
                "evaluation_ref": evaluation_ref,
                "model_ref": model_ref,
            }
        )
        # Mock the LLM completions for all the calls during evaluation
        # This is a simplified mock - in reality the evaluation would make multiple calls
        with with_simple_mock_litellm_completion(
            json.dumps({"score": 9})
        ):  # Mock score response
            if run_mode_local:
                with with_client_bound_to_project(
                    entity, project, ch_only_trace_server
                ):
                    eval_res = await evaluate_model(req)
            else:
                eval_res = await ch_only_trace_server.evaluate_model(req)
        return eval_res

    async def do_test(
        entity: str,
        project: str,
        run_mode_local: bool = False,
    ):
        project_id = f"{entity}/{project}"

        # Create all necessary objects
        model_ref_uri = create_model(entity, project)
        dataset_ref_uri = create_dataset(entity, project)
        scorer_ref_uri = create_scorer(entity, project)
        evaluation_ref_uri = create_evaluation(
            entity, project, dataset_ref_uri, scorer_ref_uri
        )

        # Run the evaluation
        eval_res = await evaluate_model_harness(
            entity, project, evaluation_ref_uri, model_ref_uri, run_mode_local
        )

        # Verify the evaluation output is a dictionary with results
        assert isinstance(eval_res.output, dict)

        # Query for calls
        calls_res = ch_only_trace_server.calls_query(
            CallsQueryReq.model_validate(
                {
                    "project_id": project_id,
                }
            )
        )

        # evaluate
        # predict_and_score
        #    predict
        # complete
        #    score
        # complete
        # summary
        assert len(calls_res.calls) == 7

        # Query for the specific evaluation call
        eval_calls_res = ch_only_trace_server.calls_query(
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
        assert eval_res.output == eval_call.output
        assert eval_call.summary == {}

    for run_mode_local in [False, True]:
        local_suffix = "_local" if run_mode_local else ""

        # Test with first project
        await do_test(
            entity=entity,
            project="test_evaluate_model_1" + local_suffix,
            run_mode_local=run_mode_local,
        )

        # Test with second project to ensure isolation
        await do_test(
            entity=entity,
            project="test_evaluate_model_2" + local_suffix,
            run_mode_local=run_mode_local,
        )
