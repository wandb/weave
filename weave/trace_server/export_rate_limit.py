"""Redis-backed cross-worker concurrency guard for managed-bucket exports."""

import hashlib
import logging
import uuid
from dataclasses import dataclass

from weave.trace_server.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# A single job may serialize all three targets, each limited to five minutes.
# The worker releases its lease on completion; this only bounds a crashed worker.
EXPORT_LOCK_TTL_SECONDS = 1_200
_LOCK_KEY_PREFIX = "weave:export:active:"
_RELEASE_IF_OWNED = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


class ExportRateLimitError(Exception):
    def __init__(self, http_status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.code = code


@dataclass(frozen=True)
class ExportSlot:
    key: str
    token: str


def acquire_export_slot(wb_user_id: str) -> ExportSlot:
    """Reserve a single bounded export slot for a user across all workers."""
    client = get_redis_client()
    if client is None:
        raise ExportRateLimitError(
            503,
            "EXPORT_LIMIT_UNAVAILABLE",
            "export concurrency limit is temporarily unavailable",
        )

    key = _export_lock_key(wb_user_id)
    token = str(uuid.uuid4())
    try:
        acquired = client.set(key, token, nx=True, ex=EXPORT_LOCK_TTL_SECONDS)
    except Exception as exc:
        raise ExportRateLimitError(
            503,
            "EXPORT_LIMIT_UNAVAILABLE",
            "export concurrency limit is temporarily unavailable",
        ) from exc
    if not acquired:
        raise ExportRateLimitError(
            409,
            "EXPORT_ALREADY_RUNNING",
            "an export is already running for this user",
        )
    return ExportSlot(key=key, token=token)


def release_export_slot(slot: ExportSlot) -> None:
    """Release an owned reservation without deleting a newer owner's lock."""
    try:
        client = get_redis_client()
        if client is not None:
            client.eval(  # type: ignore[no-untyped-call]
                _RELEASE_IF_OWNED, 1, slot.key, slot.token
            )
    except Exception:
        # The TTL bounds the lock if Redis is unavailable during cleanup.
        logger.warning("failed to release export concurrency slot", exc_info=True)


def _export_lock_key(wb_user_id: str) -> str:
    user_hash = hashlib.sha256(wb_user_id.encode()).hexdigest()
    return f"{_LOCK_KEY_PREFIX}{user_hash}"
