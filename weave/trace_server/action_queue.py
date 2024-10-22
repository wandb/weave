import json
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import redis

from . import environment as wf_env


class ActionQueue(ABC):
    @abstractmethod
    def pull(self) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def ack(self, action: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def push(self, action: Dict[str, Any]) -> None:
        pass


# TODO: Probably move this into a separate file.
class RedisActionQueue(ActionQueue):
    def __init__(self) -> None:
        redis_url = wf_env.wf_action_queue()
        self.redis_client = redis.from_url(redis_url)
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

    def pull(self) -> Optional[Dict[str, Any]]:
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

    def ack(self, action: Dict[str, Any]) -> None:
        self.redis_client.xack(self.stream_key, self.consumer_group, action["id"])  # type: ignore

    def claim_pending_actions(self, count: int = 10) -> List[Dict[str, Any]]:
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
        actions = []
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
