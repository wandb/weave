from functools import wraps
from typing import Any, Callable, Dict

from weave.actions_worker.celery_app import app
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.refs_internal import InternalCallRef
from weave.trace_server.trace_server_interface import (
    ActionsAckBatchReq,
    FeedbackCreateReq,
)


def ack_on_clickhouse(ctx: Dict[str, Any], succeeded: bool) -> None:
    project_id = ctx["project_id"]
    call_id = ctx["call_id"]
    id = ctx["id"]
    ClickHouseTraceServer.from_env().actions_ack_batch(
        ActionsAckBatchReq(
            project_id=project_id, call_ids=[call_id], id=id, succeeded=succeeded
        )
    )


def publish_results_as_feedback(ctx: Dict[str, Any], result: dict[str, Any]) -> None:
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


def action_task(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(ctx: Dict[str, Any], *args: list, **kwargs: dict) -> Any:
        success = True
        try:
            scorer_name = func.__name__
            result = func(*args, **kwargs)
            publish_results_as_feedback(ctx, {scorer_name: result})
            print(f"Successfully ran {func.__name__}")
            print(f"Result: {result}")
        except Exception as e:
            success = False
            raise e
        finally:
            ack_on_clickhouse(ctx, success)
        return result

    return app.task(wrapper)


@action_task
def wordcount(payload: str) -> int:
    return len(payload.split(" "))


@action_task
def llm_judge(payload: str, prompt: str, **kwargs: list) -> str:
    return "I'm sorry Hal, I'm afraid I can't do that."


@action_task
def noop() -> None:
    pass
