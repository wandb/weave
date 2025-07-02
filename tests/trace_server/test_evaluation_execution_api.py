import pytest

from tests.trace_server.completions_util import with_simple_mock_litellm_completion
from weave.trace.refs import ObjectRef
from weave.trace_server.trace_server_interface import (
    ObjCreateReq,
    RunModelReq,
    TraceServerInterface,
)


@pytest.mark.asyncio
async def test_run_model(trace_server: TraceServerInterface):
    entity = "shawn"
    project = "test_run_model"
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

    expected_output = "Fantastic - how are you?"
    with with_simple_mock_litellm_completion(expected_output):
        model_run_res = await trace_server.run_model(
            RunModelReq.model_validate(
                {
                    "project_id": project_id,
                    "model_ref": ObjectRef(
                        entity=entity,
                        project=project,
                        name=model_object_id,
                        _digest=model_digest,
                    ).uri(),
                    "inputs": {
                        "input_type": "value",
                        "value": {"user_input": "Hello, how are you?"},
                    },
                }
            )
        )

    assert model_run_res.output == expected_output
