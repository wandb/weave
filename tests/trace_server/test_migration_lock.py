from unittest.mock import Mock

import pytest

from weave.trace_server.migration_lock import (
    LOCK_TTL_SECONDS,
    MigrationLockError,
    _generate_holder_id,
    _validate_holder,
    acquire_with_retry,
    release,
    try_acquire,
)

MANAGEMENT_DB = "db_management"


def _make_ch_client(existing_rows: list | None = None) -> Mock:
    """Create a mock CH client.

    existing_rows: rows returned by query() for lock checks.
    If None, returns empty (no lock held).
    """
    ch_client = Mock()
    query_result = Mock()
    query_result.result_rows = existing_rows or []
    ch_client.query.return_value = query_result
    return ch_client


def test_try_acquire_succeeds_on_empty_table():
    ch_client = _make_ch_client(existing_rows=[])
    holder = _generate_holder_id()

    assert try_acquire(ch_client, MANAGEMENT_DB, holder) is True
    # Should have inserted the lock row
    ch_client.insert.assert_called_once()
    # Should have done two queries: initial check + verify
    assert ch_client.query.call_count == 2


def test_try_acquire_returns_false_when_held_by_another():
    other_holder = _generate_holder_id()
    ch_client = _make_ch_client(existing_rows=[(other_holder, "2026-01-01 00:00:00")])
    holder = _generate_holder_id()

    assert try_acquire(ch_client, MANAGEMENT_DB, holder) is False
    # Should NOT have inserted
    ch_client.insert.assert_not_called()


def test_try_acquire_returns_true_when_held_by_self():
    holder = _generate_holder_id()
    ch_client = _make_ch_client(existing_rows=[(holder, "2026-01-01 00:00:00")])

    assert try_acquire(ch_client, MANAGEMENT_DB, holder) is True
    ch_client.insert.assert_not_called()


def test_try_acquire_detects_race_via_verify():
    """After INSERT, if verify SELECT shows another holder won, back off."""
    other_holder = _generate_holder_id()
    holder = _generate_holder_id()

    # First query: no lock. Second query (verify): other holder won.
    empty_result = Mock()
    empty_result.result_rows = []
    race_result = Mock()
    race_result.result_rows = [(other_holder,)]

    ch_client = Mock()
    ch_client.query.side_effect = [empty_result, race_result]

    assert try_acquire(ch_client, MANAGEMENT_DB, holder) is False
    # Should have inserted (tried to acquire)
    ch_client.insert.assert_called_once()


def test_try_acquire_confirms_own_insert_via_verify():
    """After INSERT, verify shows we won."""
    holder = _generate_holder_id()

    empty_result = Mock()
    empty_result.result_rows = []
    verify_result = Mock()
    verify_result.result_rows = [(holder,)]

    ch_client = Mock()
    ch_client.query.side_effect = [empty_result, verify_result]

    assert try_acquire(ch_client, MANAGEMENT_DB, holder) is True


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


def test_acquire_with_retry_succeeds_immediately():
    ch_client = _make_ch_client(existing_rows=[])
    holder_id = acquire_with_retry(ch_client, MANAGEMENT_DB, timeout_seconds=5.0)
    assert len(holder_id) == 12


def test_acquire_with_retry_times_out():
    other_holder = _generate_holder_id()
    ch_client = _make_ch_client(existing_rows=[(other_holder, "2026-01-01 00:00:00")])

    with pytest.raises(MigrationLockError, match="Could not acquire migration lock"):
        acquire_with_retry(ch_client, MANAGEMENT_DB, timeout_seconds=1.0)


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


def test_lock_ttl_is_reasonable():
    assert LOCK_TTL_SECONDS <= 120, (
        f"Lock TTL is {LOCK_TTL_SECONDS}s — should be <=120s to avoid long "
        "stalls when a pod crashes mid-migration"
    )
