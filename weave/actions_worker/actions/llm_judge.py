import json
from functools import partial
from typing import Any

from openai import OpenAI

from weave.trace_server.interface.base_object_classes.actions import (
    LlmJudgeActionSpec,
)
from weave.trace_server.trace_server_interface import (
    CallSchema,
    TraceServerInterface,
)


def do_llm_judge_action(
    config: LlmJudgeActionSpec, call: CallSchema, trace_server: TraceServerInterface
) -> Any:
    model = config.model
    system_prompt = config.prompt
    if config.response_format is None:
        raise ValueError("response_format is required for llm_judge")

    response_is_not_object = config.response_format["type"] != "object"
    dummy_key = "response"
    if response_is_not_object:
        schema = {
            "type": "object",
            "properties": {dummy_key: config.response_format},
            "additionalProperties": False,
        }
    else:
        schema = config.response_format

    response_format = {
        "type": "json_schema",
        "json_schema": {"name": "response_format", "schema": schema},
    }

    args = {
        "inputs": call.inputs,
        "output": call.output,
    }

    client = OpenAI()
    # Silly hack to get around issue in tests:
    create = client.chat.completions.create
    if hasattr(create, "resolve_fn"):
        create = partial(create.resolve_fn, self=client.chat.completions)
    completion = create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(args)},
        ],
        response_format=response_format,
    )
    res = json.loads(completion.choices[0].message.content)
    if response_is_not_object:
        res = res[dummy_key]
    return res
