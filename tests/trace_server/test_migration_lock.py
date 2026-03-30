from unittest.mock import Mock

import pytest

from weave.trace_server.migration_lock import (
    CONSISTENT_READ_SETTINGS,
    LOCK_TTL_SECONDS,
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
# try_acquire
# ---------------------------------------------------------------------------


def test_try_acquire_succeeds_when_verify_confirms():
    holder = _generate_holder_id()
    ch_client = _make_ch_client(initial_rows=[], verify_rows=[(holder,)])

    assert try_acquire(ch_client, MANAGEMENT_DB, holder) is True
    ch_client.insert.assert_called_once()
    assert ch_client.query.call_count == 2


def test_try_acquire_returns_false_when_held_by_another():
    other_holder = _generate_holder_id()
    ch_client = _make_ch_client(initial_rows=[(other_holder, "2026-01-01 00:00:00")])
    holder = _generate_holder_id()

    assert try_acquire(ch_client, MANAGEMENT_DB, holder) is False
    ch_client.insert.assert_not_called()


def test_try_acquire_returns_true_when_held_by_self():
    holder = _generate_holder_id()
    ch_client = _make_ch_client(initial_rows=[(holder, "2026-01-01 00:00:00")])

    assert try_acquire(ch_client, MANAGEMENT_DB, holder) is True
    ch_client.insert.assert_not_called()


def test_try_acquire_detects_race_via_verify():
    """After INSERT, if verify SELECT shows another holder won, back off."""
    other_holder = _generate_holder_id()
    holder = _generate_holder_id()
    ch_client = _make_ch_client(initial_rows=[], verify_rows=[(other_holder,)])

    assert try_acquire(ch_client, MANAGEMENT_DB, holder) is False
    ch_client.insert.assert_called_once()


def test_try_acquire_retries_when_verify_returns_empty():
    """If verify returns no rows (insert not yet visible), return False to retry."""
    holder = _generate_holder_id()
    ch_client = _make_ch_client(initial_rows=[], verify_rows=[])

    assert try_acquire(ch_client, MANAGEMENT_DB, holder) is False
    ch_client.insert.assert_called_once()


def test_try_acquire_passes_consistent_read_settings():
    """Both queries should use select_sequential_consistency=1."""
    holder = _generate_holder_id()
    ch_client = _make_ch_client(initial_rows=[], verify_rows=[(holder,)])

    try_acquire(ch_client, MANAGEMENT_DB, holder)

    for call in ch_client.query.call_args_list:
        assert call.kwargs.get("settings") == CONSISTENT_READ_SETTINGS


# ---------------------------------------------------------------------------
# release
# ---------------------------------------------------------------------------


def test_release_issues_delete():
    ch_client = Mock()
    holder = _generate_holder_id()
    release(ch_client, MANAGEMENT_DB, holder)
    ch_client.command.assert_called_once()
    call_sql = ch_client.command.call_args[0][0]
    assert "DELETE" in call_sql
    assert "migration_lock" in call_sql


def test_release_swallows_errors():
    ch_client = Mock()
    ch_client.command.side_effect = RuntimeError("connection lost")
    holder = _generate_holder_id()
    # Should not raise
    release(ch_client, MANAGEMENT_DB, holder)


# ---------------------------------------------------------------------------
# acquire_with_retry
# ---------------------------------------------------------------------------


def test_acquire_with_retry_succeeds_immediately():
    holder = _generate_holder_id()
    ch_client = _make_ch_client(initial_rows=[], verify_rows=[(holder,)])
    # acquire_with_retry generates its own holder, so mock both queries
    # to return success for any holder.
    ch_client.query.side_effect = None
    empty_result = Mock()
    empty_result.result_rows = []

    def _query_side_effect(sql, **kwargs):
        if ch_client.query.call_count % 2 == 1:
            return empty_result
        # verify query — return the holder that was just inserted
        insert_data = ch_client.insert.call_args[1].get(
            "data",
            ch_client.insert.call_args[0][1]
            if len(ch_client.insert.call_args[0]) > 1
            else None,
        )
        result = Mock()
        if insert_data:
            result.result_rows = [(insert_data[0][1],)]
        else:
            result.result_rows = []
        return result

    ch_client.query.side_effect = _query_side_effect
    holder_id = acquire_with_retry(ch_client, MANAGEMENT_DB, timeout_seconds=5.0)
    assert len(holder_id) == 12


def test_acquire_with_retry_times_out():
    other_holder = _generate_holder_id()
    ch_client = _make_ch_client(initial_rows=[(other_holder, "2026-01-01 00:00:00")])

    with pytest.raises(MigrationLockError, match="Could not acquire migration lock"):
        acquire_with_retry(ch_client, MANAGEMENT_DB, timeout_seconds=1.0)


# ---------------------------------------------------------------------------
# migration_lock context manager
# ---------------------------------------------------------------------------


def test_migration_lock_context_manager_acquires_and_releases():
    ch_client = Mock()

    # The context manager calls acquire_with_retry which generates its own
    # holder, so we dynamically return the inserted holder in the verify query.
    empty_result = Mock()
    empty_result.result_rows = []

    call_count = 0

    def _query_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Initial check — no lock held
            return empty_result
        # Verify — return whoever was just inserted
        inserted = ch_client.insert.call_args.kwargs["data"][0]
        result = Mock()
        result.result_rows = [(inserted[1],)]  # holder column
        return result

    ch_client.query.side_effect = _query_side_effect

    with migration_lock(ch_client, MANAGEMENT_DB, timeout_seconds=5.0) as holder:
        assert len(holder) == 12
        ch_client.insert.assert_called_once()

    # After exiting, release should have been called
    ch_client.command.assert_called_once()
    assert "DELETE" in ch_client.command.call_args[0][0]


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


def test_validate_holder_rejects_bad_input():
    with pytest.raises(ValueError, match="Invalid holder ID"):
        _validate_holder("'; DROP TABLE --")

    with pytest.raises(ValueError, match="Invalid holder ID"):
        _validate_holder("")

    with pytest.raises(ValueError, match="Invalid holder ID"):
        _validate_holder("too_long_holder_id_12345")


def test_validate_holder_accepts_valid():
    _validate_holder(_generate_holder_id())
    _validate_holder("abcdef012345")


def test_lock_ttl_is_600s():
    assert LOCK_TTL_SECONDS == 600


# ---------------------------------------------------------------------------
# Integration test — real ClickHouse
# ---------------------------------------------------------------------------


@pytest.fixture
def real_ch_lock(ensure_clickhouse_db):
    """Real ClickHouse client + lock table for integration tests."""
    import clickhouse_connect

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
