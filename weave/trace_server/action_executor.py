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
        # effect_dict = json.loads(configured_action_ref)
        # task_name = effect_dict["task"]
        # task_kwargs = effect_dict["kwargs"]  # This should be a dict
        # if task_name == "noop":
        #     tasks.noop.delay(ctx, **task_kwargs)  # type: ignore
        # elif task_name == "wordcount":
        #     tasks.wordcount.delay(ctx, **task_kwargs)  # type: ignore
        # else:
        #     raise ValueError(f"Unknown task: {task_name}")

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


# TODO: Probably move this into a separate file.
# class RedisActionQueue(ActionQueue):
#     def __init__(self, addr: str) -> None:
#         self.redis_client = redis.from_url(addr)
#         self.stream_key = "action_queue_stream"
#         self.consumer_group = "action_processors"
#         self.consumer_name = "consumer-" + str(uuid.uuid4())

#         # Create consumer group if it doesn't exist
#         try:
#             self.redis_client.xgroup_create(
#                 self.stream_key, self.consumer_group, mkstream=True
#             )
#         except redis.exceptions.ResponseError:
#             # Group already exists
#             pass

#     def pull(self) -> Optional[ActionQueueItem]:
#         # First try to claim any pending actions.
#         actions = self.claim_pending_actions(1)
#         if actions:
#             return actions[0]

#         # Otherwise, read a new action from the stream.
#         response = self.redis_client.xreadgroup(
#             self.consumer_group,
#             self.consumer_name,
#             {self.stream_key: ">"},
#             count=1,
#             block=1000,
#         )
#         if response:
#             [[_, messages]] = response
#             message_id, message = messages[0]
#             return {"id": message_id, "data": json.loads(message[b"data"])}
#         return None

#     def ack(self, id: str) -> None:
#         self.redis_client.xack(self.stream_key, self.consumer_group, id)  # type: ignore

#     def claim_pending_actions(self, count: int = 1) -> List[ActionQueueItem]:
#         # Claim messages that haven't been acknowledged for 10 minutes
#         min_idle_time = 10 * 60 * 1000  # 10 minutes in milliseconds
#         claimed = self.redis_client.xautoclaim(
#             self.stream_key,
#             self.consumer_group,
#             self.consumer_name,
#             min_idle_time,
#             start_id="0-0",
#             count=count,
#         )

#         # Process the claimed messages
#         actions: List[ActionQueueItem] = []
#         for message_id, message in claimed[1]:
#             actions.append({"id": message_id, "data": json.loads(message[b"data"])})

#         return actions

#     def push(self, action: Dict[str, Any]) -> None:
#         try:
#             res = self.redis_client.xadd(self.stream_key, {"data": json.dumps(action)})
#         except redis.exceptions.RedisError as e:
#             # Log the error and re-raise
#             logging.error(f"Failed to push action to Redis stream: {e}")
#             raise

#     def _TESTONLY_clear_queue(self) -> None:
#         # Delete the stream
#         self.redis_client.delete(self.stream_key)

#         # Delete the consumer group if it exists
#         try:
#             self.redis_client.xgroup_destroy(self.stream_key, self.consumer_group)  # type: ignore
#         except redis.exceptions.ResponseError:
#             pass  # Group doesn't exist, which is fine

#         # Recreate the consumer group
#         self.redis_client.xgroup_create(
#             self.stream_key, self.consumer_group, id="0", mkstream=True
#         )
