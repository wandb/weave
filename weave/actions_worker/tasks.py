import json
from functools import partial
from typing import Any, Tuple

from openai import OpenAI

from weave.trace_server.feedback import RunnablePayloadSchema
from weave.trace_server.interface.base_models.action_base_models import (
    ActionConfigType,
    ConfiguredLlmJudgeAction,
)
from weave.trace_server.refs_internal import (
    InternalCallRef,
    InternalObjectRef,
    InternalOpRef,
    parse_internal_uri,
)
from weave.trace_server.trace_server_interface import (
    CallSchema,
    FeedbackCreateReq,
)


def publish_results_as_feedback(
    target_call: CallSchema,
    runnable_ref: str,
    result: Any,
) -> FeedbackCreateReq:
    project_id = target_call.project_id
    call_id = target_call.id
    weave_ref = InternalCallRef(project_id, call_id).uri()
    parsed_action_ref = parse_internal_uri(runnable_ref)
    if not isinstance(parsed_action_ref, (InternalObjectRef, InternalOpRef)):
        raise ValueError(f"Invalid action ref: {runnable_ref}")
    action_name = parsed_action_ref.name

    return FeedbackCreateReq(
        project_id=project_id,
        weave_ref=weave_ref,
        feedback_type="wandb.runnable." + action_name,
        runnable_ref=runnable_ref,
        payload=RunnablePayloadSchema(output=result).model_dump(),
    )


def do_llm_judge_action(config: ConfiguredLlmJudgeAction, call: CallSchema) -> Any:
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


def do_action(
    configured_action_ref: str, action_config: ActionConfigType, call: CallSchema
) -> Tuple[Any, FeedbackCreateReq]:
    runnable_ref = None
    if isinstance(action_config, ConfiguredLlmJudgeAction):
        result = do_llm_judge_action(action_config, call)
        runnable_ref = configured_action_ref
    else:
        raise ValueError(f"Unsupported action config: {action_config}")
    req = publish_results_as_feedback(call, runnable_ref, result)
    return result, req
