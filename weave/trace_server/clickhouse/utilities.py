"""General-purpose helpers for the ClickHouse trace server.

Serialization, datetime conversion, parameter processing, and insert error
handling utilities shared across the CH trace server modules.
"""

import datetime
import hashlib
import json
import logging
from collections.abc import Sequence
from typing import Any

from clickhouse_connect.driver.exceptions import DatabaseError

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server.errors import InsertTooLarge

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON serialization helpers
# ---------------------------------------------------------------------------


def num_bytes(data: Any) -> int:
    """Calculate the number of bytes in a string.

    This can be computationally expensive, only call when necessary.
    Never raise on a failed str cast, just return 0.
    """
    try:
        return len(str(data).encode("utf-8"))
    except Exception:
        return 0


def dict_value_to_dump(
    value: dict,
) -> str:
    if not isinstance(value, dict):
        raise TypeError(f"Value is not a dict: {value}")
    return json.dumps(value)


def any_value_to_dump(
    value: Any,
) -> str:
    return json.dumps(value)


def dict_dump_to_dict(val: str) -> dict[str, Any]:
    res = json.loads(val)
    if not isinstance(res, dict):
        raise TypeError(f"Value is not a dict: {val}")
    return res


def any_dump_to_any(val: str) -> Any:
    return json.loads(val)


def nullable_any_dump_to_any(
    val: str | None,
) -> Any | None:
    return any_dump_to_any(val) if val else None


# ---------------------------------------------------------------------------
# Datetime helpers
# ---------------------------------------------------------------------------


def ensure_datetimes_have_tz(
    dt: datetime.datetime | None = None,
) -> datetime.datetime | None:
    # https://github.com/ClickHouse/clickhouse-connect/issues/210
    # Clickhouse does not support timezone-aware datetimes. You can specify the
    # desired timezone at query time. However according to the issue above,
    # clickhouse will produce a timezone-naive datetime when the preferred
    # timezone is UTC. This is a problem because it does not match the ISO8601
    # standard as datetimes are to be interpreted locally unless specified
    # otherwise. This function ensures that the datetime has a timezone, and if
    # it does not, it adds the UTC timezone to correctly convey that the
    # datetime is in UTC for the caller.
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def ensure_datetimes_have_tz_strict(
    dt: datetime.datetime,
) -> datetime.datetime:
    res = ensure_datetimes_have_tz(dt)
    if res is None:
        raise ValueError(f"Datetime is None: {dt}")
    return res


def datetime_to_microseconds(dt: datetime.datetime) -> int:
    """Convert a datetime to microseconds since Unix epoch.

    This is needed for DateTime64(6) parameterized queries because
    clickhouse-connect truncates datetime objects to whole seconds
    when passing them as parameters. By converting to microseconds
    and using Int64 type, we preserve full precision.

    Args:
        dt: A datetime object (should be timezone-aware).

    Returns:
        int: Microseconds since Unix epoch (1970-01-01 00:00:00 UTC).

    Examples:
        >>> import datetime
        >>> dt = datetime.datetime(2026, 1, 14, 23, 15, 38, 704246, tzinfo=datetime.timezone.utc)
        >>> datetime_to_microseconds(dt)
        1768432538704246
    """
    # Ensure we have timezone info for accurate conversion
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    # Convert to microseconds: timestamp() gives seconds as float, multiply by 1M
    return int(dt.timestamp() * 1_000_000)


# ---------------------------------------------------------------------------
# ClickHouse query helpers
# ---------------------------------------------------------------------------


def process_parameters(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    # Special processing for datetimes! For some reason, the clickhouse connect
    # client truncates the datetime to the nearest second, so we need to convert
    # the datetime to a float which is then converted back to a datetime in the
    # clickhouse query
    parameters = parameters.copy()
    for key, value in parameters.items():
        if isinstance(value, datetime.datetime):
            parameters[key] = value.timestamp()
    return parameters


def string_to_int_in_range(input_string: str, range_max: int) -> int:
    """Convert a string to a deterministic integer within a specified range.

    Args:
        input_string: The string to convert to an integer
        range_max: The maximum allowed value (exclusive)

    Returns:
        int: A deterministic integer value between 0 and range_max
    """
    hash_obj = hashlib.md5(input_string.encode())
    hash_int = int(hash_obj.hexdigest(), 16)
    return hash_int % range_max


# ---------------------------------------------------------------------------
# Insert error helpers
# ---------------------------------------------------------------------------


def convert_to_insert_too_large(e: Exception) -> Exception:
    """Convert ValueError to InsertTooLarge if the error indicates data is too large."""
    if isinstance(e, ValueError) and "negative shift count" in str(e):
        return InsertTooLarge(
            "Database insertion failed. Record too large. "
            "A likely cause is that a single row or cell exceeded "
            "the limit. If logging images, save them as `Image.PIL`."
        )
    return e


def should_retry_empty_query(e: Exception, table: str, attempt: int) -> bool:
    """Check if we should retry an empty query error. Logs warning if retrying.

    Attempts to fix a longstanding "Empty query" error that intermittently
    occurs during ClickHouse inserts. This happens when clickhouse-connect's
    internal serialization generator gets exhausted during an HTTP connection
    retry (after CH Cloud's keep-alive timeout causes a connection reset).
    """
    is_empty_query = isinstance(e, DatabaseError) and "Empty query" in str(e)
    should_retry = is_empty_query and attempt < ch_settings.INSERT_MAX_RETRIES - 1
    if should_retry:
        logger.warning(
            "clickhouse_insert_empty_query_retry",
            extra={
                "table": table,
                "attempt": attempt + 1,
                "max_retries": ch_settings.INSERT_MAX_RETRIES,
            },
        )
    return should_retry


def log_and_raise_insert_error(
    e: Exception, table: str, data: Sequence[Sequence[Any]]
) -> None:
    """Log insert error with data size info and re-raise."""
    data_bytes = sum(num_bytes(row) for row in data)
    logger.exception(
        "clickhouse_insert_error",
        extra={
            "error_str": str(e),
            "table": table,
            "data_len": len(data),
            "data_bytes": data_bytes,
        },
    )
    raise e
