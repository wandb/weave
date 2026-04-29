"""General-purpose helpers for the ClickHouse trace server.

Serialization, datetime conversion, parameter processing, and insert error
handling utilities shared across the CH trace server modules.
"""

import datetime
import hashlib
import json
import logging
import math
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, TypedDict

import ddtrace
import sqlparse
from clickhouse_connect.driver.exceptions import DatabaseError

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.datadog import set_current_span_dd_tags
from weave.trace_server.errors import InsertTooLarge
from weave.trace_server.kafka import KafkaProducer

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
# Typed inputs/output map extraction (fast-filter path)
# ---------------------------------------------------------------------------


# Skip strings longer than this many bytes when building the typed maps.
# Long strings (chat content, completion text, base64 blobs) are the bulk
# of inputs/output payloads and almost never make sense as exact-match
# filter targets — keep them out of the maps so column size stays small.
PAYLOAD_MAP_STRING_MAX_LEN = 256

# Hard cap on entries per row, summed across all four typed maps. Bounds
# the per-row map width so a pathological payload (deep config dict, very
# wide list-of-objects flattened by a future iteration, ...) can't blow
# up the column. Leaves past the cap fall back through JSON_VALUE.
PAYLOAD_MAP_MAX_ENTRIES = 200


def _flatten_payload(obj: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Walk a payload and emit ``(dot-joined-path, leaf-value)`` pairs.

    Only descends into dicts. Lists are intentionally skipped: list-index
    paths (``messages.0.role``, ``messages.1.role``, ...) explode the
    keyset across calls and quickly dominate column size for chat-style
    traces. Filters on list-index paths fall back to JSON_VALUE.

    Mirrors the dot-path convention already used by read-side filters
    (``inputs.usage.total_tokens``), so a caller filtering on that key
    hits the same map entry the extractor writes.
    """
    if not isinstance(obj, dict):
        return []
    result: list[tuple[str, Any]] = []
    for key, val in obj.items():
        full_key = key if not prefix else f"{prefix}.{key}"
        if isinstance(val, dict):
            result.extend(_flatten_payload(val, full_key))
        else:
            result.append((full_key, val))
    return result


class TypedInputsMaps(TypedDict):
    """Typed inputs maps keyed by their CH column name. Spread into a
    ``CallStartCHInsertable`` / ``CallCompleteCHInsertable`` constructor.
    """

    inputs_map_str: dict[str, str]
    inputs_map_int: dict[str, int]
    inputs_map_float: dict[str, float]
    inputs_map_bool: dict[str, bool]


class TypedOutputMaps(TypedDict):
    """Typed output maps keyed by their CH column name."""

    output_map_str: dict[str, str]
    output_map_int: dict[str, int]
    output_map_float: dict[str, float]
    output_map_bool: dict[str, bool]


def _extract_typed_payload_raw(
    payload: Any,
) -> tuple[dict[str, str], dict[str, int], dict[str, float], dict[str, bool]]:
    """Walk ``payload`` and route scalar leaves into four typed maps.

    Dispatch rules:

    - ``bool`` checked before ``int`` (Python ``bool`` subclasses ``int``).
    - Non-finite floats (NaN, +/-Inf) dropped — they don't round-trip
      through JSON/CH.
    - Strings longer than ``PAYLOAD_MAP_STRING_MAX_LEN`` bytes dropped.
    - Lists and other non-scalar leaves dropped entirely. List-index
      paths are filterable through the JSON_VALUE fallback and would
      otherwise duplicate large structured values into the string map.
    - Total entries capped at ``PAYLOAD_MAP_MAX_ENTRIES``; additional
      leaves are dropped, and the JSON_VALUE fallback still answers
      filters that target the dropped keys.

    Returns four bare dicts; ``extract_typed_inputs`` / ``extract_typed_output``
    wrap them with the column-prefixed keys insertables expect.
    """
    map_str: dict[str, str] = {}
    map_int: dict[str, int] = {}
    map_float: dict[str, float] = {}
    map_bool: dict[str, bool] = {}
    if not isinstance(payload, dict):
        return map_str, map_int, map_float, map_bool

    total = 0
    for key, val in _flatten_payload(payload):
        if total >= PAYLOAD_MAP_MAX_ENTRIES:
            break
        if val is None:
            continue
        if isinstance(val, bool):
            map_bool[key] = val
        elif isinstance(val, int):
            map_int[key] = val
        elif isinstance(val, float):
            if not math.isfinite(val):
                continue
            map_float[key] = val
        elif isinstance(val, str):
            if len(val) > PAYLOAD_MAP_STRING_MAX_LEN:
                continue
            map_str[key] = val
        else:
            # Non-scalar leaf (list, custom object, ...). Skip — JSON_VALUE
            # fallback can still answer filters against these keys, and we
            # don't want serialized lists/objects bloating the string map.
            continue
        total += 1

    return map_str, map_int, map_float, map_bool


def extract_typed_inputs(inputs: Any) -> TypedInputsMaps:
    """Build the inputs typed-map columns for one call. See
    ``_extract_typed_payload_raw`` for dispatch rules.
    """
    s, i, f, b = _extract_typed_payload_raw(inputs)
    return {
        "inputs_map_str": s,
        "inputs_map_int": i,
        "inputs_map_float": f,
        "inputs_map_bool": b,
    }


def extract_typed_output(output: Any) -> TypedOutputMaps:
    """Build the output typed-map columns for one call. See
    ``_extract_typed_payload_raw`` for dispatch rules.
    """
    s, i, f, b = _extract_typed_payload_raw(output)
    return {
        "output_map_str": s,
        "output_map_int": i,
        "output_map_float": f,
        "output_map_bool": b,
    }


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
