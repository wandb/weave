import json
from functools import wraps
from typing import Any, Callable, TypeVar

from weave.actions_worker.celery_app import app
from weave.trace_server.action_queue import TaskCtx
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.interface.base_models.action_base_models import (
    ConfiguredAction,
    ConfiguredLevenshteinAction,
    ConfiguredLlmJudgeAction,
    ConfiguredNoopAction,
    ConfiguredWordCountAction,
)
from weave.trace_server.refs_internal import InternalCallRef
from weave.trace_server.trace_server_interface import (
    ActionsAckBatchReq,
    CallSchema,
    CallsFilter,
    CallsQueryReq,
    FeedbackCreateReq,
    RefsReadBatchReq,
)


def ack_on_clickhouse(ctx: TaskCtx, succeeded: bool) -> None:
    project_id = ctx["project_id"]
    call_id = ctx["call_id"]
    id = ctx["id"]
    ClickHouseTraceServer.from_env().actions_ack_batch(
        ActionsAckBatchReq(
            project_id=project_id, call_ids=[call_id], id=id, succeeded=succeeded
        )
    )


def publish_results_as_feedback(ctx: TaskCtx, result: dict[str, Any]) -> None:
    project_id = ctx["project_id"]
    call_id = ctx["call_id"]
    id = ctx["id"]
    call_ref = InternalCallRef(project_id, call_id).uri()
    ClickHouseTraceServer.from_env().feedback_create(
        FeedbackCreateReq(
            project_id=project_id,
            weave_ref=call_ref,
            creator="actions_worker",
            feedback_type="wandb.online_score",
            payload=result,
            wb_user_id="wandb",
        )
    )


def resolve_action_ref(configured_action_ref: str) -> ConfiguredAction:
    server = ClickHouseTraceServer.from_env()
    action_dict_res = server.refs_read_batch(
        RefsReadBatchReq(refs=[configured_action_ref])
    )
    action_str = action_dict_res.vals[0]
    action = ConfiguredAction.model_validate(json.loads(action_str))
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
    func: Callable[[str, ActionConfigT], ActionResultT],
) -> Callable[[TaskCtx, str, ActionConfigT], ActionResultT]:
    @wraps(func)
    def wrapper(
        ctx: TaskCtx, payload: str, configured_action: ActionConfigT
    ) -> ActionResultT:
        success = True
        try:
            scorer_name = func.__name__
            result = func(payload, configured_action)
            publish_results_as_feedback(ctx, {scorer_name: result})
            print(f"Successfully ran {func.__name__}")
            print(f"Result: {result}")
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
    output = call.output
    if not isinstance(output, str):
        # TODO Probably log this somewhere.
        return

    if action.config.action_type == "wordcount":
        wordcount(ctx, output, action.config)
    elif action.config.action_type == "llm_judge":
        llm_judge(ctx, output, action.config)
    elif action.config.action_type == "noop":
        noop(ctx, output, action.config)
    elif action.config.action_type == "levenshtein":
        levenshtein(ctx, output, action.config)
    else:
        raise ValueError(f"Unknown action type: {action.config.action_type}")


@action_task
def wordcount(payload: str, config: ConfiguredWordCountAction) -> int:
    return len(payload.split(" "))


@action_task
def llm_judge(payload: str, config: ConfiguredLlmJudgeAction) -> str:
    return "I'm sorry Hal, I'm afraid I can't do that."


@action_task
def levenshtein(payload: str, config: ConfiguredLevenshteinAction) -> int:
    from Levenshtein import distance

    return distance(payload, config.expected)


@action_task
def noop(payload: str, config: ConfiguredNoopAction) -> None:
    pass
