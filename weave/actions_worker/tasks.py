import json
import logging
from functools import partial, wraps
from typing import Any, Callable, TypeVar

from weave.actions_worker.celery_app import app
from weave.trace_server.action_executor import TaskCtx
from weave.trace_server.clickhouse_trace_server_batched import (
    ActionsAckBatchReq,
    ClickHouseTraceServer,
)
from weave.trace_server.interface.base_models.action_base_models import (
    ConfiguredAction,
    ConfiguredContainsWordsAction,
    ConfiguredLlmJudgeAction,
    ConfiguredNoopAction,
    ConfiguredWordCountAction,
)
from weave.trace_server.interface.base_models.base_model_registry import base_model_name
from weave.trace_server.interface.base_models.feedback_base_model_registry import (
    ActionScore,
)
from weave.trace_server.refs_internal import InternalCallRef
from weave.trace_server.trace_server_interface import (
    CallSchema,
    CallsFilter,
    CallsQueryReq,
    FeedbackCreateReq,
    RefsReadBatchReq,
)

WEAVE_ACTION_EXECUTOR_PACEHOLDER_ID = "WEAVE_ACTION_EXECUTOR"


def ack_on_clickhouse(ctx: TaskCtx, succeeded: bool) -> None:
    project_id = ctx["project_id"]
    call_id = ctx["call_id"]
    id = ctx["id"]
    ClickHouseTraceServer.from_env().actions_ack_batch(
        ActionsAckBatchReq(
            project_id=project_id, call_ids=[call_id], id=id, succeeded=succeeded
        )
    )


def publish_results_as_feedback(
    ctx: TaskCtx, result: Any, configured_action_ref: str
) -> None:
    project_id = ctx["project_id"]
    call_id = ctx["call_id"]
    id = ctx["id"]
    call_ref = InternalCallRef(project_id, call_id).uri()
    ClickHouseTraceServer.from_env().feedback_create(
        FeedbackCreateReq(
            project_id=project_id,
            weave_ref=call_ref,
            feedback_type=base_model_name(ActionScore),
            payload=ActionScore(
                configured_action_ref=configured_action_ref, output=result
            ).model_dump(),
            wb_user_id=WEAVE_ACTION_EXECUTOR_PACEHOLDER_ID,
        )
    )


def resolve_action_ref(configured_action_ref: str) -> ConfiguredAction:
    server = ClickHouseTraceServer.from_env()
    action_dict_res = server.refs_read_batch(
        RefsReadBatchReq(refs=[configured_action_ref])
    )
    action_dict = action_dict_res.vals[0]
    assert isinstance(action_dict, dict)
    action = ConfiguredAction.model_validate(action_dict)
    return action


def resolve_call(ctx: TaskCtx) -> CallSchema:
    project_id, call_id = ctx["project_id"], ctx["call_id"]
    server = ClickHouseTraceServer.from_env()
    calls_query_res = server.calls_query(
        CallsQueryReq(
            project_id=project_id, filter=CallsFilter(call_ids=[call_id]), limit=1
        )
    )
    return calls_query_res.calls[0]


ActionConfigT = TypeVar("ActionConfigT")
ActionResultT = TypeVar("ActionResultT")


def action_task(
    func: Callable[[str, str, ActionConfigT], ActionResultT],
) -> Callable[[TaskCtx, str, str, str, ActionConfigT], ActionResultT]:
    @wraps(func)
    def wrapper(
        ctx: TaskCtx,
        call_input: str,
        call_output: str,
        configured_action_ref: str,
        configured_action: ActionConfigT,
    ) -> ActionResultT:
        success = True
        try:
            result = func(call_input, call_output, configured_action)
            publish_results_as_feedback(ctx, result, configured_action_ref)
            logging.info(f"Successfully ran {func.__name__}")
            logging.info(f"Result: {result}")
        except Exception as e:
            success = False
            raise e
        finally:
            ack_on_clickhouse(ctx, success)
        return result

    return wrapper


@app.task()
def do_task(ctx: TaskCtx, configured_action_ref: str) -> None:
    action = resolve_action_ref(configured_action_ref)
    call = resolve_call(ctx)
    call_input = json.dumps(call.inputs)
    call_output = call.output
    if not isinstance(call_output, str):
        call_output = json.dumps(call_output)

    if action.config.action_type == "wordcount":
        wordcount(ctx, call_input, call_output, configured_action_ref, action.config)
    elif action.config.action_type == "llm_judge":
        llm_judge(ctx, call_input, call_output, configured_action_ref, action.config)
    elif action.config.action_type == "noop":
        noop(ctx, call_input, call_output, configured_action_ref, action.config)
    elif action.config.action_type == "contains_words":
        contains_words(
            ctx, call_input, call_output, configured_action_ref, action.config
        )
    else:
        raise ValueError(f"Unknown action type: {action.config.action_type}")


@action_task
def wordcount(
    call_input: str, call_output: str, config: ConfiguredWordCountAction
) -> int:
    return len(call_output.split(" "))


@action_task
def llm_judge(
    call_input: str, call_output: str, config: ConfiguredLlmJudgeAction
) -> str:
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
        "inputs": call_input,
        "output": call_output,
    }
    from openai import OpenAI

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


@action_task
def contains_words(
    call_input: str, call_output: str, config: ConfiguredContainsWordsAction
) -> bool:
    word_set = set(call_output.split(" "))
    return len(set(config.target_words) & word_set) > 0


@action_task
def noop(call_input: str, call_output: str, config: ConfiguredNoopAction) -> None:
    pass
