"""Distributed migration lock backed by a ClickHouse MergeTree table.

On multi-replica deployments, init containers race to apply migrations. This
module provides a lease-based advisory lock: one replica writes a lock row and
heartbeats it while it works; others see the live lease and wait. A holder that
dies stops heartbeating, so its lease expires within `LOCK_LEASE_TTL_SECONDS`
and the next replica takes over -- bounding the worst-case stall instead of
waiting out a long fixed TTL.

Ownership is first-come-first-served: the earliest `acquired_at` wins, ties
broken deterministically by holder id so every replica agrees on the winner.
Liveness is tracked separately via `heartbeat_at` (refreshed by re-inserting a
row), so a live holder keeps the lock as long as it heartbeats without moving
the ownership anchor.

The lock is best-effort -- ClickHouse reads are eventually consistent, so there
is a small window where two replicas could briefly believe they hold it.
Combined with idempotent DDL, the window shrinks to near-zero without external
dependencies.
"""

import logging
import re
import threading
import uuid
from collections.abc import Callable, Generator
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

from weave.trace_server.environment import wf_clickhouse_disable_lightweight_update

logger = logging.getLogger(__name__)

LOCK_TABLE = "migration_lock"

# Liveness window: a holder must refresh its lease within this many seconds or
# it is treated as dead and another replica may take over. Bounds the
# worst-case stall after a holder crashes mid-migration.
LOCK_LEASE_TTL_SECONDS = 120

# How often the holder refreshes its lease (must be << LOCK_LEASE_TTL_SECONDS).
LOCK_HEARTBEAT_INTERVAL_SECONDS = 30

# Rows are garbage-collected this long after their last write. Generous so a
# live holder's ownership anchor survives any realistic migration; liveness is
# governed by LOCK_LEASE_TTL_SECONDS, not by this.
LOCK_ROW_GC_SECONDS = 3600

# Column definitions shared between cloud/replicated/distributed table creation.
LOCK_TABLE_COLUMNS = """
    lock_id String,
    holder String,
    acquired_at DateTime64(3) DEFAULT now64(3),
    heartbeat_at DateTime64(3) DEFAULT now64(3)
"""

# Polling configuration for waiting on a lock held by another replica.
LOCK_WAIT_INITIAL_DELAY_SECONDS = 0.5
LOCK_WAIT_MAX_DELAY_SECONDS = 5.0
# Must comfortably exceed LOCK_LEASE_TTL_SECONDS so a waiter outlasts one dead
# holder's lease expiry rather than timing out alongside it.
LOCK_WAIT_TIMEOUT_SECONDS = 300.0

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
        TTL toDateTime(heartbeat_at) + INTERVAL {LOCK_ROW_GC_SECONDS} SECOND
    """


def add_heartbeat_column_sql(management_db: str) -> str:
    """SQL to add `heartbeat_at` to an already-deployed lock table. Idempotent."""
    return (
        f"ALTER TABLE {management_db}.{LOCK_TABLE} "
        f"ADD COLUMN IF NOT EXISTS heartbeat_at DateTime64(3) DEFAULT now64(3)"
    )


def _active_owner(ch_client: CHClient, management_db: str) -> str | None:
    """Return the holder that currently owns the lock, or None if free.

    The owner is the earliest `acquired_at` among holders whose lease is still
    live (`max(heartbeat_at)` within the TTL), ties broken by holder id so every
    replica computes the same winner.
    """
    result = ch_client.query(
        f"SELECT holder FROM {management_db}.{LOCK_TABLE} "
        f"WHERE lock_id = 'migration' "
        f"GROUP BY holder "
        f"HAVING max(heartbeat_at) > now64(3) - INTERVAL {LOCK_LEASE_TTL_SECONDS} SECOND "
        f"ORDER BY min(acquired_at) ASC, holder ASC "
        f"LIMIT 1",
    )
    if result.result_rows:
        return result.result_rows[0][0]
    return None


def try_acquire(ch_client: CHClient, management_db: str, holder: str) -> bool:
    """Attempt to acquire the lock. Returns True if acquired.

    Uses insert-then-verify: after inserting a lock row, re-reads the active
    owner to confirm no earlier replica won the race.
    """
    _validate_holder(holder)

    owner = _active_owner(ch_client, management_db)
    if owner is not None:
        if owner == holder:
            return True
        logger.info("Migration lock held by %s, waiting...", owner)
        return False

    # No active owner -- stake a claim.
    ch_client.insert(
        f"{management_db}.{LOCK_TABLE}",
        data=[["migration", holder]],
        column_names=["lock_id", "holder"],
    )

    # Verify we won the race. The earliest acquired_at wins; if someone else
    # got in first, back off.
    owner = _active_owner(ch_client, management_db)
    if owner is None:
        logger.info("No active owner after insert (not yet visible), retrying...")
        return False
    if owner != holder:
        logger.info("Lost lock race to %s, backing off...", owner)
        return False
    return True


def heartbeat(ch_client: CHClient, management_db: str, holder: str) -> None:
    """Refresh the holder's lease by inserting a fresh row.

    The new row's `acquired_at` is later than the original, but ownership uses
    `min(acquired_at)` per holder, so the first-come anchor is preserved while
    `max(heartbeat_at)` advances.
    """
    _validate_holder(holder)
    ch_client.insert(
        f"{management_db}.{LOCK_TABLE}",
        data=[["migration", holder]],
        column_names=["lock_id", "holder"],
    )


def release(ch_client: CHClient, management_db: str, holder: str) -> None:
    """Release the lock by deleting our rows.

    Prefers lightweight `DELETE FROM` (promptly visible); old ClickHouse without
    it falls back to the async `ALTER ... DELETE` mutation via the env flag.
    """
    _validate_holder(holder)
    where = "WHERE lock_id = 'migration' AND holder = %(holder)s"
    if wf_clickhouse_disable_lightweight_update():
        statement = f"ALTER TABLE {management_db}.{LOCK_TABLE} DELETE {where}"
    else:
        statement = f"DELETE FROM {management_db}.{LOCK_TABLE} {where}"
    try:
        ch_client.command(statement, parameters={"holder": holder})
    except Exception:
        logger.warning(
            "Failed to release migration lock (will expire via lease)", exc_info=True
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
            f"Another migration may be stuck -- check {management_db}.{LOCK_TABLE} "
            f"and delete stale rows if needed."
        ) from exc

    logger.info("Acquired migration lock (holder=%s)", holder)
    return holder


def _heartbeat_loop(
    client_factory: Callable[[], CHClient],
    management_db: str,
    holder: str,
    stop: threading.Event,
) -> None:
    """Refresh the lease on a dedicated connection until signalled to stop.

    A separate connection is required because clickhouse_connect clients are not
    safe to share across threads with the in-progress migration.
    """
    hb_client: CHClient | None = None
    try:
        hb_client = client_factory()
        while not stop.wait(LOCK_HEARTBEAT_INTERVAL_SECONDS):
            try:
                heartbeat(hb_client, management_db, holder)
            except Exception:
                logger.warning("Migration lock heartbeat failed", exc_info=True)
    except Exception:
        logger.warning("Migration lock heartbeat thread could not start", exc_info=True)
    finally:
        if hb_client is not None:
            hb_client.close()


@contextmanager
def migration_lock(
    ch_client: CHClient,
    management_db: str,
    *,
    timeout_seconds: float = LOCK_WAIT_TIMEOUT_SECONDS,
    heartbeat_client_factory: Callable[[], CHClient] | None = None,
) -> Generator[str]:
    """Acquire the lock, heartbeat it while held, and release on exit.

    If `heartbeat_client_factory` is provided, a background thread refreshes the
    lease on a dedicated connection so a long migration is not mistaken for a
    dead holder. Without it the lock degrades to a single fixed lease, which is
    fine for uncontended callers (tests, single-replica boots).
    """
    holder = acquire_with_retry(
        ch_client, management_db, timeout_seconds=timeout_seconds
    )
    stop = threading.Event()
    hb_thread: threading.Thread | None = None
    if heartbeat_client_factory is not None:
        hb_thread = threading.Thread(
            target=_heartbeat_loop,
            args=(heartbeat_client_factory, management_db, holder, stop),
            daemon=True,
        )
        hb_thread.start()
    try:
        yield holder
    finally:
        stop.set()
        if hb_thread is not None:
            # Drain any in-flight heartbeat before deleting, else a late insert
            # resurrects the lock row after release.
            hb_thread.join()
        release(ch_client, management_db, holder)
