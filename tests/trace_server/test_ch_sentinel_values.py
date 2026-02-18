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

# ---------------------------------------------------------------------------
# is_sentinel_field
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    list(SENTINEL_STRING_FIELDS) + list(SENTINEL_DATETIME_FIELDS),
)
def test_is_sentinel_field_returns_true_for_all_known_sentinel_fields(
    field: str,
) -> None:
    """All fields in SENTINEL_STRING_FIELDS and SENTINEL_DATETIME_FIELDS return True."""
    assert is_sentinel_field(field) is True


@pytest.mark.parametrize(
    "field",
    ["op_name", "id", "inputs_dump", "wb_run_step", "trace_id", "span_id", "foo"],
)
def test_is_sentinel_field_returns_false_for_non_sentinel_fields(
    field: str,
) -> None:
    """Non-sentinel fields return False."""
    assert is_sentinel_field(field) is False


# ---------------------------------------------------------------------------
# get_sentinel_value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", list(SENTINEL_STRING_FIELDS))
def test_get_sentinel_value_returns_empty_string_for_string_fields(
    field: str,
) -> None:
    """String sentinel fields return empty string as sentinel."""
    assert get_sentinel_value(field) == ""


@pytest.mark.parametrize("field", list(SENTINEL_DATETIME_FIELDS))
def test_get_sentinel_value_returns_sentinel_datetime_for_datetime_fields(
    field: str,
) -> None:
    """Datetime sentinel fields return SENTINEL_DATETIME."""
    assert get_sentinel_value(field) is SENTINEL_DATETIME


@pytest.mark.parametrize(
    "field",
    ["op_name", "id", "inputs_dump", "wb_run_step"],
)
def test_get_sentinel_value_returns_none_for_non_sentinel_fields(
    field: str,
) -> None:
    """Non-sentinel fields return None."""
    assert get_sentinel_value(field) is None


# ---------------------------------------------------------------------------
# sentinel_ch_type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", list(SENTINEL_STRING_FIELDS))
def test_sentinel_ch_type_returns_string_for_string_fields(field: str) -> None:
    """String sentinel fields return 'String' as ClickHouse type."""
    assert sentinel_ch_type(field) == "String"


@pytest.mark.parametrize(
    ("field", "expected_precision"),
    [
        ("ended_at", 6),
        ("updated_at", 3),
        ("deleted_at", 3),
    ],
)
def test_sentinel_ch_type_returns_datetime64_with_correct_precision(
    field: str,
    expected_precision: int,
) -> None:
    """Datetime sentinel fields return DateTime64(N) with correct precision."""
    assert sentinel_ch_type(field) == f"DateTime64({expected_precision})"


def test_sentinel_ch_type_datetime_precision_matches_module_constant() -> None:
    """DATETIME_PRECISION is the single source of truth for precision."""
    for field in SENTINEL_DATETIME_FIELDS:
        precision = DATETIME_PRECISION[field]
        assert sentinel_ch_type(field) == f"DateTime64({precision})"


@pytest.mark.parametrize(
    "field",
    ["op_name", "id", "wb_run_step", "trace_id"],
)
def test_sentinel_ch_type_raises_value_error_for_non_sentinel_fields(
    field: str,
) -> None:
    """Non-sentinel fields raise ValueError."""
    with pytest.raises(ValueError, match=f"Not a sentinel field: {field}"):
        sentinel_ch_type(field)


# ---------------------------------------------------------------------------
# sentinel_ch_literal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "expected_precision"),
    [
        ("ended_at", 6),
        ("updated_at", 3),
        ("deleted_at", 3),
    ],
)
def test_sentinel_ch_literal_returns_to_datetime64_with_correct_precision(
    field: str,
    expected_precision: int,
) -> None:
    """Datetime sentinel fields return toDateTime64(0, N) with correct precision."""
    assert sentinel_ch_literal(field) == f"toDateTime64(0, {expected_precision})"


@pytest.mark.parametrize(
    "field",
    ["parent_id", "display_name", "op_name", "wb_run_step"],
)
def test_sentinel_ch_literal_raises_value_error_for_non_datetime_fields(
    field: str,
) -> None:
    """Non-datetime sentinel fields raise ValueError (only datetime fields supported)."""
    with pytest.raises(ValueError, match=f"Not a sentinel datetime field: {field}"):
        sentinel_ch_literal(field)


# ---------------------------------------------------------------------------
# to_ch_value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", list(SENTINEL_STRING_FIELDS))
def test_to_ch_value_non_none_passes_through_for_string_sentinel_fields(
    field: str,
) -> None:
    """Non-None values pass through unchanged for string sentinel fields."""
    assert to_ch_value(field, "hello") == "hello"
    assert to_ch_value(field, "x") == "x"


@pytest.mark.parametrize("field", list(SENTINEL_DATETIME_FIELDS))
def test_to_ch_value_non_none_passes_through_for_datetime_sentinel_fields(
    field: str,
) -> None:
    """Non-None values pass through unchanged for datetime sentinel fields."""
    dt = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
    assert to_ch_value(field, dt) is dt


@pytest.mark.parametrize("field", list(SENTINEL_STRING_FIELDS))
def test_to_ch_value_none_becomes_empty_string_for_string_sentinel_fields(
    field: str,
) -> None:
    """None maps to empty string for string sentinel fields."""
    assert to_ch_value(field, None) == ""


@pytest.mark.parametrize("field", list(SENTINEL_DATETIME_FIELDS))
def test_to_ch_value_none_becomes_sentinel_datetime_for_datetime_sentinel_fields(
    field: str,
) -> None:
    """None maps to SENTINEL_DATETIME for datetime sentinel fields."""
    assert to_ch_value(field, None) is SENTINEL_DATETIME


@pytest.mark.parametrize("field", ["wb_run_step", "op_name", "id"])
def test_to_ch_value_none_stays_none_for_non_sentinel_fields(field: str) -> None:
    """None stays None for non-sentinel (nullable) fields."""
    assert to_ch_value(field, None) is None


@pytest.mark.parametrize("field", ["wb_run_step", "op_name", "id"])
def test_to_ch_value_non_none_passes_through_for_non_sentinel_fields(
    field: str,
) -> None:
    """Non-None values pass through unchanged for non-sentinel fields."""
    obj = {"foo": "bar"}
    assert to_ch_value(field, obj) is obj


# ---------------------------------------------------------------------------
# from_ch_value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", list(SENTINEL_STRING_FIELDS))
def test_from_ch_value_empty_string_becomes_none_for_string_sentinel_fields(
    field: str,
) -> None:
    """Empty string maps to None for string sentinel fields."""
    assert from_ch_value(field, "") is None


@pytest.mark.parametrize("field", list(SENTINEL_STRING_FIELDS))
def test_from_ch_value_non_empty_string_passes_through_for_string_sentinel_fields(
    field: str,
) -> None:
    """Non-empty strings pass through for string sentinel fields."""
    assert from_ch_value(field, "hello") == "hello"
    assert from_ch_value(field, "x") == "x"


@pytest.mark.parametrize("field", list(SENTINEL_DATETIME_FIELDS))
def test_from_ch_value_sentinel_datetime_becomes_none_for_datetime_sentinel_fields(
    field: str,
) -> None:
    """SENTINEL_DATETIME (with timezone) maps to None for datetime sentinel fields."""
    assert from_ch_value(field, SENTINEL_DATETIME) is None


@pytest.mark.parametrize("field", list(SENTINEL_DATETIME_FIELDS))
def test_from_ch_value_naive_datetime_at_epoch_zero_becomes_none(
    field: str,
) -> None:
    """Naive datetime at epoch zero maps to None (timezone-ignoring comparison)."""
    naive_epoch = datetime.datetime(1970, 1, 1)
    assert from_ch_value(field, naive_epoch) is None


@pytest.mark.parametrize("field", list(SENTINEL_DATETIME_FIELDS))
def test_from_ch_value_real_datetime_passes_through_for_datetime_sentinel_fields(
    field: str,
) -> None:
    """Real (non-sentinel) datetimes pass through for datetime sentinel fields."""
    dt = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
    assert from_ch_value(field, dt) is dt

    naive_dt = datetime.datetime(2024, 1, 15, 12, 0, 0)
    assert from_ch_value(field, naive_dt) is naive_dt


@pytest.mark.parametrize("field", list(SENTINEL_DATETIME_FIELDS))
def test_from_ch_value_none_stays_none_for_datetime_sentinel_fields(
    field: str,
) -> None:
    """None stays None for datetime sentinel fields (CH may return None during migration)."""
    assert from_ch_value(field, None) is None


@pytest.mark.parametrize("field", ["op_name", "id", "wb_run_step", "inputs_dump"])
def test_from_ch_value_non_sentinel_fields_pass_through_unchanged(
    field: str,
) -> None:
    """Non-sentinel fields pass through unchanged regardless of value."""
    assert from_ch_value(field, None) is None
    assert from_ch_value(field, "hello") == "hello"
    assert from_ch_value(field, 42) == 42
    obj = {"key": "val"}
    assert from_ch_value(field, obj) is obj


# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------


def test_all_sentinel_fields_union_of_string_and_datetime() -> None:
    """ALL_SENTINEL_FIELDS is the union of string and datetime sentinel fields."""
    assert ALL_SENTINEL_FIELDS == SENTINEL_STRING_FIELDS | SENTINEL_DATETIME_FIELDS


def test_sentinel_datetime_is_utc_epoch() -> None:
    """SENTINEL_DATETIME is 1970-01-01 00:00:00 UTC."""
    assert SENTINEL_DATETIME == datetime.datetime(
        1970, 1, 1, tzinfo=datetime.timezone.utc
    )


def test_sentinel_string_is_empty() -> None:
    """SENTINEL_STRING is empty string."""
    assert SENTINEL_STRING == ""


# ---------------------------------------------------------------------------
# null_check_sql
# ---------------------------------------------------------------------------


def test_null_check_sql_string_sentinel_field_calls_complete() -> None:
    """For calls_complete, string sentinel fields compare against empty-string param."""
    pb = ParamBuilder("pb")
    result = null_check_sql("parent_id", "t.parent_id", ReadTable.CALLS_COMPLETE, pb)
    assert "=" in result
    assert "IS NULL" not in result
    assert "String" in result


def test_null_check_sql_datetime_sentinel_field_calls_complete() -> None:
    """For calls_complete, datetime sentinel fields compare against epoch-zero param."""
    pb = ParamBuilder("pb")
    result = null_check_sql("ended_at", "t.ended_at", ReadTable.CALLS_COMPLETE, pb)
    assert "=" in result
    assert "IS NULL" not in result
    assert "DateTime64(6)" in result


def test_null_check_sql_sentinel_field_calls_merged() -> None:
    """For calls_merged, sentinel fields still use IS NULL (nullable columns)."""
    pb = ParamBuilder("pb")
    result = null_check_sql("parent_id", "t.parent_id", ReadTable.CALLS_MERGED, pb)
    assert result == "t.parent_id IS NULL"


def test_null_check_sql_non_sentinel_field_calls_complete() -> None:
    """For calls_complete, non-sentinel fields still use IS NULL."""
    pb = ParamBuilder("pb")
    result = null_check_sql(
        "wb_run_step", "t.wb_run_step", ReadTable.CALLS_COMPLETE, pb
    )
    assert result == "t.wb_run_step IS NULL"


def test_null_check_sql_negate_calls_complete() -> None:
    """Negated check for calls_complete sentinel field uses != sentinel."""
    pb = ParamBuilder("pb")
    result = null_check_sql(
        "wb_run_id", "t.wb_run_id", ReadTable.CALLS_COMPLETE, pb, negate=True
    )
    assert "!=" in result
    assert "IS NOT NULL" not in result


def test_null_check_sql_negate_calls_merged() -> None:
    """Negated check for calls_merged uses IS NOT NULL."""
    pb = ParamBuilder("pb")
    result = null_check_sql(
        "wb_run_id", "t.wb_run_id", ReadTable.CALLS_MERGED, pb, negate=True
    )
    assert result == "t.wb_run_id IS NOT NULL"


def test_null_check_sql_negate_non_sentinel_field() -> None:
    """Negated check for non-sentinel field always uses IS NOT NULL."""
    pb = ParamBuilder("pb")
    result = null_check_sql(
        "op_name", "t.op_name", ReadTable.CALLS_COMPLETE, pb, negate=True
    )
    assert result == "t.op_name IS NOT NULL"
