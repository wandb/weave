"""Distributed migration lock backed by a ClickHouse MergeTree table.

On multi-replica deployments, init containers race to apply migrations.
This module provides a simple advisory lock: one replica writes a lock row,
others see it and wait (with backoff) until it expires or is released.

The lock is best-effort — ClickHouse reads are eventually consistent, so
there is a small window where two replicas could both believe they hold it.
Combined with idempotent DDL (IF NOT EXISTS, retry on 517), this shrinks
the race window to near-zero without adding external dependencies.
"""

import logging
import re
import uuid
from collections.abc import Generator
from contextlib import contextmanager

from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.exceptions import OperationalError
from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception_type,
    retry_if_result,
    stop_after_delay,
    wait_exponential,
)

logger = logging.getLogger(__name__)

LOCK_TABLE = "migration_lock"

# How long a lock is valid before it's considered stale.
LOCK_TTL_SECONDS = 600

# Column definitions shared between cloud/replicated/distributed table creation.
LOCK_TABLE_COLUMNS = """
    lock_id String,
    holder String,
    acquired_at DateTime64(3) DEFAULT now64(3)
"""

# Polling configuration for waiting on a lock held by another replica.
LOCK_WAIT_INITIAL_DELAY_SECONDS = 0.5
LOCK_WAIT_MAX_DELAY_SECONDS = 5.0
LOCK_WAIT_TIMEOUT_SECONDS = 120.0

HOLDER_PATTERN = re.compile(r"^[0-9a-f]{12}$")


class MigrationLockError(RuntimeError):
    """Raised when the migration lock cannot be acquired."""


def _generate_holder_id() -> str:
    return uuid.uuid4().hex[:12]


def _validate_holder(holder: str) -> None:
    if not HOLDER_PATTERN.match(holder):
        raise ValueError(f"Invalid holder ID format: {holder!r}")


def create_lock_table_sql(management_db: str) -> str:
    """SQL to create the migration lock table. Idempotent."""
    return f"""
        CREATE TABLE IF NOT EXISTS {management_db}.{LOCK_TABLE} (
            {LOCK_TABLE_COLUMNS}
        )
        ENGINE = MergeTree()
        ORDER BY lock_id
        TTL toDateTime(acquired_at) + INTERVAL {LOCK_TTL_SECONDS} SECOND
    """


def try_acquire(ch_client: CHClient, management_db: str, holder: str) -> bool:
    """Attempt to acquire the lock. Returns True if acquired.

    Uses insert-then-verify: after inserting a lock row, re-reads to confirm
    no other replica inserted concurrently. The earliest acquired_at wins.
    """
    _validate_holder(holder)

    # No special read settings needed: ch_client routes insert + verify to the
    # same node, and idempotent DDL is the ultimate safety net.
    result = ch_client.query(
        f"SELECT holder, acquired_at FROM {management_db}.{LOCK_TABLE} "
        f"WHERE lock_id = 'migration' "
        f"AND acquired_at > now64(3) - INTERVAL {LOCK_TTL_SECONDS} SECOND "
        f"ORDER BY acquired_at ASC LIMIT 1",
    )
    if result.result_rows:
        existing_holder = result.result_rows[0][0]
        if existing_holder == holder:
            return True
        logger.info(
            "Migration lock held by %s, waiting...",
            existing_holder,
        )
        return False

    # No active lock — try to take it
    ch_client.insert(
        f"{management_db}.{LOCK_TABLE}",
        data=[["migration", holder]],
        column_names=["lock_id", "holder"],
    )

    # Verify we won the race (insert-then-verify pattern). The earliest
    # acquired_at wins; if someone else inserted first, back off.
    verify = ch_client.query(
        f"SELECT holder FROM {management_db}.{LOCK_TABLE} "
        f"WHERE lock_id = 'migration' "
        f"AND acquired_at > now64(3) - INTERVAL {LOCK_TTL_SECONDS} SECOND "
        f"ORDER BY acquired_at ASC LIMIT 1",
    )
    if not verify.result_rows:
        # Insert not yet visible — retry rather than assuming success.
        logger.info("Verify returned no rows after insert, retrying...")
        return False
    if verify.result_rows[0][0] != holder:
        logger.info(
            "Lost lock race to %s, backing off...",
            verify.result_rows[0][0],
        )
        return False

    return True


def release(ch_client: CHClient, management_db: str, holder: str) -> None:
    """Release the lock by deleting our row."""
    _validate_holder(holder)
    try:
        ch_client.command(
            f"ALTER TABLE {management_db}.{LOCK_TABLE} "
            f"DELETE WHERE lock_id = 'migration' AND holder = %(holder)s",
            parameters={"holder": holder},
        )
    except Exception:
        logger.warning(
            "Failed to release migration lock (will expire via TTL)", exc_info=True
        )


def acquire_with_retry(
    ch_client: CHClient,
    management_db: str,
    holder: str | None = None,
    timeout_seconds: float = LOCK_WAIT_TIMEOUT_SECONDS,
) -> str:
    """Block until the migration lock is acquired. Returns the holder ID.

    Raises MigrationLockError if the lock cannot be acquired within the timeout.
    """
    if holder is None:
        holder = _generate_holder_id()

    # Retry both on a lost race (returned False) and on transient CH
    # connection errors during init-container startup.
    retrying = Retrying(
        retry=(
            retry_if_result(lambda acquired: not acquired)
            | retry_if_exception_type(OperationalError)
        ),
        wait=wait_exponential(
            multiplier=LOCK_WAIT_INITIAL_DELAY_SECONDS,
            max=LOCK_WAIT_MAX_DELAY_SECONDS,
        ),
        stop=stop_after_delay(timeout_seconds),
        reraise=True,
    )

    try:
        retrying(try_acquire, ch_client, management_db, holder)
    except (RetryError, OperationalError) as exc:
        raise MigrationLockError(
            f"Could not acquire migration lock after {timeout_seconds:.0f}s. "
            f"Another migration may be stuck — check {management_db}.{LOCK_TABLE} "
            f"and delete stale rows if needed."
        ) from exc

    logger.info("Acquired migration lock (holder=%s)", holder)
    return holder


@contextmanager
def migration_lock(
    ch_client: CHClient,
    management_db: str,
    timeout_seconds: float = LOCK_WAIT_TIMEOUT_SECONDS,
) -> Generator[str]:
    """Context manager that acquires and releases the migration lock."""
    holder = acquire_with_retry(
        ch_client, management_db, timeout_seconds=timeout_seconds
    )
    try:
        yield holder
    finally:
        release(ch_client, management_db, holder)
