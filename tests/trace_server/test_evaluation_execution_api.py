import pytest

from tests.trace_server.completions_util import with_simple_mock_litellm_completion
from weave.trace.refs import ObjectRef
from weave.trace_server.trace_server_interface import (
    CallsQueryReq,
    ObjCreateReq,
    ObjQueryReq,
    RunModelReq,
    RunModelRes,
    TraceServerInterface,
)


@pytest.mark.asyncio
async def test_run_model(trace_server: TraceServerInterface):
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
        model_create_res = trace_server.obj_create(
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

    async def run_model(
        entity: str,
        project: str,
        model_ref_uri: str,
        user_input: str,
        expected_output: str,
    ) -> RunModelRes:
        project_id = f"{entity}/{project}"
        with with_simple_mock_litellm_completion(expected_output):
            model_run_res = await trace_server.run_model(
                RunModelReq.model_validate(
                    {
                        "project_id": project_id,
                        "model_ref": model_ref_uri,
                        "inputs": {
                            "input_type": "value",
                            "value": {"user_input": user_input},
                        },
                    }
                )
            )
        return model_run_res

    async def do_test(entity: str, project: str, expected_output: str, user_input: str):
        project_id = f"{entity}/{project}"
        model_ref_uri = create_model(entity, project)
        model_run_res = await run_model(
            entity, project, model_ref_uri, user_input, expected_output
        )

        assert model_run_res.output == expected_output

        calls_res = trace_server.calls_query(
            CallsQueryReq.model_validate(
                {
                    "project_id": project_id,
                }
            )
        )

        # Completion call and predict call
        assert len(calls_res.calls) == 2

        objs_res = trace_server.objs_query(
            ObjQueryReq.model_validate(
                {
                    "project_id": project_id,
                }
            )
        )

        # Model definition & predict object
        assert len(objs_res.objs) == 2

        calls_res = trace_server.calls_query(
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

    # First, do the test with the first project
    await do_test(
        entity=entity,
        project="test_run_model_1",
        expected_output="Fantastic - how are you?",
        user_input="Hello, how are you?",
    )

    # Perform the test with a different project
    # Internal assertions ensure that the calls and objects are isolated
    await do_test(
        entity=entity,
        project="test_run_model_2",
        expected_output="Hi friend",
        user_input="Hey there!",
    )
