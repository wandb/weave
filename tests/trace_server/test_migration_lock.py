from unittest.mock import Mock

import clickhouse_connect
import pytest
from clickhouse_connect.driver.exceptions import OperationalError

from weave.trace_server.migration_lock import (
    MigrationLockError,
    _generate_holder_id,
    _validate_holder,
    acquire_with_retry,
    create_lock_table_sql,
    migration_lock,
    release,
    try_acquire,
)

MANAGEMENT_DB = "db_management"


def _make_ch_client(
    initial_rows: list | None = None,
    verify_rows: list | None = None,
) -> Mock:
    """Create a mock CH client.

    initial_rows: rows returned by the first query (lock check).
    verify_rows: rows returned by the second query (post-insert verify).
    If only initial_rows is provided, both queries return that value.
    """
    ch_client = Mock()

    if verify_rows is not None:
        initial_result = Mock()
        initial_result.result_rows = initial_rows or []
        verify_result = Mock()
        verify_result.result_rows = verify_rows
        ch_client.query.side_effect = [initial_result, verify_result]
    else:
        query_result = Mock()
        query_result.result_rows = initial_rows or []
        ch_client.query.return_value = query_result

    return ch_client


# ---------------------------------------------------------------------------
# try_acquire — all outcomes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("initial_rows", "verify_rows", "expected", "should_insert"),
    [
        # No lock held, verify confirms we won → acquire succeeds
        ([], "self", True, True),
        # No lock held, verify shows another holder won the race → back off
        ([], "other", False, True),
        # No lock held, verify returns empty (insert not yet visible) → retry
        ([], [], False, True),
        # Lock held by another holder → don't even try to insert
        ("other_held", None, False, False),
        # Lock already held by us (idempotent re-acquire) → no insert needed
        ("self_held", None, True, False),
    ],
    ids=[
        "win_race",
        "lose_race",
        "insert_not_visible",
        "held_by_other",
        "idempotent_reacquire",
    ],
)
def test_try_acquire_outcomes(initial_rows, verify_rows, expected, should_insert):
    holder = _generate_holder_id()
    other = _generate_holder_id()

    # Resolve symbolic row values to actual rows
    if initial_rows == "other_held":
        initial_rows = [(other, "2026-01-01 00:00:00")]
    elif initial_rows == "self_held":
        initial_rows = [(holder, "2026-01-01 00:00:00")]

    if verify_rows == "self":
        verify_rows = [(holder,)]
    elif verify_rows == "other":
        verify_rows = [(other,)]

    ch_client = _make_ch_client(
        initial_rows=initial_rows,
        verify_rows=verify_rows,
    )

    assert try_acquire(ch_client, MANAGEMENT_DB, holder) is expected

    if should_insert:
        ch_client.insert.assert_called_once()
    else:
        ch_client.insert.assert_not_called()


# ---------------------------------------------------------------------------
# Full lifecycle: context manager acquire → use → release
# ---------------------------------------------------------------------------


def test_migration_lock_acquires_releases_and_handles_errors():
    """The context manager should acquire, yield the holder, release on exit,
    and swallow release errors gracefully.
    """
    ch_client = Mock()

    empty_result = Mock()
    empty_result.result_rows = []
    call_count = 0

    def _query_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return empty_result
        inserted = ch_client.insert.call_args.kwargs["data"][0]
        result = Mock()
        result.result_rows = [(inserted[1],)]
        return result

    ch_client.query.side_effect = _query_side_effect

    # Happy path: acquire + release
    with migration_lock(ch_client, MANAGEMENT_DB, timeout_seconds=5.0) as holder:
        assert len(holder) == 12
        ch_client.insert.assert_called_once()

    ch_client.command.assert_called_once()
    assert ch_client.command.call_args[0][0] == (
        "ALTER TABLE db_management.migration_lock "
        "DELETE WHERE lock_id = 'migration' AND holder = %(holder)s"
    )

    # Release swallows errors (lock will expire via TTL)
    release_holder = _generate_holder_id()
    error_client = Mock()
    error_client.command.side_effect = RuntimeError("connection lost")
    release(error_client, MANAGEMENT_DB, release_holder)  # should not raise


def test_acquire_with_retry_times_out_when_lock_held():
    other_holder = _generate_holder_id()
    ch_client = _make_ch_client(initial_rows=[(other_holder, "2026-01-01 00:00:00")])

    with pytest.raises(MigrationLockError, match="Could not acquire migration lock"):
        acquire_with_retry(ch_client, MANAGEMENT_DB, timeout_seconds=1.0)


def test_acquire_with_retry_recovers_from_transient_error():
    """Transient OperationalError should retry, not fail fast."""
    ch_client = Mock()
    empty_result = Mock()
    empty_result.result_rows = []
    call_count = 0

    def _query_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # First call on first attempt: raise transient error.
        # Subsequent calls: behave like a normal successful acquire.
        if call_count == 1:
            raise OperationalError("connection reset")
        if ch_client.insert.call_count == 0:
            return empty_result
        result = Mock()
        result.result_rows = [(ch_client.insert.call_args.kwargs["data"][0][1],)]
        return result

    ch_client.query.side_effect = _query_side_effect

    holder = acquire_with_retry(ch_client, MANAGEMENT_DB, timeout_seconds=5.0)
    assert len(holder) == 12
    assert call_count >= 2  # proves we retried


def test_acquire_with_retry_surfaces_persistent_error():
    """Persistent OperationalError should raise MigrationLockError, not bubble raw."""
    ch_client = Mock()
    ch_client.query.side_effect = OperationalError("clickhouse down")

    with pytest.raises(MigrationLockError, match="Could not acquire migration lock"):
        acquire_with_retry(ch_client, MANAGEMENT_DB, timeout_seconds=1.0)


# ---------------------------------------------------------------------------
# Holder validation — SQL injection defense
# ---------------------------------------------------------------------------


def test_holder_validation():
    # Rejects SQL injection attempts, empty strings, and oversized values
    for bad_input in ["'; DROP TABLE --", "", "too_long_holder_id_12345"]:
        with pytest.raises(ValueError, match="Invalid holder ID"):
            _validate_holder(bad_input)

    # Accepts well-formed holder IDs
    _validate_holder(_generate_holder_id())
    _validate_holder("abcdef012345")


# ---------------------------------------------------------------------------
# Integration test — real ClickHouse
# ---------------------------------------------------------------------------


@pytest.fixture
def real_ch_lock(require_clickhouse, ensure_clickhouse_db):
    """Real ClickHouse client + lock table for integration tests."""
    host, port = next(ensure_clickhouse_db())
    client = clickhouse_connect.get_client(host=host, port=port)
    mgmt_db = "test_lock_integ"
    client.command(f"CREATE DATABASE IF NOT EXISTS {mgmt_db}")
    client.command(create_lock_table_sql(mgmt_db))
    yield client, mgmt_db
    try:
        client.command(f"DROP DATABASE IF EXISTS {mgmt_db}")
    except Exception:
        pass
    client.close()


def test_lock_acquire_release_real_clickhouse(real_ch_lock):
    """Two holders race on a real ClickHouse — only one wins at a time."""
    client, mgmt_db = real_ch_lock
    holder_a = _generate_holder_id()
    holder_b = _generate_holder_id()

    # A acquires successfully
    assert try_acquire(client, mgmt_db, holder_a) is True
    # B cannot acquire while A holds it
    assert try_acquire(client, mgmt_db, holder_b) is False
    # A can re-acquire (idempotent)
    assert try_acquire(client, mgmt_db, holder_a) is True

    # Release A, then B acquires via retry (lightweight delete is async)
    release(client, mgmt_db, holder_a)
    result = acquire_with_retry(client, mgmt_db, holder=holder_b, timeout_seconds=10.0)
    assert result == holder_b
    release(client, mgmt_db, holder_b)
