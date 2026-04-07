"""Task manager for tracking long-running operations via Redis.

Each task is stored as a Redis hash with one field per TaskDetails key.
Integer counters use HINCRBY for atomic, thread-safe increments.
"""

import uuid
from datetime import datetime
from typing import Any

from redis import Redis

from .redis_client import get_redis_client
from .trace_server_interface import TaskDetails

TASK_TTL_SECONDS = 3600  # 1 hour - prevents orphaned tasks from persisting indefinitely


def _make_task_details(data: dict[str, Any]) -> TaskDetails:
    """Convert a flat Redis hash dict into a TaskDetails model.

    Pydantic coerces string values to int where needed and handles
    empty-string → None conversion for canceled_at.
    """
    return TaskDetails.model_validate(
        {**data, "canceled_at": data.get("canceled_at") or None}
    )


class TaskID(str):
    """A unique identifier for a task."""

    def __new__(cls) -> "TaskID":
        return super().__new__(cls, str(uuid.uuid4()))


class TaskManager:
    """Manages task state in Redis for tracking long-running operations."""

    def __init__(self, project_id: str, wb_user_id: str | None) -> None:
        redis_client = get_redis_client()

        if redis_client is None:
            raise ValueError("Redis client is not initialized")

        self._redis_client: Redis = redis_client

        self._project_id = project_id
        self._wb_user_id = wb_user_id or "anonymous"

    @property
    def _task_key_prefix(self) -> str:
        return f"weave:task:{self._project_id}:{self._wb_user_id}:"

    @property
    def _index_key(self) -> str:
        return f"weave:task:{self._project_id}:{self._wb_user_id}:_index"

    def _make_task_key(self, task_id: str) -> str:
        return f"{self._task_key_prefix}{task_id}"

    def create_task(self, total_items: int) -> TaskDetails:
        """Create a new task with the given total number of items."""
        task_id = TaskID()
        key = self._make_task_key(task_id)

        mapping = {
            "id": task_id,
            "total_items": total_items,
            "successful_items": 0,
            "failed_items": 0,
            "created_at": datetime.now().isoformat(),
            "canceled_at": "",
        }

        self._redis_client.hset(key, mapping=mapping)
        self._redis_client.expire(key, TASK_TTL_SECONDS)
        self._redis_client.sadd(self._index_key, task_id)

        return _make_task_details(mapping)

    def get_task(self, task_id: str) -> TaskDetails | None:
        """Get task details by ID."""
        data = self._redis_client.hgetall(self._make_task_key(task_id))

        if not data:
            return None

        return _make_task_details(data)

    def increment_successful_items(self, task_id: str) -> TaskDetails | None:
        """Atomically increment the successful items count for a task."""
        key = self._make_task_key(task_id)

        if not self._redis_client.exists(key):
            return None

        self._redis_client.hincrby(key, "successful_items", 1)

        return self.get_task(task_id)

    def increment_failed_items(self, task_id: str) -> TaskDetails | None:
        """Atomically increment the failed items count for a task."""
        key = self._make_task_key(task_id)

        if not self._redis_client.exists(key):
            return None

        self._redis_client.hincrby(key, "failed_items", 1)

        return self.get_task(task_id)

    def complete_task(self, task_id: str) -> None:
        """Mark a task as complete by removing it from Redis."""
        self._redis_client.delete(self._make_task_key(task_id))
        self._redis_client.srem(self._index_key, task_id)

    def is_canceled(self, task_id: str) -> bool:
        """Return True if the task has been canceled."""
        canceled_at = self._redis_client.hget(self._make_task_key(task_id), "canceled_at")

        if canceled_at is None:
            return False

        return canceled_at != ""

    def cancel_task(self, task_id: str) -> TaskDetails | None:
        """Mark a task as canceled by setting canceled_at timestamp."""
        key = self._make_task_key(task_id)

        if not self._redis_client.exists(key):
            return None

        self._redis_client.hset(key, "canceled_at", datetime.now().isoformat())

        return self.get_task(task_id)

    def list_tasks(self) -> list[TaskDetails]:
        """List all tasks for this project and user."""
        task_ids = self._redis_client.smembers(self._index_key)
        tasks: list[TaskDetails] = []
        stale_ids: list[str] = []

        for task_id in task_ids:
            data = self._redis_client.hgetall(self._make_task_key(task_id))

            if data:
                tasks.append(_make_task_details(data))
            else:
                stale_ids.append(task_id)

        if stale_ids:
            self._redis_client.srem(self._index_key, *stale_ids)

        return tasks

    def clear_tasks(self) -> None:
        """Delete all task keys for this project and user from Redis."""
        task_ids = self._redis_client.smembers(self._index_key)

        if task_ids:
            keys = [self._make_task_key(task_id) for task_id in task_ids]
            self._redis_client.delete(*keys)

        self._redis_client.delete(self._index_key)
