"""Unit tests for ch_sentinel_values module.

Tests sentinel value handling for non-nullable ClickHouse columns in calls_complete:
conversion between Python None and ClickHouse sentinel representations.
"""

import datetime

import pytest

from weave.trace_server.ch_sentinel_values import (
    ALL_SENTINEL_FIELDS,
    DATETIME_PRECISION,
    SENTINEL_DATETIME,
    SENTINEL_DATETIME_FIELDS,
    SENTINEL_INT,
    SENTINEL_INT_FIELDS,
    SENTINEL_STRING,
    SENTINEL_STRING_FIELDS,
    from_ch_value,
    get_sentinel_value,
    is_sentinel_field,
    null_check_literal_sql,
    null_check_sql,
    sentinel_ch_literal,
    sentinel_ch_type,
    to_ch_value,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable

NON_SENTINEL_FIELDS = ["op_name", "id", "inputs_dump", "trace_id"]


def test_constants() -> None:
    """Sentinel constants and field sets are internally consistent."""
    assert SENTINEL_STRING == ""
    assert SENTINEL_DATETIME == datetime.datetime(
        1970, 1, 1, tzinfo=datetime.timezone.utc
    )
    assert SENTINEL_INT == 0
    assert ALL_SENTINEL_FIELDS == (
        SENTINEL_STRING_FIELDS | SENTINEL_DATETIME_FIELDS | SENTINEL_INT_FIELDS
    )
    assert len(SENTINEL_STRING_FIELDS) > 0
    assert len(SENTINEL_DATETIME_FIELDS) > 0
    assert len(SENTINEL_INT_FIELDS) > 0
    assert SENTINEL_STRING_FIELDS.isdisjoint(SENTINEL_DATETIME_FIELDS)
    assert SENTINEL_STRING_FIELDS.isdisjoint(SENTINEL_INT_FIELDS)
    assert SENTINEL_DATETIME_FIELDS.isdisjoint(SENTINEL_INT_FIELDS)


def test_is_sentinel_field() -> None:
    """Known sentinel fields return True; other fields return False."""
    for field in (
        SENTINEL_STRING_FIELDS | SENTINEL_DATETIME_FIELDS | SENTINEL_INT_FIELDS
    ):
        assert is_sentinel_field(field) is True, f"{field} should be sentinel"

    for field in NON_SENTINEL_FIELDS:
        assert is_sentinel_field(field) is False, f"{field} should not be sentinel"


def test_get_sentinel_value() -> None:
    """Returns correct sentinel for each field type, None otherwise."""
    for field in SENTINEL_STRING_FIELDS:
        assert get_sentinel_value(field) == "", f"{field} sentinel should be ''"

    for field in SENTINEL_DATETIME_FIELDS:
        assert get_sentinel_value(field) is SENTINEL_DATETIME, (
            f"{field} sentinel should be SENTINEL_DATETIME"
        )

    for field in SENTINEL_INT_FIELDS:
        assert get_sentinel_value(field) == 0, f"{field} sentinel should be 0"

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

    for field in SENTINEL_INT_FIELDS:
        assert sentinel_ch_type(field) == "UInt64"

    for field in NON_SENTINEL_FIELDS:
        with pytest.raises(ValueError, match=f"Not a sentinel field: {field}"):
            sentinel_ch_type(field)


def test_sentinel_ch_literal() -> None:
    """Returns SQL literals for sentinel fields; raises for non-sentinel fields."""
    # String sentinel fields return empty string literal.
    assert sentinel_ch_literal("parent_id") == "''"
    for field in SENTINEL_STRING_FIELDS:
        assert sentinel_ch_literal(field) == "''"

    # Datetime sentinel fields return toDateTime64(0, N).
    assert sentinel_ch_literal("ended_at") == "toDateTime64(0, 6)"
    assert sentinel_ch_literal("updated_at") == "toDateTime64(0, 3)"
    assert sentinel_ch_literal("deleted_at") == "toDateTime64(0, 3)"

    # Int sentinel fields return 0.
    assert sentinel_ch_literal("wb_run_step") == "0"
    assert sentinel_ch_literal("wb_run_step_end") == "0"

    # Non-sentinel fields raise ValueError.
    for field in NON_SENTINEL_FIELDS:
        with pytest.raises(ValueError, match=f"Not a sentinel field: {field}"):
            sentinel_ch_literal(field)


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

    for field in SENTINEL_INT_FIELDS:
        assert to_ch_value(field, None) == 0
        assert to_ch_value(field, 42) == 42

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

    for field in SENTINEL_INT_FIELDS:
        assert from_ch_value(field, 0) is None
        assert from_ch_value(field, 42) == 42
        assert from_ch_value(field, 1) == 1

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

    # calls_complete: int sentinel field uses = sentinel param
    pb = ParamBuilder("pb")
    result = null_check_sql(
        "wb_run_step", "t.wb_run_step", ReadTable.CALLS_COMPLETE, pb
    )
    assert "=" in result
    assert "IS NULL" not in result
    assert "UInt64" in result

    # calls_merged: int sentinel fields still use IS NULL (nullable columns)
    pb = ParamBuilder("pb")
    result = null_check_sql("wb_run_step", "t.wb_run_step", ReadTable.CALLS_MERGED, pb)
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


def test_null_check_literal_sql() -> None:
    """Generates correct SQL using inline literals (no ParamBuilder) for all paths."""
    # calls_merged: sentinel fields use IS NULL (nullable columns).
    result = null_check_literal_sql("parent_id", "t.parent_id", ReadTable.CALLS_MERGED)
    assert result == "t.parent_id IS NULL"

    result = null_check_literal_sql(
        "parent_id", "t.parent_id", ReadTable.CALLS_MERGED, negate=True
    )
    assert result == "t.parent_id IS NOT NULL"

    # calls_complete sentinel string field: uses = '' or != ''.
    result = null_check_literal_sql(
        "parent_id", "t.parent_id", ReadTable.CALLS_COMPLETE
    )
    assert result == "t.parent_id = ''"

    result = null_check_literal_sql(
        "parent_id", "t.parent_id", ReadTable.CALLS_COMPLETE, negate=True
    )
    assert result == "t.parent_id != ''"

    # calls_complete sentinel datetime field: uses = toDateTime64(0, N) or !=.
    result = null_check_literal_sql("ended_at", "t.ended_at", ReadTable.CALLS_COMPLETE)
    assert result == "t.ended_at = toDateTime64(0, 6)"

    result = null_check_literal_sql(
        "ended_at", "t.ended_at", ReadTable.CALLS_COMPLETE, negate=True
    )
    assert result == "t.ended_at != toDateTime64(0, 6)"

    # calls_complete int sentinel field: uses = 0 or != 0.
    result = null_check_literal_sql(
        "wb_run_step", "t.wb_run_step", ReadTable.CALLS_COMPLETE
    )
    assert result == "t.wb_run_step = 0"

    result = null_check_literal_sql(
        "wb_run_step", "t.wb_run_step", ReadTable.CALLS_COMPLETE, negate=True
    )
    assert result == "t.wb_run_step != 0"

    # Non-sentinel field: always uses IS NULL regardless of table.
    result = null_check_literal_sql(
        "op_name", "t.op_name", ReadTable.CALLS_COMPLETE, negate=True
    )
    assert result == "t.op_name IS NOT NULL"
