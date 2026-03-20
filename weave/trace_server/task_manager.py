"""Task manager for tracking long-running operations via Redis."""

import json
import uuid
from datetime import datetime
from typing import TypedDict

from .redis_client import get_redis_client

TASK_TTL_SECONDS = 3600  # 1 hour - prevents orphaned tasks from persisting indefinitely


class TaskID(str):
    """A unique identifier for a task."""

    def __new__(cls) -> "TaskID":
        return super().__new__(cls, str(uuid.uuid4()))


class TaskDetails(TypedDict):
    """Details about a task's progress."""

    id: str
    total_items: int
    successful_items: int
    failed_items: int
    created_at: str
    canceled_at: str | None


class TaskManager:
    """Manages task state in Redis for tracking long-running operations."""

    def __init__(self, project_id: str, wb_user_id: str | None) -> None:
        self._redis_client = get_redis_client()

        if self._redis_client is None:
            raise ValueError("Redis client is not initialized")

        self._project_id = project_id
        self._wb_user_id = wb_user_id or "anonymous"

    @property
    def _task_key_prefix(self) -> str:
        return f"weave:task:{self._project_id}:{self._wb_user_id}:"

    def _make_task_key(self, task_id: str) -> str:
        return f"{self._task_key_prefix}{task_id}"

    def _set_task(self, task_id: str, task_details: TaskDetails) -> None:
        if self._redis_client is None:
            return

        key = self._make_task_key(task_id)

        self._redis_client.set(key, json.dumps(task_details), ex=TASK_TTL_SECONDS)

    def create_task(self, total_items: int) -> TaskDetails:
        """Create a new task with the given total number of items."""
        task_id = TaskID()

        task_details = TaskDetails(
            id=task_id,
            total_items=total_items,
            successful_items=0,
            failed_items=0,
            created_at=datetime.now().isoformat(),
            canceled_at=None,
        )

        self._set_task(task_id, task_details)

        return task_details

    def get_task(self, task_id: str) -> TaskDetails | None:
        """Get task details by ID."""
        if self._redis_client is None:
            return None

        task_details = self._redis_client.get(self._make_task_key(task_id))

        if task_details is None:
            return None

        return json.loads(task_details)

    def increment_successful_items(self, task_id: str) -> TaskDetails | None:
        """Increment the successful items count for a task."""
        task_details = self.get_task(task_id)

        if task_details is None:
            return None

        task_details["successful_items"] += 1

        self._set_task(task_id, task_details)

        return task_details

    def increment_failed_items(self, task_id: str) -> TaskDetails | None:
        """Increment the failed items count for a task."""
        task_details = self.get_task(task_id)

        if task_details is None:
            return None

        task_details["failed_items"] += 1

        self._set_task(task_id, task_details)

        return task_details

    def complete_task(self, task_id: str) -> None:
        """Mark a task as complete by removing it from Redis."""
        if self._redis_client is None:
            return

        self._redis_client.delete(self._make_task_key(task_id))

    def is_canceled(self, task_id: str) -> bool:
        """Return True if the task has been canceled."""
        task_details = self.get_task(task_id)
        if task_details is None:
            return False
        return task_details["canceled_at"] is not None

    def cancel_task(self, task_id: str) -> TaskDetails | None:
        """Mark a task as canceled by setting canceled_at timestamp."""
        task_details = self.get_task(task_id)

        if task_details is None:
            return None

        task_details["canceled_at"] = datetime.now().isoformat()

        self._set_task(task_id, task_details)

        return task_details

    def list_tasks(self) -> list[TaskDetails]:
        """List all tasks for this project and user."""
        if self._redis_client is None:
            return []

        tasks: list[TaskDetails] = []

        cursor = 0

        while True:
            cursor, keys = self._redis_client.scan(
                cursor=cursor, match=f"{self._task_key_prefix}*"
            )

            for key in keys:
                data = self._redis_client.get(key)

                if data:
                    tasks.append(json.loads(data))

            if cursor == 0:
                break

        return tasks

    def clear_tasks(self) -> None:
        """Delete all task keys for this project and user from Redis."""
        if self._redis_client is None:
            return

        cursor = 0

        while True:
            cursor, keys = self._redis_client.scan(
                cursor=cursor, match=f"{self._task_key_prefix}*"
            )

            if keys:
                self._redis_client.delete(*keys)

            if cursor == 0:
                break
