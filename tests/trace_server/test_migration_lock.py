import threading
from unittest.mock import Mock, patch

import clickhouse_connect
import pytest
from clickhouse_connect.driver.exceptions import OperationalError

from weave.trace_server.migration_lock import (
    MigrationLockError,
    _active_owner,
    _generate_holder_id,
    _heartbeat_loop,
    _validate_holder,
    acquire_with_retry,
    create_lock_table_sql,
    heartbeat,
    migration_lock,
    release,
    try_acquire,
)

MANAGEMENT_DB = "db_management"


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
        "DELETE FROM db_management.migration_lock "
        "WHERE lock_id = 'migration' AND holder = %(holder)s"
    )

    # Release swallows errors (lock will expire via TTL)
    release_holder = _generate_holder_id()
    error_client = Mock()
    error_client.command.side_effect = RuntimeError("connection lost")
    release(error_client, MANAGEMENT_DB, release_holder)  # should not raise


@pytest.mark.parametrize(
    ("disable_lightweight", "expected_prefix"),
    [
        (False, "DELETE FROM db_management.migration_lock"),
        (True, "ALTER TABLE db_management.migration_lock DELETE"),
    ],
)
def test_release_respects_lightweight_delete_flag(
    monkeypatch, disable_lightweight, expected_prefix
):
    """Old ClickHouse without lightweight delete falls back to ALTER ... DELETE."""
    monkeypatch.setattr(
        "weave.trace_server.migration_lock.wf_clickhouse_disable_lightweight_update",
        lambda: disable_lightweight,
    )
    ch_client = Mock()
    holder = _generate_holder_id()

    release(ch_client, MANAGEMENT_DB, holder)

    stmt = ch_client.command.call_args[0][0]
    assert stmt.startswith(expected_prefix)
    assert ch_client.command.call_args.kwargs["parameters"] == {"holder": holder}


# ---------------------------------------------------------------------------
# Heartbeat / lease liveness
# ---------------------------------------------------------------------------


def test_active_owner_returns_holder_or_none():
    holder = _generate_holder_id()
    ch_client = Mock()

    present = Mock()
    present.result_rows = [(holder,)]
    ch_client.query.return_value = present
    assert _active_owner(ch_client, MANAGEMENT_DB) == holder

    empty = Mock()
    empty.result_rows = []
    ch_client.query.return_value = empty
    assert _active_owner(ch_client, MANAGEMENT_DB) is None


def test_heartbeat_inserts_fresh_row():
    ch_client = Mock()
    holder = _generate_holder_id()

    heartbeat(ch_client, MANAGEMENT_DB, holder)

    ch_client.insert.assert_called_once()
    assert ch_client.insert.call_args.kwargs["data"] == [["migration", holder]]
    assert ch_client.insert.call_args.kwargs["column_names"] == ["lock_id", "holder"]


def test_heartbeat_loop_refreshes_until_stopped(monkeypatch):
    """The loop refreshes on its own connection and closes it on exit."""
    monkeypatch.setattr(
        "weave.trace_server.migration_lock.LOCK_HEARTBEAT_INTERVAL_SECONDS", 0.01
    )
    hb_client = Mock()
    stop = threading.Event()
    # Stop right after the first heartbeat so the test is deterministic.
    hb_client.insert.side_effect = lambda *a, **k: stop.set()

    _heartbeat_loop(lambda: hb_client, MANAGEMENT_DB, _generate_holder_id(), stop)

    hb_client.insert.assert_called_once()
    hb_client.close.assert_called_once()


def _acquire_then_own_client() -> Mock:
    """Mock CH client whose acquire sequence: no owner, then we own it."""
    ch_client = Mock()
    empty = Mock()
    empty.result_rows = []

    def _query(*_args, **_kwargs):
        if ch_client.insert.call_count == 0:
            return empty
        won = Mock()
        won.result_rows = [(ch_client.insert.call_args.kwargs["data"][0][1],)]
        return won

    ch_client.query.side_effect = _query
    return ch_client


def test_migration_lock_thread_lifecycle():
    """A heartbeat thread runs only when a client factory is supplied; the lock
    is always released via a lightweight delete on exit.
    """
    with patch("weave.trace_server.migration_lock.threading.Thread") as mock_thread:
        with migration_lock(
            _acquire_then_own_client(),
            MANAGEMENT_DB,
            timeout_seconds=5.0,
            heartbeat_client_factory=Mock(),
        ):
            pass
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()
        mock_thread.return_value.join.assert_called_once()

    with patch("weave.trace_server.migration_lock.threading.Thread") as mock_thread:
        ch_client = _acquire_then_own_client()
        with migration_lock(ch_client, MANAGEMENT_DB, timeout_seconds=5.0):
            pass
        mock_thread.assert_not_called()
    assert ch_client.command.call_args[0][0].startswith("DELETE FROM")


def test_acquire_with_retry_outcomes():
    """acquire_with_retry: times out under a held lock, retries through a
    transient error, and surfaces a persistent error as MigrationLockError.
    """
    # Held by another holder for the whole window -> timeout.
    held_client = _make_ch_client(
        initial_rows=[(_generate_holder_id(), "2026-01-01 00:00:00")]
    )
    with pytest.raises(MigrationLockError, match="Could not acquire migration lock"):
        acquire_with_retry(held_client, MANAGEMENT_DB, timeout_seconds=1.0)

    # Transient OperationalError on the first query, then a normal acquire.
    transient_client = Mock()
    empty_result = Mock()
    empty_result.result_rows = []
    call_count = 0

    def _query_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OperationalError("connection reset")
        if transient_client.insert.call_count == 0:
            return empty_result
        result = Mock()
        result.result_rows = [(transient_client.insert.call_args.kwargs["data"][0][1],)]
        return result

    transient_client.query.side_effect = _query_side_effect
    holder = acquire_with_retry(transient_client, MANAGEMENT_DB, timeout_seconds=5.0)
    assert len(holder) == 12
    assert call_count >= 2  # proves we retried

    # Persistent OperationalError -> MigrationLockError, not the raw error.
    down_client = Mock()
    down_client.query.side_effect = OperationalError("clickhouse down")
    with pytest.raises(MigrationLockError, match="Could not acquire migration lock"):
        acquire_with_retry(down_client, MANAGEMENT_DB, timeout_seconds=1.0)


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
def real_ch_lock(ensure_clickhouse_db):
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


def _make_ch_client(
    initial_rows: list | None = None,
    verify_rows: list | None = None,
) -> Mock:
    """Mock CH client.

    initial_rows back the first query (lock check); verify_rows back the second
    (post-insert verify). With only initial_rows, both queries return it.
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
