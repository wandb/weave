import json
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypedDict

import redis


class ActionQueueItem(TypedDict):
    id: str
    data: Dict[str, Any]


def queue_from_addr(addr: str) -> "ActionQueue":
    if addr == "noop://":
        return NoOpActionQueue()
    elif addr.startswith("redis://"):
        return RedisActionQueue(addr)
    else:
        raise ValueError(f"Invalid action queue address: {addr}")


class ActionQueue(ABC):
    @abstractmethod
    def pull(self) -> Optional[ActionQueueItem]:
        pass

    @abstractmethod
    def ack(self, id: str) -> None:
        pass

    @abstractmethod
    def push(self, action: Dict[str, Any]) -> None:
        pass


# TODO: Probably move this into a separate file.
class RedisActionQueue(ActionQueue):
    def __init__(self, addr: str) -> None:
        self.redis_client = redis.from_url(addr)
        self.stream_key = "action_queue_stream"
        self.consumer_group = "action_processors"
        self.consumer_name = "consumer-" + str(uuid.uuid4())

        # Create consumer group if it doesn't exist
        try:
            self.redis_client.xgroup_create(
                self.stream_key, self.consumer_group, mkstream=True
            )
        except redis.exceptions.ResponseError:
            # Group already exists
            pass

    def pull(self) -> Optional[ActionQueueItem]:
        # First try to claim any pending actions.
        actions = self.claim_pending_actions(1)
        if actions:
            return actions[0]

        # Otherwise, read a new action from the stream.
        response = self.redis_client.xreadgroup(
            self.consumer_group,
            self.consumer_name,
            {self.stream_key: ">"},
            count=1,
            block=1000,
        )
        if response:
            [[_, messages]] = response
            message_id, message = messages[0]
            return {"id": message_id, "data": json.loads(message[b"data"])}
        return None

    def ack(self, id: str) -> None:
        self.redis_client.xack(self.stream_key, self.consumer_group, id)  # type: ignore

    def claim_pending_actions(self, count: int = 1) -> List[ActionQueueItem]:
        # Claim messages that haven't been acknowledged for 10 minutes
        min_idle_time = 10 * 60 * 1000  # 10 minutes in milliseconds
        claimed = self.redis_client.xautoclaim(
            self.stream_key,
            self.consumer_group,
            self.consumer_name,
            min_idle_time,
            start_id="0-0",
            count=count,
        )

        # Process the claimed messages
        actions: List[ActionQueueItem] = []
        for message_id, message in claimed[1]:
            actions.append({"id": message_id, "data": json.loads(message[b"data"])})

        return actions

    def push(self, action: Dict[str, Any]) -> None:
        try:
            res = self.redis_client.xadd(self.stream_key, {"data": json.dumps(action)})
        except redis.exceptions.RedisError as e:
            # Log the error and re-raise
            logging.error(f"Failed to push action to Redis stream: {e}")
            raise

    def _TESTONLY_clear_queue(self) -> None:
        # Delete the stream
        self.redis_client.delete(self.stream_key)

        # Delete the consumer group if it exists
        try:
            self.redis_client.xgroup_destroy(self.stream_key, self.consumer_group)  # type: ignore
        except redis.exceptions.ResponseError:
            pass  # Group doesn't exist, which is fine

        # Recreate the consumer group
        self.redis_client.xgroup_create(
            self.stream_key, self.consumer_group, id="0", mkstream=True
        )


class NoOpActionQueue(ActionQueue):
    def pull(self) -> Optional[ActionQueueItem]:
        return {"id": "", "data": {}}

    def ack(self, id: str) -> None:
        pass

    def push(self, action: Dict[str, Any]) -> None:
        pass
