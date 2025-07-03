import pytest

from tests.trace_server.completions_util import with_simple_mock_litellm_completion
from weave.trace.refs import ObjectRef
from weave.trace_server.execution_runner.run_as_user import with_client_bound_to_project
from weave.trace_server.execution_runner.user_scripts.run_model import run_model
from weave.trace_server.trace_server_interface import (
    CallsQueryReq,
    ObjCreateReq,
    ObjQueryReq,
    RunModelReq,
    RunModelRes,
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
                with with_client_bound_to_project(entity, project, ch_only_trace_server):
                    model_run_res = run_model(req)
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
