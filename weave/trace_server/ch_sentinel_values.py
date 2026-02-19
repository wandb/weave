"""Sentinel values for non-nullable ClickHouse columns in calls_complete.

The calls_complete table uses non-nullable columns with sentinel defaults
instead of Nullable(T). This module provides conversion functions between
Python None values and their ClickHouse sentinel representations.

The app layer converts between Python None and sentinels at the CH boundary:
- On write (insert): None -> sentinel via to_ch_value()
- On read (query result): sentinel -> None via from_ch_value()
- On query (SQL generation): null_check_sql() generates the correct IS NULL
  or = sentinel comparison based on which table is being queried.

IMPORTANT: Never write raw ``IS NULL`` / ``IS NOT NULL`` checks on sentinel
fields in SQL query builders. Always use ``null_check_sql()`` from this module,
which generates the correct comparison for the active ``ReadTable``:
- calls_merged (nullable columns): ``field IS [NOT] NULL``
- calls_complete (sentinel columns): ``field [!]= <sentinel>``

Sentinel string fields: parent_id, display_name, exception, otel_dump,
    wb_user_id, wb_run_id, thread_id, turn_id  (sentinel = '')
Sentinel datetime fields: ended_at, updated_at, deleted_at
    (sentinel = epoch zero)
Sentinel int fields: wb_run_step, wb_run_step_end  (sentinel = 0)
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from weave.trace_server.project_version.types import ReadTable

if TYPE_CHECKING:
    from weave.trace_server.orm import ParamBuilder

SENTINEL_DATETIME = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
SENTINEL_STRING = ""
SENTINEL_INT = 0

SENTINEL_STRING_FIELDS = frozenset(
    {
        "parent_id",
        "display_name",
        "otel_dump",
        "exception",
        "wb_user_id",
        "wb_run_id",
        "thread_id",
        "turn_id",
    }
)

SENTINEL_DATETIME_FIELDS = frozenset(
    {
        "ended_at",
        "updated_at",
        "deleted_at",
    }
)

SENTINEL_INT_FIELDS = frozenset(
    {
        "wb_run_step",
        "wb_run_step_end",
    }
)

ALL_SENTINEL_FIELDS = (
    SENTINEL_STRING_FIELDS | SENTINEL_DATETIME_FIELDS | SENTINEL_INT_FIELDS
)

# Single source of truth for ClickHouse DateTime64 precision per column.
# Must match the column definitions in migration 024_calls_complete_v2.up.sql.
DATETIME_PRECISION: dict[str, int] = {
    "ended_at": 6,
    "updated_at": 3,
    "deleted_at": 3,
}


def is_sentinel_field(field: str) -> bool:
    """Check if a field uses sentinel values in calls_complete."""
    return field in ALL_SENTINEL_FIELDS


def sentinel_ch_type(field: str) -> str:
    """Return the ClickHouse type string for a sentinel field's parameterized slot.

    Args:
        field: The column name.

    Returns:
        ClickHouse type string, e.g. "String" or "DateTime64(6)".

    Raises:
        ValueError: If the field is not a sentinel field.

    Examples:
        >>> sentinel_ch_type("deleted_at")
        'DateTime64(3)'
        >>> sentinel_ch_type("exception")
        'String'
        >>> sentinel_ch_type("wb_run_step")
        'UInt64'
    """
    if field in SENTINEL_STRING_FIELDS:
        return "String"
    if field in SENTINEL_DATETIME_FIELDS:
        precision = DATETIME_PRECISION[field]
        return f"DateTime64({precision})"
    if field in SENTINEL_INT_FIELDS:
        return "UInt64"
    raise ValueError(f"Not a sentinel field: {field}")


def sentinel_ch_literal(field: str) -> str:
    """Return a raw SQL literal for a sentinel field's value.

    Useful in contexts where a parameterized slot is not available
    (e.g. stats_query_base, hardcoded SQL fragments).

    Args:
        field: The column name (must be a sentinel field).

    Returns:
        SQL expression: ``toDateTime64(0, N)`` for datetime fields, ``''`` for
        string fields.

    Raises:
        ValueError: If the field is not a sentinel field.

    Examples:
        >>> sentinel_ch_literal("deleted_at")
        'toDateTime64(0, 3)'
        >>> sentinel_ch_literal("parent_id")
        "''"
        >>> sentinel_ch_literal("wb_run_step")
        '0'
    """
    if field in SENTINEL_STRING_FIELDS:
        return "''"
    if field in SENTINEL_DATETIME_FIELDS:
        precision = DATETIME_PRECISION[field]
        return f"toDateTime64(0, {precision})"
    if field in SENTINEL_INT_FIELDS:
        return "0"
    raise ValueError(f"Not a sentinel field: {field}")


def null_check_literal_sql(
    field_name: str,
    field_sql: str,
    read_table: ReadTable,
    *,
    negate: bool = False,
) -> str:
    """Like ``null_check_sql`` but uses inline literals instead of parameters.

    Use this in contexts where a ``ParamBuilder`` is not available (e.g.
    ``build_grouped_calls_subquery``).

    Args:
        field_name: The column name (e.g. "deleted_at", "parent_id").
        field_sql: The fully-qualified SQL expression (e.g. "t.deleted_at").
        read_table: Which table variant is being queried.
        negate: If True, check for non-null/non-sentinel instead.

    Returns:
        A SQL fragment like ``t.deleted_at IS NULL`` or
        ``t.deleted_at = toDateTime64(0, 3)``.

    Examples:
        >>> null_check_literal_sql("deleted_at", "cm.deleted_at", ReadTable.CALLS_COMPLETE)
        "cm.deleted_at = toDateTime64(0, 3)"
        >>> null_check_literal_sql("parent_id", "t.parent_id", ReadTable.CALLS_MERGED)
        "t.parent_id IS NULL"
    """
    if read_table == ReadTable.CALLS_MERGED or field_name not in ALL_SENTINEL_FIELDS:
        return f"{field_sql} IS NOT NULL" if negate else f"{field_sql} IS NULL"

    literal = sentinel_ch_literal(field_name)
    op = "!=" if negate else "="
    return f"{field_sql} {op} {literal}"


def get_sentinel_value(field: str) -> str | datetime.datetime | int | None:
    """Return the sentinel value for a given field, or None if not a sentinel field."""
    if field in SENTINEL_STRING_FIELDS:
        return SENTINEL_STRING
    if field in SENTINEL_DATETIME_FIELDS:
        return SENTINEL_DATETIME
    if field in SENTINEL_INT_FIELDS:
        return SENTINEL_INT
    return None


def to_ch_value(field: str, value: Any) -> Any:
    """Convert Python None to the appropriate sentinel for CH insertion.

    Args:
        field: The column name.
        value: The Python value (may be None).

    Returns:
        The value to insert into ClickHouse. None values for sentinel fields
        are replaced with their sentinel; other values pass through unchanged.
    """
    if value is not None:
        return value
    if field in SENTINEL_STRING_FIELDS:
        return SENTINEL_STRING
    if field in SENTINEL_DATETIME_FIELDS:
        return SENTINEL_DATETIME
    if field in SENTINEL_INT_FIELDS:
        return SENTINEL_INT
    return value


def from_ch_value(field: str, value: Any) -> Any:
    """Convert a ClickHouse sentinel back to Python None.

    Args:
        field: The column name.
        value: The value read from ClickHouse.

    Returns:
        None if the value matches the sentinel for that field,
        otherwise the original value.
    """
    if field in SENTINEL_STRING_FIELDS:
        return None if value == SENTINEL_STRING else value
    if field in SENTINEL_DATETIME_FIELDS:
        if value is None:
            return None
        if isinstance(value, datetime.datetime):
            # Compare ignoring timezone: CH may return naive datetimes
            val_utc = value.replace(tzinfo=None)
            sentinel_utc = SENTINEL_DATETIME.replace(tzinfo=None)
            return None if val_utc == sentinel_utc else value
        return value
    if field in SENTINEL_INT_FIELDS:
        return None if value == SENTINEL_INT else value
    return value


def null_check_sql(
    field_name: str,
    field_sql: str,
    read_table: ReadTable,
    pb: ParamBuilder,
    *,
    negate: bool = False,
) -> str:
    """Generate SQL to check whether a field is null/sentinel, aware of table type.

    For calls_merged (nullable columns): produces ``field IS [NOT] NULL``.
    For calls_complete sentinel fields: produces ``field [!]= <sentinel_param>``.
    For calls_complete non-sentinel fields: produces ``field IS [NOT] NULL``.

    Args:
        field_name: The column name (e.g. "ended_at", "parent_id").
        field_sql: The fully-qualified SQL expression (e.g. "t.ended_at").
        read_table: Which table variant is being queried.
        pb: Parameter builder for adding parameterized sentinel values.
        negate: If True, check for non-null/non-sentinel instead.

    Returns:
        A SQL fragment like ``t.ended_at IS NULL`` or ``t.ended_at = {pb_N:DateTime64(6)}``.

    Examples:
        >>> null_check_sql("ended_at", "t.ended_at", ReadTable.CALLS_COMPLETE, pb)
        't.ended_at = {pb_0:DateTime64(6)}'
        >>> null_check_sql("ended_at", "t.ended_at", ReadTable.CALLS_MERGED, pb)
        't.ended_at IS NULL'
    """
    if read_table == ReadTable.CALLS_MERGED or field_name not in ALL_SENTINEL_FIELDS:
        return f"{field_sql} IS NOT NULL" if negate else f"{field_sql} IS NULL"

    sentinel = get_sentinel_value(field_name)
    ch_type = sentinel_ch_type(field_name)
    # Use pb.add() (non-deduplicating) so each sentinel field gets its own
    # parameter with the correct type annotation (handles diff Datetime precisions)
    sentinel_slot = pb.add(sentinel, param_type=ch_type)
    op = "!=" if negate else "="
    return f"{field_sql} {op} {sentinel_slot}"
