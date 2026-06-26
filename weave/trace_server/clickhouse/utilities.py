"""General-purpose helpers for the ClickHouse trace server.

Serialization, datetime conversion, parameter processing, and insert error
handling utilities shared across the CH trace server modules.
"""

import datetime
import hashlib
import json
import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, NamedTuple, TypeVar, cast

import ddtrace
import sqlparse
from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.exceptions import DatabaseError
from clickhouse_connect.driver.summary import QuerySummary

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.datadog import set_current_span_dd_tags
from weave.trace_server.errors import InsertTooLarge
from weave.trace_server.kafka import KafkaProducer

logger = logging.getLogger(__name__)

T = TypeVar("T")


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


def sanitize_invalid_utf8_surrogates(value: T) -> T:
    r"""Normalize malformed client Unicode before ClickHouse UTF-8 encoding.

    Python can deserialize JSON strings containing lone UTF-16 surrogate escapes
    such as "\\ud83d", but `clickhouse_connect` later rejects those strings when
    encoding column data as UTF-8. Decoding through UTF-16 preserves valid
    surrogate pairs as their real code point and replaces unpaired surrogates.
    """
    if isinstance(value, str):
        sanitized = value.encode("utf-16", errors="surrogatepass").decode(
            "utf-16", errors="replace"
        )
        return value if sanitized == value else cast(T, sanitized)
    if isinstance(value, list):
        for idx, item in enumerate(value):
            sanitized = sanitize_invalid_utf8_surrogates(item)
            if sanitized is not item:
                sanitized_items = [*value[:idx], sanitized]
                sanitized_items.extend(
                    sanitize_invalid_utf8_surrogates(rest) for rest in value[idx + 1 :]
                )
                return cast(T, sanitized_items)
        return value
    if isinstance(value, tuple):
        for idx, item in enumerate(value):
            sanitized = sanitize_invalid_utf8_surrogates(item)
            if sanitized is not item:
                return cast(
                    T,
                    (
                        *value[:idx],
                        sanitized,
                        *(
                            sanitize_invalid_utf8_surrogates(rest)
                            for rest in value[idx + 1 :]
                        ),
                    ),
                )
        return value
    if isinstance(value, dict):
        items = value.items()
        for idx, (key, val) in enumerate(items):
            sanitized_key = sanitize_invalid_utf8_surrogates(key)
            sanitized_val = sanitize_invalid_utf8_surrogates(val)
            if sanitized_key is not key or sanitized_val is not val:
                item_list = list(value.items())
                sanitized_items = [
                    *item_list[:idx],
                    (sanitized_key, sanitized_val),
                    *(
                        (
                            sanitize_invalid_utf8_surrogates(rest_key),
                            sanitize_invalid_utf8_surrogates(rest_val),
                        )
                        for rest_key, rest_val in item_list[idx + 1 :]
                    ),
                ]
                return cast(T, dict(sanitized_items))
        return value
    return value


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
# Migration SQL helpers
# ---------------------------------------------------------------------------


def split_migration_sql(sql: str) -> list[str]:
    """Split a ClickHouse migration SQL script into individual statements.

    A naive ``sql.split(";")`` breaks on ``;`` inside ``--`` line comments,
    ``/* ... */`` block comments, or single-quoted string literals — the
    migrator then sends a mid-comment fragment to ClickHouse and gets
    ``DB::Exception: Empty query. (SYNTAX_ERROR)``.

    Delegates to ``sqlparse`` (already a project dependency) for
    string/comment-aware splitting, then strips comments and empty
    statements from the result.
    """
    statements: list[str] = []
    for raw in sqlparse.split(sql, strip_semicolon=True):
        stripped = sqlparse.format(raw, strip_comments=True).strip()
        if stripped:
            statements.append(stripped)
    return statements


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


def started_at_gte_query(dt: datetime.datetime) -> tsi.Query:
    """A calls query selecting calls with started_at >= dt.

    The literal is unix seconds; the query builder converts it to a datetime
    string so ClickHouse can prune on the started_at primary key / partition.
    """
    return tsi.Query(
        **{
            "$expr": {
                "$gte": [
                    {"$getField": "started_at"},
                    {"$literal": datetime_to_microseconds(dt) / 1_000_000},
                ]
            }
        }
    )


class CallStartedAt(NamedTuple):
    """A call id paired with its started_at, the input to delete chunking."""

    id: str
    started_at: datetime.datetime


@dataclass(frozen=True)
class CallDeleteChunk:
    """Call ids batched for one windowed calls_complete delete.

    The ids share the inclusive [min_started_at, max_started_at] window, which
    brackets the partition/primary key so the DELETE prunes to a thin slice.
    """

    ids: list[str]
    min_started_at: datetime.datetime
    max_started_at: datetime.datetime


def chunk_calls_by_started_at(
    call_started_ats: list[CallStartedAt],
    chunk_size: int,
) -> list[CallDeleteChunk]:
    """Group calls into started_at-ordered chunks for windowed deletes.

    Sorting by started_at keeps each chunk's window tight, so the DELETE for a
    chunk prunes to a thin partition/primary-key slice instead of rescanning the
    full span on every batch.
    """
    ordered = sorted(call_started_ats, key=lambda c: c.started_at)
    chunks: list[CallDeleteChunk] = []
    for start in range(0, len(ordered), chunk_size):
        batch = ordered[start : start + chunk_size]
        ids = [c.id for c in batch]
        # batch is sorted by started_at, so the ends are the window bounds.
        chunks.append(CallDeleteChunk(ids, batch[0].started_at, batch[-1].started_at))
    return chunks


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


def insert_with_empty_query_retry(
    ch_client: CHClient,
    table: str,
    data: Sequence[Sequence[Any]],
    column_names: list[str],
    settings: dict[str, Any] | None = None,
) -> QuerySummary:
    """Insert rows, retrying ClickHouse "Empty query" errors with a fresh generator.

    The shared insert primitive: `_insert` and direct `ch_client.insert` callers
    (agent spans, ttl settings) all route through this so the empty-query retry
    lives in one place.
    """
    for attempt in range(ch_settings.INSERT_MAX_RETRIES):
        try:
            return ch_client.insert(
                table, data=data, column_names=column_names, settings=settings
            )
        except DatabaseError as e:
            if should_retry_empty_query(e, table, attempt):
                continue
            raise


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


# ---------------------------------------------------------------------------
# Kafka helpers
# ---------------------------------------------------------------------------


def maybe_enqueue_minimal_call_end(
    kafka_producer: KafkaProducer | None,
    project_id: str,
    id: str,
    ended_at: datetime.datetime,
    flush_immediately: bool = False,
) -> None:
    """Enqueue a minimal call end event to Kafka if online eval is enabled.

    This is used for online eval triggers where we only need the call identity,
    not the full payload. Large fields (output, summary, exception) are stripped.

    Args:
        kafka_producer: The Kafka producer to use.
        project_id: The project ID.
        id: The call ID.
        ended_at: The call end timestamp.
        flush_immediately: Whether to flush the producer immediately.
    """
    if kafka_producer is None:
        return

    minimal_end = tsi.EndedCallSchemaForInsert(
        project_id=project_id,
        id=id,
        ended_at=ended_at,
        output=None,
        summary={},
        exception=None,
    )
    kafka_producer.produce_call_end(minimal_end, flush_immediately)


# ---------------------------------------------------------------------------
# Call tree utilities
# ---------------------------------------------------------------------------


@ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.find_call_descendants")
def find_call_descendants(
    root_ids: list[str],
    all_calls: list[tsi.CallSchema],
) -> list[str]:
    set_current_span_dd_tags(
        {
            "clickhouse_trace_server_batched.find_call_descendants.root_ids_count": str(
                len(root_ids)
            ),
            "clickhouse_trace_server_batched.find_call_descendants.all_calls_count": str(
                len(all_calls)
            ),
        }
    )
    # make a map of call_id to children list
    children_map = defaultdict(list)
    for call in all_calls:
        if call.parent_id is not None:
            children_map[call.parent_id].append(call.id)

    # do DFS to get all descendants
    def find_all_descendants(root_ids: list[str]) -> set[str]:
        descendants = set()
        stack = root_ids

        while stack:
            current_id = stack.pop()
            if current_id not in descendants:
                descendants.add(current_id)
                stack += children_map.get(current_id, [])

        return descendants

    # Find descendants for each initial id
    descendants = find_all_descendants(root_ids)

    return list(descendants)
