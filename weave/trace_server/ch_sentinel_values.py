"""Sentinel values for non-nullable ClickHouse columns in calls_complete.

The calls_complete table uses non-nullable columns with sentinel defaults
instead of Nullable(T). This module provides conversion functions between
Python None values and their ClickHouse sentinel representations.

The app layer converts between Python None and sentinels at the CH boundary:
- On write (insert): None -> sentinel via to_ch_value()
- On read (query result): sentinel -> None via from_ch_value()
"""

import datetime
from typing import Any

SENTINEL_DATETIME = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
SENTINEL_STRING = ""

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

ALL_SENTINEL_FIELDS = SENTINEL_STRING_FIELDS | SENTINEL_DATETIME_FIELDS

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
    """
    if field in SENTINEL_STRING_FIELDS:
        return "String"
    if field in SENTINEL_DATETIME_FIELDS:
        precision = DATETIME_PRECISION[field]
        return f"DateTime64({precision})"
    raise ValueError(f"Not a sentinel field: {field}")


def sentinel_ch_literal(field: str) -> str:
    """Return a raw SQL literal for the sentinel value of a datetime field.

    Useful in contexts where a parameterized slot is not available
    (e.g. stats_query_base, hardcoded SQL fragments).

    Args:
        field: The datetime column name.

    Returns:
        SQL expression like "toDateTime64(0, 3)".

    Raises:
        ValueError: If the field is not a sentinel datetime field.

    Examples:
        >>> sentinel_ch_literal("deleted_at")
        'toDateTime64(0, 3)'
    """
    if field not in SENTINEL_DATETIME_FIELDS:
        raise ValueError(f"Not a sentinel datetime field: {field}")
    precision = DATETIME_PRECISION[field]
    return f"toDateTime64(0, {precision})"


def get_sentinel_value(field: str) -> str | datetime.datetime | None:
    """Return the sentinel value for a given field, or None if not a sentinel field."""
    if field in SENTINEL_STRING_FIELDS:
        return SENTINEL_STRING
    if field in SENTINEL_DATETIME_FIELDS:
        return SENTINEL_DATETIME
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
    return value  # Nullable fields (wb_run_step, etc.) keep None


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
    return value
