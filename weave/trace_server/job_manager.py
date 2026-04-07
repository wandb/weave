"""Job manager for tracking long-running operations via Redis.

Each job is stored as a Redis hash with one field per JobDetails key.
Integer counters use HINCRBY for atomic, thread-safe increments.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from weave.trace_server.redis_client import get_redis_client
from weave.trace_server.trace_server_interface import JobDetails

if TYPE_CHECKING:
    from redis import Redis

JOB_TTL_SECONDS = 3600  # 1 hour - prevents orphaned jobs from persisting indefinitely


def _get_required_redis_client() -> "Redis":
    client = get_redis_client()
    if client is None:
        raise ValueError("Redis client is not initialized")
    return client


def _make_job_details(data: dict[str, Any]) -> JobDetails:
    """Convert a flat Redis hash dict into a JobDetails model.

    Pydantic coerces string values to int where needed and handles
    empty-string → None conversion for canceled_at.
    """
    return JobDetails.model_validate(
        {**data, "canceled_at": data.get("canceled_at") or None}
    )


class JobID(str):
    """A unique identifier for a job."""

    def __new__(cls) -> "JobID":
        return super().__new__(cls, str(uuid.uuid4()))


@dataclass(frozen=True)
class JobManager:
    """Manages job state in Redis for tracking long-running operations."""

    project_id: str
    wb_user_id: str | None = "anonymous"
    _redis_client: "Redis" = field(init=False, repr=False, default_factory=_get_required_redis_client)

    @property
    def _user_id(self) -> str:
        return self.wb_user_id or "anonymous"

    @property
    def _job_key_prefix(self) -> str:
        return f"weave:job:{self.project_id}:{self._user_id}:"

    @property
    def _index_key(self) -> str:
        return f"weave:job:{self.project_id}:{self._user_id}:_index"

    def _make_job_key(self, job_id: str) -> str:
        return f"{self._job_key_prefix}{job_id}"

    def create_job(self, total_items: int) -> JobDetails:
        """Create a new job with the given total number of items."""
        job_id = JobID()
        key = self._make_job_key(job_id)

        created_at = datetime.now().isoformat()

        self._redis_client.hset(
            key,
            mapping={
                "id": str(job_id),
                "total_items": str(total_items),
                "successful_items": "0",
                "failed_items": "0",
                "created_at": created_at,
                "canceled_at": "",
            },
        )
        self._redis_client.expire(key, JOB_TTL_SECONDS)
        self._redis_client.sadd(self._index_key, job_id)

        return JobDetails(
            id=str(job_id),
            total_items=total_items,
            successful_items=0,
            failed_items=0,
            created_at=created_at,
        )

    def get_job(self, job_id: str) -> JobDetails | None:
        """Get job details by ID."""
        data = self._redis_client.hgetall(self._make_job_key(job_id))

        if not data:
            return None

        return _make_job_details(data)

    def increment_successful_items(self, job_id: str) -> JobDetails | None:
        """Atomically increment the successful items count for a job."""
        key = self._make_job_key(job_id)

        if not self._redis_client.exists(key):
            return None

        self._redis_client.hincrby(key, "successful_items", 1)

        return self.get_job(job_id)

    def increment_failed_items(self, job_id: str) -> JobDetails | None:
        """Atomically increment the failed items count for a job."""
        key = self._make_job_key(job_id)

        if not self._redis_client.exists(key):
            return None

        self._redis_client.hincrby(key, "failed_items", 1)

        return self.get_job(job_id)

    def complete_job(self, job_id: str) -> None:
        """Mark a job as complete by removing it from Redis."""
        self._redis_client.delete(self._make_job_key(job_id))
        self._redis_client.srem(self._index_key, job_id)

    def is_canceled(self, job_id: str) -> bool:
        """Return True if the job has been canceled."""
        canceled_at = self._redis_client.hget(
            self._make_job_key(job_id), "canceled_at"
        )

        if canceled_at is None:
            return False

        return canceled_at != ""

    def cancel_job(self, job_id: str) -> JobDetails | None:
        """Mark a job as canceled by setting canceled_at timestamp."""
        key = self._make_job_key(job_id)

        if not self._redis_client.exists(key):
            return None

        self._redis_client.hset(key, "canceled_at", datetime.now().isoformat())

        return self.get_job(job_id)

    def list_jobs(self) -> list[JobDetails]:
        """List all jobs for this project and user."""
        job_ids = self._redis_client.smembers(self._index_key)
        jobs: list[JobDetails] = []
        stale_ids: list[str] = []

        for job_id in job_ids:
            data = self._redis_client.hgetall(self._make_job_key(job_id))

            if data:
                jobs.append(_make_job_details(data))
            else:
                stale_ids.append(job_id)

        if stale_ids:
            self._redis_client.srem(self._index_key, *stale_ids)

        return jobs

    def clear_jobs(self) -> None:
        """Delete all job keys for this project and user from Redis."""
        job_ids = self._redis_client.smembers(self._index_key)

        if job_ids:
            keys = [self._make_job_key(job_id) for job_id in job_ids]
            self._redis_client.delete(*keys)

        self._redis_client.delete(self._index_key)
