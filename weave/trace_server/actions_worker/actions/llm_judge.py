import json
from typing import Any

from weave.trace_server.interface.builtin_object_classes.actions import (
    LlmJudgeActionConfig,
)
from weave.trace_server.trace_server_interface import (
    CallSchema,
    CompletionsCreateReq,
    TraceServerInterface,
)


def do_llm_judge_action(
    project_id: str,
    config: LlmJudgeActionConfig,
    call: CallSchema,
    trace_server: TraceServerInterface,
) -> Any:
    model = config.model
    system_prompt = config.prompt

    response_is_not_object = config.response_schema["type"] != "object"
    dummy_key = "response"
    if response_is_not_object:
        schema = {
            "type": "object",
            "properties": {dummy_key: config.response_schema},
            "additionalProperties": False,
        }
    else:
        schema = config.response_schema

    response_format = {
        "type": "json_schema",
        "json_schema": {"name": "response_format", "schema": schema},
    }

    args = {
        "inputs": call.inputs,
        "output": call.output,
    }

    completion = trace_server.completions_create(
        CompletionsCreateReq(
            project_id=project_id,
            inputs={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(args)},
                ],
                "response_format": response_format,
            },
            track_llm_call=False,
        )
    )

    content = (
        completion.response.get("choices", [{}])[0].get("message", {}).get("content")
    )
    if content is None:
        res = None
    else:
        res = json.loads(content)
        if response_is_not_object:
            res = res[dummy_key]
    return res
