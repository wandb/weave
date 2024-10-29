from abc import ABC, abstractmethod

from redis import Redis
from typing_extensions import TypedDict

from weave.trace_server import environment as wf_env


def queue_from_addr(addr: str) -> "ActionExecutor":
    if addr == "noop://":
        return NoOpActionQueue()
    elif addr.startswith("redis://"):
        return CeleryActionQueue()
    else:
        raise ValueError(f"Invalid action queue address: {addr}")


TaskCtx = TypedDict("TaskCtx", {"project_id": str, "call_id": str, "id": str})


class ActionExecutor(ABC):
    @abstractmethod
    def enqueue(self, ctx: TaskCtx, configured_action_ref: str) -> None:
        pass

    @abstractmethod
    def do_now(self, ctx: TaskCtx, configured_action_ref: str) -> None:
        pass

    @abstractmethod
    def _TESTONLY_clear_queue(self) -> None:
        pass


class CeleryActionQueue(ActionExecutor):
    def enqueue(self, ctx: TaskCtx, configured_action_ref: str) -> None:
        # TODO We put this in here to break a circular import. Fix this later.
        import weave.actions_worker.tasks as tasks

        tasks.do_task.delay(ctx, configured_action_ref)

    def do_now(self, ctx: TaskCtx, configured_action_ref: str) -> None:
        import weave.actions_worker.tasks as tasks

        tasks.do_task(ctx, configured_action_ref)

    def _TESTONLY_clear_queue(self) -> None:
        redis = Redis.from_url(wf_env.wf_action_executor())
        redis.delete("celery")


class NoOpActionQueue(ActionExecutor):
    def enqueue(self, ctx: TaskCtx, configured_action_ref: str) -> None:
        pass

    def do_now(self, ctx: TaskCtx, configured_action_ref: str) -> None:
        pass

    def _TESTONLY_clear_queue(self) -> None:
        pass
