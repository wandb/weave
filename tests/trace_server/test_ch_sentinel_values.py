"""Unit tests for ch_sentinel_values module.

Tests sentinel value handling for non-nullable ClickHouse columns in calls_complete:
conversion between Python None and ClickHouse sentinel representations.
"""

import datetime

from weave.trace_server.ch_sentinel_values import (
    ALL_SENTINEL_FIELDS,
    DATETIME_PRECISION,
    SENTINEL_DATETIME,
    SENTINEL_DATETIME_FIELDS,
    SENTINEL_STRING,
    SENTINEL_STRING_FIELDS,
    from_ch_value,
    get_sentinel_value,
    is_sentinel_field,
    null_check_sql,
    sentinel_ch_literal,
    sentinel_ch_type,
    to_ch_value,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable

NON_SENTINEL_FIELDS = ["op_name", "id", "inputs_dump", "wb_run_step", "trace_id"]


def test_constants() -> None:
    """Sentinel constants and field sets are internally consistent."""
    assert SENTINEL_STRING == ""
    assert SENTINEL_DATETIME == datetime.datetime(
        1970, 1, 1, tzinfo=datetime.timezone.utc
    )
    assert ALL_SENTINEL_FIELDS == SENTINEL_STRING_FIELDS | SENTINEL_DATETIME_FIELDS
    assert len(SENTINEL_STRING_FIELDS) > 0
    assert len(SENTINEL_DATETIME_FIELDS) > 0
    assert SENTINEL_STRING_FIELDS.isdisjoint(SENTINEL_DATETIME_FIELDS)


def test_is_sentinel_field() -> None:
    """Known sentinel fields return True; other fields return False."""
    for field in SENTINEL_STRING_FIELDS | SENTINEL_DATETIME_FIELDS:
        assert is_sentinel_field(field) is True, f"{field} should be sentinel"

    for field in NON_SENTINEL_FIELDS:
        assert is_sentinel_field(field) is False, f"{field} should not be sentinel"


def test_get_sentinel_value() -> None:
    """Returns empty string for string fields, SENTINEL_DATETIME for datetime fields, None otherwise."""
    for field in SENTINEL_STRING_FIELDS:
        assert get_sentinel_value(field) == "", f"{field} sentinel should be ''"

    for field in SENTINEL_DATETIME_FIELDS:
        assert get_sentinel_value(field) is SENTINEL_DATETIME, (
            f"{field} sentinel should be SENTINEL_DATETIME"
        )

    for field in NON_SENTINEL_FIELDS:
        assert get_sentinel_value(field) is None, (
            f"{field} should return None (not a sentinel field)"
        )


def test_sentinel_ch_type() -> None:
    """Returns correct CH type strings and raises for non-sentinel fields."""
    for field in SENTINEL_STRING_FIELDS:
        assert sentinel_ch_type(field) == "String"

    for field in SENTINEL_DATETIME_FIELDS:
        precision = DATETIME_PRECISION[field]
        assert sentinel_ch_type(field) == f"DateTime64({precision})"

    # Specific precision values per migration schema
    assert sentinel_ch_type("ended_at") == "DateTime64(6)"
    assert sentinel_ch_type("updated_at") == "DateTime64(3)"
    assert sentinel_ch_type("deleted_at") == "DateTime64(3)"

    for field in NON_SENTINEL_FIELDS:
        try:
            sentinel_ch_type(field)
            raise AssertionError(f"Expected ValueError for {field}")
        except ValueError as e:
            assert f"Not a sentinel field: {field}" in str(e)


def test_sentinel_ch_literal() -> None:
    """Returns toDateTime64 SQL literals for datetime fields; raises for others."""
    assert sentinel_ch_literal("ended_at") == "toDateTime64(0, 6)"
    assert sentinel_ch_literal("updated_at") == "toDateTime64(0, 3)"
    assert sentinel_ch_literal("deleted_at") == "toDateTime64(0, 3)"

    for field in list(SENTINEL_STRING_FIELDS) + NON_SENTINEL_FIELDS:
        try:
            sentinel_ch_literal(field)
            raise AssertionError(f"Expected ValueError for {field}")
        except ValueError as e:
            assert f"Not a sentinel datetime field: {field}" in str(e)


def test_to_ch_value() -> None:
    """Converts None to sentinels on write; passes through non-None and non-sentinel fields."""
    dt = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)

    for field in SENTINEL_STRING_FIELDS:
        assert to_ch_value(field, None) == ""
        assert to_ch_value(field, "hello") == "hello"
        assert to_ch_value(field, "x") == "x"

    for field in SENTINEL_DATETIME_FIELDS:
        assert to_ch_value(field, None) is SENTINEL_DATETIME
        assert to_ch_value(field, dt) is dt

    for field in NON_SENTINEL_FIELDS:
        assert to_ch_value(field, None) is None
        obj = {"foo": "bar"}
        assert to_ch_value(field, obj) is obj


def test_from_ch_value() -> None:
    """Converts sentinels back to None on read; passes through real values."""
    real_dt = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
    naive_epoch = datetime.datetime(1970, 1, 1)
    naive_real = datetime.datetime(2024, 1, 15, 12, 0, 0)

    for field in SENTINEL_STRING_FIELDS:
        assert from_ch_value(field, "") is None
        assert from_ch_value(field, "hello") == "hello"
        assert from_ch_value(field, "x") == "x"

    for field in SENTINEL_DATETIME_FIELDS:
        assert from_ch_value(field, SENTINEL_DATETIME) is None
        assert from_ch_value(field, naive_epoch) is None  # timezone-ignoring
        assert from_ch_value(field, real_dt) is real_dt
        assert from_ch_value(field, naive_real) is naive_real
        assert from_ch_value(field, None) is None  # CH may return None during migration

    for field in NON_SENTINEL_FIELDS:
        assert from_ch_value(field, None) is None
        assert from_ch_value(field, "hello") == "hello"
        assert from_ch_value(field, 42) == 42
        obj = {"key": "val"}
        assert from_ch_value(field, obj) is obj


def test_null_check_sql() -> None:
    """Generates correct SQL for null/sentinel checks across table types and negate flag."""
    # calls_complete: string sentinel field uses = sentinel param
    pb = ParamBuilder("pb")
    result = null_check_sql("parent_id", "t.parent_id", ReadTable.CALLS_COMPLETE, pb)
    assert "=" in result
    assert "IS NULL" not in result
    assert "String" in result

    # calls_complete: datetime sentinel field uses = sentinel param
    pb = ParamBuilder("pb")
    result = null_check_sql("ended_at", "t.ended_at", ReadTable.CALLS_COMPLETE, pb)
    assert "=" in result
    assert "IS NULL" not in result
    assert "DateTime64(6)" in result

    # calls_merged: sentinel fields still use IS NULL (nullable columns)
    pb = ParamBuilder("pb")
    result = null_check_sql("parent_id", "t.parent_id", ReadTable.CALLS_MERGED, pb)
    assert result == "t.parent_id IS NULL"

    # calls_complete: non-sentinel fields still use IS NULL
    pb = ParamBuilder("pb")
    result = null_check_sql(
        "wb_run_step", "t.wb_run_step", ReadTable.CALLS_COMPLETE, pb
    )
    assert result == "t.wb_run_step IS NULL"

    # negate: calls_complete sentinel field uses != sentinel
    pb = ParamBuilder("pb")
    result = null_check_sql(
        "wb_run_id", "t.wb_run_id", ReadTable.CALLS_COMPLETE, pb, negate=True
    )
    assert "!=" in result
    assert "IS NOT NULL" not in result

    # negate: calls_merged uses IS NOT NULL
    pb = ParamBuilder("pb")
    result = null_check_sql(
        "wb_run_id", "t.wb_run_id", ReadTable.CALLS_MERGED, pb, negate=True
    )
    assert result == "t.wb_run_id IS NOT NULL"

    # negate: non-sentinel field always uses IS NOT NULL
    pb = ParamBuilder("pb")
    result = null_check_sql(
        "op_name", "t.op_name", ReadTable.CALLS_COMPLETE, pb, negate=True
    )
    assert result == "t.op_name IS NOT NULL"
