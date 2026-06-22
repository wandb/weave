# In-Memory ("fake") Trace Server
#
# A pure-Python, dict/list-backed implementation of the full trace server
# interface, intended as a fast drop-in replacement for the ClickHouse trace
# server in tests. It lives parallel to `clickhouse_trace_server_batched.py`.
#
# Behavioral contract: this server replicates the *ClickHouse* trace server
# (the production backend) at the interface level, so tests written against
# ClickHouse behavior pass unmodified. That includes ClickHouse's observable
# semantics: JSON_VALUE string typing for dynamic fields ('' for missing keys,
# JSON nulls, and non-scalars), to*OrNull cast rules, NULLS-LAST ordering with
# existence-first sorting for dynamic fields, DateTime64 column comparisons,
# and the computed summary fields (status/latency_ms/trace_name).
# ClickHouse *internals* (SQL, table routing/residence, batching, bucket file
# storage) are out of scope; tests asserting those are ClickHouse-gated.

import copy
import datetime
import json
import logging
import math
import re
import statistics
import threading
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from operator import attrgetter
from pathlib import Path
from typing import Any, cast

from clickhouse_connect.driver.exceptions import DatabaseError
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans

from weave.shared import refs_internal as ri
from weave.shared.digest import (
    compute_file_digest,
    compute_object_digest_result,
    compute_row_digest,
    compute_table_digest,
)
from weave.shared.trace_server_interface_util import (
    WILDCARD_ARTIFACT_VERSION_AND_PATH,
    assert_non_null_wb_user_id,
    extract_refs_from_values,
    split_exact_and_wildcard_values,
    wildcard_version_value_to_ref_prefix,
)
from weave.trace_server import constants, object_creation_utils, usage_utils
from weave.trace_server import eval_results_helpers as eval_helpers
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.completion_spans import build_completion_span
from weave.trace_server.agents.types import (
    AgentSpanSchema,
    AgentSpansQueryReq,
    AgentSpansQueryRes,
)
from weave.trace_server.call_stats_helpers import validate_call_stats_range
from weave.trace_server.calls_query_builder.stats_query_base import (
    GRANULARITY_1H,
    auto_select_granularity_seconds,
    ensure_max_buckets,
)
from weave.trace_server.ch_sentinel_values import EXPIRE_AT_NEVER, SENTINEL_EPOCH

# Completion request preparation (prompt resolution, provider/secret setup) is
# backend-agnostic business logic that currently lives in the ClickHouse
# module; import it rather than fork it.
from weave.trace_server.clickhouse_trace_server_batched import (
    CompletionPrepResult,
    _setup_completion_model_info,
)
from weave.trace_server.clickhouse_trace_server_settings import (
    MAX_DELETE_CALLS_COUNT,
)
from weave.trace_server.common_interface import SortBy
from weave.trace_server.digest_validation import validate_expected_digest
from weave.trace_server.errors import (
    InvalidFieldError,
    InvalidRequest,
    NotFoundError,
    ObjectDeletedError,
    ObjectNameTypeCollision,
    RequestTooLarge,
)
from weave.trace_server.feedback import (
    TABLE_FEEDBACK,
    format_feedback_to_res,
    format_feedback_to_row,
    process_feedback_payload,
    validate_feedback_create_req,
    validate_feedback_purge_req,
)
from weave.trace_server.feedback_payload_schema import discover_payload_schema
from weave.trace_server.ids import generate_id
from weave.trace_server.image_completion import lite_llm_image_generation
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.interface.feedback_types import (
    MULTI_VALUE_FEEDBACK_TYPES,
    RUNNABLE_FEEDBACK_TYPE_PREFIX,
)
from weave.trace_server.llm_completion import (
    lite_llm_completion,
    lite_llm_completion_stream,
    resolve_and_apply_prompt,
)
from weave.trace_server.methods.evaluation_status import evaluation_status
from weave.trace_server.model_providers.model_providers import (
    read_model_to_provider_info_map,
)
from weave.trace_server.opentelemetry.helpers import AttributePathConflictError
from weave.trace_server.opentelemetry.python_spans import Resource, Span
from weave.trace_server.orm import Table, split_escaped_field_path
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context
from weave.trace_server.token_costs import (
    DEFAULT_PRICING_LEVEL_ID,
    LLM_TOKEN_PRICES_TABLE,
    PRICING_LEVELS,
    validate_cost_purge_req,
)
from weave.trace_server.trace_server_common import (
    apply_tags_and_synth_latest_in_place,
    assert_parameter_length_less_than_max,
    determine_call_status,
    digest_is_content_hash,
    digest_is_version_like,
    empty_str_to_none,
    eval_run_refs_from_call,
    get_nested_key,
    get_prediction_inputs,
    hydrate_calls_with_feedback,
    make_derived_summary_fields,
    make_feedback_query_req,
    op_name_matches,
    scorer_read_res_from_obj,
    set_nested_key,
)
from weave.trace_server.trace_server_interface import (
    EvaluateModelArgs,
    RescoringArgs,
)
from weave.trace_server.ttl_settings import (
    RETENTION_DAYS_NO_TTL,
    compute_expire_at,
    invalidate_ttl_cache,
)
from weave.trace_server.validation import object_id_validator
from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
    EvaluateModelDispatcher,
)

logger = logging.getLogger(__name__)

MAX_REFS_BATCH_SIZE = 1000
MAX_OTEL_ERROR_MESSAGES = 20

_DEFAULT_COSTS_FILE = str(
    Path(__file__).parent / "migrations" / "006_seed_costs.up.sql"
)

# Top-level calls columns (mirrors ALLOWED_CALL_FIELDS in the ClickHouse
# query builder, with the *_dump suffixes normalized away).
_CALLS_PLAIN_COLUMNS = frozenset(
    {
        "id",
        "project_id",
        "trace_id",
        "parent_id",
        "thread_id",
        "turn_id",
        "op_name",
        "display_name",
        "started_at",
        "ended_at",
        "exception",
        "wb_user_id",
        "wb_run_id",
        "wb_run_step",
        "wb_run_step_end",
        "deleted_at",
        "expire_at",
        "input_refs",
        "output_refs",
    }
)

# Mirrors DISALLOWED_FILTERING_FIELDS / DATETIME_COLUMN_FIELDS in the
# ClickHouse calls query builder.
_DISALLOWED_FILTERING_FIELDS = frozenset(
    {"storage_size_bytes", "total_storage_size_bytes"}
)
_DATETIME_COLUMN_FIELDS = frozenset(
    {"started_at", "ended_at", "deleted_at", "expire_at"}
)
# Summary fields with computed handlers (anything else under summary.weave.
# raises InvalidFieldError, mirroring SUMMARY_FIELD_HANDLERS).
_SUMMARY_FIELD_HANDLERS = frozenset({"status", "latency_ms", "trace_name"})

# Integer-literal pattern for the ClickHouse toInt64OrNull mirror.
_CH_INT64_RE = re.compile(r"^[+-]?\d+$")


def _compile_call_column(column: str) -> Any:
    """Per-record getter for a plain calls column; unknown columns raise
    InvalidFieldError like the ClickHouse query builder.
    """
    if column not in _CALLS_PLAIN_COLUMNS:
        raise InvalidFieldError(f"Field {column} is not allowed")
    return attrgetter(column)


def _ensure_tz(dt: datetime.datetime) -> datetime.datetime:
    """Coerce a datetime to tz-aware UTC (naive datetimes are UTC wall time)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def _maybe_datetime_literal(value: Any) -> datetime.datetime | None:
    """Literal normalization for DateTime64 column comparisons.

    Mirrors _maybe_convert_datetime_operands: numeric unix timestamps and
    parseable date(time) strings convert; everything else returns None.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return datetime.datetime.fromtimestamp(float(value), tz=datetime.timezone.utc)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.endswith(("Z", "z")):
            s = s[:-1] + "+00:00"
        try:
            return _ensure_tz(datetime.datetime.fromisoformat(s))
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Generic JSON value helpers (dict-shaped doc traversal + stable ordering)
# ---------------------------------------------------------------------------


def _minify_json(val: Any) -> str:
    """JSON text with minified separators, as the backends store dumps."""
    return json.dumps(val, separators=(",", ":"))


def _json_extract(parsed: Any, path_parts: list[str] | None) -> tuple[Any, str | None]:
    """Dot-path traversal over a parsed JSON doc, with a type tag.

    Returns (value, json_type) where json_type is one of:
    'object', 'array', 'text', 'integer', 'real', 'true', 'false', 'null',
    or None when the path does not exist. Scalars convert to their stored
    renderings: true/false -> 1/0, objects/arrays -> minified JSON text.
    Used by the generic doc sorts (table rows) and ref expansion.
    """
    val = parsed
    for part in path_parts or []:
        if isinstance(val, dict):
            if part not in val:
                return (None, None)
            val = val[part]
        elif isinstance(val, list):
            try:
                idx = int(part)
            except ValueError:
                return (None, None)
            if idx < 0 or idx >= len(val):
                return (None, None)
            val = val[idx]
        else:
            return (None, None)

    if val is None:
        return (None, "null")
    if isinstance(val, bool):
        return (1, "true") if val else (0, "false")
    if isinstance(val, int):
        return (val, "integer")
    if isinstance(val, float):
        return (val, "real")
    if isinstance(val, str):
        return (val, "text")
    if isinstance(val, dict):
        return (_minify_json(val), "object")
    if isinstance(val, list):
        return (_minify_json(val), "array")
    # Unknown python type (shouldn't happen for JSON-derived data); treat as
    # its text rendering.
    return (str(val), "text")


def _ch_json_value(parsed: Any, path_parts: list[str] | None) -> str:
    """Mirror the ClickHouse dynamic-field read:
    coalesce(nullIf(JSON_VALUE(dump, path), 'null'), '').

    The trace server enables function_json_value_return_type_allow_complex,
    so objects/arrays render as minified JSON text. Missing paths and JSON
    nulls read as ''. Numbers are normalized (5.0 -> '5', 1e3 -> '1000'),
    booleans render as 'true'/'false', strings are unquoted.
    """
    val = parsed
    for part in path_parts or []:
        if isinstance(val, dict):
            if part not in val:
                return ""
            val = val[part]
        elif isinstance(val, list):
            try:
                idx = int(part)
            except ValueError:
                return ""
            if idx < 0 or idx >= len(val):
                return ""
            val = val[idx]
        else:
            return ""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, str):
        return val
    if isinstance(val, (dict, list)):
        return _minify_json(val)
    if isinstance(val, float) and val.is_integer() and not math.isinf(val):
        return str(int(val))
    return str(val)


def _ch_json_exists(parsed: Any, path_parts: list[str] | None) -> bool:
    """Mirror the builder's exists cast:
    NOT (JSONType(...) = 'Null' OR JSONType(...) IS NULL) — i.e. the path
    exists AND its value is not JSON null.
    """
    val = parsed
    for part in path_parts or []:
        if isinstance(val, dict):
            if part not in val:
                return False
            val = val[part]
        elif isinstance(val, list):
            try:
                idx = int(part)
            except ValueError:
                return False
            if idx < 0 or idx >= len(val):
                return False
            val = val[idx]
        else:
            return False
    return val is not None


def _ch_to_int64_or_null(value: Any) -> int | None:
    """ClickHouse toInt64OrNull over a string expression."""
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    if not _CH_INT64_RE.match(text):
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _ch_to_float64_or_null(value: Any) -> float | None:
    """ClickHouse toFloat64OrNull over a string expression."""
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _ch_to_uint8_or_null(value: Any) -> int | None:
    """ClickHouse toUInt8OrNull over a string expression."""
    parsed = _ch_to_int64_or_null(value)
    if parsed is None or parsed < 0 or parsed > 255:
        return None
    return parsed


def _ch_cast_json_value(value: str | None, cast_to: str | None) -> Any:
    """Mirror clickhouse_cast_json_value applied to a JSON_VALUE string."""
    if cast_to is None or cast_to == "string":
        return value
    if cast_to == "int":
        return _ch_to_int64_or_null(value)
    if cast_to in {"double", "float"}:
        return _ch_to_float64_or_null(value)
    if cast_to == "bool":
        if value == "true":
            return 1
        if value == "false":
            return 0
        return _ch_to_uint8_or_null(value)
    raise ValueError(f"Unknown cast: {cast_to}")


def _ch_to_string(value: Any) -> str | None:
    """ClickHouse toString over a scalar."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _ch_compare(lhs: Any, rhs: Any, op: str) -> bool | None:
    """Typed comparison with NULL propagation (ClickHouse semantics).

    Both sides arrive same-typed (the inferred-cast machinery aligns them);
    bools coerce to ints, ints/floats interoperate, datetimes compare
    temporally.
    """
    if lhs is None or rhs is None:
        return None
    if isinstance(lhs, bool):
        lhs = int(lhs)
    if isinstance(rhs, bool):
        rhs = int(rhs)
    if isinstance(lhs, datetime.datetime):
        lhs = _ensure_tz(lhs)
    if isinstance(rhs, datetime.datetime):
        rhs = _ensure_tz(rhs)
    # Cross-type numeric/string comparisons would be a CH type error; the
    # inferred casts prevent them for valid queries. Treat as no-match.
    lhs_numeric = isinstance(lhs, (int, float))
    rhs_numeric = isinstance(rhs, (int, float))
    if lhs_numeric != rhs_numeric:
        return None
    try:
        if op == "eq":
            return bool(lhs == rhs)
        if op == "gt":
            return bool(lhs > rhs)
        if op == "gte":
            return bool(lhs >= rhs)
        if op == "lt":
            return bool(lhs < rhs)
        if op == "lte":
            return bool(lhs <= rhs)
    except TypeError:
        return None
    raise ValueError(f"Unknown comparison op: {op}")


def _ch_position(haystack: Any, needle: Any, case_insensitive: bool) -> bool:
    """ClickHouse position()/positionCaseInsensitive() > 0 over strings."""
    if not isinstance(haystack, str) or not isinstance(needle, str):
        return False
    if case_insensitive:
        return needle.lower() in haystack.lower()
    return needle in haystack


def _ch_sorted_by_terms(
    rows: list[Any],
    terms: Sequence[tuple[Any, str]],
    value_fn: Any,
) -> list[Any]:
    """Sort rows by (term, direction) pairs with ClickHouse semantics:
    NULLs order last for both ASC and DESC. Applies stable sorts from the
    last term to the first.
    """
    result = list(rows)
    for term, direction in reversed(terms):
        reverse = direction.lower() == "desc"

        def value_of(row: Any, _term: Any = term) -> Any:
            value = value_fn(row, _term)
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, datetime.datetime):
                return _ensure_tz(value)
            return value

        # Two stable passes per term: order non-NULL values by direction,
        # then float NULLs to the end regardless of direction.
        result.sort(
            key=lambda row: _OrderableOrNone(value_of(row)),
            reverse=reverse,
        )
        result.sort(key=lambda row: value_of(row) is None)
    return result


class _OrderableOrNone:
    """Sort key wrapper: None never orders before or after anything (its
    final position is decided by the stable NULLs-last pass). Only used as
    a list.sort key, so only __lt__ is ever invoked.
    """

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value

    def __lt__(self, other: "_OrderableOrNone") -> bool:
        if self.value is None or other.value is None:
            return False
        try:
            return self.value < other.value
        except TypeError:
            return False


def _to_sql_text(value: Any) -> str | None:
    """Coerce a value to its stored text rendering (bools -> 1/0, floats
    keep a trailing .0, containers minify). Feeds the generic sorters and
    the ORM contains path, which only ever see strings in practice.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        if value == int(value) and not math.isinf(value) and not math.isnan(value):
            return f"{value:.1f}"
        return str(value)
    if isinstance(value, (int, str)):
        return str(value)
    return _minify_json(value)


def _value_rank(value: Any) -> int:
    # Legacy storage-class ranks (NULL < numeric < text), used by the
    # remaining generic sorters until they move to _ch_sorted_by_terms.
    if value is None:
        return 0
    if isinstance(value, (bool, int, float)):
        return 1
    return 2


def _truthy(value: Any) -> bool:
    """SQL WHERE-clause truthiness: NULL, 0, and false filter out."""
    return bool(value) if value is not None else False


def _sort_key_for_term(value: Any) -> tuple[int, Any]:
    rank = _value_rank(value)
    if rank == 1:  # numeric
        return (rank, float(int(value) if isinstance(value, bool) else value))
    if rank == 2:  # text
        return (rank, value)
    return (rank, 0)


def _sorted_by_terms(
    rows: list[Any],
    terms: list[tuple[Any, str]],
    value_fn: Any,
) -> list[Any]:
    """Sort rows by (term, direction) pairs with storage-class ordering
    (NULL < numeric < text). Used for object/table-row sorts, where the
    typed columns involved make this observably equivalent to ClickHouse
    ordering. Applies stable sorts from the last term to the first so
    earlier terms take precedence.
    """
    result = list(rows)
    for term, direction in reversed(terms):
        reverse = direction.lower() == "desc"
        result.sort(
            key=lambda row: _sort_key_for_term(value_fn(row, term)), reverse=reverse
        )
    return result


def _get_type(val: Any) -> str:
    if val is None:
        return "none"
    elif isinstance(val, dict):
        if "_type" in val:
            if "weave_type" in val:
                return val["weave_type"]["type"]
            return val["_type"]
        return "dict"
    elif isinstance(val, list):
        return "list"
    return "unknown"


def _get_kind(val: Any) -> str:
    val_type = _get_type(val)
    if val_type == "Op":
        return "op"
    return "object"


def _normalize_datetime_for_costs(
    value: datetime.datetime | str | None,
) -> datetime.datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.datetime.fromisoformat(value)
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def _serialize_cost_datetime(value: datetime.datetime) -> str:
    normalized = _normalize_datetime_for_costs(value)
    assert normalized is not None
    return normalized.isoformat()


def _safe_int_for_costs(value: Any) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _cost_usage_from_summary(
    summary: dict[str, Any] | None,
) -> dict[str, dict[str, int]]:
    usage_map = (summary or {}).get("usage")
    if not isinstance(usage_map, dict):
        return {}

    normalized_usage: dict[str, dict[str, int]] = {}
    for llm_id, usage in usage_map.items():
        if not isinstance(usage, dict):
            continue
        normalized_usage[str(llm_id)] = {
            "prompt_tokens": _safe_int_for_costs(usage.get("prompt_tokens"))
            + _safe_int_for_costs(usage.get("input_tokens")),
            "completion_tokens": _safe_int_for_costs(usage.get("completion_tokens"))
            + _safe_int_for_costs(usage.get("output_tokens")),
            "requests": _safe_int_for_costs(usage.get("requests")),
            # Match ClickHouse: keep total_tokens as-reported rather than deriving it.
            "total_tokens": _safe_int_for_costs(usage.get("total_tokens")),
            "cache_read_input_tokens": _safe_int_for_costs(
                usage.get("cache_read_input_tokens")
            ),
            "cache_creation_input_tokens": _safe_int_for_costs(
                usage.get("cache_creation_input_tokens")
            ),
        }
    return normalized_usage


@lru_cache(maxsize=1)
def _load_default_cost_definitions() -> tuple[dict[str, Any], ...]:
    with open(_DEFAULT_COSTS_FILE, encoding="utf-8") as f:
        seed_sql = f.read()

    now = _serialize_cost_datetime(datetime.datetime.now(datetime.timezone.utc))
    default_rows: list[dict[str, Any]] = []
    row_pattern = re.compile(
        r"\(generateUUIDv4\(\), '([^']+)', '([^']+)', '([^']+)', '([^']+)', now\(\), ([^,]+), '([^']+)', ([^,]+), '([^']+)', '([^']+)', now\(\)\)"
    )
    for match in row_pattern.finditer(seed_sql):
        (
            pricing_level,
            pricing_level_id,
            provider_id,
            llm_id,
            prompt_token_cost,
            prompt_token_cost_unit,
            completion_token_cost,
            completion_token_cost_unit,
            created_by,
        ) = match.groups()
        default_rows.append(
            {
                "pricing_level": pricing_level,
                "pricing_level_id": pricing_level_id,
                "provider_id": provider_id,
                "llm_id": llm_id,
                "effective_date": now,
                "prompt_token_cost": float(prompt_token_cost),
                "completion_token_cost": float(completion_token_cost),
                "prompt_token_cost_unit": prompt_token_cost_unit,
                "completion_token_cost_unit": completion_token_cost_unit,
                "created_by": created_by,
                "created_at": now,
            }
        )
    return tuple(default_rows)


def _apply_aggregations(
    bucket: dict[str, Any],
    metric: str,
    values: list[float] | list[int],
    aggregations: list[tsi.AggregationType],
    percentiles: list[float] | None = None,
) -> None:
    """Apply aggregation functions and percentiles to a list of values, writing results into bucket."""
    for agg in aggregations:
        if agg == tsi.AggregationType.SUM:
            bucket[f"sum_{metric}"] = sum(values)
        elif agg == tsi.AggregationType.AVG:
            bucket[f"avg_{metric}"] = sum(values) / len(values) if values else 0
        elif agg == tsi.AggregationType.MIN:
            bucket[f"min_{metric}"] = min(values) if values else 0
        elif agg == tsi.AggregationType.MAX:
            bucket[f"max_{metric}"] = max(values) if values else 0
        elif agg == tsi.AggregationType.COUNT:
            bucket[f"count_{metric}"] = len(values)
    if percentiles:
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        for p in percentiles:
            idx = int(p / 100 * (n - 1))
            idx = max(0, min(idx, n - 1))
            bucket[f"p{int(p)}_{metric}"] = sorted_vals[idx]


@lru_cache(maxsize=1)
def _model_to_provider_info_map() -> dict[str, Any]:
    """Provider info for known model names, loaded once (it is static file
    data; ClickHouse loads it per server instance in __init__).
    """
    return read_model_to_provider_info_map()


def _aggregate_stream_chunks(
    chunks: list[dict[str, Any]], model_name: str
) -> dict[str, Any]:
    """Assemble streamed completion chunks into a chat.completion response
    (compact mirror of the ClickHouse stream wrapper's accumulation).
    """
    contents: dict[int, list[str]] = {}
    finish_reasons: dict[int, Any] = {}
    roles: dict[int, str] = {}
    metadata: dict[str, Any] = {}
    usage: dict[str, Any] | None = None
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        for key in ("id", "created", "model", "system_fingerprint"):
            if key not in metadata and chunk.get(key) is not None:
                metadata[key] = chunk[key]
        if chunk.get("usage"):
            usage = chunk["usage"]
        for choice in chunk.get("choices") or []:
            idx = choice.get("index", 0)
            delta = choice.get("delta") or {}
            if delta.get("role"):
                roles[idx] = delta["role"]
            if delta.get("content"):
                contents.setdefault(idx, []).append(delta["content"])
            if choice.get("finish_reason"):
                finish_reasons[idx] = choice["finish_reason"]
    choices = [
        {
            "index": idx,
            "message": {
                "role": roles.get(idx, "assistant"),
                "content": "".join(contents.get(idx, [])),
            },
            "finish_reason": finish_reasons.get(idx),
        }
        for idx in sorted(set(contents) | set(finish_reasons) | {0})
    ]
    response: dict[str, Any] = {
        "id": metadata.get("id", ""),
        "object": "chat.completion",
        "created": metadata.get("created", 0),
        "model": model_name,
        "choices": choices,
    }
    if metadata.get("system_fingerprint") is not None:
        response["system_fingerprint"] = metadata["system_fingerprint"]
    if usage is not None:
        response["usage"] = usage
    return response


# Agent-monitor scores land under this scorer_ratings key; the feedback
# aggregate rating filter targets it (mirrors feedback_agg_query_builder).
_FEEDBACK_RATING_KEY = "_rating_"


def _ref_object_id(ref: str | None) -> str:
    """A ref's object id: the last path segment's name, before any ':digest'
    (the splitByChar expression in the aggregate query builder).
    """
    return (ref or "").split("/")[-1].split(":")[0]


def _object_id_matches(ref: str | None, values: list[str]) -> bool:
    """Exact object-id match by default; a trailing '*' opts into prefix."""
    object_id = _ref_object_id(ref)
    for value in values:
        if value.endswith("*"):
            if object_id.startswith(value.rstrip("*")):
                return True
        elif object_id == value:
            return True
    return False


def _feedback_aggregate_dimension(row: dict[str, Any], dimension: str) -> Any:
    """A row's value for a client-facing group_by dimension. `scorer_id` is
    derived from runnable_ref; every other dimension is a stored column.
    """
    if dimension == "scorer_id":
        return _ref_object_id(row.get("runnable_ref"))
    return row.get(dimension)


def _feedback_aggregate_matches(
    row: dict[str, Any], req: tsi.FeedbackAggregateReq
) -> bool:
    """The WHERE clause of build_feedback_aggregate_query, row at a time."""
    if row["project_id"] != req.project_id:
        return False
    created_ms = row["created_at"].timestamp() * 1000
    if not (req.after_ms <= created_ms < req.before_ms):
        return False
    if req.feedback_types and not any(
        (row.get("feedback_type") or "").startswith(value.rstrip("*"))
        for value in req.feedback_types
    ):
        return False
    if req.monitor_ids and not _object_id_matches(
        row.get("trigger_ref"), req.monitor_ids
    ):
        return False
    if req.scorer_ids and not _object_id_matches(
        row.get("runnable_ref"), req.scorer_ids
    ):
        return False
    if req.span_agent_names and row.get("span_agent_name") not in req.span_agent_names:
        return False
    if req.span_types:
        # The span type is the weave_ref's second-to-last path segment.
        segments = (row.get("weave_ref") or "").split("/")
        span_type = segments[-2] if len(segments) >= 2 else ""
        if span_type not in req.span_types:
            return False
    if req.tags:
        row_tags = row.get("scorer_tags") or []
        if not any(tag in row_tags for tag in req.tags):
            return False
    if req.rating_min is not None or req.rating_max is not None:
        ratings = row.get("scorer_ratings") or {}
        if _FEEDBACK_RATING_KEY not in ratings:
            return False
        rating = ratings[_FEEDBACK_RATING_KEY]
        if req.rating_min is not None and not (rating >= req.rating_min):
            return False
        if req.rating_max is not None and not (rating <= req.rating_max):
            return False
    return True


def _interpolated_quantile(durations: list[float], level: float) -> float | None:
    """Interpolated quantile over a sorted list (ClickHouse `quantile()`)."""
    if not durations:
        return None
    k = level * (len(durations) - 1)
    f = int(k)
    c = f + 1
    if c >= len(durations):
        return durations[-1]
    return durations[f] + (k - f) * (durations[c] - durations[f])


@dataclass(slots=True)
class _CallRec:
    project_id: str
    id: str
    trace_id: str | None
    parent_id: str | None
    thread_id: str | None
    turn_id: str | None
    op_name: str | None
    display_name: str | None
    started_at: datetime.datetime | None
    attributes: Any
    inputs: Any
    input_refs: list[str]
    wb_user_id: str | None
    wb_run_id: str | None
    wb_run_step: int | None
    otel_dump: Any
    expire_at: datetime.datetime
    attributes_len: int | None = None
    inputs_len: int | None = None
    output_len: int | None = None
    summary_len: int | None = None
    otel_dump_len: int | None = None
    ended_at: datetime.datetime | None = None
    exception: str | None = None
    output: Any = None
    output_refs: list[str] = field(default_factory=list)
    summary: Any = None
    wb_run_step_end: int | None = None
    deleted_at: datetime.datetime | None = None
    storage_size_bytes: int | None = None


@dataclass(slots=True)
class _ObjRec:
    project_id: str
    object_id: str
    created_at: datetime.datetime
    kind: str
    base_object_class: str | None
    leaf_object_class: str | None
    val: Any
    digest: str
    version_index: int
    is_latest: int
    wb_user_id: str | None
    val_dump_len: int = 0
    deleted_at: datetime.datetime | None = None


@dataclass(slots=True)
class _TableRowRec:
    project_id: str
    val: Any
    val_dump_len: int = 0


@dataclass(slots=True)
class _AliasRec:
    digest: str
    created_at: datetime.datetime


@dataclass(slots=True)
class _TtlRec:
    project_id: str
    retention_days: int
    updated_at: datetime.datetime
    updated_by: str


# The value domain the evaluator produces and compares: query literals plus the
# scalars ClickHouse's JSON_VALUE casting yields (a subset of these). Mirrors
# ``LiteralOperation.literal_``; the _ch_* comparison helpers treat it dynamically.
_FilterValue = (
    str
    | int
    | float
    | bool
    | dict[str, tsi_query.LiteralOperation]
    | list[tsi_query.LiteralOperation]
    | None
)


class _QueryFilterEvaluator:
    """Evaluate a ``tsi.Query`` filter expression against a single row.

    Mirrors ClickHouse filter semantics in pure Python. The only row-specific
    piece is ``resolve``, which maps a ``(field_path, cast)`` pair to the row's
    value; everything else (operand evaluation, comparison, boolean recursion)
    is identical across query sites, so it lives here once instead of being
    re-implemented as nested closures inside each query method.
    """

    def __init__(
        self, resolve: Callable[[str, tsi_query.CastTo | None], _FilterValue]
    ) -> None:
        self._resolve = resolve

    def matches(self, query: tsi.Query) -> bool:
        """The row matches when the query's top-level expression is truthy."""
        return _truthy(self._evaluate(query.expr_))

    def _operand_value(
        self, operand: tsi_query.Operand, cast: tsi_query.CastTo | None = None
    ) -> _FilterValue:
        """Resolve an operand (an expression leaf) to a concrete value: a literal,
        a field reference (looked up via the row resolver), a type cast, or a
        nested boolean operation (handed back to _evaluate).
        """
        if isinstance(operand, tsi_query.LiteralOperation):
            return operand.literal_
        if isinstance(operand, tsi_query.GetFieldOperator):
            return self._resolve(operand.get_field_, cast)
        if isinstance(operand, tsi_query.ConvertOperation):
            inner = self._operand_value(operand.convert_.input)
            if operand.convert_.to == "exists":
                return inner is not None
            return _ch_cast_json_value(_ch_to_string(inner), operand.convert_.to)
        return self._evaluate(operand)

    def _binary(
        self, lhs: tsi_query.Operand, rhs: tsi_query.Operand, op: str
    ) -> bool | None:
        """Compare two operands. ClickHouse infers a field's cast from the literal
        it is compared against, so mirror that for each side before comparing.
        """
        lhs_cast = (
            tsi_query.infer_literal_filter_cast(rhs)
            if isinstance(rhs, tsi_query.LiteralOperation)
            else None
        )
        rhs_cast = (
            tsi_query.infer_literal_filter_cast(lhs)
            if isinstance(lhs, tsi_query.LiteralOperation)
            else None
        )
        return _ch_compare(
            self._operand_value(lhs, lhs_cast),
            self._operand_value(rhs, rhs_cast),
            op,
        )

    def _evaluate(self, operation: tsi_query.Operation) -> bool | None:
        """Recursively evaluate an operation node: boolean ops (and/or/not) combine
        their sub-expressions; comparison ops (eq/gt/lt/in/contains/...) compare
        resolved operand values.
        """
        if isinstance(operation, tsi_query.AndOperation):
            return all(_truthy(self._evaluate_operand(op)) for op in operation.and_)
        if isinstance(operation, tsi_query.OrOperation):
            return any(_truthy(self._evaluate_operand(op)) for op in operation.or_)
        if isinstance(operation, tsi_query.NotOperation):
            inner = self._evaluate_operand(operation.not_[0])
            return None if inner is None else not _truthy(inner)
        if isinstance(operation, tsi_query.EqOperation):
            return self._binary(operation.eq_[0], operation.eq_[1], "eq")
        if isinstance(operation, tsi_query.GtOperation):
            return self._binary(operation.gt_[0], operation.gt_[1], "gt")
        if isinstance(operation, tsi_query.GteOperation):
            return self._binary(operation.gte_[0], operation.gte_[1], "gte")
        if isinstance(operation, tsi_query.LtOperation):
            return self._binary(operation.lt_[0], operation.lt_[1], "lt")
        if isinstance(operation, tsi_query.LteOperation):
            return self._binary(operation.lte_[0], operation.lte_[1], "lte")
        if isinstance(operation, tsi_query.InOperation):
            lhs = self._operand_value(operation.in_[0])
            if lhs is None:
                return None
            return any(
                _truthy(_ch_compare(lhs, self._operand_value(op), "eq"))
                for op in operation.in_[1]
            )
        if isinstance(operation, tsi_query.ContainsOperation):
            return _ch_position(
                self._operand_value(operation.contains_.input),
                self._operand_value(operation.contains_.substr),
                bool(operation.contains_.case_insensitive),
            )
        raise TypeError(f"Unknown operation type: {operation}")

    def _evaluate_operand(self, operand: tsi_query.Operand) -> _FilterValue:
        """Dispatch a sub-node: leaf operands resolve to a value, nested boolean or
        comparison operations recurse back into _evaluate.
        """
        if isinstance(
            operand,
            (
                tsi_query.LiteralOperation,
                tsi_query.GetFieldOperator,
                tsi_query.ConvertOperation,
            ),
        ):
            return self._operand_value(operand)
        return self._evaluate(operand)


class InMemoryTraceServer(tsi.FullTraceServerInterface):
    """Pure in-memory trace server for tests, replicating ClickHouse semantics."""

    def __init__(
        self,
        evaluate_model_dispatcher: EvaluateModelDispatcher | None = None,
    ):
        self.lock = threading.RLock()
        self._evaluate_model_dispatcher = evaluate_model_dispatcher
        self._init_storage()

    def _init_storage(self) -> None:
        # Calls keyed by (project_id, id), mirroring ClickHouse's scoping
        # of calls by project.
        self._calls: dict[tuple[str, str], _CallRec] = {}
        # Objects keyed by (project_id, kind, object_id, digest), insertion
        # ordered (rowid order matters for version_index and tie-breaks).
        self._objs: dict[tuple[str, str, str, str], _ObjRec] = {}
        # Tables keyed by (project_id, digest) -> ordered row digests.
        self._tables: dict[tuple[str, str], list[str]] = {}
        # Table rows keyed by (project_id, digest), matching ClickHouse's
        # project-scoped table_rows primary key.
        self._table_rows: dict[tuple[str, str], _TableRowRec] = {}
        # Files keyed by (project_id, digest).
        self._files: dict[tuple[str, str], bytes] = {}
        # Tags keyed by (project_id, object_id, digest) -> set of tags.
        self._tags: dict[tuple[str, str, str], set[str]] = {}
        # Aliases keyed by (project_id, object_id, alias) -> digest record.
        self._aliases: dict[tuple[str, str, str], _AliasRec] = {}
        # Feedback rows: stored in the post-insert read shape (see
        # _feedback_row_for_storage), insertion ordered.
        self._feedback: list[dict[str, Any]] = []
        # LLM token price rows (plain dicts mirroring the table columns).
        self._llm_token_prices: list[dict[str, Any]] = []
        # Project TTL settings, append-only audit rows.
        self._ttl_settings: list[_TtlRec] = []
        # Annotation queues / items / per-annotator progress (one mutable
        # record per id, soft-deleted via deleted_at — mirrors the ClickHouse
        # lightweight-update model).
        self._annotation_queues: dict[str, dict[str, Any]] = {}
        self._annotation_queue_items: dict[str, dict[str, Any]] = {}
        self._annotation_progress: dict[str, dict[str, Any]] = {}
        # Agent spans keyed by span_id (ReplacingMergeTree semantics: a
        # re-insert with the same span_id replaces the row).
        self._agent_spans: dict[str, Any] = {}

    def close(self) -> None:
        pass

    def drop_tables(self) -> None:
        self._init_storage()

    def setup_tables(self) -> None:
        pass

    # ------------------------------------------------------------------
    # TTL helpers
    # ------------------------------------------------------------------

    def _get_project_retention_days(self, project_id: str) -> int:
        """Return retention_days for a project (RETENTION_DAYS_NO_TTL = no TTL)."""
        with self.lock:
            rows = [r for r in self._ttl_settings if r.project_id == project_id]
        if not rows:
            return RETENTION_DAYS_NO_TTL
        # ORDER BY updated_at DESC, rowid DESC LIMIT 1: rows is in rowid
        # order, so take the max updated_at preferring the later row.
        best = rows[0]
        for row in rows[1:]:
            if row.updated_at >= best.updated_at:
                best = row
        return int(best.retention_days)

    def _compute_call_expire_at(
        self, project_id: str, anchor: datetime.datetime
    ) -> datetime.datetime:
        retention_days = self._get_project_retention_days(project_id)
        expire_at = compute_expire_at(retention_days, anchor)
        if expire_at is None:
            return EXPIRE_AT_NEVER
        return _ensure_tz(expire_at)

    # ------------------------------------------------------------------
    # Call write path
    # ------------------------------------------------------------------

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        res = []
        for item in req.batch:
            if item.mode == "start":
                res.append(self.call_start(item.req))
            elif item.mode == "end":
                res.append(self.call_end(item.req))
            else:
                raise ValueError("Invalid mode")
        return tsi.CallCreateBatchRes(res=res)

    def calls_complete(
        self, req: tsi.CallsUpsertCompleteReq
    ) -> tsi.CallsUpsertCompleteRes:
        with self.lock:
            for call in req.batch:
                parsable_output = call.output
                if not isinstance(parsable_output, dict):
                    parsable_output = {"output": parsable_output}
                parsable_output = cast(dict, parsable_output)

                attributes_json = json.dumps(call.attributes)
                inputs_json = json.dumps(call.inputs)
                output_json = json.dumps(call.output)
                summary_json = json.dumps(call.summary)
                storage_size = (
                    len(attributes_json)
                    + len(inputs_json)
                    + len(output_json)
                    + len(summary_json)
                )

                expire_at = self._compute_call_expire_at(
                    call.project_id, call.started_at
                )

                rec = _CallRec(
                    project_id=call.project_id,
                    id=call.id,
                    trace_id=call.trace_id,
                    parent_id=call.parent_id,
                    thread_id=call.thread_id,
                    turn_id=call.turn_id,
                    op_name=call.op_name,
                    display_name=call.display_name,
                    started_at=_ensure_tz(call.started_at),
                    ended_at=_ensure_tz(call.ended_at),
                    exception=call.exception,
                    attributes=json.loads(attributes_json),
                    inputs=json.loads(inputs_json),
                    input_refs=extract_refs_from_values(list(call.inputs.values())),
                    output=json.loads(output_json),
                    output_refs=extract_refs_from_values(
                        list(parsable_output.values())
                    ),
                    summary=json.loads(summary_json),
                    wb_user_id=call.wb_user_id,
                    wb_run_id=call.wb_run_id,
                    wb_run_step=call.wb_run_step,
                    wb_run_step_end=call.wb_run_step_end,
                    otel_dump=copy.deepcopy(call.otel_dump),
                    otel_dump_len=(
                        len(json.dumps(call.otel_dump))
                        if call.otel_dump is not None
                        else None
                    ),
                    storage_size_bytes=storage_size,
                    expire_at=expire_at,
                    attributes_len=len(attributes_json),
                    inputs_len=len(inputs_json),
                    output_len=len(output_json),
                    summary_len=len(summary_json),
                )
                self._calls[rec.project_id, rec.id] = rec
        return tsi.CallsUpsertCompleteRes()

    def call_start_v2(self, req: tsi.CallStartV2Req) -> tsi.CallStartV2Res:
        res = self.call_start(tsi.CallStartReq(start=req.start))
        return tsi.CallStartV2Res(id=res.id, trace_id=res.trace_id)

    def call_end_v2(self, req: tsi.CallEndV2Req) -> tsi.CallEndV2Res:
        with self.lock:
            existing = self._calls.get((req.end.project_id, req.end.id))
            if existing is None or existing.started_at is None:
                raise NotFoundError(
                    f"Cannot end call {req.end.id}: no start found in project "
                    f"{req.end.project_id}"
                )

        self.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=req.end.project_id,
                    id=req.end.id,
                    ended_at=req.end.ended_at,
                    exception=req.end.exception,
                    output=req.end.output,
                    summary=req.end.summary,
                    wb_run_step_end=req.end.wb_run_step_end,
                )
            )
        )
        return tsi.CallEndV2Res()

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        if req.start.trace_id is None:
            raise ValueError("trace_id is required")
        if req.start.id is None:
            raise ValueError("id is required")
        with self.lock:
            attributes_json = json.dumps(req.start.attributes)
            inputs_json = json.dumps(req.start.inputs)
            expire_at = self._compute_call_expire_at(
                req.start.project_id, req.start.started_at
            )
            existing = self._calls.get((req.start.project_id, req.start.id))
            if existing is not None:
                # An end part arrived first (ClickHouse merges call parts in
                # any order); fill in the start-side columns.
                existing.trace_id = req.start.trace_id
                existing.parent_id = req.start.parent_id
                existing.thread_id = req.start.thread_id
                existing.turn_id = req.start.turn_id
                existing.op_name = req.start.op_name
                existing.display_name = req.start.display_name
                existing.started_at = _ensure_tz(req.start.started_at)
                existing.attributes = json.loads(attributes_json)
                existing.inputs = json.loads(inputs_json)
                existing.input_refs = extract_refs_from_values(
                    list(req.start.inputs.values())
                )
                existing.wb_user_id = req.start.wb_user_id
                existing.wb_run_id = req.start.wb_run_id
                existing.wb_run_step = req.start.wb_run_step
                existing.otel_dump = copy.deepcopy(req.start.otel_dump)
                existing.otel_dump_len = (
                    len(json.dumps(req.start.otel_dump))
                    if req.start.otel_dump is not None
                    else None
                )
                existing.expire_at = expire_at
                existing.attributes_len = len(attributes_json)
                existing.inputs_len = len(inputs_json)
            else:
                rec = _CallRec(
                    project_id=req.start.project_id,
                    id=req.start.id,
                    trace_id=req.start.trace_id,
                    parent_id=req.start.parent_id,
                    thread_id=req.start.thread_id,
                    turn_id=req.start.turn_id,
                    op_name=req.start.op_name,
                    display_name=req.start.display_name,
                    started_at=_ensure_tz(req.start.started_at),
                    attributes=json.loads(attributes_json),
                    inputs=json.loads(inputs_json),
                    input_refs=extract_refs_from_values(
                        list(req.start.inputs.values())
                    ),
                    wb_user_id=req.start.wb_user_id,
                    wb_run_id=req.start.wb_run_id,
                    wb_run_step=req.start.wb_run_step,
                    otel_dump=copy.deepcopy(req.start.otel_dump),
                    otel_dump_len=(
                        len(json.dumps(req.start.otel_dump))
                        if req.start.otel_dump is not None
                        else None
                    ),
                    expire_at=expire_at,
                    attributes_len=len(attributes_json),
                    inputs_len=len(inputs_json),
                )
                self._calls[rec.project_id, rec.id] = rec

        return tsi.CallStartRes(
            id=req.start.id,
            trace_id=req.start.trace_id,
        )

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        parsable_output = req.end.output
        if not isinstance(parsable_output, dict):
            parsable_output = {"output": parsable_output}
        parsable_output = cast(dict, parsable_output)
        output_json = json.dumps(req.end.output)
        summary_json = json.dumps(req.end.summary)
        with self.lock:
            rec = self._calls.get((req.end.project_id, req.end.id))
            if rec is None:
                # End part arrived before the start (ClickHouse merges parts
                # in any order); create an end-only row.
                rec = _CallRec(
                    project_id=req.end.project_id,
                    id=req.end.id,
                    trace_id=None,
                    parent_id=None,
                    thread_id=None,
                    turn_id=None,
                    op_name=None,
                    display_name=None,
                    started_at=(
                        _ensure_tz(req.end.started_at)
                        if req.end.started_at is not None
                        else None
                    ),
                    attributes={},
                    inputs={},
                    input_refs=[],
                    wb_user_id=None,
                    wb_run_id=None,
                    wb_run_step=None,
                    otel_dump=None,
                    expire_at=self._compute_call_expire_at(
                        req.end.project_id,
                        req.end.started_at
                        if req.end.started_at is not None
                        else req.end.ended_at,
                    ),
                )
                self._calls[rec.project_id, rec.id] = rec
            if rec is not None:
                rec.ended_at = _ensure_tz(req.end.ended_at)
                rec.exception = req.end.exception
                rec.output = json.loads(output_json)
                rec.output_refs = extract_refs_from_values(
                    list(parsable_output.values())
                )
                rec.summary = json.loads(summary_json)
                rec.wb_run_step_end = req.end.wb_run_step_end
                rec.output_len = len(output_json)
                rec.summary_len = len(summary_json)
                rec.storage_size_bytes = (
                    (rec.attributes_len or 0)
                    + (rec.inputs_len or 0)
                    + len(output_json)
                    + len(summary_json)
                )
        return tsi.CallEndRes()

    # ------------------------------------------------------------------
    # Cost application (the llm_token_prices join both backends perform)
    # ------------------------------------------------------------------

    def _ensure_default_costs(self) -> bool:
        for row in self._llm_token_prices:
            if (
                row["pricing_level"] == PRICING_LEVELS["DEFAULT"]
                and row["pricing_level_id"] == DEFAULT_PRICING_LEVEL_ID
            ):
                return False

        for row in _load_default_cost_definitions():
            self._llm_token_prices.append(
                {
                    "id": generate_id(),
                    "pricing_level": row["pricing_level"],
                    "pricing_level_id": row["pricing_level_id"],
                    "provider_id": row["provider_id"],
                    "llm_id": row["llm_id"],
                    "effective_date": row["effective_date"],
                    "prompt_token_cost": row["prompt_token_cost"],
                    "completion_token_cost": row["completion_token_cost"],
                    "cache_read_input_token_cost": row.get(
                        "cache_read_input_token_cost", 0
                    ),
                    "cache_creation_input_token_cost": row.get(
                        "cache_creation_input_token_cost", 0
                    ),
                    "prompt_token_cost_unit": row["prompt_token_cost_unit"],
                    "completion_token_cost_unit": row["completion_token_cost_unit"],
                    "created_by": row["created_by"],
                    "created_at": row["created_at"],
                }
            )
        return True

    def _pick_best_cost_row(
        self,
        rows: list[dict[str, Any]],
        started_at: datetime.datetime,
        project_id: str,
    ) -> dict[str, Any] | None:
        if not rows:
            return None

        def rank_key(row: dict[str, Any]) -> tuple[int, int, float]:
            effective_date = _normalize_datetime_for_costs(row["effective_date"])
            assert effective_date is not None
            is_future = 1 if effective_date > started_at else 0
            if (
                row["pricing_level"] == PRICING_LEVELS["PROJECT"]
                and row["pricing_level_id"] == project_id
            ):
                pricing_rank = 0
            elif (
                row["pricing_level"] == PRICING_LEVELS["DEFAULT"]
                and row["pricing_level_id"] == DEFAULT_PRICING_LEVEL_ID
            ):
                pricing_rank = 1
            else:
                pricing_rank = 2
            return (is_future, pricing_rank, -effective_date.timestamp())

        return min(rows, key=rank_key)

    def _apply_costs_to_calls(
        self,
        calls: list[dict[str, Any]],
        project_id: str,
    ) -> None:
        """Attach per-call LLM cost breakdowns to each call's
        summary.weave.costs, mirroring the ClickHouse cost-join query.
        """
        # ---- Collect each call's token usage and the LLM ids involved ----
        usage_by_call_id: dict[str, dict[str, dict[str, int]]] = {}
        llm_ids: set[str] = set()

        for call in calls:
            summary = call.get("summary")
            if not isinstance(summary, dict):
                continue
            usage_by_model = _cost_usage_from_summary(summary)
            if not usage_by_model:
                continue
            usage_by_call_id[call["id"]] = usage_by_model
            llm_ids.update(usage_by_model.keys())

        if not llm_ids:
            return

        # ---- Load the applicable price rows (project overrides, else default) ----
        with self.lock:
            self._ensure_default_costs()
            price_rows = [
                dict(row)
                for row in self._llm_token_prices
                if row["llm_id"] in llm_ids
                and (
                    (
                        row["pricing_level"] == PRICING_LEVELS["PROJECT"]
                        and row["pricing_level_id"] == project_id
                    )
                    or (
                        row["pricing_level"] == PRICING_LEVELS["DEFAULT"]
                        and row["pricing_level_id"] == DEFAULT_PRICING_LEVEL_ID
                    )
                )
            ]

        price_rows_by_llm: dict[str, list[dict[str, Any]]] = {}
        for row in price_rows:
            price_rows_by_llm.setdefault(str(row["llm_id"]), []).append(row)

        # ---- Compute each call's per-model cost and write summary.weave.costs ----
        for call in calls:
            summary = call.get("summary")
            if not isinstance(summary, dict):
                continue

            weave_summary = summary.get("weave")
            if not isinstance(weave_summary, dict):
                weave_summary = {}
                summary["weave"] = weave_summary
            else:
                weave_summary.pop("costs", None)

            started_at = _normalize_datetime_for_costs(call.get("started_at"))
            assert started_at is not None

            call_costs: dict[str, dict[str, Any]] = {}
            for llm_id, usage in usage_by_call_id.get(call["id"], {}).items():
                best_row = self._pick_best_cost_row(
                    price_rows_by_llm.get(llm_id, []), started_at, project_id
                )
                if best_row is None:
                    continue

                prompt_cost = float(best_row["prompt_token_cost"] or 0.0)
                completion_cost = float(best_row["completion_token_cost"] or 0.0)
                cache_read_cost = float(
                    best_row.get("cache_read_input_token_cost") or 0.0
                )
                cache_creation_cost = float(
                    best_row.get("cache_creation_input_token_cost") or 0.0
                )
                prompt_tokens = usage["prompt_tokens"]
                completion_tokens = usage["completion_tokens"]
                cache_read_input_tokens = usage.get("cache_read_input_tokens", 0)
                cache_creation_input_tokens = usage.get(
                    "cache_creation_input_tokens", 0
                )

                call_costs[llm_id] = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cache_read_input_tokens": cache_read_input_tokens,
                    "cache_creation_input_tokens": cache_creation_input_tokens,
                    "requests": usage["requests"],
                    "total_tokens": usage["total_tokens"],
                    # Subtract cached tokens: they are billed at the cache
                    # rate, not the regular input rate.
                    "prompt_tokens_total_cost": (
                        prompt_tokens
                        - cache_read_input_tokens
                        - cache_creation_input_tokens
                    )
                    * prompt_cost,
                    "completion_tokens_total_cost": completion_tokens * completion_cost,
                    "cache_read_input_tokens_total_cost": cache_read_input_tokens
                    * cache_read_cost,
                    "cache_creation_input_tokens_total_cost": cache_creation_input_tokens
                    * cache_creation_cost,
                    "prompt_token_cost": prompt_cost,
                    "completion_token_cost": completion_cost,
                    "cache_read_input_token_cost": cache_read_cost,
                    "cache_creation_input_token_cost": cache_creation_cost,
                    "prompt_token_cost_unit": best_row["prompt_token_cost_unit"],
                    "completion_token_cost_unit": best_row[
                        "completion_token_cost_unit"
                    ],
                    "effective_date": best_row["effective_date"],
                    "provider_id": best_row["provider_id"],
                    "pricing_level": best_row["pricing_level"],
                    "pricing_level_id": best_row["pricing_level_id"],
                    "created_at": best_row["created_at"],
                    "created_by": best_row["created_by"],
                }

            if call_costs:
                weave_summary["costs"] = call_costs

    # ------------------------------------------------------------------
    # Calls query engine
    # ------------------------------------------------------------------

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        calls = self.calls_query(
            tsi.CallsQueryReq(
                project_id=req.project_id,
                limit=1,
                filter=tsi.CallsFilter(call_ids=[req.id]),
                include_costs=req.include_costs,
                include_storage_size=req.include_storage_size,
                include_total_storage_size=req.include_total_storage_size,
            )
        ).calls
        return tsi.CallReadRes(call=calls[0] if calls else None)

    def _feedback_rows_for_call(
        self, project_id: str, call_id: str, feedback_type: str | None
    ) -> list[dict[str, Any]]:
        """Feedback rows attached to a call ref, in insertion (rowid) order."""
        call_ref = ri.InternalCallRef(project_id=project_id, id=call_id).uri
        with self.lock:
            rows = [row for row in self._feedback if row["weave_ref"] == call_ref]
        if feedback_type is not None:
            rows = [row for row in rows if row["feedback_type"] == feedback_type]
        return rows

    def _compile_feedback_field(self, field_path: str) -> Any:
        """Compile a `feedback.[type].…` field into a per-record evaluator,
        mirroring CallsMergedFeedbackPayloadField in the ClickHouse builder:
        anyIf over the call's feedback rows, then JSON_VALUE extraction —
        a String expression where "no feedback" reads as ''.
        """
        path = field_path[len("feedback.") :]
        match = re.match(r"^\[(.+?)\]\.(.+)$", path)
        if not match:
            raise InvalidFieldError(f"Invalid feedback field path: {field_path}")
        feedback_type, rest = match.groups()

        parts = rest.split(".")
        if parts[0] == "payload":
            db_column = "payload"
            extra_parts = parts[1:]
        elif parts[0] in {"runnable_ref", "trigger_ref"}:
            db_column = parts[0]
            extra_parts = []
        else:
            raise InvalidFieldError(f"Invalid feedback field path: {field_path}")

        def extract(row: dict[str, Any]) -> str:
            raw = row.get(db_column)
            if db_column == "payload":
                if extra_parts:
                    return _ch_json_value(raw, extra_parts)
                return "" if raw is None else _minify_json(raw)
            return raw if isinstance(raw, str) else ""

        if feedback_type == "*":

            def evaluate_any(rec: _CallRec) -> str:
                # anyIf(extracted, extracted != ''): first non-empty value
                # across all feedback rows; '' when none.
                for row in self._feedback_rows_for_call(rec.project_id, rec.id, None):
                    value = extract(row)
                    if value != "":
                        return value
                return ""

            return evaluate_any

        def evaluate(rec: _CallRec) -> str:
            rows = self._feedback_rows_for_call(rec.project_id, rec.id, feedback_type)
            if not rows:
                return ""
            return extract(rows[0])

        return evaluate

    def _feedback_values_array(self, rec: _CallRec, field_path: str) -> list[str]:
        """Mirror as_array_sql: groupArrayIf of extracted values for a
        multi-value feedback type (non-empty extracted values only when an
        extra path is present).
        """
        path = field_path[len("feedback.") :]
        match = re.match(r"^\[(.+?)\]\.(.+)$", path)
        if not match:
            raise InvalidFieldError(f"Invalid feedback field path: {field_path}")
        feedback_type, rest = match.groups()
        parts = rest.split(".")
        extra_parts = parts[1:] if parts[0] == "payload" else []
        rows = self._feedback_rows_for_call(rec.project_id, rec.id, feedback_type)
        values: list[str] = []
        for row in rows:
            payload = row.get("payload")
            if extra_parts:
                value = _ch_json_value(payload, extra_parts)
                if value != "":
                    values.append(value)
            else:
                values.append("" if payload is None else _minify_json(payload))
        return values

    def _compile_calls_field(self, field_path: str, cast_to: str | None = None) -> Any:
        """Compile a calls field reference into a per-record evaluator,
        mirroring get_field_by_name + the field classes' as_sql in the
        ClickHouse calls query builder.
        """
        if field_path.startswith("summary.weave."):
            summary_field = field_path[len("summary.weave.") :]
            if summary_field not in _SUMMARY_FIELD_HANDLERS:
                supported = ", ".join(sorted(_SUMMARY_FIELD_HANDLERS))
                raise InvalidFieldError(
                    f"Summary field '{summary_field}' is not allowed. "
                    f"Supported fields are: {supported}"
                )
            if summary_field == "status":
                return self._status_case
            if summary_field == "latency_ms":
                return self._latency_ms
            return self._trace_name_case
        for col_name in ("inputs", "output", "attributes", "summary"):
            if field_path == col_name or field_path.startswith(col_name + "."):
                json_path = (
                    split_escaped_field_path(field_path[len(col_name) + 1 :])
                    if field_path != col_name
                    else []
                )
                if cast_to == "exists":

                    def evaluate_exists(
                        rec: _CallRec,
                        _col_name: str = col_name,
                        _json_path: list[str] = json_path,
                    ) -> bool:
                        return _ch_json_exists(getattr(rec, _col_name), _json_path)

                    return evaluate_exists

                def evaluate(
                    rec: _CallRec,
                    _col_name: str = col_name,
                    _json_path: list[str] = json_path,
                    _cast_to: str | None = cast_to,
                ) -> Any:
                    value = _ch_json_value(getattr(rec, _col_name), _json_path)
                    return _ch_cast_json_value(value, _cast_to)

                return evaluate

        # Plain column access. Casts are not applied to static columns in
        # filters (mirroring process_operand); storage-size fields are
        # filterable nowhere.
        if field_path in _DISALLOWED_FILTERING_FIELDS:
            raise InvalidFieldError(f"Field {field_path} is not allowed")
        return _compile_call_column(field_path)

    def _latency_ms(self, rec: _CallRec) -> int | None:
        # CH: toUnixTimestamp64Milli(ended) - toUnixTimestamp64Milli(started);
        # NULL while the call is still running.
        if rec.ended_at is None or rec.started_at is None:
            return None
        started_ms = int(rec.started_at.timestamp() * 1000)
        ended_ms = int(rec.ended_at.timestamp() * 1000)
        return ended_ms - started_ms

    def _status_case(self, rec: _CallRec) -> str:
        # ClickHouse handler order: error, then descendant_error, then
        # running, then success.
        if rec.exception is not None:
            return "error"
        error_count = _ch_cast_json_value(
            _ch_json_value(rec.summary, ["status_counts", "error"]), "int"
        )
        if (error_count or 0) > 0:
            return "descendant_error"
        if rec.ended_at is None:
            return "running"
        return "success"

    def _trace_name_case(self, rec: _CallRec) -> Any:
        if rec.display_name is not None and rec.display_name != "":
            return rec.display_name
        op_name = rec.op_name
        if op_name is not None and op_name.startswith(
            ri.WEAVE_INTERNAL_SCHEME + ":///"
        ):
            last_segment = op_name.rsplit("/", 1)[-1]
            colon_idx = last_segment.find(":")
            if colon_idx == -1:
                # The SQL substring expression yields an empty string when no
                # colon is present.
                return ""
            return last_segment[:colon_idx]
        return op_name

    def _live_queue_ids_for_call(self, rec: _CallRec) -> set[str]:
        """Queue ids with a live annotation_queue_items row for this call
        (the INNER JOIN the ClickHouse builder adds for queue filters).
        """
        return {
            item["queue_id"]
            for item in self._annotation_queue_items.values()
            if item["project_id"] == rec.project_id
            and item["call_id"] == rec.id
            and item["deleted_at"] is None
        }

    def _compile_calls_query(
        self, query: tsi.Query, expand_columns: list[str] | None = None
    ) -> Any:
        """Compile the mongo-style query into a per-record predicate,
        mirroring process_query_to_conditions in the ClickHouse calls query
        builder. Compilation walks the AST once; evaluation is a closure
        call per record.
        """

        def is_multi_value_feedback(operand: tsi_query.Operand) -> bool:
            if not isinstance(operand, tsi_query.GetFieldOperator):
                return False
            return any(
                f"feedback.[{ft}]" in operand.get_field_
                for ft in MULTI_VALUE_FEEDBACK_TYPES
            )

        def queue_field_name(operand: tsi_query.Operand) -> str | None:
            if not isinstance(operand, tsi_query.GetFieldOperator):
                return None
            name = operand.get_field_
            if not name.startswith("annotation_queue_items."):
                return None
            field_name = name[len("annotation_queue_items.") :]
            if field_name != "queue_id":
                raise InvalidFieldError(
                    f"Invalid annotation_queue_items field: {field_name}"
                )
            return field_name

        def datetime_field_name(operand: tsi_query.Operand) -> str | None:
            if (
                isinstance(operand, tsi_query.GetFieldOperator)
                and operand.get_field_ in _DATETIME_COLUMN_FIELDS
            ):
                return operand.get_field_
            return None

        def compile_operation(operation: tsi_query.Operation) -> Any:
            if isinstance(operation, tsi_query.AndOperation):
                if len(operation.and_) == 0:
                    raise ValueError("Empty AND operation")
                elif len(operation.and_) == 1:
                    return compile_operand(operation.and_[0])
                and_parts = [compile_operand(op) for op in operation.and_]
                return lambda rec: all(_truthy(part(rec)) for part in and_parts)
            elif isinstance(operation, tsi_query.OrOperation):
                if len(operation.or_) == 0:
                    raise ValueError("Empty OR operation")
                elif len(operation.or_) == 1:
                    return compile_operand(operation.or_[0])
                or_parts = [compile_operand(op) for op in operation.or_]
                return lambda rec: any(_truthy(part(rec)) for part in or_parts)
            elif isinstance(operation, tsi_query.NotOperation):
                inner = compile_operand(operation.not_[0])

                def evaluate_not(rec: _CallRec) -> Any:
                    value = inner(rec)
                    if value is None:
                        return None
                    return not _truthy(value)

                return evaluate_not
            elif isinstance(operation, tsi_query.EqOperation):
                lhs_op, rhs_op = operation.eq_
                # Queue membership: rendered as an INNER JOIN by ClickHouse.
                queue_lhs = queue_field_name(lhs_op)
                if queue_lhs is not None:
                    rhs_fn = compile_operand(rhs_op)
                    return lambda rec: rhs_fn(rec) in self._live_queue_ids_for_call(rec)
                if is_multi_value_feedback(lhs_op):
                    field_path = lhs_op.get_field_
                    if (
                        isinstance(rhs_op, tsi_query.LiteralOperation)
                        and rhs_op.literal_ is None
                    ):
                        return lambda rec: (
                            len(self._feedback_values_array(rec, field_path)) == 0
                        )
                    rhs_fn = compile_operand(rhs_op)
                    return lambda rec: (
                        rhs_fn(rec) in self._feedback_values_array(rec, field_path)
                    )
                if (
                    isinstance(rhs_op, tsi_query.LiteralOperation)
                    and rhs_op.literal_ is None
                ):
                    lhs_fn = compile_operand(lhs_op)
                    return lambda rec: lhs_fn(rec) is None
                return compile_binary(lhs_op, rhs_op, "eq")
            elif isinstance(operation, tsi_query.GtOperation):
                return compile_binary(operation.gt_[0], operation.gt_[1], "gt")
            elif isinstance(operation, tsi_query.LtOperation):
                return compile_binary(operation.lt_[0], operation.lt_[1], "lt")
            elif isinstance(operation, tsi_query.GteOperation):
                return compile_binary(operation.gte_[0], operation.gte_[1], "gte")
            elif isinstance(operation, tsi_query.LteOperation):
                return compile_binary(operation.lte_[0], operation.lte_[1], "lte")
            elif isinstance(operation, tsi_query.InOperation):
                in_cast = tsi_query.infer_shared_literal_filter_cast(operation.in_[1])
                lhs_fn = compile_get_field_with_inferred_cast(operation.in_[0], in_cast)
                if lhs_fn is None:
                    lhs_fn = compile_operand(operation.in_[0])
                elems = [compile_operand(op) for op in operation.in_[1]]

                def evaluate_in(rec: _CallRec) -> Any:
                    lhs_part = lhs_fn(rec)
                    if lhs_part is None:
                        return None
                    for elem_fn in elems:
                        if _truthy(_ch_compare(lhs_part, elem_fn(rec), "eq")):
                            return True
                    return False

                return evaluate_in
            elif isinstance(operation, tsi_query.ContainsOperation):
                case_insensitive = bool(operation.contains_.case_insensitive)
                if is_multi_value_feedback(operation.contains_.input):
                    field_path = operation.contains_.input.get_field_
                    substr_fn = compile_operand(operation.contains_.substr)

                    def evaluate_array_contains(rec: _CallRec) -> bool:
                        needle = substr_fn(rec)
                        return any(
                            _ch_position(value, needle, case_insensitive)
                            for value in self._feedback_values_array(rec, field_path)
                        )

                    return evaluate_array_contains
                input_fn = compile_operand(operation.contains_.input)
                substr_fn = compile_operand(operation.contains_.substr)
                return lambda rec: _ch_position(
                    input_fn(rec), substr_fn(rec), case_insensitive
                )
            else:
                raise TypeError(f"Unknown operation type: {operation}")

        def compile_binary(
            lhs: tsi_query.Operand,
            rhs: tsi_query.Operand,
            op: str,
        ) -> Any:
            # DateTime64 column comparisons: normalize the literal side.
            lhs_dt = datetime_field_name(lhs)
            rhs_dt = datetime_field_name(rhs)
            converted_literal: datetime.datetime | None = None
            literal_side = None
            if lhs_dt or rhs_dt:
                for side, operand in (("lhs", lhs), ("rhs", rhs)):
                    if isinstance(operand, tsi_query.LiteralOperation):
                        parsed = _maybe_datetime_literal(operand.literal_)
                        if parsed is not None:
                            converted_literal = parsed
                            literal_side = side
            lhs_cast = tsi_query.infer_literal_filter_cast(rhs)
            rhs_cast = tsi_query.infer_literal_filter_cast(lhs)
            if literal_side is not None:
                lhs_cast = rhs_cast = None
            lhs_fn = compile_get_field_with_inferred_cast(lhs, lhs_cast)
            if lhs_fn is None:
                lhs_fn = compile_operand(lhs)
            rhs_fn = compile_get_field_with_inferred_cast(rhs, rhs_cast)
            if rhs_fn is None:
                rhs_fn = compile_operand(rhs)
            if literal_side == "lhs":
                lhs_fn = lambda rec, _v=converted_literal: _v
            elif literal_side == "rhs":
                rhs_fn = lambda rec, _v=converted_literal: _v

            def evaluate_binary(rec: _CallRec) -> Any:
                return _ch_compare(lhs_fn(rec), rhs_fn(rec), op)

            return evaluate_binary

        def compile_get_field_with_inferred_cast(
            operand: tsi_query.Operand,
            cast_to: tsi_query.CastTo | None,
        ) -> Any:
            """Mirror process_json_field_operand_with_inferred_cast: only
            dynamic JSON fields and single-value feedback fields take the
            inferred cast.
            """
            if cast_to is None or not isinstance(operand, tsi_query.GetFieldOperator):
                return None
            field_name = operand.get_field_
            if field_name in _DISALLOWED_FILTERING_FIELDS:
                raise InvalidFieldError(f"Field {field_name} is not allowed")
            if has_expand_prefix(field_name):
                return self._compile_expanded_field(
                    field_name, expand_columns or [], cast_to
                )
            if field_name.startswith("feedback."):
                if field_name.startswith("feedback.[*]") or is_multi_value_feedback(
                    operand
                ):
                    return None
                inner = self._compile_feedback_field(field_name)
                return lambda rec: _ch_cast_json_value(inner(rec), cast_to)
            if field_name.startswith("summary.weave."):
                return None
            for col_name in ("inputs", "output", "attributes", "summary"):
                if field_name == col_name or field_name.startswith(col_name + "."):
                    return self._compile_calls_field(field_name, cast_to)
            return None

        def has_expand_prefix(field_name: str) -> bool:
            if not expand_columns:
                return False
            return any(
                field_name == col or field_name.startswith(col + ".")
                for col in expand_columns
            )

        def compile_operand(operand: tsi_query.Operand) -> Any:
            """Compile a single query operand into a per-record value getter,
            dispatching on its AST node type.
            """
            if isinstance(operand, tsi_query.LiteralOperation):
                literal = operand.literal_
                if not (
                    literal is None or isinstance(literal, (str, int, float, bool))
                ):
                    raise ValueError(f"Unknown value type: {literal}")
                return lambda rec, _value=literal: _value
            elif isinstance(operand, tsi_query.GetFieldOperator):
                field_name = operand.get_field_
                if field_name in _DISALLOWED_FILTERING_FIELDS:
                    raise InvalidFieldError(f"Field {field_name} is not allowed")
                if has_expand_prefix(field_name):
                    return self._compile_expanded_field(
                        field_name, expand_columns or [], None
                    )
                if field_name.startswith("feedback."):
                    return self._compile_feedback_field(field_name)
                if field_name.startswith("annotation_queue_items."):
                    queue_field_name(operand)  # validates the subfield
                    return lambda rec: next(
                        iter(self._live_queue_ids_for_call(rec)), None
                    )
                return self._compile_calls_field(field_name, None)
            elif isinstance(operand, tsi_query.ConvertOperation):
                inner = compile_operand(operand.convert_.input)
                convert_to = operand.convert_.to
                if convert_to == "exists":
                    return lambda rec: inner(rec) is not None
                return lambda rec: _ch_cast_json_value(
                    inner(rec)
                    if isinstance(inner(rec), str)
                    else _ch_to_string(inner(rec)),
                    convert_to,
                )
            elif isinstance(
                operand,
                (
                    tsi_query.AndOperation,
                    tsi_query.OrOperation,
                    tsi_query.NotOperation,
                    tsi_query.EqOperation,
                    tsi_query.GtOperation,
                    tsi_query.LtOperation,
                    tsi_query.GteOperation,
                    tsi_query.LteOperation,
                    tsi_query.InOperation,
                    tsi_query.ContainsOperation,
                ),
            ):
                return compile_operation(operand)
            else:
                raise TypeError(f"Unknown operand type: {operand}")

        return compile_operation(query.expr_)

    @staticmethod
    def _validate_calls_filter(filter: tsi.CallsFilter) -> None:
        """Parameter-length validation the backends perform while building
        SQL — it must fire even when no rows exist.
        """
        if filter.op_names:
            assert_parameter_length_less_than_max("op_names", len(filter.op_names))
        if filter.input_refs:
            assert_parameter_length_less_than_max("input_refs", len(filter.input_refs))
        if filter.output_refs:
            assert_parameter_length_less_than_max(
                "output_refs", len(filter.output_refs)
            )
        if filter.parent_ids:
            assert_parameter_length_less_than_max("parent_ids", len(filter.parent_ids))
        if filter.trace_ids:
            assert_parameter_length_less_than_max("trace_ids", len(filter.trace_ids))
        if filter.call_ids:
            assert_parameter_length_less_than_max("call_ids", len(filter.call_ids))
        if filter.thread_ids is not None:
            assert_parameter_length_less_than_max("thread_ids", len(filter.thread_ids))
        if filter.turn_ids is not None:
            assert_parameter_length_less_than_max("turn_ids", len(filter.turn_ids))

    def _calls_filter_matches(self, rec: _CallRec, filter: tsi.CallsFilter) -> bool:
        """Return whether a call record satisfies every clause of a CallsFilter,
        mirroring the WHERE conditions the ClickHouse query builder emits.
        """
        if filter.op_names:
            non_wildcarded_names: list[str] = []
            wildcarded_names: list[str] = []
            for name in filter.op_names:
                if name.endswith(WILDCARD_ARTIFACT_VERSION_AND_PATH):
                    wildcarded_names.append(name)
                else:
                    non_wildcarded_names.append(name)
            matched = rec.op_name in non_wildcarded_names
            if not matched:
                for name in wildcarded_names:
                    # ClickHouse renders the wildcard as LIKE 'name:%'.
                    prefix = name[: -len(WILDCARD_ARTIFACT_VERSION_AND_PATH)] + ":"
                    if rec.op_name is not None and rec.op_name.startswith(prefix):
                        matched = True
                        break
            if not matched:
                return False

        if filter.input_refs and not self._refs_filter_matches(
            rec.input_refs, filter.input_refs
        ):
            return False
        if filter.output_refs and not self._refs_filter_matches(
            rec.output_refs, filter.output_refs
        ):
            return False
        if filter.parent_ids and rec.parent_id not in filter.parent_ids:
            return False
        if filter.trace_ids and rec.trace_id not in filter.trace_ids:
            return False
        if filter.call_ids and rec.id not in filter.call_ids:
            return False
        if filter.trace_roots_only and rec.parent_id is not None:
            return False
        if filter.wb_run_ids and rec.wb_run_id not in filter.wb_run_ids:
            return False
        if filter.wb_user_ids and rec.wb_user_id not in filter.wb_user_ids:
            return False
        if filter.thread_ids is not None and rec.thread_id not in filter.thread_ids:
            return False
        if filter.turn_ids is not None and rec.turn_id not in filter.turn_ids:
            return False
        return True

    @staticmethod
    def _refs_filter_matches(stored_refs: list[str], filter_refs: list[str]) -> bool:
        exact_refs, wildcard_refs = split_exact_and_wildcard_values(filter_refs)
        for ref in exact_refs:
            if ref in stored_refs:
                return True
        for ref in wildcard_refs:
            prefix = wildcard_version_value_to_ref_prefix(ref)
            if any(stored.startswith(prefix) for stored in stored_refs):
                return True
        return False

    def _compile_calls_sort_field(
        self,
        sort_field: str,
        direction: str,
        expand_columns: list[str] | None = None,
    ) -> list[tuple[Any, str]]:
        """Compile an ORDER BY term into [(evaluator, direction)] terms,
        mirroring OrderField.as_sql: dynamic (JSON/feedback) fields sort by
        existence DESC, then the float cast, then the string cast.
        """
        if expand_columns and any(
            sort_field == col or sort_field.startswith(col + ".")
            for col in expand_columns
        ):
            exists_fn = self._compile_expanded_field(
                sort_field, expand_columns, "exists"
            )
            value_fn = self._compile_expanded_field(sort_field, expand_columns, None)
            return [
                (lambda rec: 1 if exists_fn(rec) else 0, "desc"),
                (lambda rec: _ch_to_float64_or_null(value_fn(rec)), direction),
                (value_fn, direction),
            ]
        is_dynamic = any(
            sort_field == col or sort_field.startswith(col + ".")
            for col in ("inputs", "output", "attributes", "summary")
        ) and not sort_field.startswith("summary.weave.")
        if sort_field.startswith("feedback."):
            exists_fn_inner = self._compile_feedback_field(sort_field)

            def feedback_exists(rec: _CallRec) -> int:
                return 1 if exists_fn_inner(rec) != "" else 0

            value_fn = self._compile_feedback_field(sort_field)
            return [
                (feedback_exists, "desc"),
                (lambda rec: _ch_to_float64_or_null(value_fn(rec)), direction),
                (value_fn, direction),
            ]
        if is_dynamic:
            exists_fn = self._compile_calls_field(sort_field, "exists")
            value_fn = self._compile_calls_field(sort_field, None)
            return [
                (lambda rec: 1 if exists_fn(rec) else 0, "desc"),
                (lambda rec: _ch_to_float64_or_null(value_fn(rec)), direction),
                (value_fn, direction),
            ]
        return [(self._compile_calls_field(sort_field, None), direction)]

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        """Run a calls query end to end, mirroring the ClickHouse calls query:
        filter, project columns, sort, paginate, then assemble each row and
        hydrate costs/feedback.
        """
        # ---- Load the project's live calls and apply filter + query predicates ----
        with self.lock:
            records = [
                rec
                for rec in self._calls.values()
                if rec.deleted_at is None
                and rec.project_id == req.project_id
                and rec.op_name is not None
                and rec.started_at is not None
            ]
            # Snapshot for total-storage aggregation before filtering (the
            # backend subquery aggregates over all calls in the project).
            all_records = (
                [
                    rec
                    for rec in self._calls.values()
                    if rec.project_id == req.project_id and rec.deleted_at is None
                ]
                if req.include_total_storage_size
                else None
            )

        if req.filter:
            self._validate_calls_filter(req.filter)
            records = [
                rec for rec in records if self._calls_filter_matches(rec, req.filter)
            ]

        if req.query:
            predicate = self._compile_calls_query(req.query, req.expand_columns)
            records = [rec for rec in records if _truthy(predicate(rec))]

        # ---- Resolve which columns to project (interface behavior shared by the backends) ----
        required_columns = ["id", "trace_id", "project_id", "op_name", "started_at"]
        select_columns = [
            key
            for key in tsi.CallSchema.model_fields.keys()
            if key
            not in {"storage_size_bytes", "total_storage_size_bytes", "wb_username"}
        ]
        if req.columns:
            simple_columns = []
            for column in req.columns:
                top_level_column = column.split(".")[0]
                if (
                    top_level_column.endswith("_dump")
                    and top_level_column[:-5] in select_columns
                ):
                    top_level_column = top_level_column[:-5]
                if top_level_column not in simple_columns:
                    simple_columns.append(top_level_column)
            if req.include_usernames and "wb_user_id" not in simple_columns:
                simple_columns.append("wb_user_id")
            if req.include_costs and "summary" not in simple_columns:
                simple_columns.append("summary")
            if "summary" in simple_columns or req.include_costs:
                for column in ["ended_at", "exception", "display_name"]:
                    if column not in simple_columns:
                        simple_columns.append(column)

            select_columns = [x for x in simple_columns if x in select_columns]
            select_columns += [
                rcol for rcol in required_columns if rcol not in select_columns
            ]

        # ---- Sort the records, including the implicit id tiebreaker the backends append ----
        if req.sort_by is None:
            order_by: list[tuple[str, str]] | None = [
                ("started_at", "asc"),
                ("id", "asc"),
            ]
        elif len(req.sort_by) == 0:
            order_by = None
        else:
            order_by = [(s.field, s.direction) for s in req.sort_by]
            if not any(field_name == "id" for field_name, _ in order_by):
                last_sort = req.sort_by[-1]
                if last_sort.field == "started_at":
                    order_by.append(("id", last_sort.direction))
                else:
                    order_by.append(("id", "desc"))

        if order_by is not None:
            for _, direction in order_by:
                assert direction in {
                    "ASC",
                    "DESC",
                    "asc",
                    "desc",
                }, f"Invalid order_by direction: {direction}"
            compiled_terms = [
                term
                for field_name, direction in order_by
                for term in self._compile_calls_sort_field(
                    field_name, direction, req.expand_columns
                )
            ]
            records = _ch_sorted_by_terms(
                records,
                compiled_terms,
                lambda rec, term_fn: term_fn(rec),
            )

        # ---- Apply LIMIT/OFFSET pagination (falsy limits mean unlimited) ----
        offset = req.offset if req.offset and req.offset > 0 else 0
        if offset:
            records = records[offset:]
        if req.limit and req.limit > 0:
            records = records[: req.limit]

        # ---- Assemble each output row: project columns, storage, ref expansion, derived summary ----
        total_storage_by_trace: dict[str | None, int] = {}
        if req.include_total_storage_size and all_records is not None:
            for rec in all_records:
                total_storage_by_trace[rec.trace_id] = total_storage_by_trace.get(
                    rec.trace_id, 0
                ) + (
                    (rec.attributes_len or 0)
                    + (rec.inputs_len or 0)
                    + (rec.output_len or 0)
                    + (rec.summary_len or 0)
                )

        calls = []
        for rec in records:
            call_dict: dict[str, Any] = {}
            for col in select_columns:
                if col in {"attributes", "inputs", "output", "summary"}:
                    call_dict[col] = copy.deepcopy(getattr(rec, col))
                else:
                    call_dict[col] = getattr(rec, col)

            if req.include_storage_size:
                call_dict["storage_size_bytes"] = (
                    rec.storage_size_bytes
                    if rec.storage_size_bytes is not None
                    else (
                        (rec.attributes_len or 0)
                        + (rec.inputs_len or 0)
                        + (rec.output_len or 0)
                        + (rec.summary_len or 0)
                    )
                )
            if req.include_total_storage_size:
                call_dict["total_storage_size_bytes"] = (
                    total_storage_by_trace.get(rec.trace_id)
                    if rec.parent_id is None
                    else None
                )

            # Ref expansion over the json fields.
            if req.expand_columns:
                for json_field in ["attributes", "summary", "inputs", "output"]:
                    if call_dict.get(json_field):
                        call_dict[json_field] = self._expand_refs(
                            {json_field: call_dict[json_field]}, req.expand_columns
                        )[json_field]

            # For backwards/future compatibility: inject otel_dump into
            # attributes if present.
            if rec.otel_dump:
                if "attributes" not in call_dict:
                    call_dict["attributes"] = {}
                call_dict["attributes"]["otel_span"] = copy.deepcopy(rec.otel_dump)

            if "display_name" in call_dict:
                call_dict["display_name"] = empty_str_to_none(call_dict["display_name"])

            call_dict["summary"] = make_derived_summary_fields(
                summary=call_dict.get("summary") or {},
                op_name=call_dict["op_name"],
                started_at=call_dict["started_at"],
                ended_at=call_dict.get("ended_at"),
                exception=call_dict.get("exception"),
                display_name=call_dict.get("display_name"),
            )

            raw_expire_at = call_dict.get("expire_at")
            if raw_expire_at is not None:
                call_dict["expire_at"] = (
                    None
                    if _ensure_tz(raw_expire_at) == EXPIRE_AT_NEVER
                    else raw_expire_at
                )

            for col, mfield in tsi.CallSchema.model_fields.items():
                if mfield.is_required() and col not in call_dict:
                    if isinstance(mfield.annotation, str):
                        call_dict[col] = ""
                    elif isinstance(
                        mfield.annotation, (datetime.datetime, datetime.date)
                    ):
                        raise ValueError(f"Field '{col}' is required for selection")
                    else:
                        call_dict[col] = {}
            calls.append(call_dict)

        # ---- Hydrate the assembled rows with costs and feedback when requested ----
        if req.include_costs and calls:
            self._apply_costs_to_calls(calls, req.project_id)

        if req.include_feedback:
            feedback_query_req = make_feedback_query_req(req.project_id, calls)
            feedback = self.feedback_query(feedback_query_req)
            hydrate_calls_with_feedback(calls, feedback)

        return tsi.CallsQueryRes(calls=[tsi.CallSchema(**call) for call in calls])

    def _expand_refs(
        self, data: dict[str, Any], expand_columns: list[str]
    ) -> dict[str, Any]:
        """Recursively expand refs in the data. Only expand refs if requested in the
        expand_columns list. expand_columns must be sorted by depth, shallowest first.
        """
        cols = sorted(expand_columns, key=lambda x: x.count("."))
        for col in cols:
            val = data.get(col)
            if not val:
                val = get_nested_key(data, col)
                if not val:
                    continue

            if not ri.any_will_be_interpreted_as_ref_str(val):
                continue

            if not isinstance(ri.parse_internal_uri(val), ri.InternalObjectRef):
                continue

            derefed_val = self.refs_read_batch(tsi.RefsReadBatchReq(refs=[val])).vals[0]
            set_nested_key(data, col, derefed_val)
            ref_col = f"{col}._ref"
            set_nested_key(data, ref_col, val)

        return data

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        return iter(self.calls_query(req).calls)

    def _calls_query_stream_for_eval_subtree(
        self,
        project_id: str,
        eval_root_ids: list[str],
        include_children: bool = True,
    ) -> Iterator[tsi.CallSchema]:
        columns = [
            "id",
            "parent_id",
            "op_name",
            "attributes",
            "inputs",
            "output",
            "summary",
            "started_at",
            "ended_at",
        ]
        eval_root_children = list(
            self.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=project_id,
                    filter=tsi.CallsFilter(parent_ids=eval_root_ids),
                    columns=columns,
                    sort_by=[tsi.SortBy(field="started_at", direction="asc")],
                )
            )
        )
        yield from eval_root_children
        if include_children:
            eval_root_children_ids = [c.id for c in eval_root_children]
            if eval_root_children_ids:
                yield from self.calls_query_stream(
                    tsi.CallsQueryReq(
                        project_id=project_id,
                        filter=tsi.CallsFilter(parent_ids=eval_root_children_ids),
                        columns=columns,
                        sort_by=[tsi.SortBy(field="started_at", direction="asc")],
                    )
                )

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        if req.limit is not None and req.limit < 1:
            raise ValueError("Limit must be a positive integer")
        calls = self.calls_query(
            tsi.CallsQueryReq(
                project_id=req.project_id,
                filter=req.filter,
                query=req.query,
                limit=req.limit,
                include_total_storage_size=req.include_total_storage_size,
            )
        ).calls
        count = len(calls)
        return tsi.CallsQueryStatsRes(
            count=count,
            has_more=req.limit is not None and count >= req.limit,
            total_storage_size_bytes=sum(
                call.total_storage_size_bytes
                for call in calls
                if call.total_storage_size_bytes is not None
            ),
        )

    def call_stats(self, req: tsi.CallStatsReq) -> tsi.CallStatsRes:
        end = req.end or datetime.datetime.now(datetime.timezone.utc)
        validate_call_stats_range(req.start, end)

        granularity = req.granularity or int((end - req.start).total_seconds())
        if granularity <= 0:
            granularity = 1

        calls = list(
            self.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=req.project_id,
                    filter=req.filter,
                )
            )
        )

        calls = [
            c
            for c in calls
            if c.started_at is not None
            and c.started_at >= req.start
            and c.started_at < end
        ]

        token_keys_map: dict[str, list[str]] = {
            "input_tokens": ["prompt_tokens", "input_tokens"],
            "output_tokens": ["completion_tokens", "output_tokens"],
            "total_tokens": ["total_tokens"],
        }

        def _bucket_ts(started_at: datetime.datetime) -> str:
            """Map a timestamp to the ISO start of its granularity bucket."""
            offset = int((started_at - req.start).total_seconds())
            bucket_idx = offset // granularity
            return (
                req.start + datetime.timedelta(seconds=bucket_idx * granularity)
            ).isoformat()

        usage_buckets: list[dict[str, Any]] = []
        if req.usage_metrics:
            raw: dict[
                tuple[str, str], dict[str, list[int]]
            ] = {}  # (ts, model) -> metric -> values

            for call in calls:
                if not call.summary or not isinstance(call.summary, dict):
                    continue
                usage = call.summary.get("usage")
                if not isinstance(usage, dict):
                    continue
                ts = _bucket_ts(call.started_at)
                for model, model_usage in usage.items():
                    if not isinstance(model_usage, dict):
                        continue
                    key = (ts, model)
                    if key not in raw:
                        raw[key] = {}
                    for spec in req.usage_metrics:
                        token_keys = token_keys_map.get(spec.metric, [])
                        val = 0
                        for k in token_keys:
                            raw_val = model_usage.get(k)
                            if isinstance(raw_val, (int, float, str)):
                                val += int(raw_val)
                        raw[key].setdefault(spec.metric, []).append(val)

            for (ts, model), metrics in sorted(raw.items()):
                bucket: dict[str, Any] = {"timestamp": ts, "model": model}
                for spec in req.usage_metrics:
                    values = metrics.get(spec.metric, [])
                    if not values:
                        continue
                    _apply_aggregations(
                        bucket, spec.metric, values, spec.aggregations, spec.percentiles
                    )
                usage_buckets.append(bucket)

        call_buckets: list[dict[str, Any]] = []
        if req.call_metrics:
            bucket_data: dict[str, dict[str, list[Any]]] = {}

            for call in calls:
                ts = _bucket_ts(call.started_at)
                if ts not in bucket_data:
                    bucket_data[ts] = {}
                for cm_spec in req.call_metrics:
                    if cm_spec.metric == "latency_ms":
                        if call.ended_at and call.started_at:
                            ms = (
                                call.ended_at - call.started_at
                            ).total_seconds() * 1000
                            bucket_data[ts].setdefault("latency_ms", []).append(ms)
                    elif cm_spec.metric == "call_count":
                        bucket_data[ts].setdefault("call_count", []).append(1)
                    elif cm_spec.metric == "error_count":
                        bucket_data[ts].setdefault("error_count", []).append(
                            1 if call.exception else 0
                        )

            for ts, metrics in sorted(bucket_data.items()):
                bucket = {"timestamp": ts}
                for cm_spec in req.call_metrics:
                    values = metrics.get(cm_spec.metric, [])
                    if not values:
                        continue
                    _apply_aggregations(
                        bucket,
                        cm_spec.metric,
                        values,
                        cm_spec.aggregations,
                        cm_spec.percentiles,
                    )
                call_buckets.append(bucket)

        return tsi.CallStatsRes(
            start=req.start,
            end=end,
            granularity=granularity,
            timezone=req.timezone or "UTC",
            usage_buckets=usage_buckets,
            call_buckets=call_buckets,
        )

    def trace_usage(self, req: tsi.TraceUsageReq) -> tsi.TraceUsageRes:
        calls = self.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=req.project_id,
                filter=req.filter,
                query=req.query,
                columns=["id", "parent_id", "summary"],
                include_costs=req.include_costs,
                limit=req.limit,
            )
        )

        usage_calls: list[usage_utils.UsageCall] = []
        unfinished_call_ids: set[str] = set()
        for call in calls:
            usage_calls.append(
                usage_utils.UsageCall(
                    id=call.id,
                    parent_id=call.parent_id,
                    summary=dict(call.summary) if call.summary else None,
                )
            )
            if call.ended_at is None:
                unfinished_call_ids.add(call.id)

        aggregated_usage = usage_utils.aggregate_usage_with_descendants(
            usage_calls, req.include_costs
        )

        return tsi.TraceUsageRes(
            call_usage=aggregated_usage,
            unfinished_call_ids=sorted(unfinished_call_ids),
        )

    def calls_usage(self, req: tsi.CallsUsageReq) -> tsi.CallsUsageRes:
        """Aggregate per-call usage (including descendants) for the requested
        root calls, mirroring the ClickHouse trace-scoped usage rollup.
        """
        if not req.call_ids:
            return tsi.CallsUsageRes(call_usage={}, unfinished_call_ids=[])

        # ---- Resolve the traces the requested root calls belong to ----
        root_calls = self.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=req.project_id,
                filter=tsi.CallsFilter(call_ids=req.call_ids),
                columns=["trace_id"],
                limit=len(req.call_ids),
            )
        )
        trace_ids = {call.trace_id for call in root_calls}
        if not trace_ids:
            root_usage: dict[str, dict[str, tsi.LLMAggregatedUsage]] = {
                call_id: {} for call_id in req.call_ids
            }
            return tsi.CallsUsageRes(call_usage=root_usage, unfinished_call_ids=[])

        # ---- Fetch every call in those traces and aggregate usage with descendants ----
        calls = self.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=req.project_id,
                filter=tsi.CallsFilter(trace_ids=list(trace_ids)),
                columns=["id", "parent_id", "summary"],
                include_costs=req.include_costs,
                limit=req.limit,
            )
        )

        usage_calls: list[usage_utils.UsageCall] = []
        unfinished_call_ids: set[str] = set()
        for call in calls:
            usage_calls.append(
                usage_utils.UsageCall(
                    id=call.id,
                    parent_id=call.parent_id,
                    summary=dict(call.summary) if call.summary else None,
                )
            )
            if call.ended_at is None:
                unfinished_call_ids.add(call.id)

        aggregated_usage = usage_utils.aggregate_usage_with_descendants(
            usage_calls, req.include_costs
        )

        # ---- Project the aggregated usage back onto the requested root calls ----
        root_usage = {
            call_id: aggregated_usage.get(call_id, {}) for call_id in req.call_ids
        }

        return tsi.CallsUsageRes(
            call_usage=root_usage,
            unfinished_call_ids=sorted(unfinished_call_ids),
        )

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        assert_non_null_wb_user_id(req)
        if len(req.call_ids) > MAX_DELETE_CALLS_COUNT:
            raise RequestTooLarge(
                f"Cannot delete more than {MAX_DELETE_CALLS_COUNT} calls at once"
            )

        with self.lock:
            # Descendant discovery is trace-scoped (mirrors ClickHouse): find
            # the requested calls' traces, then DFS the parent/child graph of
            # every live call in those traces starting from the requested ids.
            requested_ids = set(req.call_ids)
            trace_ids = {
                rec.trace_id
                for rec in self._calls.values()
                if rec.deleted_at is None
                and rec.project_id == req.project_id
                and rec.id in requested_ids
            }
            children_by_parent: dict[str | None, list[str]] = {}
            for rec in self._calls.values():
                if (
                    rec.deleted_at is None
                    and rec.project_id == req.project_id
                    and rec.trace_id in trace_ids
                    and rec.parent_id is not None
                ):
                    children_by_parent.setdefault(rec.parent_id, []).append(rec.id)

            # Roots are always counted, even if the call does not exist.
            all_ids: set[str] = set()
            stack = list(req.call_ids)
            while stack:
                current_id = stack.pop()
                if current_id not in all_ids:
                    all_ids.add(current_id)
                    stack.extend(children_by_parent.get(current_id, []))

            deleted_at = datetime.datetime.now(datetime.timezone.utc)
            for call_id in all_ids:
                call_rec = self._calls.get((req.project_id, call_id))
                if call_rec is not None and call_rec.deleted_at is None:
                    call_rec.deleted_at = deleted_at

        return tsi.CallsDeleteRes(num_deleted=len(all_ids))

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        assert_non_null_wb_user_id(req)
        if req.display_name is None:
            raise ValueError("One of [display_name] is required for call update")

        with self.lock:
            rec = self._calls.get((req.project_id, req.call_id))
            if rec is not None:
                rec.display_name = req.display_name
        return tsi.CallUpdateRes()

    # ------------------------------------------------------------------
    # Objects
    # ------------------------------------------------------------------

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        digest_result = compute_object_digest_result(
            req.obj.val,
            req.obj.builtin_object_class,
        )
        processed_val = digest_result.processed_val
        digest = digest_result.digest
        validate_expected_digest(
            expected=req.obj.expected_digest,
            actual=digest,
            label=f"obj {req.obj.object_id!r}",
        )
        project_id, object_id, wb_user_id = (
            req.obj.project_id,
            req.obj.object_id,
            req.obj.wb_user_id,
        )

        object_id_validator(object_id)

        kind = _get_kind(processed_val)
        with self.lock:
            if self._obj_exists(project_id, object_id, digest):
                # Even on dedup: move "latest" alias to this digest.
                self._set_alias(project_id, object_id, "latest", digest)
                return tsi.ObjCreateRes(digest=digest, object_id=object_id)

            self._reject_obj_name_type_collision(
                project_id=project_id,
                object_id=object_id,
                kind=kind,
                new_base_object_class=digest_result.base_object_class,
            )

            self._mark_existing_objects_as_not_latest(project_id, object_id)
            version_index = self._get_obj_version_index(project_id, object_id)
            rec = _ObjRec(
                project_id=project_id,
                object_id=object_id,
                created_at=datetime.datetime.now(datetime.timezone.utc),
                kind=kind,
                base_object_class=digest_result.base_object_class,
                leaf_object_class=digest_result.leaf_object_class,
                val=json.loads(digest_result.json_val),
                digest=digest,
                version_index=version_index,
                is_latest=1,
                wb_user_id=wb_user_id,
                val_dump_len=len(digest_result.json_val),
                deleted_at=None,
            )
            key = (project_id, kind, object_id, digest)
            existing = self._objs.get(key)
            if existing is not None:
                # ON CONFLICT DO UPDATE: refresh the existing row in place
                # (notably resurrecting a previously deleted version).
                existing.created_at = rec.created_at
                existing.base_object_class = rec.base_object_class
                existing.leaf_object_class = rec.leaf_object_class
                existing.val = rec.val
                existing.val_dump_len = rec.val_dump_len
                existing.version_index = rec.version_index
                existing.is_latest = 1
                existing.deleted_at = None
            else:
                self._objs[key] = rec
            self._set_alias(project_id, object_id, "latest", digest)
        return tsi.ObjCreateRes(digest=digest, object_id=object_id)

    def _set_alias(
        self, project_id: str, object_id: str, alias: str, digest: str
    ) -> None:
        self._aliases[project_id, object_id, alias] = _AliasRec(
            digest=digest, created_at=datetime.datetime.now(datetime.timezone.utc)
        )

    def _objs_for_object_id(self, project_id: str, object_id: str) -> list[_ObjRec]:
        return [
            rec
            for rec in self._objs.values()
            if rec.project_id == project_id and rec.object_id == object_id
        ]

    def _obj_exists(self, project_id: str, object_id: str, digest: str) -> bool:
        return any(
            rec.digest == digest and rec.deleted_at is None
            for rec in self._objs_for_object_id(project_id, object_id)
        )

    def _reject_obj_name_type_collision(
        self,
        project_id: str,
        object_id: str,
        kind: str,
        new_base_object_class: str | None,
    ) -> None:
        existing_classes = {
            rec.base_object_class
            for rec in self._objs_for_object_id(project_id, object_id)
            if rec.kind == kind and rec.deleted_at is None
        }
        mismatched = [c for c in existing_classes if c != new_base_object_class]
        if mismatched:
            raise ObjectNameTypeCollision(
                object_id=object_id,
                kind=kind,
                new_base_object_class=new_base_object_class,
                existing_base_object_classes=mismatched,
            )

    def _mark_existing_objects_as_not_latest(
        self, project_id: str, object_id: str
    ) -> None:
        for rec in self._objs_for_object_id(project_id, object_id):
            rec.is_latest = 0

    def _get_obj_version_index(self, project_id: str, object_id: str) -> int:
        return len(self._objs_for_object_id(project_id, object_id))

    def _has_latest_alias(self, project_id: str, object_id: str) -> bool:
        return (project_id, object_id, "latest") in self._aliases

    def _obj_is_latest(self, rec: _ObjRec) -> bool:
        """Hybrid is_latest: the explicit "latest" alias row wins when present;
        otherwise fall back to the column-based flag (mirrors
        `_IS_LATEST_FROM_ALIASES_SQL`).
        """
        alias = self._aliases.get((rec.project_id, rec.object_id, "latest"))
        if alias is not None:
            return alias.digest == rec.digest
        return rec.is_latest == 1

    def _obj_matches_digest_condition(self, rec: _ObjRec, digest: str) -> bool:
        if digest == "latest":
            return self._obj_is_latest(rec)
        (is_version, version_index) = digest_is_version_like(digest)
        if is_version:
            return rec.version_index == version_index
        return rec.digest == digest

    def _maybe_resolve_alias(
        self,
        project_id: str,
        object_id: str,
        digest: str,
    ) -> str | None:
        (is_version, _) = digest_is_version_like(digest)
        if is_version:
            return None
        if digest_is_content_hash(digest):
            return None
        alias = self._aliases.get((project_id, object_id, digest))
        if alias is not None:
            return alias.digest
        return None

    def _obj_rec_to_schema(
        self,
        rec: _ObjRec,
        metadata_only: bool,
        include_storage_size: bool = False,
    ) -> tsi.ObjSchema:
        return tsi.ObjSchema(
            size_bytes=rec.val_dump_len if include_storage_size else None,
            project_id=rec.project_id,
            object_id=rec.object_id,
            created_at=rec.created_at,
            kind=rec.kind,
            base_object_class=rec.base_object_class,
            val={} if metadata_only else copy.deepcopy(rec.val),
            digest=rec.digest,
            version_index=rec.version_index,
            is_latest=1 if self._obj_is_latest(rec) else 0,
            deleted_at=rec.deleted_at,
            wb_user_id=rec.wb_user_id,
            leaf_object_class=rec.leaf_object_class,
        )

    def _select_objs(
        self,
        project_id: str,
        predicate: Any = None,
        metadata_only: bool | None = False,
        limit: int | None = None,
        include_deleted: bool = False,
        offset: int | None = None,
        sort_by: list[SortBy] | None = None,
        include_storage_size: bool = False,
    ) -> list[tsi.ObjSchema]:
        with self.lock:
            recs = [rec for rec in self._objs.values() if rec.project_id == project_id]
            if not include_deleted:
                recs = [rec for rec in recs if rec.deleted_at is None]
            if predicate is not None:
                recs = [rec for rec in recs if predicate(rec)]

            sort_terms: list[tuple[str, str]] = []
            if sort_by:
                valid_sort_fields = {"object_id", "created_at"}
                for sort in sort_by:
                    if sort.field in valid_sort_fields and sort.direction in {
                        "asc",
                        "desc",
                    }:
                        sort_terms.append((sort.field, sort.direction))
                if sort_terms:
                    sort_terms.append(("version_index", "asc"))
            if not sort_terms:
                sort_terms = [("created_at", "asc"), ("version_index", "asc")]

            recs = _sorted_by_terms(recs, sort_terms, getattr)

            if limit is not None:
                if limit >= 0:
                    recs = recs[(offset or 0) : (offset or 0) + limit]
                elif offset is not None:
                    recs = recs[offset:]
            elif offset is not None:
                recs = recs[offset:]

            return [
                self._obj_rec_to_schema(rec, bool(metadata_only), include_storage_size)
                for rec in recs
            ]

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        digest = req.digest
        resolved_digest = self._maybe_resolve_alias(
            req.project_id, req.object_id, digest
        )
        if resolved_digest is not None:
            digest = resolved_digest

        target_digest = digest
        objs = self._select_objs(
            req.project_id,
            predicate=lambda rec: (
                rec.object_id == req.object_id
                and self._obj_matches_digest_condition(rec, target_digest)
            ),
            include_deleted=True,
            metadata_only=req.metadata_only,
        )
        if len(objs) == 0:
            raise NotFoundError(f"Obj {req.object_id}:{req.digest} not found")
        if objs[0].deleted_at is not None:
            raise ObjectDeletedError(
                f"{req.object_id}:v{objs[0].version_index} was deleted at {objs[0].deleted_at}",
                deleted_at=objs[0].deleted_at,
            )
        if req.include_tags_and_aliases:
            self._enrich_objs_with_tags_and_aliases(req.project_id, objs)
        return tsi.ObjReadRes(obj=objs[0])

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        filter = req.filter

        def predicate(rec: _ObjRec) -> bool:
            if filter is None:
                return True
            if filter.is_op is not None:
                if filter.is_op and rec.kind != "op":
                    return False
                if not filter.is_op and rec.kind == "op":
                    return False
            if filter.object_ids and rec.object_id not in filter.object_ids:
                return False
            if filter.latest_only and not self._obj_is_latest(rec):
                return False
            if (
                filter.base_object_classes
                and rec.base_object_class not in filter.base_object_classes
            ):
                return False
            if (
                filter.exclude_base_object_classes
                and rec.base_object_class in filter.exclude_base_object_classes
            ):
                return False
            if (
                filter.leaf_object_classes
                and rec.leaf_object_class not in filter.leaf_object_classes
            ):
                return False
            if filter.tags:
                tags = self._tags.get(
                    (rec.project_id, rec.object_id, rec.digest), set()
                )
                if not any(tag in tags for tag in filter.tags):
                    return False
            if filter.aliases:
                non_latest = [a for a in filter.aliases if a != "latest"]
                has_latest = "latest" in filter.aliases
                matched = False
                if non_latest:
                    for alias_name in non_latest:
                        alias = self._aliases.get(
                            (rec.project_id, rec.object_id, alias_name)
                        )
                        if alias is not None and alias.digest == rec.digest:
                            matched = True
                            break
                if not matched and has_latest:
                    matched = self._obj_is_latest(rec)
                if not matched:
                    return False
            return True

        objs = self._select_objs(
            req.project_id,
            predicate=predicate,
            metadata_only=req.metadata_only,
            limit=req.limit,
            offset=req.offset,
            sort_by=req.sort_by,
            include_storage_size=bool(req.include_storage_size),
        )

        if req.include_tags_and_aliases:
            self._enrich_objs_with_tags_and_aliases(req.project_id, objs)

        return tsi.ObjQueryRes(objs=objs)

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        max_objects_to_delete = 100
        if req.digests and len(req.digests) > max_objects_to_delete:
            raise ValueError(
                f"Object delete request contains {len(req.digests)} objects. Please delete {max_objects_to_delete} or fewer objects at a time."
            )

        with self.lock:
            live_versions = [
                rec
                for rec in self._objs_for_object_id(req.project_id, req.object_id)
                if rec.deleted_at is None
            ]
            if req.digests:
                matching_objects = [
                    rec
                    for rec in live_versions
                    if any(
                        self._obj_matches_digest_condition(rec, digest)
                        for digest in req.digests
                    )
                ]
            else:
                matching_objects = live_versions

            if len(matching_objects) == 0:
                raise NotFoundError(
                    f"Object {req.object_id} ({req.digests}) not found when deleting."
                )
            found_digests = {rec.digest for rec in matching_objects}
            if req.digests:
                given_digests = set(req.digests)
                if len(given_digests) != len(found_digests):
                    raise NotFoundError(
                        f"Delete request contains {len(req.digests)} digests, but found {len(found_digests)} objects to delete. Diff digests: {given_digests - found_digests}"
                    )

            deleted_at = datetime.datetime.now(datetime.timezone.utc)
            for rec in self._objs_for_object_id(req.project_id, req.object_id):
                if rec.digest in found_digests:
                    rec.deleted_at = deleted_at

            # Cascade: clean up tags and aliases for deleted digests.
            for digest in found_digests:
                self._tags.pop((req.project_id, req.object_id, digest), None)
            for key in [
                k
                for k, v in self._aliases.items()
                if k[0] == req.project_id
                and k[1] == req.object_id
                and v.digest in found_digests
            ]:
                self._aliases.pop(key, None)

            # Re-point the column-based is_latest to the most-recent
            # surviving version (created_at DESC, version_index DESC).
            survivors = [
                rec
                for rec in self._objs_for_object_id(req.project_id, req.object_id)
                if rec.deleted_at is None
            ]
            latest_digest: str | None = None
            if survivors:
                best = max(survivors, key=lambda r: (r.created_at, r.version_index))
                latest_digest = best.digest
            for rec in self._objs_for_object_id(req.project_id, req.object_id):
                rec.is_latest = 1 if rec.digest == latest_digest else 0

        return tsi.ObjDeleteRes(num_deleted=len(matching_objects))

    def _ensure_obj_version_exists(
        self, project_id: str, object_id: str, digest: str
    ) -> None:
        for rec in self._objs_for_object_id(project_id, object_id):
            if rec.digest == digest and rec.deleted_at is None:
                return
        raise NotFoundError(f"Object version {object_id}:{digest} not found")

    def obj_add_tags(self, req: tsi.ObjAddTagsReq) -> tsi.ObjAddTagsRes:
        with self.lock:
            self._ensure_obj_version_exists(req.project_id, req.object_id, req.digest)
            tags = self._tags.setdefault(
                (req.project_id, req.object_id, req.digest), set()
            )
            tags.update(req.tags)
        return tsi.ObjAddTagsRes()

    def obj_remove_tags(self, req: tsi.ObjRemoveTagsReq) -> tsi.ObjRemoveTagsRes:
        with self.lock:
            tags = self._tags.get((req.project_id, req.object_id, req.digest))
            if tags is not None:
                tags.difference_update(req.tags)
        return tsi.ObjRemoveTagsRes()

    def obj_set_aliases(self, req: tsi.ObjSetAliasesReq) -> tsi.ObjSetAliasesRes:
        with self.lock:
            self._ensure_obj_version_exists(req.project_id, req.object_id, req.digest)
            for alias in req.aliases:
                self._set_alias(req.project_id, req.object_id, alias, req.digest)
        return tsi.ObjSetAliasesRes()

    def obj_remove_aliases(
        self, req: tsi.ObjRemoveAliasesReq
    ) -> tsi.ObjRemoveAliasesRes:
        with self.lock:
            for alias in req.aliases:
                self._aliases.pop((req.project_id, req.object_id, alias), None)
        return tsi.ObjRemoveAliasesRes()

    def tags_list(self, req: tsi.TagsListReq) -> tsi.TagsListRes:
        with self.lock:
            tags = sorted(
                {
                    tag
                    for (project_id, _, _), tag_set in self._tags.items()
                    if project_id == req.project_id
                    for tag in tag_set
                }
            )
        return tsi.TagsListRes(tags=tags)

    def aliases_list(self, req: tsi.AliasesListReq) -> tsi.AliasesListRes:
        with self.lock:
            aliases = sorted(
                {
                    alias
                    for (project_id, _, alias) in self._aliases.keys()
                    if project_id == req.project_id
                }
            )
        return tsi.AliasesListRes(aliases=aliases)

    def _get_tags_for_objects(
        self,
        project_id: str,
        object_ids: list[str],
    ) -> dict[tuple[str, str], list[str]]:
        if not object_ids:
            return {}
        with self.lock:
            result: dict[tuple[str, str], list[str]] = {}
            for (pid, object_id, digest), tag_set in self._tags.items():
                if pid == project_id and object_id in object_ids:
                    result[object_id, digest] = sorted(tag_set)
            return result

    def _get_aliases_for_objects(
        self,
        project_id: str,
        object_ids: list[str],
    ) -> dict[tuple[str, str], list[str]]:
        if not object_ids:
            return {}
        with self.lock:
            result: dict[tuple[str, str], list[str]] = {}
            for (pid, object_id, alias), rec in self._aliases.items():
                if pid == project_id and object_id in object_ids:
                    result.setdefault((object_id, rec.digest), []).append(alias)
            return result

    def _enrich_objs_with_tags_and_aliases(
        self,
        project_id: str,
        objs: list[tsi.ObjSchema],
    ) -> None:
        if not objs:
            return
        object_ids = list({obj.object_id for obj in objs})
        tags_map = self._get_tags_for_objects(project_id, object_ids)
        aliases_map = self._get_aliases_for_objects(project_id, object_ids)
        apply_tags_and_synth_latest_in_place(objs, tags_map, aliases_map)

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        insert_rows = []
        for r in req.table.rows:
            if not isinstance(r, dict):
                raise TypeError("All rows must be dictionaries")
            row_json = json.dumps(r)
            row_digest = compute_row_digest(r)
            insert_rows.append((req.table.project_id, row_digest, row_json))

        row_digests = [r[1] for r in insert_rows]
        digest = compute_table_digest(row_digests)
        validate_expected_digest(
            expected=req.table.expected_digest,
            actual=digest,
            label=f"table ({len(row_digests)} rows)",
        )

        with self.lock:
            for project_id, row_digest, row_json in insert_rows:
                row_key = (project_id, row_digest)
                if row_key not in self._table_rows:
                    self._table_rows[row_key] = _TableRowRec(
                        project_id=project_id,
                        val=json.loads(row_json),
                        val_dump_len=len(row_json),
                    )
            self._tables.setdefault((req.table.project_id, digest), list(row_digests))

        return tsi.TableCreateRes(digest=digest, row_digests=row_digests)

    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes:
        digest = compute_table_digest(req.row_digests)
        validate_expected_digest(
            expected=req.expected_digest,
            actual=digest,
            label=f"table ({len(req.row_digests)} rows)",
        )

        with self.lock:
            self._tables.setdefault((req.project_id, digest), list(req.row_digests))

        return tsi.TableCreateFromDigestsRes(digest=digest)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        with self.lock:
            base = self._tables.get((req.project_id, req.base_digest))
            if base is None:
                raise IndexError("list index out of range")
            final_row_digests: list[str] = list(base)
        new_rows_needed_to_insert: list[tuple[str, str, str]] = []
        known_digests = set(final_row_digests)

        def add_new_row_needed_to_insert(row_data: Any) -> str:
            if not isinstance(row_data, dict):
                raise TypeError("All rows must be dictionaries")
            row_json = json.dumps(row_data)
            row_digest = compute_row_digest(row_data)
            if row_digest not in known_digests:
                new_rows_needed_to_insert.append((req.project_id, row_digest, row_json))
                known_digests.add(row_digest)
            return row_digest

        updated_digests = []
        for update in req.updates:
            if isinstance(update, tsi.TableAppendSpec):
                new_digest = add_new_row_needed_to_insert(update.append.row)
                final_row_digests.append(new_digest)
                updated_digests.append(new_digest)
            elif isinstance(update, tsi.TablePopSpec):
                if update.pop.index >= len(final_row_digests) or update.pop.index < 0:
                    raise ValueError("Index out of range")
                popped_digest = final_row_digests.pop(update.pop.index)
                updated_digests.append(popped_digest)
            elif isinstance(update, tsi.TableInsertSpec):
                if (
                    update.insert.index > len(final_row_digests)
                    or update.insert.index < 0
                ):
                    raise ValueError("Index out of range")
                new_digest = add_new_row_needed_to_insert(update.insert.row)
                final_row_digests.insert(update.insert.index, new_digest)
                updated_digests.append(new_digest)
            else:
                raise TypeError("Unrecognized update", update)

        with self.lock:
            for project_id, row_digest, row_json in new_rows_needed_to_insert:
                row_key = (project_id, row_digest)
                if row_key not in self._table_rows:
                    self._table_rows[row_key] = _TableRowRec(
                        project_id=project_id,
                        val=json.loads(row_json),
                        val_dump_len=len(row_json),
                    )

            digest = compute_table_digest(final_row_digests)
            self._tables.setdefault((req.project_id, digest), final_row_digests)

        return tsi.TableUpdateRes(digest=digest, updated_row_digests=updated_digests)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        with self.lock:
            row_digests = self._tables.get((req.project_id, req.digest)) or []
            # (original_index, digest, val) tuples; rows are materialized as
            # schema objects (with copied vals) only for the returned slice.
            entries: list[tuple[int, str, Any]] = []
            for original_index, row_digest in enumerate(row_digests):
                row_rec = self._table_rows.get((req.project_id, row_digest))
                if row_rec is None:
                    continue
                if (
                    req.filter
                    and req.filter.row_digests
                    and row_digest not in req.filter.row_digests
                ):
                    continue
                entries.append((original_index, row_digest, row_rec.val))

        if req.sort_by:
            sort_terms: list[tuple[str, str]] = []
            for sort in req.sort_by:
                field_name = sort.field
                if not field_name or not field_name.strip():
                    raise InvalidRequest("Sort field cannot be empty")
                if (
                    field_name.startswith(".")
                    or field_name.endswith(".")
                    or ".." in field_name
                ):
                    raise InvalidRequest(
                        f"Invalid sort field '{field_name}': field names cannot start/end with dots or contain consecutive dots"
                    )
                if "." in field_name:
                    parts = field_name.split(".")
                    if any(not component.strip() for component in parts):
                        raise InvalidRequest(
                            f"Invalid sort field '{field_name}': field path components cannot be empty"
                        )
                sort_terms.append((field_name, sort.direction.upper()))

            def sort_value(entry: tuple[int, str, Any], term: str) -> Any:
                value, _ = _json_extract(entry[2], term.split("."))
                return value

            entries = _sorted_by_terms(entries, sort_terms, sort_value)

        if req.offset is not None and req.offset > 0:
            entries = entries[req.offset :]
        if req.limit is not None and req.limit >= 0:
            entries = entries[: req.limit]

        return tsi.TableQueryRes(
            rows=[
                tsi.TableRowSchema(
                    digest=row_digest,
                    val=copy.deepcopy(val),
                    original_index=original_index,
                )
                for original_index, row_digest, val in entries
            ]
        )

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        results = self.table_query(req)
        yield from results.rows

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        batch_req = tsi.TableQueryStatsBatchReq(
            project_id=req.project_id, digests=[req.digest]
        )

        res = self.table_query_stats_batch(batch_req)

        if len(res.tables) == 0:
            logger.warning("No table_query_stats results for digest %s", req.digest)
            return tsi.TableQueryStatsRes(count=0)

        count = res.tables[0].count
        return tsi.TableQueryStatsRes(count=count)

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        tables = []
        with self.lock:
            for digest in req.digests or []:
                row_digests = self._tables.get((req.project_id, digest))
                if row_digests is None:
                    continue
                storage_size: int | None = None
                if req.include_storage_size:
                    storage_size = sum(
                        rec.val_dump_len
                        for row_digest in row_digests
                        if (rec := self._table_rows.get((req.project_id, row_digest)))
                        is not None
                    )
                tables.append(
                    tsi.TableStatsRow(
                        count=len(row_digests),
                        digest=digest,
                        storage_size_bytes=storage_size,
                    )
                )
        return tsi.TableQueryStatsBatchRes(tables=tables)

    def _table_rows_read_batch(
        self, project_id: str, digests: list[str]
    ) -> dict[str, Any]:
        """Batch read table_rows by digest. Returns {digest: parsed_val}."""
        if not digests:
            return {}
        with self.lock:
            result = {}
            for digest in digests:
                rec = self._table_rows.get((project_id, digest))
                if rec is not None and rec.project_id == project_id:
                    result[digest] = copy.deepcopy(rec.val)
            return result

    def _table_row_read(self, project_id: str, row_digest: str) -> tsi.TableRowSchema:
        with self.lock:
            rec = self._table_rows.get((project_id, row_digest))
            if rec is None or rec.project_id != project_id:
                raise NotFoundError(f"Row {row_digest} not found")
            return tsi.TableRowSchema(digest=row_digest, val=copy.deepcopy(rec.val))

    # ------------------------------------------------------------------
    # Refs
    # ------------------------------------------------------------------

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        if len(req.refs) > MAX_REFS_BATCH_SIZE:
            raise ValueError("Too many refs")

        parsed_refs = [ri.parse_internal_uri(r) for r in req.refs]
        if any(isinstance(r, ri.InternalTableRef) for r in parsed_refs):
            raise ValueError("Table refs not supported")
        if any(isinstance(r, ri.InternalCallRef) for r in parsed_refs):
            raise ValueError("Call refs not supported")
        parsed_obj_refs = cast(list[ri.InternalObjectRef], parsed_refs)

        return tsi.RefsReadBatchRes(
            vals=[self._read_internal_obj_ref(r) for r in parsed_obj_refs]
        )

    def _read_internal_obj_ref(self, r: ri.InternalObjectRef) -> Any:
        objs = self._select_objs(
            r.project_id,
            predicate=lambda rec: rec.object_id == r.name and rec.digest == r.version,
            include_deleted=True,
        )
        if len(objs) == 0:
            raise NotFoundError(f"Obj {r.name}:{r.version} not found")
        obj = objs[0]
        if obj.deleted_at is not None:
            return None
        val = obj.val
        extra = r.extra
        for extra_index in range(0, len(extra), 2):
            op, arg = extra[extra_index], extra[extra_index + 1]
            if op == ri.DICT_KEY_EDGE_NAME:
                val = val[arg]
            elif op == ri.OBJECT_ATTR_EDGE_NAME:
                val = val[arg]
            elif op == ri.LIST_INDEX_EDGE_NAME:
                val = val[int(arg)]
            elif op == ri.TABLE_ROW_ID_EDGE_NAME:
                weave_internal_prefix = ri.WEAVE_INTERNAL_SCHEME + ":///"
                if isinstance(val, str) and val.startswith(weave_internal_prefix):
                    table_ref = ri.parse_internal_uri(val)
                    if not isinstance(table_ref, ri.InternalTableRef):
                        raise ValueError(
                            "invalid data layout encountered, expected TableRef when resolving id"
                        )
                    row = self._table_row_read(
                        project_id=table_ref.project_id,
                        row_digest=arg,
                    )
                    val = row.val
                else:
                    raise ValueError(
                        "invalid data layout encountered, expected TableRef when resolving id"
                    )
            else:
                raise ValueError(f"Unknown ref type: {extra[extra_index]}")
        return val

    def _resolve_ref_str_for_filter(self, value: Any) -> Any:
        """Best-effort ref dereference for expand_columns filtering/sorting.

        Mirrors the ObjectRef CTE joins: unresolvable refs simply produce no
        joined value (None) rather than erroring.
        """
        if not isinstance(value, str) or not ri.string_will_be_interpreted_as_ref(
            value
        ):
            return None
        try:
            parsed = ri.parse_internal_uri(value)
        except Exception:
            return None
        if not isinstance(parsed, ri.InternalObjectRef):
            return None
        try:
            return self._read_internal_obj_ref(parsed)
        except (NotFoundError, KeyError, IndexError, ValueError, TypeError):
            return None

    def _compile_expanded_field(
        self,
        field_path: str,
        expand_columns: list[str],
        cast_to: str | None,
    ) -> Any:
        """Evaluator for a field whose path traverses refs named in
        expand_columns (mirrors the ObjectRefQueryProcessor CTE joins).
        """
        ordered = sorted(
            (
                col
                for col in expand_columns
                if field_path.startswith(col + ".") or field_path == col
            ),
            key=lambda col: col.count("."),
        )

        def evaluate(rec: _CallRec) -> Any:
            doc: Any = {
                "inputs": rec.inputs,
                "output": rec.output,
                "attributes": rec.attributes,
                "summary": rec.summary,
            }
            consumed = ""
            for col in ordered:
                rel = col[len(consumed) :].lstrip(".")
                ref_value, _ = _json_extract(doc, split_escaped_field_path(rel))
                resolved = self._resolve_ref_str_for_filter(ref_value)
                if resolved is None:
                    return False if cast_to == "exists" else None
                doc = resolved
                consumed = col
            remainder = field_path[len(consumed) :].lstrip(".")
            parts = split_escaped_field_path(remainder) if remainder else []
            if cast_to == "exists":
                return _ch_json_exists(doc, parts)
            return _ch_cast_json_value(_ch_json_value(doc, parts), cast_to)

        return evaluate

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        digest = compute_file_digest(req.content)
        validate_expected_digest(
            expected=req.expected_digest, actual=digest, label="file"
        )
        with self.lock:
            self._files.setdefault((req.project_id, digest), req.content)
        return tsi.FileCreateRes(digest=digest)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        with self.lock:
            content = self._files.get((req.project_id, req.digest))
        if content is None:
            raise NotFoundError(f"File {req.digest} not found")
        return tsi.FileContentReadRes(content=content)

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        with self.lock:
            total = sum(
                len(content)
                for (project_id, _digest), content in self._files.items()
                if project_id == req.project_id
            )
        return tsi.FilesStatsRes(total_size_bytes=total)

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------

    def _feedback_row_for_storage(self, row: dict[str, Any]) -> dict[str, Any]:
        """Normalize a freshly created feedback row for storage: created_at
        as a tz-aware datetime (ClickHouse returns DateTime64 values) and the
        payload normalized through JSON serialization.
        """
        stored = dict(row)
        created_at = stored["created_at"]
        if isinstance(created_at, datetime.datetime):
            stored["created_at"] = _ensure_tz(created_at)
        stored["payload"] = json.loads(json.dumps(stored["payload"]))
        for col in (
            "scorer_tags",
            "scorer_tag_reasons",
            "scorer_tag_confidences",
            "scorer_ratings",
            "scorer_rating_reasons",
            "scorer_rating_confidences",
        ):
            stored[col] = json.loads(json.dumps(stored.get(col)))
        return stored

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        assert_non_null_wb_user_id(req)
        validate_feedback_create_req(req, self)

        processed_payload = process_feedback_payload(req)
        row = format_feedback_to_row(req, processed_payload)
        with self.lock:
            self._feedback.append(self._feedback_row_for_storage(row))

        return format_feedback_to_res(row)

    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        rows_to_insert = []
        results = []

        for feedback_req in req.batch:
            assert_non_null_wb_user_id(feedback_req)
            validate_feedback_create_req(feedback_req, self)

            processed_payload = process_feedback_payload(feedback_req)
            row = format_feedback_to_row(feedback_req, processed_payload)
            rows_to_insert.append(row)
            results.append(format_feedback_to_res(row))

        if rows_to_insert:
            with self.lock:
                for row in rows_to_insert:
                    self._feedback.append(self._feedback_row_for_storage(row))

        return tsi.FeedbackCreateBatchRes(res=results)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        with self.lock:
            rows = list(self._feedback)
        result = _orm_select(
            TABLE_FEEDBACK,
            rows,
            project_id=req.project_id,
            fields=req.fields,
            query=req.query,
            sort_by=req.sort_by,
            limit=req.limit,
            offset=req.offset,
        )
        return tsi.FeedbackQueryRes(result=result)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        validate_feedback_purge_req(req)
        with self.lock:
            keep = []
            for row in self._feedback:
                if row["project_id"] == req.project_id and _truthy(
                    _orm_eval_query(TABLE_FEEDBACK, row, req.query)
                ):
                    continue
                keep.append(row)
            self._feedback = keep
        return tsi.FeedbackPurgeRes()

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        # Validate the replacement payload before purging — if validation
        # rejects we want the old row preserved, not destroyed.
        create_req = tsi.FeedbackCreateReq(**req.model_dump(exclude={"feedback_id"}))
        validate_feedback_create_req(create_req, self)
        purge_request = tsi.FeedbackPurgeReq(
            project_id=req.project_id,
            query={
                "$expr": {
                    "$eq": [
                        {"$getField": "id"},
                        {"$literal": req.feedback_id},
                    ],
                }
            },
        )
        self.feedback_purge(purge_request)
        create_result = self.feedback_create(create_req)

        return tsi.FeedbackReplaceRes(
            id=create_result.id,
            created_at=create_result.created_at,
            wb_user_id=create_result.wb_user_id,
            payload=create_result.payload,
        )

    def _fetch_feedback_stats_rows(
        self,
        project_id: str,
        start: datetime.datetime,
        end: datetime.datetime,
        feedback_type: str | None = None,
        trigger_ref: str | None = None,
    ) -> list[tuple[str, str]]:
        """(created_at, payload_dump) tuples for the stats window."""
        with self.lock:
            rows = list(self._feedback)
        result: list[tuple[Any, str]] = []
        for row in rows:
            if row["project_id"] != project_id:
                continue
            created_at = row["created_at"]
            if not (_ensure_tz(start) <= created_at < _ensure_tz(end)):
                continue
            if feedback_type is not None and row["feedback_type"] != feedback_type:
                continue
            if trigger_ref is not None:
                row_trigger = row.get("trigger_ref")
                if trigger_ref.endswith(":*"):
                    if row_trigger is None or not row_trigger.startswith(
                        trigger_ref[:-2]
                    ):
                        continue
                elif row_trigger != trigger_ref:
                    continue
            result.append((created_at, json.dumps(row["payload"])))
        return result

    def feedback_stats(self, req: tsi.FeedbackStatsReq) -> tsi.FeedbackStatsRes:
        """Compute feedback stats: a per-time-bucket series plus a window-wide
        rollup, mirroring the ClickHouse stats query.
        """
        # ---- Resolve the window and bucket granularity ----
        end = req.end or datetime.datetime.now(datetime.timezone.utc)
        if not req.metrics:
            return tsi.FeedbackStatsRes(
                start=req.start,
                end=end,
                granularity=GRANULARITY_1H,
                timezone=req.timezone or "UTC",
                buckets=[],
            )

        start = req.start
        if start.tzinfo is None:
            start = start.replace(tzinfo=datetime.timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=datetime.timezone.utc)

        time_range = end - start
        granularity = req.granularity or auto_select_granularity_seconds(time_range)
        granularity = ensure_max_buckets(granularity, time_range.total_seconds())

        # ---- Load the matching rows and bin each metric's values ----
        rows = self._fetch_feedback_stats_rows(
            req.project_id,
            start,
            end,
            req.feedback_type,
            req.trigger_ref,
        )
        metrics = [m for m in req.metrics if m.aggregations or m.percentiles]

        bucket_data: dict[datetime.datetime, dict[str, list[Any]]] = {}
        bucket_counts: dict[datetime.datetime, int] = {}
        all_values: dict[str, list[Any]] = {m.json_path: [] for m in metrics}

        for created_at_value, payload_str in rows:
            ts = (
                created_at_value
                if isinstance(created_at_value, datetime.datetime)
                else _parse_feedback_row_ts(created_at_value)
            )
            bk = _stats_bucket_key(_ensure_tz(ts), start, granularity)
            if bk not in bucket_data:
                bucket_data[bk] = {m.json_path: [] for m in metrics}
            bucket_counts[bk] = bucket_counts.get(bk, 0) + 1
            for m in metrics:
                val = _extract_stats_value(payload_str or "", m.json_path, m.value_type)
                if val is not None:
                    bucket_data[bk][m.json_path].append(val)
                    all_values[m.json_path].append(val)

        # ---- Emit one row per bucket, including empty buckets (count 0) ----
        all_bucket_starts = []
        t = start
        while t < end:
            all_bucket_starts.append(t)
            t += datetime.timedelta(seconds=granularity)

        buckets: list[dict[str, Any]] = []
        for bk in all_bucket_starts:
            row_dict: dict[str, Any] = {"timestamp": bk}
            for m in metrics:
                slug = m.json_path.replace(".", "_")
                vals = bucket_data.get(bk, {}).get(m.json_path, [])
                if m.value_type == "boolean":
                    bool_vals = vals
                    for agg in m.aggregations or []:
                        if agg.value == "count_true":
                            row_dict[f"count_true_{slug}"] = sum(
                                1 for v in bool_vals if v is True
                            )
                        elif agg.value == "count_false":
                            row_dict[f"count_false_{slug}"] = sum(
                                1 for v in bool_vals if v is False
                            )
                else:
                    numeric_vals = [float(v) for v in vals if v is not None]
                    for agg in m.aggregations or []:
                        row_dict[f"{agg.value}_{slug}"] = _compute_stats_agg(
                            numeric_vals, agg.value
                        )
                    for pct in m.percentiles or []:
                        key = f"p{pct:g}"
                        row_dict[f"{key}_{slug}"] = _compute_stats_percentile(
                            numeric_vals, pct
                        )
            row_dict["count"] = bucket_counts.get(bk, 0)
            buckets.append(row_dict)

        # ---- Roll the same aggregations up over the whole window ----
        window_stats: dict[str, dict[str, float | None]] | None = None
        has_window_aggs = any(m.aggregations or m.percentiles for m in metrics)
        if has_window_aggs:
            window_stats = {}
            for m in metrics:
                slug = m.json_path.replace(".", "_")
                vals = all_values[m.json_path]
                stat: dict[str, float | None] = {}
                if m.value_type == "boolean":
                    for agg in m.aggregations or []:
                        if agg.value == "count_true":
                            stat["count_true"] = float(
                                sum(1 for v in vals if v is True)
                            )
                        elif agg.value == "count_false":
                            stat["count_false"] = float(
                                sum(1 for v in vals if v is False)
                            )
                else:
                    numeric_vals = [float(v) for v in vals if v is not None]
                    for agg in m.aggregations or []:
                        stat[agg.value] = _compute_stats_agg(numeric_vals, agg.value)
                    for pct in m.percentiles or []:
                        key = f"p{pct:g}"
                        stat[key] = _compute_stats_percentile(numeric_vals, pct)
                window_stats[slug] = stat

        return tsi.FeedbackStatsRes(
            start=start,
            end=end,
            granularity=granularity,
            timezone=req.timezone or "UTC",
            buckets=buckets,
            window_stats=window_stats,
        )

    def feedback_aggregate(
        self, req: tsi.FeedbackAggregateReq
    ) -> tsi.FeedbackAggregateRes:
        """Mirror build_feedback_aggregate_query evaluated over stored rows:
        the same WHERE filters, time-bucket/group_by keys, and sumMap-style
        per-key tallies. Like ClickHouse, a query with no grouping keys at
        all returns exactly one global rollup row.
        """
        # ---- Fetch the matching feedback rows ----
        with self.lock:
            rows = [
                row for row in self._feedback if _feedback_aggregate_matches(row, req)
            ]

        # ---- Group rows by time bucket and group_by dimensions ----
        bucket_seconds = req.time_bucket_seconds
        bucketed = bucket_seconds is not None
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for row in rows:
            key: list[Any] = []
            if bucket_seconds is not None:
                epoch_s = row["created_at"].timestamp()
                bucket_start_s = int(epoch_s // bucket_seconds) * bucket_seconds
                key.append(bucket_start_s * 1000)
            for dimension in req.group_by:
                key.append(_feedback_aggregate_dimension(row, dimension))
            groups.setdefault(tuple(key), []).append(row)

        if not bucketed and not req.group_by:
            # No GROUP BY keys: ClickHouse global aggregation always yields
            # one row, even over an empty selection.
            groups.setdefault((), [])

        # ---- Order the groups: by bucket for a time series, else by dimensions ----
        if bucketed:
            ordered_keys = sorted(groups, key=lambda group_key: group_key[0])
        else:
            ordered_keys = sorted(groups)

        # ---- Tally tags/ratings per group into output buckets ----
        buckets: list[tsi.FeedbackAggregateBucket] = []
        for group_key in ordered_keys:
            group_rows = groups[group_key]
            tag_counts: dict[str, int] = {}
            rating_sums: dict[str, float] = {}
            rating_counts: dict[str, int] = {}
            scored_count = 0
            for row in group_rows:
                tags = row.get("scorer_tags") or []
                ratings = row.get("scorer_ratings") or {}
                if tags or ratings:
                    scored_count += 1
                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
                for rating_key, rating_value in ratings.items():
                    rating_sums[rating_key] = rating_sums.get(rating_key, 0.0) + float(
                        rating_value
                    )
                    rating_counts[rating_key] = rating_counts.get(rating_key, 0) + 1
            dims = group_key[1:] if bucketed else group_key
            buckets.append(
                tsi.FeedbackAggregateBucket(
                    time_bucket_start_ms=group_key[0] if bucketed else None,
                    group={
                        dimension: str(value)
                        for dimension, value in zip(req.group_by, dims, strict=True)
                    },
                    total_count=len(group_rows),
                    scored_count=scored_count,
                    tag_counts=tag_counts,
                    rating_counts=rating_counts,
                    rating_sums=rating_sums,
                )
            )

        return tsi.FeedbackAggregateRes(
            time_bucket_seconds=req.time_bucket_seconds,
            after_ms=req.after_ms,
            before_ms=req.before_ms,
            buckets=buckets,
        )

    def feedback_payload_schema(
        self, req: tsi.FeedbackPayloadSchemaReq
    ) -> tsi.FeedbackPayloadSchemaRes:
        end = req.end or datetime.datetime.now(datetime.timezone.utc)
        start = req.start
        if start.tzinfo is None:
            start = start.replace(tzinfo=datetime.timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=datetime.timezone.utc)

        rows = self._fetch_feedback_stats_rows(
            req.project_id,
            start,
            end,
            req.feedback_type,
            req.trigger_ref,
        )
        payload_strs = [row[1] for row in rows if row[1]]
        if req.sample_limit and len(payload_strs) > req.sample_limit:
            payload_strs = payload_strs[: req.sample_limit]

        paths = discover_payload_schema(payload_strs)
        return tsi.FeedbackPayloadSchemaRes(paths=paths)

    # ------------------------------------------------------------------
    # Costs API
    # ------------------------------------------------------------------

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        assert_non_null_wb_user_id(req)
        created_at = _serialize_cost_datetime(
            datetime.datetime.now(datetime.timezone.utc)
        )

        created_costs: list[tuple[str, str]] = []
        with self.lock:
            for llm_id, cost in req.costs.items():
                cost_id = generate_id()
                row = {
                    "id": cost_id,
                    "pricing_level": PRICING_LEVELS["PROJECT"],
                    "pricing_level_id": req.project_id,
                    "provider_id": cost.provider_id or "default",
                    "llm_id": llm_id,
                    "effective_date": _serialize_cost_datetime(
                        cost.effective_date
                        or datetime.datetime.now(datetime.timezone.utc)
                    ),
                    "prompt_token_cost": cost.prompt_token_cost,
                    "completion_token_cost": cost.completion_token_cost,
                    "prompt_token_cost_unit": cost.prompt_token_cost_unit or "USD",
                    "completion_token_cost_unit": cost.completion_token_cost_unit
                    or "USD",
                    "created_by": req.wb_user_id,
                    "created_at": created_at,
                }
                self._llm_token_prices.append(row)
                created_costs.append((cost_id, llm_id))
        return tsi.CostCreateRes(ids=created_costs)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        expr = {
            "$and": [
                (
                    req.query.expr_
                    if req.query
                    else {
                        "$eq": [
                            {"$getField": "pricing_level_id"},
                            {"$literal": req.project_id},
                        ],
                    }
                ),
                {
                    "$eq": [
                        {"$getField": "pricing_level"},
                        {"$literal": PRICING_LEVELS["PROJECT"]},
                    ],
                },
            ]
        }
        query_with_pricing_level = tsi.Query(**{"$expr": expr})
        with self.lock:
            rows = [dict(row) for row in self._llm_token_prices]
        results = _orm_select(
            LLM_TOKEN_PRICES_TABLE,
            rows,
            project_id=None,
            fields=req.fields,
            query=query_with_pricing_level,
            sort_by=req.sort_by,
            limit=req.limit,
            offset=req.offset,
        )
        return tsi.CostQueryRes(results=results)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        validate_cost_purge_req(req)
        expr = {
            "$and": [
                req.query.expr_,
                {
                    "$eq": [
                        {"$getField": "pricing_level_id"},
                        {"$literal": req.project_id},
                    ],
                },
                {
                    "$eq": [
                        {"$getField": "pricing_level"},
                        {"$literal": PRICING_LEVELS["PROJECT"]},
                    ],
                },
            ]
        }
        query_with_pricing_level = tsi.Query(**{"$expr": expr})
        with self.lock:
            self._llm_token_prices = [
                row
                for row in self._llm_token_prices
                if not _truthy(
                    _orm_eval_query(
                        LLM_TOKEN_PRICES_TABLE, row, query_with_pricing_level
                    )
                )
            ]
        return tsi.CostPurgeRes()

    # ------------------------------------------------------------------
    # LLM completions / image generation (mirrors ClickHouse: completions
    # persist agent spans; image generation persists a call)
    # ------------------------------------------------------------------

    def _insert_agent_span(self, span: Any) -> None:
        """ReplacingMergeTree semantics: same span_id replaces the row."""
        with self.lock:
            self._agent_spans[span.span_id] = span

    def agent_spans_query(self, req: AgentSpansQueryReq) -> AgentSpansQueryRes:
        """Minimal spans query: project-scoped, newest first."""
        schema_fields = set(AgentSpanSchema.model_fields)
        with self.lock:
            spans = [
                span
                for span in self._agent_spans.values()
                if span.project_id == req.project_id
            ]
        spans.sort(key=lambda span: _ensure_tz(span.started_at), reverse=True)
        total = len(spans)
        if req.offset:
            spans = spans[req.offset :]
        if req.limit is not None:
            spans = spans[: req.limit]
        results = []
        for span in spans:
            data = {
                key: value
                for key, value in span.model_dump().items()
                if key in schema_fields
            }
            results.append(AgentSpanSchema(**data))
        return AgentSpansQueryRes(spans=results, total_count=total)

    def _prepare_completion_request(
        self, req: tsi.CompletionsCreateReq
    ) -> CompletionPrepResult | tsi.CompletionsCreateRes:
        """Resolve prompt + model info, or return a short-circuit error
        response (mirrors the ClickHouse implementation).
        """
        prompt = req.inputs.prompt
        template_vars = req.inputs.template_vars
        initial_messages = req.inputs.messages or []

        if prompt:
            try:
                combined_messages, initial_messages = resolve_and_apply_prompt(
                    prompt=prompt,
                    messages=req.inputs.messages,
                    template_vars=template_vars,
                    project_id=req.project_id,
                    obj_read_func=self.obj_read,
                )
                req.inputs.messages = combined_messages
            except Exception as e:
                logger.exception("Failed to resolve prompt")
                return tsi.CompletionsCreateRes(
                    response={"error": f"Failed to resolve prompt: {e!s}"}
                )

        model_info = _model_to_provider_info_map().get(req.inputs.model)
        try:
            completion_model_info = _setup_completion_model_info(
                model_info, req, self.obj_read
            )
        except Exception as e:
            return tsi.CompletionsCreateRes(response={"error": str(e)})

        return CompletionPrepResult(initial_messages, completion_model_info)

    def _log_completion_span(
        self,
        req: tsi.CompletionsCreateReq,
        prep: CompletionPrepResult,
        response: dict[str, Any] | None,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        span_id: str,
        trace_id: str,
        conversation_id: str,
    ) -> None:
        """Build a completion span from the request + response and insert it.

        Called with response=None to open a span before a stream, then again to
        close it.
        """
        retention_days = self._get_project_retention_days(req.project_id)
        span = build_completion_span(
            project_id=req.project_id,
            trace_id=trace_id,
            span_id=span_id,
            conversation_id=conversation_id,
            conversation_name=req.conversation_name or "",
            started_at=start_time,
            ended_at=end_time,
            provider_name=prep.completion_model_info.provider or "",
            model_name=prep.completion_model_info.model_name,
            request_inputs=req.inputs,
            response=response if response is not None else None,
            wb_user_id=req.wb_user_id or "",
            retention_days=retention_days,
            error=(response or {}).get("error"),
            source=req.source,
        )
        self._insert_agent_span(span)

    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        """Non-streaming completion: prepare the request, call the provider
        (LiteLLM), and — when tracking is on — log a span and return its ids.
        """
        prep = self._prepare_completion_request(req)
        if isinstance(prep, tsi.CompletionsCreateRes):
            return prep

        info = prep.completion_model_info
        start_time = datetime.datetime.now()
        res = lite_llm_completion(
            api_key=info.api_key,
            inputs=req.inputs,
            provider=info.provider,
            base_url=info.base_url,
            extra_headers=info.extra_headers,
            vertex_credentials=info.vertex_credentials,
        )
        end_time = datetime.datetime.now()

        if not req.track_llm_call:
            return tsi.CompletionsCreateRes(response=res.response)

        req.inputs.messages = prep.initial_messages
        span_id = generate_id()
        trace_id = req.trace_id or generate_id()
        conversation_id = req.conversation_id or generate_id()
        self._log_completion_span(
            req,
            prep,
            res.response,
            start_time,
            end_time,
            span_id,
            trace_id,
            conversation_id,
        )
        return tsi.CompletionsCreateRes(
            response=res.response,
            weave_call_id=span_id,
            span_id=span_id,
            trace_id=trace_id,
            conversation_id=conversation_id,
        )

    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        """Streaming completion: open a span up front, stream the provider's
        chunks to the caller, then close the span from the aggregated chunks
        (or error) once the stream finishes.
        """
        prep = self._prepare_completion_request(req)
        if isinstance(prep, tsi.CompletionsCreateRes):
            error_response = prep.response

            def error_iter() -> Iterator[dict[str, Any]]:
                yield error_response

            return error_iter()

        info = prep.completion_model_info
        start_time = datetime.datetime.now()

        span_id = generate_id()
        trace_id = req.trace_id or generate_id()
        conversation_id = req.conversation_id or generate_id()

        if req.track_llm_call:
            # Open span (UNSET status) written before the stream starts.
            req.inputs.messages = prep.initial_messages
            self._log_completion_span(
                req,
                prep,
                None,
                start_time,
                SENTINEL_EPOCH,
                span_id,
                trace_id,
                conversation_id,
            )

        api_inputs = req.inputs.model_copy(deep=True)
        api_inputs.prompt = None
        api_inputs.template_vars = None
        chunk_iter = lite_llm_completion_stream(
            api_key=info.api_key,
            inputs=api_inputs,
            provider=info.provider,
            base_url=info.base_url,
            extra_headers=info.extra_headers,
            return_type=info.return_type,
            vertex_credentials=info.vertex_credentials,
        )

        if not req.track_llm_call:
            return chunk_iter

        req.inputs.messages = prep.initial_messages

        def tracked() -> Iterator[dict[str, Any]]:
            yield {
                "_meta": {
                    "weave_call_id": span_id,
                    "span_id": span_id,
                    "trace_id": trace_id,
                    "conversation_id": conversation_id,
                }
            }
            chunks: list[dict[str, Any]] = []
            stream_error: str | None = None
            try:
                for chunk in chunk_iter:
                    if "error" in chunk and "choices" not in chunk:
                        stream_error = str(chunk["error"])
                    chunks.append(chunk)
                    yield chunk
            except Exception as exc:
                stream_error = str(exc)
                raise
            finally:
                aggregated = _aggregate_stream_chunks(
                    chunks, prep.completion_model_info.model_name
                )
                if stream_error is not None:
                    aggregated["error"] = stream_error
                self._log_completion_span(
                    req,
                    prep,
                    aggregated,
                    start_time,
                    datetime.datetime.now(),
                    span_id,
                    trace_id,
                    conversation_id,
                )

        return tracked()

    def image_create(
        self, req: tsi.ImageGenerationCreateReq
    ) -> tsi.ImageGenerationCreateRes:
        """Image generation: validate inputs and credentials, call the provider,
        and — when tracking is on — log it as a call.
        """
        if req.inputs.model is None:
            return tsi.ImageGenerationCreateRes(
                response={"error": "No model specified in request"}
            )
        if req.inputs.prompt is None:
            return tsi.ImageGenerationCreateRes(
                response={"error": "No prompt specified in request"}
            )

        secret_fetcher = _secret_fetcher_context.get()
        if secret_fetcher is None:
            return tsi.ImageGenerationCreateRes(
                response={
                    "error": "Unable to access required credentials for image generation"
                }
            )
        api_key = (
            secret_fetcher.fetch("OPENAI_API_KEY")
            .get("secrets", {})
            .get("OPENAI_API_KEY")
        )
        if not api_key:
            return tsi.ImageGenerationCreateRes(
                response={"error": "No OpenAI API key found"}
            )

        start_time = datetime.datetime.now(datetime.timezone.utc)
        try:
            res = lite_llm_image_generation(
                api_key=api_key,
                inputs=req.inputs.model_dump(exclude_none=True),
                trace_server=self,
                project_id=req.project_id,
                wb_user_id=req.wb_user_id,
            )
        except Exception as e:
            return tsi.ImageGenerationCreateRes(
                response={"error": f"Image generation failed: {e}"}
            )
        if "error" in res.response:
            return res
        end_time = datetime.datetime.now(datetime.timezone.utc)

        if not req.track_llm_call:
            return res

        call_id = generate_id()
        trace_id = generate_id()
        start = tsi.StartedCallSchemaForInsert(
            project_id=req.project_id,
            id=call_id,
            trace_id=trace_id,
            op_name=constants.IMAGE_GENERATION_CREATE_OP_NAME,
            started_at=start_time,
            attributes={},
            inputs=req.inputs.model_dump(exclude_none=False),
            wb_user_id=req.wb_user_id,
        )
        end = tsi.EndedCallSchemaForInsert(
            project_id=req.project_id,
            id=call_id,
            ended_at=end_time,
            output=res.response,
            summary={},
        )
        if "usage" in res.response:
            end.summary["usage"] = {req.inputs.model: res.response["usage"]}
        if "error" in res.response:
            end.exception = res.response["error"]
        try:
            self.call_start(tsi.CallStartReq(start=start))
            self.call_end(tsi.CallEndReq(end=end))
        except Exception:
            logger.exception("Failed to track image generation call")

        return tsi.ImageGenerationCreateRes(
            response=res.response, weave_call_id=call_id
        )

    # ------------------------------------------------------------------
    # OTel export
    # ------------------------------------------------------------------

    def otel_export(self, req: tsi.OTelExportReq) -> tsi.OTelExportRes:
        calls: list[tsi.CallBatchStartMode | tsi.CallBatchEndMode] = []
        rejected_spans = 0
        error_messages: list[str] = []
        for processed_span in req.processed_spans:
            wb_run_id = processed_span.run_id

            if not isinstance(processed_span.resource_spans, ResourceSpans):
                raise TypeError(
                    f"Expected resource_spans as ResourceSpans, got {type(processed_span.resource_spans)}"
                )

            proto_resource_spans = processed_span.resource_spans
            resource = Resource.from_proto(proto_resource_spans.resource)
            for proto_scope_spans in proto_resource_spans.scope_spans:
                for proto_span in proto_scope_spans.spans:
                    try:
                        span = Span.from_proto(proto_span, resource)
                    except AttributePathConflictError as e:
                        rejected_spans += 1
                        try:
                            trace_id = proto_span.trace_id.hex()
                            span_id = proto_span.span_id.hex()
                            name = getattr(proto_span, "name", "")
                        except Exception:
                            trace_id = ""
                            span_id = ""
                            name = ""
                        span_ident = (
                            f"name='{name}' trace_id='{trace_id}' span_id='{span_id}'"
                        )
                        error_messages.append(f"Rejected span ({span_ident}): {e!s}")
                        continue

                    start_call, end_call = span.to_call(
                        req.project_id,
                        wb_user_id=req.wb_user_id,
                        wb_run_id=wb_run_id,
                    )
                    # ClickHouse resolves span names to op objects and stores
                    # op refs as op_name; placeholder ops are content-
                    # addressed so repeats dedupe.
                    op_res = self.op_create(
                        tsi.OpCreateReq(
                            project_id=req.project_id,
                            name=start_call.op_name,
                        )
                    )
                    start_call.op_name = ri.InternalOpRef(
                        project_id=req.project_id,
                        name=op_res.object_id,
                        version=op_res.digest,
                    ).uri
                    calls.extend(
                        [
                            tsi.CallBatchStartMode(
                                req=tsi.CallStartReq(start=start_call)
                            ),
                            tsi.CallBatchEndMode(req=tsi.CallEndReq(end=end_call)),
                        ]
                    )
        self.call_start_batch(tsi.CallCreateBatchReq(batch=calls))
        if rejected_spans > 0:
            return tsi.OTelExportRes(
                partial_success=tsi.ExportTracePartialSuccess(
                    rejected_spans=rejected_spans,
                    error_message=(
                        "; ".join(error_messages[:MAX_OTEL_ERROR_MESSAGES])
                        + (
                            "; ..."
                            if len(error_messages) > MAX_OTEL_ERROR_MESSAGES
                            else ""
                        )
                    ),
                )
            )
        return tsi.OTelExportRes()

    # ------------------------------------------------------------------
    # Project stats / TTL settings
    # ------------------------------------------------------------------

    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        def _default_true(val: bool | None) -> bool:
            return True if val is None else val

        include_trace = _default_true(req.include_trace_storage_size)
        include_objects = _default_true(req.include_object_storage_size)
        include_tables = _default_true(req.include_table_storage_size)
        include_files = _default_true(req.include_file_storage_size)
        if not any((include_trace, include_objects, include_tables, include_files)):
            raise ValueError(
                "At least one of include_trace_storage_size, "
                "include_objects_storage_size, include_tables_storage_size, or "
                "include_files_storage_size must be True"
            )

        kwargs: dict[str, int] = {}
        with self.lock:
            if include_trace:
                kwargs["trace_storage_size_bytes"] = sum(
                    (rec.attributes_len or 0)
                    + (rec.inputs_len or 0)
                    + (rec.output_len or 0)
                    + (rec.summary_len or 0)
                    + (rec.otel_dump_len or 0)
                    for rec in self._calls.values()
                    if rec.project_id == req.project_id
                )
            if include_objects:
                kwargs["objects_storage_size_bytes"] = sum(
                    rec.val_dump_len
                    for rec in self._objs.values()
                    if rec.project_id == req.project_id
                )
            if include_tables:
                kwargs["tables_storage_size_bytes"] = sum(
                    rec.val_dump_len
                    for rec in self._table_rows.values()
                    if rec.project_id == req.project_id
                )
            if include_files:
                kwargs["files_storage_size_bytes"] = sum(
                    len(content)
                    for (project_id, _digest), content in self._files.items()
                    if project_id == req.project_id
                )
        return tsi.ProjectStatsRes(**kwargs)

    def project_ttl_settings_read(
        self, req: tsi.ProjectTTLSettingsReadReq
    ) -> tsi.ProjectTTLSettingsReadRes:
        stored_days = self._get_project_retention_days(req.project_id)
        return tsi.ProjectTTLSettingsReadRes(
            retention_days=stored_days if stored_days != RETENTION_DAYS_NO_TTL else None
        )

    def project_ttl_settings_update(
        self, req: tsi.ProjectTTLSettingsUpdateReq
    ) -> tsi.ProjectTTLSettingsUpdateRes:
        if req.retention_days is not None and req.retention_days < 1:
            raise InvalidRequest(
                "retention_days must be None (no TTL) or >= 1 (days of retention)"
            )
        if not req.wb_user_id:
            raise InvalidRequest("wb_user_id is required for audit trail")

        stored_days = (
            RETENTION_DAYS_NO_TTL if req.retention_days is None else req.retention_days
        )
        updated_at = datetime.datetime.now(datetime.timezone.utc)
        with self.lock:
            self._ttl_settings.append(
                _TtlRec(
                    project_id=req.project_id,
                    retention_days=stored_days,
                    updated_at=updated_at,
                    updated_by=req.wb_user_id,
                )
            )
        invalidate_ttl_cache(req.project_id)
        return tsi.ProjectTTLSettingsUpdateRes(retention_days=req.retention_days)

    # ------------------------------------------------------------------
    # Threads
    # ------------------------------------------------------------------

    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        """Stream threads with aggregated statistics, mirroring
        make_threads_query: aggregates over turn calls (id == turn_id) with
        argMin/argMax turn ids and interpolated turn-duration quantiles.
        """
        # ---- Select turn calls (id == turn_id) in the window for the requested threads ----
        after_datetime = None
        before_datetime = None
        thread_ids = None
        if req.filter is not None:
            after_datetime = req.filter.after_datetime
            before_datetime = req.filter.before_datetime
            thread_ids = req.filter.thread_ids

        with self.lock:
            turn_calls = [
                rec
                for rec in self._calls.values()
                if rec.project_id == req.project_id and rec.id == rec.turn_id
            ]

        # End-only part-merge stubs have no started_at and are invisible
        # to reads, mirroring calls_query.
        turn_calls = [rec for rec in turn_calls if rec.started_at is not None]
        if after_datetime is not None:
            after_dt = _ensure_tz(after_datetime)
            turn_calls = [
                rec
                for rec in turn_calls
                if rec.started_at is not None and rec.started_at > after_dt
            ]
        if before_datetime is not None:
            before_dt = _ensure_tz(before_datetime)
            turn_calls = [
                rec
                for rec in turn_calls
                if rec.started_at is not None and rec.started_at < before_dt
            ]

        if thread_ids is not None and len(thread_ids) > 0:
            turn_calls = [rec for rec in turn_calls if rec.thread_id in thread_ids]
        else:
            turn_calls = [
                rec
                for rec in turn_calls
                if rec.thread_id is not None and rec.thread_id != ""
            ]

        # ---- Group turn calls by thread ----
        grouped: dict[str | None, list[_CallRec]] = {}
        for rec in turn_calls:
            grouped.setdefault(rec.thread_id, []).append(rec)

        # ---- Aggregate per-thread stats (span, first/last turn, duration quantiles) ----
        threads: list[dict[str, Any]] = []
        for thread_id, recs in grouped.items():
            starts = [
                (rec.started_at, rec.id) for rec in recs if rec.started_at is not None
            ]
            ends = [(rec.ended_at, rec.id) for rec in recs if rec.ended_at is not None]
            start_time = min(start for start, _ in starts)
            first_turn_id = min(starts, key=lambda pair: pair[0])[1]
            last_updated = max(end for end, _ in ends) if ends else None
            last_turn_id = (
                max(ends, key=lambda pair: pair[0])[1] if ends else recs[0].id
            )
            durations = sorted(
                (rec.ended_at - rec.started_at).total_seconds() * 1000.0
                for rec in recs
                if rec.ended_at is not None and rec.started_at is not None
            )
            threads.append(
                {
                    "thread_id": thread_id,
                    "turn_count": len(recs),
                    "start_time": start_time,
                    "last_updated": last_updated,
                    "first_turn_id": first_turn_id,
                    "last_turn_id": last_turn_id,
                    "p50_turn_duration_ms": _interpolated_quantile(durations, 0.5),
                    "p99_turn_duration_ms": _interpolated_quantile(durations, 0.99),
                }
            )

        # ---- Sort and paginate ----
        valid_sort_fields = {
            "thread_id",
            "turn_count",
            "start_time",
            "last_updated",
            "p50_turn_duration_ms",
            "p99_turn_duration_ms",
        }
        if req.sort_by:
            sort_terms = []
            for sort in req.sort_by:
                if sort.field not in valid_sort_fields:
                    raise ValueError(
                        f"Unsupported sort field: {sort.field}. Supported fields: {list(valid_sort_fields)}"
                    )
                sort_terms.append((sort.field, sort.direction))
        else:
            sort_terms = [("last_updated", "desc")]

        threads = _ch_sorted_by_terms(threads, sort_terms, lambda row, term: row[term])

        if req.offset is not None and req.offset > 0:
            threads = threads[req.offset :]
        if req.limit is not None and req.limit >= 0:
            threads = threads[: req.limit]

        # ---- Stream the surviving threads ----
        for thread in threads:
            start_time = thread["start_time"]
            last_updated = thread["last_updated"]
            if start_time is None or last_updated is None:
                # Mirrors the ClickHouse stream: skip threads without valid
                # timestamps.
                continue

            yield tsi.ThreadSchema(
                thread_id=thread["thread_id"],
                turn_count=thread["turn_count"],
                start_time=_ensure_tz(start_time),
                last_updated=_ensure_tz(last_updated),
                first_turn_id=thread["first_turn_id"],
                last_turn_id=thread["last_turn_id"],
                p50_turn_duration_ms=thread["p50_turn_duration_ms"],
                p99_turn_duration_ms=thread["p99_turn_duration_ms"],
            )

    # ------------------------------------------------------------------
    # Annotation queues (mirrors the ClickHouse implementation: one mutable
    # record per id, soft-deleted via deleted_at tombstones)
    # ------------------------------------------------------------------

    _QUEUE_SORT_FIELDS = frozenset({"id", "name", "created_at", "updated_at"})
    _QUEUE_ITEM_SORT_FIELDS = frozenset(
        {"call_started_at", "call_op_name", "created_at", "updated_at"}
    )

    def _queue_to_schema(self, queue: dict[str, Any]) -> tsi.AnnotationQueueSchema:
        """Convert an internal queue dict to its API schema (tz-normalizing timestamps)."""
        return tsi.AnnotationQueueSchema(
            id=queue["id"],
            project_id=queue["project_id"],
            name=queue["name"],
            description=queue["description"] or "",
            scorer_refs=list(queue["scorer_refs"]),
            created_at=_ensure_tz(queue["created_at"]),
            created_by=queue["created_by"],
            updated_at=_ensure_tz(queue["updated_at"]),
            deleted_at=queue["deleted_at"],
        )

    def _live_queue(self, project_id: str, queue_id: str) -> dict[str, Any] | None:
        """Fetch a queue only if it exists, belongs to the project, and isn't soft-deleted."""
        queue = self._annotation_queues.get(queue_id)
        if (
            queue is None
            or queue["project_id"] != project_id
            or queue["deleted_at"] is not None
        ):
            return None
        return queue

    def annotation_queue_create(
        self, req: tsi.AnnotationQueueCreateReq
    ) -> tsi.AnnotationQueueCreateRes:
        """Create a new annotation queue."""
        assert_non_null_wb_user_id(req)
        queue_id = generate_id()
        now = datetime.datetime.now(datetime.timezone.utc)
        with self.lock:
            self._annotation_queues[queue_id] = {
                "id": queue_id,
                "project_id": req.project_id,
                "name": req.name,
                "description": req.description,
                "scorer_refs": list(req.scorer_refs),
                "created_at": now,
                "created_by": req.wb_user_id,
                "updated_at": now,
                "deleted_at": None,
            }
        return tsi.AnnotationQueueCreateRes(id=queue_id)

    def annotation_queues_query_stream(
        self, req: tsi.AnnotationQueuesQueryReq
    ) -> Iterator[tsi.AnnotationQueueSchema]:
        """List a project's live queues: optional name filter, then sort and paginate."""
        with self.lock:
            queues = [
                queue
                for queue in self._annotation_queues.values()
                if queue["project_id"] == req.project_id and queue["deleted_at"] is None
            ]
        if req.name:
            needle = req.name.lower()
            queues = [q for q in queues if needle in q["name"].lower()]

        sort_terms: list[tuple[str, str]] = []
        if req.sort_by:
            for sort in req.sort_by:
                if sort.field in self._QUEUE_SORT_FIELDS and sort.direction.lower() in {
                    "asc",
                    "desc",
                }:
                    sort_terms.append((sort.field, sort.direction))
        if sort_terms:
            sort_terms.append(("id", "asc"))
        else:
            sort_terms = [("created_at", "desc"), ("id", "asc")]
        queues = _ch_sorted_by_terms(queues, sort_terms, lambda q, term: q[term])

        if req.offset is not None and req.offset > 0:
            queues = queues[req.offset :]
        if req.limit is not None and req.limit >= 0:
            queues = queues[: req.limit]

        for queue in queues:
            if queue["created_at"] is None or queue["updated_at"] is None:
                continue
            yield self._queue_to_schema(queue)

    def annotation_queue_read(
        self, req: tsi.AnnotationQueueReadReq
    ) -> tsi.AnnotationQueueReadRes:
        """Read a single live queue (raises NotFound if missing or deleted)."""
        with self.lock:
            queue = self._live_queue(req.project_id, req.queue_id)
        if queue is None:
            raise NotFoundError(f"Queue {req.queue_id} not found")
        return tsi.AnnotationQueueReadRes(queue=self._queue_to_schema(queue))

    def annotation_queue_update(
        self, req: tsi.AnnotationQueueUpdateReq
    ) -> tsi.AnnotationQueueUpdateRes:
        """Update only the queue fields provided (name / description / scorer_refs)."""
        assert_non_null_wb_user_id(req)
        with self.lock:
            queue = self._live_queue(req.project_id, req.queue_id)
            if queue is None:
                raise NotFoundError(
                    f"Queue {req.queue_id} not found or already deleted"
                )
            if req.name is None and req.description is None and req.scorer_refs is None:
                return tsi.AnnotationQueueUpdateRes(queue=self._queue_to_schema(queue))
            if req.name is not None:
                queue["name"] = req.name
            if req.description is not None:
                queue["description"] = req.description
            if req.scorer_refs is not None:
                queue["scorer_refs"] = list(req.scorer_refs)
            queue["updated_at"] = datetime.datetime.now(datetime.timezone.utc)
            return tsi.AnnotationQueueUpdateRes(queue=self._queue_to_schema(queue))

    def annotation_queue_delete(
        self, req: tsi.AnnotationQueueDeleteReq
    ) -> tsi.AnnotationQueueDeleteRes:
        """Soft-delete a queue; items and progress rows are intentionally left in place."""
        with self.lock:
            queue = self._live_queue(req.project_id, req.queue_id)
            if queue is None:
                raise NotFoundError(
                    f"Queue {req.queue_id} not found or already deleted"
                )
            now = datetime.datetime.now(datetime.timezone.utc)
            queue["deleted_at"] = now
            queue["updated_at"] = now
            # No cascade: items and progress rows stay (mirrors ClickHouse).
            return tsi.AnnotationQueueDeleteRes(queue=self._queue_to_schema(queue))

    def annotation_queue_add_calls(
        self, req: tsi.AnnotationQueueAddCallsReq
    ) -> tsi.AnnotationQueueAddCallsRes:
        """Add calls to a queue as items, skipping calls already queued or missing/deleted."""
        assert_non_null_wb_user_id(req)
        with self.lock:
            existing_call_ids = {
                item["call_id"]
                for item in self._annotation_queue_items.values()
                if item["project_id"] == req.project_id
                and item["queue_id"] == req.queue_id
                and item["deleted_at"] is None
                and item["call_id"] in set(req.call_ids)
            }
            new_call_ids = [
                call_id for call_id in req.call_ids if call_id not in existing_call_ids
            ]
            if not new_call_ids:
                return tsi.AnnotationQueueAddCallsRes(
                    added_count=0, duplicates=len(req.call_ids)
                )

            calls_data = [
                rec
                for call_id in new_call_ids
                if (rec := self._calls.get((req.project_id, call_id))) is not None
                and rec.project_id == req.project_id
                and rec.deleted_at is None
            ]
            if not calls_data:
                return tsi.AnnotationQueueAddCallsRes(
                    added_count=0, duplicates=len(existing_call_ids)
                )

            now = datetime.datetime.now(datetime.timezone.utc)
            for rec in calls_data:
                item_id = generate_id()
                self._annotation_queue_items[item_id] = {
                    "id": item_id,
                    "project_id": req.project_id,
                    "queue_id": req.queue_id,
                    "call_id": rec.id,
                    "call_started_at": rec.started_at,
                    "call_ended_at": rec.ended_at,
                    "call_op_name": rec.op_name or "",
                    "call_trace_id": rec.trace_id or "",
                    "display_fields": list(req.display_fields),
                    "added_by": req.wb_user_id,
                    "created_at": now,
                    "created_by": req.wb_user_id,
                    "updated_at": now,
                    "deleted_at": None,
                }
        return tsi.AnnotationQueueAddCallsRes(
            added_count=len(calls_data), duplicates=len(existing_call_ids)
        )

    def _item_progress_state(self, item_id: str) -> tuple[str, str | None]:
        """Global most-recent state across annotators (argMax by updated_at);
        defaults to 'unstarted' with no annotator.
        """
        progress_rows = [
            row
            for row in self._annotation_progress.values()
            if row["queue_item_id"] == item_id and row["deleted_at"] is None
        ]
        if not progress_rows:
            # ClickHouse String default is the empty string, not NULL.
            return ("unstarted", "")
        latest = max(progress_rows, key=lambda row: row["updated_at"])
        return (latest["annotation_state"], latest["annotator_id"])

    def _queue_item_to_schema(
        self,
        item: dict[str, Any],
        position_in_queue: int | None = None,
    ) -> tsi.AnnotationQueueItemSchema:
        """Convert an item dict to its schema, attaching the computed progress
        state (across annotators) and an optional 1-based queue position.
        """
        state, annotator = self._item_progress_state(item["id"])
        return tsi.AnnotationQueueItemSchema(
            id=item["id"],
            project_id=item["project_id"],
            queue_id=item["queue_id"],
            call_id=item["call_id"],
            call_started_at=item["call_started_at"],
            call_ended_at=item["call_ended_at"],
            call_op_name=item["call_op_name"],
            call_trace_id=item["call_trace_id"],
            display_fields=list(item["display_fields"]),
            added_by=item["added_by"],
            annotation_state=state,
            annotator_user_id=annotator,
            created_at=item["created_at"],
            created_by=item["created_by"],
            updated_at=item["updated_at"],
            deleted_at=item["deleted_at"],
            position_in_queue=position_in_queue,
        )

    def annotation_queue_items_query(
        self, req: tsi.AnnotationQueueItemsQueryReq
    ) -> tsi.AnnotationQueueItemsQueryRes:
        """List a queue's items: field filters, sort, then the annotation-state
        filter (applied after the progress aggregation), optional positions,
        then pagination.
        """
        with self.lock:
            items = [
                item
                for item in self._annotation_queue_items.values()
                if item["project_id"] == req.project_id
                and item["queue_id"] == req.queue_id
                and item["deleted_at"] is None
            ]

        item_filter = req.filter
        if item_filter is not None:
            if item_filter.id is not None:
                items = [i for i in items if i["id"] == item_filter.id]
            if item_filter.call_id is not None:
                items = [i for i in items if i["call_id"] == item_filter.call_id]
            if item_filter.call_op_name is not None:
                items = [
                    i for i in items if i["call_op_name"] == item_filter.call_op_name
                ]
            if item_filter.call_trace_id is not None:
                items = [
                    i for i in items if i["call_trace_id"] == item_filter.call_trace_id
                ]
            if item_filter.added_by is not None:
                items = [i for i in items if i["added_by"] == item_filter.added_by]

        sort_terms: list[tuple[str, str]] = []
        if req.sort_by:
            for sort in req.sort_by:
                if (
                    sort.field in self._QUEUE_ITEM_SORT_FIELDS
                    and sort.direction.lower() in {"asc", "desc"}
                ):
                    sort_terms.append((sort.field, sort.direction))
        if sort_terms:
            sort_terms.append(("id", "asc"))
        else:
            sort_terms = [("created_at", "asc"), ("id", "asc")]
        items = _ch_sorted_by_terms(items, sort_terms, lambda i, term: i[term])

        # State filter applies after aggregation (the state is computed from
        # the progress join).
        if item_filter is not None and item_filter.annotation_states:
            allowed = set(item_filter.annotation_states)
            items = [
                i for i in items if self._item_progress_state(i["id"])[0] in allowed
            ]

        positions: dict[str, int] = {}
        if req.include_position:
            # 1-based positions over the full filtered + sorted set, before
            # pagination.
            positions = {item["id"]: idx + 1 for idx, item in enumerate(items)}

        if req.offset is not None and req.offset > 0:
            items = items[req.offset :]
        if req.limit is not None and req.limit >= 0:
            items = items[: req.limit]

        return tsi.AnnotationQueueItemsQueryRes(
            items=[
                self._queue_item_to_schema(
                    item, positions.get(item["id"]) if req.include_position else None
                )
                for item in items
            ]
        )

    def annotation_queues_stats(
        self, req: tsi.AnnotationQueuesStatsReq
    ) -> tsi.AnnotationQueuesStatsRes:
        """Per-queue counts: total live items, and items that reached a terminal
        (completed/skipped) state.
        """
        if not req.queue_ids:
            return tsi.AnnotationQueuesStatsRes(stats=[])
        with self.lock:
            stats = []
            for queue_id in req.queue_ids:
                total_items = sum(
                    1
                    for item in self._annotation_queue_items.values()
                    if item["project_id"] == req.project_id
                    and item["queue_id"] == queue_id
                    and item["deleted_at"] is None
                )
                completed_items = len(
                    {
                        row["queue_item_id"]
                        for row in self._annotation_progress.values()
                        if row["project_id"] == req.project_id
                        and row["queue_id"] == queue_id
                        and row["annotation_state"] in {"completed", "skipped"}
                        and row["deleted_at"] is None
                    }
                )
                stats.append(
                    tsi.AnnotationQueueStatsSchema(
                        queue_id=queue_id,
                        total_items=total_items,
                        completed_items=completed_items,
                    )
                )
        return tsi.AnnotationQueuesStatsRes(stats=stats)

    def annotator_queue_items_progress_update(
        self, req: tsi.AnnotatorQueueItemsProgressUpdateReq
    ) -> tsi.AnnotatorQueueItemsProgressUpdateRes:
        """Upsert one annotator's progress (state) for a queue item."""
        allowed_states = {"completed", "skipped", "in_progress"}
        if req.annotation_state not in allowed_states:
            raise ValueError(
                f"Invalid annotation_state '{req.annotation_state}'. "
                f"Must be one of: {', '.join(sorted(allowed_states))}"
            )
        annotator_id = req.wb_user_id
        if not annotator_id:
            raise ValueError("wb_user_id is required")

        with self.lock:
            own_rows = [
                row
                for row in self._annotation_progress.values()
                if row["project_id"] == req.project_id
                and row["queue_item_id"] == req.item_id
                and row["annotator_id"] == annotator_id
                and row["deleted_at"] is None
            ]
            current_state = own_rows[0]["annotation_state"] if own_rows else None
            has_record = bool(own_rows)

            item = self._annotation_queue_items.get(req.item_id)
            item_exists = (
                item is not None
                and item["project_id"] == req.project_id
                and item["queue_id"] == req.queue_id
                and item["deleted_at"] is None
            )

            if current_state == req.annotation_state:
                pass  # Idempotent no-op.
            elif req.annotation_state == "in_progress" and has_record:
                raise ValueError(
                    "Cannot transition to 'in_progress' when a record already "
                    f"exists (current state: '{current_state}')"
                )
            elif current_state is not None and current_state not in {
                "in_progress",
                "unstarted",
            }:
                raise ValueError(
                    f"Invalid state transition from '{current_state}' to "
                    f"'{req.annotation_state}'. Only transitions from "
                    "'in_progress' or 'unstarted' are allowed."
                )

            if not item_exists:
                raise ValueError(
                    f"Queue item '{req.item_id}' not found in queue '{req.queue_id}'"
                )

            if current_state != req.annotation_state:
                now = datetime.datetime.now(datetime.timezone.utc)
                if has_record:
                    own_rows[0]["annotation_state"] = req.annotation_state
                    own_rows[0]["updated_at"] = now
                else:
                    progress_id = generate_id()
                    self._annotation_progress[progress_id] = {
                        "id": progress_id,
                        "project_id": req.project_id,
                        "queue_item_id": req.item_id,
                        "queue_id": req.queue_id,
                        "annotator_id": annotator_id,
                        "annotation_state": req.annotation_state,
                        "created_at": now,
                        "updated_at": now,
                        "deleted_at": None,
                    }

            assert item is not None
            return tsi.AnnotatorQueueItemsProgressUpdateRes(
                item=self._queue_item_to_schema(item)
            )

    # ------------------------------------------------------------------
    # Evaluate model / rescore
    # ------------------------------------------------------------------

    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        if self._evaluate_model_dispatcher is None:
            raise ValueError("Evaluate model dispatcher is not set")
        if req.wb_user_id is None:
            raise ValueError("wb_user_id is required")
        call_id = generate_id()
        self._evaluate_model_dispatcher.dispatch(
            EvaluateModelArgs(
                project_id=req.project_id,
                evaluation_ref=req.evaluation_ref,
                model_ref=req.model_ref,
                wb_user_id=req.wb_user_id,
                evaluation_call_id=call_id,
            )
        )
        return tsi.EvaluateModelRes(call_id=call_id)

    def rescore(self, req: tsi.RescoreReq) -> tsi.RescoreRes:
        if self._evaluate_model_dispatcher is None:
            raise ValueError("Evaluate model dispatcher is not set")
        if req.wb_user_id is None:
            raise ValueError("wb_user_id is required")

        new_evaluation_run_id = generate_id()
        self._evaluate_model_dispatcher.dispatch(
            RescoringArgs(
                project_id=req.project_id,
                source_evaluation_run_id=req.source_evaluation_run_id,
                scorer_refs=req.scorer_refs,
                wb_user_id=req.wb_user_id,
                new_evaluation_run_id=new_evaluation_run_id,
            )
        )
        return tsi.RescoreRes(
            call_id=new_evaluation_run_id,
            evaluation_run_id=new_evaluation_run_id,
        )

    def evaluation_status(
        self, req: tsi.EvaluationStatusReq
    ) -> tsi.EvaluationStatusRes:
        return evaluation_status(self, req)

    def calls_score(self, req: tsi.CallsScoreReq) -> tsi.CallsScoreRes:
        # ClickHouse publishes to Kafka for async scoring; with no producer
        # configured it raises exactly this error. The fake has no producer.
        raise ValueError("Kafka producer is not set")

    # ------------------------------------------------------------------
    # Object-class builder APIs (ops, datasets, scorers, evaluations,
    # models, evaluation runs, predictions, scores). These mirror the
    # backend implementations verbatim — they compose lower-level interface
    # methods only.
    # ------------------------------------------------------------------

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        source_code = req.source_code or object_creation_utils.PLACEHOLDER_OP_SOURCE
        source_file_req = tsi.FileCreateReq(
            project_id=req.project_id,
            name=object_creation_utils.OP_SOURCE_FILE_NAME,
            content=source_code.encode("utf-8"),
        )
        source_file_res = self.file_create(source_file_req)

        op_val = object_creation_utils.build_op_val(source_file_res.digest)
        object_id = object_creation_utils.make_object_id(req.name, "Op")

        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=object_id,
                val=op_val,
            )
        )
        obj_result = self.obj_create(obj_req)

        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=object_id,
            digest=obj_result.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        return tsi.OpCreateRes(
            digest=obj_result.digest,
            object_id=object_id,
            version_index=obj_read_res.obj.version_index,
        )

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
            metadata_only=False,
        )
        result = self.obj_read(obj_req)

        val = result.obj.val
        code = ""

        if isinstance(val, dict) and val.get("_type") == "CustomWeaveType":
            files = val.get("files", {})
            if object_creation_utils.OP_SOURCE_FILE_NAME in files:
                file_digest = files[object_creation_utils.OP_SOURCE_FILE_NAME]
                try:
                    file_content_res = self.file_content_read(
                        tsi.FileContentReadReq(
                            project_id=req.project_id, digest=file_digest
                        )
                    )
                    code = file_content_res.content.decode("utf-8")
                except Exception:
                    pass

        return tsi.OpReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            code=code,
        )

    def op_list(self, req: tsi.OpListReq) -> Iterator[tsi.OpReadRes]:
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(
                is_op=True,
                latest_only=True,
            ),
            limit=req.limit,
            offset=req.offset,
            metadata_only=False,
        )
        result = self.objs_query(obj_query_req)

        for obj in result.objs:
            code = ""
            try:
                val = obj.val
                if isinstance(val, dict) and val.get("_type") == "CustomWeaveType":
                    files = val.get("files", {})
                    if object_creation_utils.OP_SOURCE_FILE_NAME in files:
                        file_digest = files[object_creation_utils.OP_SOURCE_FILE_NAME]
                        try:
                            file_content_res = self.file_content_read(
                                tsi.FileContentReadReq(
                                    project_id=req.project_id, digest=file_digest
                                )
                            )
                            code = file_content_res.content.decode("utf-8")
                        except Exception:
                            pass
            except Exception:
                pass

            yield tsi.OpReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                code=code,
            )

    def op_delete(self, req: tsi.OpDeleteReq) -> tsi.OpDeleteRes:
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.OpDeleteRes(num_deleted=result.num_deleted)

    def dataset_create(self, req: tsi.DatasetCreateReq) -> tsi.DatasetCreateRes:
        dataset_id = object_creation_utils.make_object_id(req.name, "Dataset")

        table_req = tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=req.project_id,
                rows=req.rows,
            )
        )
        table_res = self.table_create(table_req)
        table_ref = ri.InternalTableRef(
            project_id=req.project_id,
            digest=table_res.digest,
        ).uri

        dataset_val = object_creation_utils.build_dataset_val(
            name=req.name,
            description=req.description,
            table_ref=table_ref,
        )
        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=dataset_id,
                val=dataset_val,
                wb_user_id=None,
            )
        )
        obj_result = self.obj_create(obj_req)

        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=dataset_id,
            digest=obj_result.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        return tsi.DatasetCreateRes(
            digest=obj_result.digest,
            object_id=dataset_id,
            version_index=obj_read_res.obj.version_index,
        )

    def dataset_read(self, req: tsi.DatasetReadReq) -> tsi.DatasetReadRes:
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self.obj_read(obj_req)
        val = result.obj.val

        name = val.get("name")
        description = val.get("description")
        rows_ref = val.get("rows", "")

        return tsi.DatasetReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=name,
            description=description,
            rows=rows_ref,
        )

    def dataset_list(self, req: tsi.DatasetListReq) -> Iterator[tsi.DatasetReadRes]:
        dataset_filter = tsi.ObjectVersionFilter(
            base_object_classes=["Dataset"], is_op=False
        )
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=dataset_filter,
            limit=req.limit,
            offset=req.offset,
        )
        obj_res = self.objs_query(obj_query_req)

        for obj in obj_res.objs:
            val = obj.val
            if not val or not isinstance(val, dict):
                continue

            name = val.get("name")
            description = val.get("description")
            rows_ref = val.get("rows", "")

            yield tsi.DatasetReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=name,
                description=description,
                rows=rows_ref,
            )

    def dataset_delete(self, req: tsi.DatasetDeleteReq) -> tsi.DatasetDeleteRes:
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.DatasetDeleteRes(num_deleted=result.num_deleted)

    def scorer_create(self, req: tsi.ScorerCreateReq) -> tsi.ScorerCreateRes:
        scorer_id = object_creation_utils.make_object_id(req.name, "Scorer")

        score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{scorer_id}_score",
            source_code=req.op_source_code,
        )
        score_op_res = self.op_create(score_op_req)
        score_op_ref = score_op_res.digest

        summarize_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{scorer_id}_summarize",
            source_code=object_creation_utils.PLACEHOLDER_SCORER_SUMMARIZE_OP_SOURCE,
        )
        summarize_op_res = self.op_create(summarize_op_req)
        summarize_op_ref = summarize_op_res.digest

        scorer_val = object_creation_utils.build_scorer_val(
            name=req.name,
            description=req.description,
            score_op_ref=score_op_ref,
            summarize_op_ref=summarize_op_ref,
        )

        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=scorer_id,
                val=scorer_val,
                wb_user_id=None,
            )
        )
        obj_result = self.obj_create(obj_req)

        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=scorer_id,
            digest=obj_result.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        scorer_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=scorer_id,
            version=obj_result.digest,
        ).uri

        return tsi.ScorerCreateRes(
            digest=obj_result.digest,
            object_id=scorer_id,
            version_index=obj_read_res.obj.version_index,
            scorer=scorer_ref,
        )

    def scorer_read(self, req: tsi.ScorerReadReq) -> tsi.ScorerReadRes:
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self.obj_read(obj_req)
        return scorer_read_res_from_obj(result.obj)

    def scorer_list(self, req: tsi.ScorerListReq) -> Iterator[tsi.ScorerReadRes]:
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(base_object_classes=["Scorer"], is_op=False),
            limit=req.limit,
            offset=req.offset,
        )
        result = self.objs_query(obj_query_req)

        for obj in result.objs:
            yield scorer_read_res_from_obj(obj)

    def scorer_delete(self, req: tsi.ScorerDeleteReq) -> tsi.ScorerDeleteRes:
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.ScorerDeleteRes(num_deleted=result.num_deleted)

    def evaluation_create(
        self, req: tsi.EvaluationCreateReq
    ) -> tsi.EvaluationCreateRes:
        evaluation_id = object_creation_utils.make_object_id(req.name, "Evaluation")

        evaluate_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}.evaluate",
            source_code=object_creation_utils.PLACEHOLDER_EVALUATE_OP_SOURCE,
        )
        evaluate_op_res = self.op_create(evaluate_op_req)
        evaluate_ref = evaluate_op_res.digest

        predict_and_score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}.predict_and_score",
            source_code=object_creation_utils.PLACEHOLDER_PREDICT_AND_SCORE_OP_SOURCE,
        )
        predict_and_score_op_res = self.op_create(predict_and_score_op_req)
        predict_and_score_ref = predict_and_score_op_res.digest

        summarize_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}.summarize",
            source_code=object_creation_utils.PLACEHOLDER_EVALUATION_SUMMARIZE_OP_SOURCE,
        )
        summarize_op_res = self.op_create(summarize_op_req)
        summarize_ref = summarize_op_res.digest

        evaluation_val = object_creation_utils.build_evaluation_val(
            name=req.name,
            dataset_ref=req.dataset,
            trials=req.trials,
            description=req.description,
            scorer_refs=req.scorers,
            evaluation_name=req.evaluation_name,
            metadata=None,
            preprocess_model_input=None,
            eval_attributes=req.eval_attributes,
            evaluate_ref=evaluate_ref,
            predict_and_score_ref=predict_and_score_ref,
            summarize_ref=summarize_ref,
        )

        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=evaluation_id,
                val=evaluation_val,
                wb_user_id=None,
            )
        )
        obj_result = self.obj_create(obj_req)

        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=evaluation_id,
            digest=obj_result.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        evaluation_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=evaluation_id,
            version=obj_result.digest,
        ).uri

        return tsi.EvaluationCreateRes(
            digest=obj_result.digest,
            object_id=evaluation_id,
            version_index=obj_read_res.obj.version_index,
            evaluation_ref=evaluation_ref,
        )

    def evaluation_read(self, req: tsi.EvaluationReadReq) -> tsi.EvaluationReadRes:
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self.obj_read(obj_req)
        val = result.obj.val

        name = val.get("name", result.obj.object_id)
        description = val.get("description")

        return tsi.EvaluationReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=name,
            description=description,
            dataset=val.get("dataset", ""),
            scorers=val.get("scorers", []),
            trials=val.get("trials", 1),
            evaluation_name=val.get("evaluation_name"),
            evaluate_op=val.get("evaluate", ""),
            predict_and_score_op=val.get("predict_and_score", ""),
            summarize_op=val.get("summarize", ""),
        )

    def evaluation_list(
        self, req: tsi.EvaluationListReq
    ) -> Iterator[tsi.EvaluationReadRes]:
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(
                base_object_classes=["Evaluation"], is_op=False
            ),
            limit=req.limit,
            offset=req.offset,
        )
        result = self.objs_query(obj_query_req)

        for obj in result.objs:
            val = obj.val if obj.val else {}

            name = (
                val.get("name", obj.object_id)
                if isinstance(val, dict)
                else obj.object_id
            )
            description = val.get("description") if isinstance(val, dict) else None

            yield tsi.EvaluationReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=name,
                description=description,
                dataset=val.get("dataset", "") if isinstance(val, dict) else "",
                scorers=val.get("scorers", []) if isinstance(val, dict) else [],
                trials=val.get("trials", 1) if isinstance(val, dict) else 1,
                evaluation_name=val.get("evaluation_name")
                if isinstance(val, dict)
                else None,
                evaluate_op=val.get("evaluate", "") if isinstance(val, dict) else "",
                predict_and_score_op=val.get("predict_and_score", "")
                if isinstance(val, dict)
                else "",
                summarize_op=val.get("summarize", "") if isinstance(val, dict) else "",
            )

    def evaluation_delete(
        self, req: tsi.EvaluationDeleteReq
    ) -> tsi.EvaluationDeleteRes:
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.EvaluationDeleteRes(num_deleted=result.num_deleted)

    # Model V2 API

    def model_create(self, req: tsi.ModelCreateReq) -> tsi.ModelCreateRes:
        source_file_req = tsi.FileCreateReq(
            project_id=req.project_id,
            name=object_creation_utils.OP_SOURCE_FILE_NAME,
            content=req.source_code.encode("utf-8"),
        )
        source_file_res = self.file_create(source_file_req)

        model_val = object_creation_utils.build_model_val(
            name=req.name,
            description=req.description,
            source_file_digest=source_file_res.digest,
            attributes=req.attributes,
        )

        object_id = object_creation_utils.make_object_id(req.name, "Model")

        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=object_id,
                val=model_val,
            )
        )
        obj_result = self.obj_create(obj_req)

        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=object_id,
            digest=obj_result.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        model_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=object_id,
            version=obj_result.digest,
        ).uri

        return tsi.ModelCreateRes(
            digest=obj_result.digest,
            object_id=object_id,
            version_index=obj_read_res.obj.version_index,
            model_ref=model_ref,
        )

    def model_read(self, req: tsi.ModelReadReq) -> tsi.ModelReadRes:
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        val = obj_read_res.obj.val
        name = val.get("name", req.object_id)
        description = val.get("description")

        files = val.get("files", {})
        source_file_digest = files.get(object_creation_utils.OP_SOURCE_FILE_NAME)
        if not source_file_digest:
            raise ValueError(f"Model {req.object_id} has no source file")

        file_content_req = tsi.FileContentReadReq(
            project_id=req.project_id,
            digest=source_file_digest,
        )
        file_content_res = self.file_content_read(file_content_req)
        source_code = file_content_res.content.decode("utf-8")

        excluded_fields = {
            "_type",
            "_class_name",
            "_bases",
            "name",
            "description",
            "files",
        }
        attributes = {k: v for k, v in val.items() if k not in excluded_fields}

        return tsi.ModelReadRes(
            object_id=req.object_id,
            digest=req.digest,
            version_index=obj_read_res.obj.version_index,
            created_at=obj_read_res.obj.created_at,
            name=name,
            description=description,
            source_code=source_code,
            attributes=attributes if attributes else None,
        )

    def model_list(self, req: tsi.ModelListReq) -> Iterator[tsi.ModelReadRes]:
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(base_object_classes=["Model"], is_op=False),
            limit=req.limit,
            offset=req.offset,
        )
        obj_query_res = self.objs_query(obj_query_req)

        for obj in obj_query_res.objs:
            val = obj.val
            name = val.get("name", obj.object_id)
            description = val.get("description")

            files = val.get("files", {})
            source_file_digest = files.get(object_creation_utils.OP_SOURCE_FILE_NAME)
            if source_file_digest:
                file_content_req = tsi.FileContentReadReq(
                    project_id=req.project_id,
                    digest=source_file_digest,
                )
                file_content_res = self.file_content_read(file_content_req)
                source_code = file_content_res.content.decode("utf-8")
            else:
                source_code = ""

            excluded_fields = {
                "_type",
                "_class_name",
                "_bases",
                "name",
                "description",
                "files",
            }
            attributes = {k: v for k, v in val.items() if k not in excluded_fields}

            yield tsi.ModelReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=name,
                description=description,
                source_code=source_code,
                attributes=attributes if attributes else None,
            )

    def model_delete(self, req: tsi.ModelDeleteReq) -> tsi.ModelDeleteRes:
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.ModelDeleteRes(num_deleted=result.num_deleted)

    def evaluation_run_create(
        self, req: tsi.EvaluationRunCreateReq
    ) -> tsi.EvaluationRunCreateRes:
        evaluation_run_id = generate_id()

        weave_attrs: dict = {
            constants.EVALUATION_RUN_ATTR_KEY: "true",
            constants.EVALUATION_RUN_EVALUATION_ATTR_KEY: req.evaluation,
            constants.EVALUATION_RUN_MODEL_ATTR_KEY: req.model,
        }
        if req.source_evaluation_run_id:
            weave_attrs[constants.EVALUATION_RUN_SOURCE_ATTR_KEY] = (
                req.source_evaluation_run_id
            )

        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=evaluation_run_id,
                trace_id=evaluation_run_id,
                op_name=constants.EVALUATION_RUN_OP_NAME,
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes={
                    constants.WEAVE_ATTRIBUTES_NAMESPACE: weave_attrs,
                },
                inputs={
                    "self": req.evaluation,
                    "model": req.model,
                },
            )
        )
        self.call_start(call_start_req)

        return tsi.EvaluationRunCreateRes(evaluation_run_id=evaluation_run_id)

    def evaluation_run_read(
        self, req: tsi.EvaluationRunReadReq
    ) -> tsi.EvaluationRunReadRes:
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.evaluation_run_id,
        )
        call_res = self.call_read(call_read_req)

        if call_res.call is None:
            raise NotFoundError(f"Evaluation run {req.evaluation_run_id} not found")

        call = call_res.call
        attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})
        evaluation_ref, model_ref = eval_run_refs_from_call(call, attributes)

        status = determine_call_status(call)

        return tsi.EvaluationRunReadRes(
            evaluation_run_id=call.id,
            evaluation=evaluation_ref,
            model=model_ref,
            status=status,
            started_at=call.started_at,
            finished_at=call.ended_at,
            summary=call.summary,
            source_evaluation_run_id=attributes.get(
                constants.EVALUATION_RUN_SOURCE_ATTR_KEY
            ),
        )

    def evaluation_run_list(
        self, req: tsi.EvaluationRunListReq
    ) -> Iterator[tsi.EvaluationRunReadRes]:
        conditions: list[tsi_query.Operand] = []

        conditions.append(
            tsi_query.EqOperation(
                eq_=[
                    tsi_query.GetFieldOperator(
                        get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_ATTR_KEY}"
                    ),
                    tsi_query.LiteralOperation(literal_="true"),
                ]
            )
        )

        if req.filter:
            if req.filter.evaluations:
                conditions.append(
                    tsi_query.InOperation(
                        in_=[
                            tsi_query.GetFieldOperator(
                                get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_EVALUATION_ATTR_KEY}"
                            ),
                            [
                                tsi_query.LiteralOperation(literal_=evaluation)
                                for evaluation in req.filter.evaluations
                            ],
                        ]
                    )
                )
            if req.filter.models:
                conditions.append(
                    tsi_query.InOperation(
                        in_=[
                            tsi_query.GetFieldOperator(
                                get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_MODEL_ATTR_KEY}"
                            ),
                            [
                                tsi_query.LiteralOperation(literal_=model)
                                for model in req.filter.models
                            ],
                        ]
                    )
                )
            if req.filter.evaluation_run_ids:
                conditions.append(
                    tsi_query.InOperation(
                        in_=[
                            tsi_query.GetFieldOperator(get_field_="id"),
                            [
                                tsi_query.LiteralOperation(literal_=evaluation_run_id)
                                for evaluation_run_id in req.filter.evaluation_run_ids
                            ],
                        ]
                    )
                )

        query = tsi.Query(expr_=tsi_query.AndOperation(and_=conditions))

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=query,
            limit=req.limit,
            offset=req.offset,
        )

        for call in self.calls_query_stream(calls_query_req):
            attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})
            status = determine_call_status(call)

            yield tsi.EvaluationRunReadRes(
                evaluation_run_id=call.id,
                evaluation=attributes.get(
                    constants.EVALUATION_RUN_EVALUATION_ATTR_KEY, ""
                ),
                model=attributes.get(constants.EVALUATION_RUN_MODEL_ATTR_KEY, ""),
                status=status,
                started_at=call.started_at,
                finished_at=call.ended_at,
                summary=call.summary,
            )

    def evaluation_run_delete(
        self, req: tsi.EvaluationRunDeleteReq
    ) -> tsi.EvaluationRunDeleteRes:
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.evaluation_run_ids,
            wb_user_id=req.wb_user_id,
        )
        self.calls_delete(calls_delete_req)
        return tsi.EvaluationRunDeleteRes(num_deleted=len(req.evaluation_run_ids))

    def evaluation_run_finish(
        self, req: tsi.EvaluationRunFinishReq
    ) -> tsi.EvaluationRunFinishRes:
        summary = req.summary or {}

        evaluation_run_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.evaluation_run_id,
        )
        evaluation_run_read_res = self.call_read(evaluation_run_read_req)
        evaluation_run_call = evaluation_run_read_res.call
        evaluation_ref = None
        if evaluation_run_call and evaluation_run_call.inputs:
            evaluation_ref = evaluation_run_call.inputs.get("self")

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(
                parent_ids=[req.evaluation_run_id],
            ),
            columns=["output", "op_name"],
        )
        predict_and_score_calls = self.calls_query_stream(calls_query_req)

        model_outputs = []
        scorer_outputs_by_name: dict[str, list[float]] = {}

        for call in predict_and_score_calls:
            if not op_name_matches(
                call.op_name, constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME
            ):
                continue

            if not call.output or not isinstance(call.output, dict):
                continue

            if "output" in call.output and call.output["output"] is not None:
                model_outputs.append(call.output["output"])

            scores = call.output.get("scores", {})
            if not isinstance(scores, dict):
                continue

            for scorer_name, score_value in scores.items():
                if scorer_name not in scorer_outputs_by_name:
                    scorer_outputs_by_name[scorer_name] = []
                if isinstance(score_value, (int, float)):
                    scorer_outputs_by_name[scorer_name].append(float(score_value))

        eval_output = {}

        for scorer_name, scores in scorer_outputs_by_name.items():
            if scores:
                eval_output[scorer_name] = {"mean": sum(scores) / len(scores)}

        if model_outputs:
            try:
                numeric_outputs = [
                    float(o) for o in model_outputs if isinstance(o, (int, float))
                ]
                if numeric_outputs:
                    eval_output["output"] = {
                        "mean": sum(numeric_outputs) / len(numeric_outputs)
                    }
            except (ValueError, TypeError):
                pass

        summarize_id = generate_id()
        summarize_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=summarize_id,
                trace_id=req.evaluation_run_id,
                parent_id=req.evaluation_run_id,
                op_name=constants.EVALUATION_SUMMARIZE_OP_NAME,
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes={},
                inputs={
                    "self": evaluation_ref,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self.call_start(summarize_start_req)

        summarize_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=summarize_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=eval_output,
                summary={},
            )
        )
        self.call_end(summarize_end_req)

        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=req.evaluation_run_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=eval_output,
                summary=summary,
            )
        )
        self.call_end(call_end_req)
        return tsi.EvaluationRunFinishRes(success=True)

    # Prediction V2 API

    def prediction_create(
        self, req: tsi.PredictionCreateReq
    ) -> tsi.PredictionCreateRes:
        prediction_id = generate_id()
        genai_span_ref = (
            [ref.model_dump(exclude_none=True) for ref in req.genai_span_ref]
            if req.genai_span_ref is not None
            else None
        )

        if req.evaluation_run_id:
            trace_id = req.evaluation_run_id
            predict_and_score_id = generate_id()

            evaluation_run_read_req = tsi.CallReadReq(
                project_id=req.project_id,
                id=req.evaluation_run_id,
            )
            evaluation_run_call = self.call_read(evaluation_run_read_req)
            evaluation_ref = (
                evaluation_run_call.call.inputs.get("self")
                if evaluation_run_call.call
                else None
            )

            predict_and_score_op_req = tsi.OpCreateReq(
                project_id=req.project_id,
                name=constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                source_code=object_creation_utils.PLACEHOLDER_EVALUATION_PREDICT_AND_SCORE_OP_SOURCE,
            )
            predict_and_score_op_res = self.op_create(predict_and_score_op_req)

            predict_and_score_op_ref = ri.InternalOpRef(
                project_id=req.project_id,
                name=constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                version=predict_and_score_op_res.digest,
            )

            predict_and_score_weave_attrs: dict[str, Any] = {
                constants.EVALUATION_RUN_PREDICT_CALL_ID_ATTR_KEY: prediction_id,
            }
            if genai_span_ref is not None:
                predict_and_score_weave_attrs[constants.GENAI_SPAN_REF_ATTR_KEY] = (
                    genai_span_ref
                )

            predict_and_score_start_req = tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=req.project_id,
                    id=predict_and_score_id,
                    trace_id=trace_id,
                    parent_id=req.evaluation_run_id,
                    op_name=predict_and_score_op_ref.uri,
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    attributes={
                        constants.WEAVE_ATTRIBUTES_NAMESPACE: predict_and_score_weave_attrs
                    },
                    inputs={
                        "self": evaluation_ref,
                        "model": req.model,
                        "example": req.inputs,
                    },
                    wb_user_id=req.wb_user_id,
                )
            )
            self.call_start(predict_and_score_start_req)

            parent_id = predict_and_score_id
        else:
            trace_id = prediction_id
            parent_id = None

        try:
            model_ref = ri.parse_internal_uri(req.model)
            if isinstance(model_ref, (ri.InternalObjectRef, ri.InternalOpRef)):
                model_name = model_ref.name
            else:
                model_name = "Model"
        except ri.InvalidInternalRef:
            model_name = "Model"

        predict_op_name = f"{model_name}.predict"
        predict_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=predict_op_name,
            source_code=object_creation_utils.PLACEHOLDER_MODEL_PREDICT_OP_SOURCE,
        )
        predict_op_res = self.op_create(predict_op_req)

        predict_op_ref = ri.InternalOpRef(
            project_id=req.project_id,
            name=predict_op_name,
            version=predict_op_res.digest,
        )

        prediction_attributes = {
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.PREDICTION_ATTR_KEY: "true",
                constants.PREDICTION_MODEL_ATTR_KEY: req.model,
            }
        }
        if req.evaluation_run_id:
            prediction_attributes[constants.WEAVE_ATTRIBUTES_NAMESPACE][
                constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
            ] = req.evaluation_run_id

        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=prediction_id,
                trace_id=trace_id,
                parent_id=parent_id,
                op_name=predict_op_ref.uri,
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes=prediction_attributes,
                inputs={
                    "self": req.model,
                    "inputs": req.inputs,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self.call_start(call_start_req)

        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=prediction_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=req.output,
                summary={},
            )
        )
        self.call_end(call_end_req)

        return tsi.PredictionCreateRes(prediction_id=prediction_id)

    def prediction_read(self, req: tsi.PredictionReadReq) -> tsi.PredictionReadRes:
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        call_res = self.call_read(call_read_req)

        if call_res.call is None:
            raise NotFoundError(f"Prediction {req.prediction_id} not found")

        call = call_res.call
        attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})

        evaluation_run_id = attributes.get(
            constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
        )
        if evaluation_run_id is None and call.parent_id:
            parent_read_req = tsi.CallReadReq(
                project_id=req.project_id,
                id=call.parent_id,
            )
            parent_res = self.call_read(parent_read_req)
            if parent_res.call and op_name_matches(
                parent_res.call.op_name,
                constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
            ):
                evaluation_run_id = parent_res.call.parent_id

        return tsi.PredictionReadRes(
            prediction_id=call.id,
            model=attributes.get(constants.PREDICTION_MODEL_ATTR_KEY, ""),
            inputs=get_prediction_inputs(call.inputs),
            output=call.output,
            evaluation_run_id=evaluation_run_id,
            wb_user_id=call.wb_user_id,
        )

    def prediction_list(
        self, req: tsi.PredictionListReq
    ) -> Iterator[tsi.PredictionReadRes]:
        conditions: list[tsi_query.Operand] = []

        conditions.append(
            tsi_query.EqOperation(
                eq_=[
                    tsi_query.GetFieldOperator(
                        get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.PREDICTION_ATTR_KEY}"
                    ),
                    tsi_query.LiteralOperation(literal_="true"),
                ]
            )
        )

        if req.evaluation_run_id:
            conditions.append(
                tsi_query.EqOperation(
                    eq_=[
                        tsi_query.GetFieldOperator(
                            get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY}"
                        ),
                        tsi_query.LiteralOperation(literal_=req.evaluation_run_id),
                    ]
                )
            )

        if len(conditions) == 1:
            query = tsi.Query(expr_=conditions[0])
        else:
            query = tsi.Query(expr_=tsi_query.AndOperation(and_=conditions))

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=query,
            limit=req.limit,
            offset=req.offset,
        )

        for call in self.calls_query_stream(calls_query_req):
            attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})

            evaluation_run_id = attributes.get(
                constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
            )
            if evaluation_run_id is None and call.parent_id:
                parent_read_req = tsi.CallReadReq(
                    project_id=req.project_id,
                    id=call.parent_id,
                )
                parent_res = self.call_read(parent_read_req)
                if parent_res.call and op_name_matches(
                    parent_res.call.op_name,
                    constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                ):
                    evaluation_run_id = parent_res.call.parent_id

            yield tsi.PredictionReadRes(
                prediction_id=call.id,
                model=attributes.get(constants.PREDICTION_MODEL_ATTR_KEY, ""),
                inputs=get_prediction_inputs(call.inputs),
                output=call.output,
                evaluation_run_id=evaluation_run_id,
                wb_user_id=call.wb_user_id,
            )

    def prediction_delete(
        self, req: tsi.PredictionDeleteReq
    ) -> tsi.PredictionDeleteRes:
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.prediction_ids,
            wb_user_id=req.wb_user_id,
        )
        self.calls_delete(calls_delete_req)
        return tsi.PredictionDeleteRes(num_deleted=len(req.prediction_ids))

    def prediction_finish(
        self, req: tsi.PredictionFinishReq
    ) -> tsi.PredictionFinishRes:
        prediction_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        prediction_res = self.call_read(prediction_read_req)

        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=req.prediction_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=None,
                summary={},
            )
        )
        self.call_end(call_end_req)

        prediction_call = prediction_res.call
        if not prediction_call or not prediction_call.parent_id:
            return tsi.PredictionFinishRes(success=True)

        parent_id = prediction_call.parent_id
        parent_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=parent_id,
        )
        parent_res = self.call_read(parent_read_req)

        if not parent_res.call or not op_name_matches(
            parent_res.call.op_name,
            constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
        ):
            return tsi.PredictionFinishRes(success=True)

        scores_dict = {}

        score_query = tsi.Query(
            expr_=tsi_query.EqOperation(
                eq_=[
                    tsi_query.GetFieldOperator(
                        get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_ATTR_KEY}"
                    ),
                    tsi_query.LiteralOperation(literal_="true"),
                ]
            )
        )

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(
                parent_ids=[parent_id],
            ),
            query=score_query,
            columns=[
                "output",
                "attributes",
            ],
        )

        for score_call in self.calls_query_stream(calls_query_req):
            if score_call.output is None:
                continue

            weave_attrs = score_call.attributes.get(
                constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
            )
            scorer_ref = weave_attrs.get(constants.SCORE_SCORER_ATTR_KEY)

            scorer_name = "unknown"
            if scorer_ref and isinstance(scorer_ref, str):
                parts = scorer_ref.split("/")
                if parts:
                    name_and_digest = parts[-1]
                    if ":" in name_and_digest:
                        scorer_name = name_and_digest.split(":")[0]

            scores_dict[scorer_name] = score_call.output

        model_latency = None
        if prediction_call.started_at and prediction_call.ended_at:
            latency_seconds = (
                prediction_call.ended_at - prediction_call.started_at
            ).total_seconds()
            model_latency = {"mean": latency_seconds}

        parent_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=parent_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output={
                    "output": prediction_call.output,
                    "scores": scores_dict,
                    "model_latency": model_latency,
                },
                summary={},
            )
        )
        self.call_end(parent_end_req)

        return tsi.PredictionFinishRes(success=True)

    # Score V2 API

    def score_create(self, req: tsi.ScoreCreateReq) -> tsi.ScoreCreateRes:
        score_id = generate_id()

        prediction_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        prediction_res = self.call_read(prediction_read_req)

        prediction_inputs = {}
        prediction_output = None
        if prediction_res.call:
            if isinstance(prediction_res.call.inputs, dict):
                prediction_inputs = prediction_res.call.inputs.get("inputs", {})
            prediction_output = prediction_res.call.output

        if req.evaluation_run_id:
            trace_id = req.evaluation_run_id

            if prediction_res.call and prediction_res.call.parent_id:
                parent_id = prediction_res.call.parent_id
            else:
                parent_id = req.evaluation_run_id
        else:
            trace_id = score_id
            parent_id = None

        scorer_ref = ri.parse_internal_uri(req.scorer)
        if not isinstance(scorer_ref, ri.InternalObjectRef):
            raise TypeError(f"Invalid scorer ref: {req.scorer}")
        scorer_name = scorer_ref.name

        score_op_name = f"{scorer_name}.score"
        score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=score_op_name,
            source_code=object_creation_utils.PLACEHOLDER_SCORER_SCORE_OP_SOURCE,
        )
        score_op_res = self.op_create(score_op_req)

        score_op_ref = ri.InternalOpRef(
            project_id=req.project_id,
            name=score_op_name,
            version=score_op_res.digest,
        )

        score_attributes = {
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.SCORE_ATTR_KEY: "true",
                constants.SCORE_PREDICTION_ID_ATTR_KEY: req.prediction_id,
                constants.SCORE_SCORER_ATTR_KEY: req.scorer,
            }
        }
        if req.evaluation_run_id:
            score_attributes[constants.WEAVE_ATTRIBUTES_NAMESPACE][
                constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY
            ] = req.evaluation_run_id

        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=score_id,
                trace_id=trace_id,
                parent_id=parent_id,
                op_name=score_op_ref.uri,
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes=score_attributes,
                inputs={
                    "self": req.scorer,
                    "inputs": prediction_inputs,
                    "output": prediction_output,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self.call_start(call_start_req)

        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=score_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=req.value,
                summary={},
            )
        )
        self.call_end(call_end_req)

        prediction_call_ref = ri.InternalCallRef(
            project_id=req.project_id,
            id=req.prediction_id,
        )

        wb_user_id = (
            req.wb_user_id
            or (prediction_res.call.wb_user_id if prediction_res.call else None)
            or "unknown"
        )

        feedback_req = tsi.FeedbackCreateReq(
            project_id=req.project_id,
            weave_ref=prediction_call_ref.uri,
            feedback_type=f"{RUNNABLE_FEEDBACK_TYPE_PREFIX}.{scorer_name}",
            payload={"output": req.value},
            runnable_ref=req.scorer,
            wb_user_id=wb_user_id,
        )
        self.feedback_create(feedback_req)

        return tsi.ScoreCreateRes(score_id=score_id)

    def score_read(self, req: tsi.ScoreReadReq) -> tsi.ScoreReadRes:
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.score_id,
        )
        call_res = self.call_read(call_read_req)

        if call_res.call is None:
            raise NotFoundError(f"Score {req.score_id} not found")

        call = call_res.call
        attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})

        value = call.output if call.output is not None else 0.0

        evaluation_run_id = attributes.get(constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY)
        if evaluation_run_id is None and call.parent_id:
            parent_read_req = tsi.CallReadReq(
                project_id=req.project_id,
                id=call.parent_id,
            )
            parent_res = self.call_read(parent_read_req)
            if parent_res.call and op_name_matches(
                parent_res.call.op_name,
                constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
            ):
                evaluation_run_id = parent_res.call.parent_id

        return tsi.ScoreReadRes(
            score_id=call.id,
            scorer=attributes.get(constants.SCORE_SCORER_ATTR_KEY, ""),
            value=value,
            evaluation_run_id=evaluation_run_id,
            wb_user_id=call.wb_user_id,
        )

    def score_list(self, req: tsi.ScoreListReq) -> Iterator[tsi.ScoreReadRes]:
        conditions: list[tsi_query.Operand] = []

        conditions.append(
            tsi_query.EqOperation(
                eq_=[
                    tsi_query.GetFieldOperator(
                        get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_ATTR_KEY}"
                    ),
                    tsi_query.LiteralOperation(literal_="true"),
                ]
            )
        )

        if req.evaluation_run_id:
            conditions.append(
                tsi_query.EqOperation(
                    eq_=[
                        tsi_query.GetFieldOperator(
                            get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY}"
                        ),
                        tsi_query.LiteralOperation(literal_=req.evaluation_run_id),
                    ]
                )
            )

        if len(conditions) == 1:
            query = tsi.Query(expr_=conditions[0])
        else:
            query = tsi.Query(expr_=tsi_query.AndOperation(and_=conditions))

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=query,
            limit=req.limit,
            offset=req.offset,
        )

        for call in self.calls_query_stream(calls_query_req):
            attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})

            value = call.output if call.output is not None else 0.0

            evaluation_run_id = attributes.get(
                constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY
            )
            if evaluation_run_id is None and call.parent_id:
                parent_read_req = tsi.CallReadReq(
                    project_id=req.project_id,
                    id=call.parent_id,
                )
                parent_res = self.call_read(parent_read_req)
                if parent_res.call and op_name_matches(
                    parent_res.call.op_name,
                    constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                ):
                    evaluation_run_id = parent_res.call.parent_id

            yield tsi.ScoreReadRes(
                score_id=call.id,
                scorer=attributes.get(constants.SCORE_SCORER_ATTR_KEY, ""),
                value=value,
                evaluation_run_id=evaluation_run_id,
                wb_user_id=call.wb_user_id,
            )

    def score_delete(self, req: tsi.ScoreDeleteReq) -> tsi.ScoreDeleteRes:
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.score_ids,
            wb_user_id=req.wb_user_id,
        )
        self.calls_delete(calls_delete_req)
        return tsi.ScoreDeleteRes(num_deleted=len(req.score_ids))

    def eval_results_query(
        self, req: tsi.EvalResultsQueryReq
    ) -> tsi.EvalResultsQueryRes:
        """Return grouped prediction/trial/score data for evaluation results."""
        eval_helpers.validate_eval_results_request(req)
        eval_root_ids = eval_helpers.resolve_eval_root_ids(req)
        if not eval_root_ids:
            empty_summary = tsi.EvalResultsSummaryRes() if req.include_summary else None
            return tsi.EvalResultsQueryRes(
                rows=[], total_rows=0, summary=empty_summary, warnings=[]
            )
        all_calls = list(
            self._calls_query_stream_for_eval_subtree(
                req.project_id,
                eval_root_ids,
                include_children=req.include_predict_and_score_children,
            )
        )
        if req.resolve_row_refs:
            reader = lambda digests: self._table_rows_read_batch(
                req.project_id, digests
            )
            eval_helpers.resolve_eval_inputs(all_calls, eval_root_ids, reader)
        if not req.filters and not req.sort_by:
            return eval_helpers.eval_results_query(self, req, eval_root_ids, all_calls)
        return self._eval_results_query_sorted_filtered(req, eval_root_ids, all_calls)

    @staticmethod
    def _eval_row_field_values(
        row: tsi.EvalResultsRow,
        field_path: str,
        scope_eval_call_id: str | None,
    ) -> list[str]:
        """Per-trial String values for a field, mirroring the CH builder's
        JSON extraction (scores.* walks trial scores; inputs/output walk the
        trial payloads; row_digest is scalar).
        """
        if field_path == "row_digest":
            return [row.row_digest]
        values: list[str] = []
        for evaluation in row.evaluations:
            if (
                scope_eval_call_id is not None
                and evaluation.evaluation_call_id != scope_eval_call_id
            ):
                continue
            for trial in evaluation.trials:
                if field_path.startswith("scores."):
                    doc: Any = trial.scores
                    parts = split_escaped_field_path(field_path[len("scores.") :])
                elif field_path.startswith("output.") or field_path == "output":
                    doc = trial.model_output
                    parts = (
                        split_escaped_field_path(field_path[len("output.") :])
                        if field_path != "output"
                        else []
                    )
                elif field_path.startswith("inputs.") or field_path == "inputs":
                    doc = row.raw_data_row
                    parts = (
                        split_escaped_field_path(field_path[len("inputs.") :])
                        if field_path != "inputs"
                        else []
                    )
                else:
                    raise InvalidRequest(
                        f"Unsupported field: '{field_path}'. "
                        "Supported prefixes: scores.*, inputs.*, output.*, row_digest."
                    )
                values.append(_ch_json_value(doc, parts))
        return values

    def _eval_results_row_matches(
        self,
        row: tsi.EvalResultsRow,
        query: tsi.Query,
        scope_eval_call_id: str | None,
    ) -> bool:
        def resolve(field_path: str, cast: tsi_query.CastTo | None) -> _FilterValue:
            values = self._eval_row_field_values(row, field_path, scope_eval_call_id)
            # Filter expressions wrap the per-trial value with any().
            value = next((v for v in values if v != ""), values[0] if values else "")
            return _ch_cast_json_value(value, cast)

        return _QueryFilterEvaluator(resolve).matches(query)

    def _eval_results_query_sorted_filtered(
        self,
        req: tsi.EvalResultsQueryReq,
        eval_root_ids: list[str],
        all_calls: list[tsi.CallSchema],
    ) -> tsi.EvalResultsQueryRes:
        """Sort/filter/paginate eval results, mirroring the ClickHouse CTE
        query: filters wrap per-trial values with any(); score sorts use
        avg(toFloat64OrNull(...)) with row_digest as the tiebreaker.
        """
        # ---- Fetch every grouped eval-results row ----
        all_rows_req = tsi.EvalResultsQueryReq(
            project_id=req.project_id,
            evaluation_call_ids=req.evaluation_call_ids,
            evaluation_run_ids=req.evaluation_run_ids,
            require_intersection=False,
            include_raw_data_rows=True,
            resolve_row_refs=False,
            include_rows=True,
            include_summary=False,
            include_predict_and_score_children=req.include_predict_and_score_children,
            summary_require_intersection=None,
            limit=None,
            offset=0,
        )
        all_rows, _ = eval_helpers.eval_results_grouped_rows(
            all_rows_req, eval_root_ids, all_calls
        )

        # ---- Apply per-evaluation filters ----
        if req.filters:
            for f in req.filters:
                all_rows = [
                    row
                    for row in all_rows
                    if self._eval_results_row_matches(
                        row, f.query, f.evaluation_call_id
                    )
                ]

        # ---- Keep only rows present in every evaluation (when intersecting) ----
        if req.require_intersection and len(eval_root_ids) > 1:
            eval_root_id_set = set(eval_root_ids)
            all_rows = [
                row
                for row in all_rows
                if eval_root_id_set.issubset(
                    {e.evaluation_call_id for e in row.evaluations}
                )
            ]

        # ---- Sort (score avg, or any() value), with row_digest as tiebreaker ----
        if req.sort_by:
            sort_terms: list[tuple[Any, str]] = []
            for s in req.sort_by:
                field_path = s.field

                if field_path.startswith("scores."):

                    def score_key(
                        row: tsi.EvalResultsRow, _fp: str = field_path
                    ) -> float | None:
                        values = [
                            parsed
                            for v in self._eval_row_field_values(row, _fp, None)
                            if (parsed := _ch_to_float64_or_null(v)) is not None
                        ]
                        if not values:
                            return None
                        return sum(values) / len(values)

                    sort_terms.append((score_key, s.direction))
                else:

                    def any_key(
                        row: tsi.EvalResultsRow, _fp: str = field_path
                    ) -> str | None:
                        values = self._eval_row_field_values(row, _fp, None)
                        return next((v for v in values if v != ""), None)

                    sort_terms.append((any_key, s.direction))
            sort_terms.append((lambda row: row.row_digest, "asc"))
            all_rows = _ch_sorted_by_terms(
                all_rows, sort_terms, lambda row, key_fn: key_fn(row)
            )
        else:
            all_rows.sort(key=lambda row: row.row_digest)

        # ---- Paginate, resolve refs, and build the optional summary ----
        total_rows = len(all_rows)
        start = max(req.offset, 0)
        end = start + req.limit if req.limit is not None else None
        rows = all_rows[start:end] if req.include_rows else []
        warnings: list[str] = []
        if req.include_rows and req.include_raw_data_rows and req.resolve_row_refs:
            warnings = eval_helpers.resolve_eval_row_refs(self, rows, req.project_id)

        summary: tsi.EvalResultsSummaryRes | None = None
        if req.include_summary:
            eval_call_metadata = eval_helpers.fetch_eval_root_metadata(
                self, req.project_id, eval_root_ids
            )
            summary = eval_helpers.compute_summary_from_rows(
                all_rows, eval_call_metadata
            )

        return tsi.EvalResultsQueryRes(
            rows=rows, total_rows=total_rows, summary=summary, warnings=warnings
        )


# ---------------------------------------------------------------------------
# ORM-equivalent row evaluation (feedback + costs tables)
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class _OrmDatetimeLiteral:
    """Marker operand: a datetime-normalized literal produced by
    `_orm_maybe_datetime_literal`.
    """

    value: datetime.datetime


def _orm_field_value(
    table: Table,
    row: dict[str, Any],
    field_name: str,
    cast_to: str | None = None,
) -> Any:
    """Resolve a field reference against a stored row, mirroring
    `_transform_external_field_to_internal_field` (ClickHouse flavor):
    dotted JSON access goes through JSON_VALUE with a default string cast.
    """
    for prefix in (*table.map_string_cols, *table.map_float_cols):
        if field_name == prefix:
            return row.get(prefix)
        if field_name.startswith(prefix + "."):
            key = field_name[len(prefix) + 1 :]
            # mapContains-guarded access: absent keys read as NULL.
            mapping = row.get(prefix) or {}
            if key not in mapping:
                return None
            value = mapping[key]
            if prefix in table.map_string_cols or cast_to in {None, "string", "exists"}:
                if cast_to == "exists":
                    return value is not None
                return value
            return value
    for prefix in table.json_cols:
        if field_name == prefix or field_name.startswith(prefix + "."):
            col = row.get(prefix)
            parts = (
                split_escaped_field_path(field_name[len(prefix) + 1 :])
                if field_name != prefix
                else []
            )
            if cast_to == "exists":
                # JSON_EXISTS: true whenever the path exists (incl. nulls).
                if col is None:
                    return False
                if not parts:
                    return True
                value = col
                for part in parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    elif isinstance(value, list):
                        try:
                            idx = int(part)
                        except ValueError:
                            return False
                        if idx < 0 or idx >= len(value):
                            return False
                        value = value[idx]
                    else:
                        return False
                return True
            if col is None and not parts:
                return None
            value = _ch_json_value(col, parts)
            return _ch_cast_json_value(value, cast_to or "string")
    if field_name in table.array_string_cols:
        return row.get(field_name) or []
    if field_name not in {c.name for c in table.cols}:
        raise ValueError(f"Unknown field: {field_name}")
    return row.get(field_name)


def _orm_field_exists(table: Table, row: dict[str, Any], field_name: str) -> bool:
    """JSON_EXISTS-equivalent for dynamic fields (explicit null still exists)."""
    result = _orm_field_value(table, row, field_name, cast_to="exists")
    return bool(result)


def _orm_literal_value(literal: Any) -> Any:
    if isinstance(literal, bool):
        # Bools compare numerically (ClickHouse Bool is UInt8 underneath).
        return 1 if literal else 0
    if literal is None or isinstance(literal, (str, int, float)):
        return literal
    raise ValueError(f"Unknown value type: {literal}")


def _orm_maybe_datetime_literal(table: Table, lhs: Any, rhs: Any) -> tuple[Any, Any]:
    """Mirror `maybe_convert_datetime_operands`: a literal compared against a
    DateTime column is normalized to 'YYYY-MM-DD HH:MM:SS.ffffff'.
    """
    from weave.trace_server.orm import (
        parse_string_to_utc_timestamp,
    )

    operands = [lhs, rhs]
    field_idx = None
    literal_idx = None
    timestamp: float | None = None
    for i, op in enumerate(operands):
        if (
            isinstance(op, tsi_query.GetFieldOperator)
            and op.get_field_ in table.datetime_cols
        ):
            field_idx = i
        elif isinstance(op, tsi_query.LiteralOperation):
            lit = op.literal_
            if isinstance(lit, bool):
                continue
            if isinstance(lit, (int, float)):
                literal_idx = i
                timestamp = float(lit)
            elif isinstance(lit, str):
                parsed = parse_string_to_utc_timestamp(lit)
                if parsed is not None:
                    literal_idx = i
                    timestamp = parsed

    if field_idx is None or literal_idx is None or timestamp is None:
        return lhs, rhs

    converted = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
    operands[literal_idx] = _OrmDatetimeLiteral(converted)
    return operands[0], operands[1]


def _orm_eval_query(table: Table, row: dict[str, Any], query: tsi.Query) -> Any:
    """Evaluate a Query against a stored row, mirroring the ORM layer's
    `_process_query_to_conditions` as ClickHouse runs it.
    """

    def process_operation(operation: tsi_query.Operation) -> Any:
        if isinstance(operation, tsi_query.AndOperation):
            if len(operation.and_) == 0:
                raise ValueError("Empty AND operation")
            elif len(operation.and_) == 1:
                return process_operand(operation.and_[0])
            return all(_truthy(process_operand(op)) for op in operation.and_)
        elif isinstance(operation, tsi_query.OrOperation):
            if len(operation.or_) == 0:
                raise ValueError("Empty OR operation")
            elif len(operation.or_) == 1:
                return process_operand(operation.or_[0])
            return any(_truthy(process_operand(op)) for op in operation.or_)
        elif isinstance(operation, tsi_query.NotOperation):
            inner = process_operand(operation.not_[0])
            if inner is None:
                return None
            return not _truthy(inner)
        elif isinstance(operation, tsi_query.EqOperation):
            lhs, rhs = process_binary_operands(*operation.eq_)
            return _ch_compare(lhs, rhs, "eq")
        elif isinstance(operation, tsi_query.GtOperation):
            lhs, rhs = process_binary_operands(*operation.gt_)
            return _ch_compare(lhs, rhs, "gt")
        elif isinstance(operation, tsi_query.LtOperation):
            lhs, rhs = process_binary_operands(*operation.lt_)
            return _ch_compare(lhs, rhs, "lt")
        elif isinstance(operation, tsi_query.GteOperation):
            lhs, rhs = process_binary_operands(*operation.gte_)
            return _ch_compare(lhs, rhs, "gte")
        elif isinstance(operation, tsi_query.LteOperation):
            lhs, rhs = process_binary_operands(*operation.lte_)
            return _ch_compare(lhs, rhs, "lte")
        elif isinstance(operation, tsi_query.InOperation):
            in_cast = tsi_query.infer_shared_literal_filter_cast(operation.in_[1])
            lhs = process_operand(operation.in_[0], cast=in_cast)
            if lhs is None:
                return None
            return any(
                _truthy(_ch_compare(lhs, process_operand(op), "eq"))
                for op in operation.in_[1]
            )
        elif isinstance(operation, tsi_query.ContainsOperation):
            input_operand = operation.contains_.input
            if (
                isinstance(input_operand, tsi_query.GetFieldOperator)
                and input_operand.get_field_ in table.array_string_cols
            ):
                # Array membership semantics for Array(String) columns.
                rhs = process_operand(operation.contains_.substr)
                values = row.get(input_operand.get_field_) or []
                if operation.contains_.case_insensitive:
                    rhs_text = _to_sql_text(rhs)
                    rhs_lower = rhs_text.lower() if rhs_text is not None else None
                    return any(
                        isinstance(v, str) and v.lower() == rhs_lower for v in values
                    )
                return rhs in values
            lhs = process_operand(input_operand)
            rhs = process_operand(operation.contains_.substr)
            if isinstance(rhs, (bool, int, float)):
                # ClickHouse position() rejects non-string needles; surface
                # the same driver error the real backend produces.
                type_name = "Int64" if isinstance(rhs, int) else "Float64"
                raise DatabaseError(
                    f"Illegal type {type_name} of argument of function position"
                )
            return _ch_position(lhs, rhs, bool(operation.contains_.case_insensitive))
        else:
            raise TypeError(f"Unknown operation type: {operation}")

    def process_binary_operands(
        lhs_op: tsi_query.Operand, rhs_op: tsi_query.Operand
    ) -> tuple[Any, Any]:
        lhs_op, rhs_op = _orm_maybe_datetime_literal(table, lhs_op, rhs_op)
        lhs_cast = (
            tsi_query.infer_literal_filter_cast(rhs_op)
            if isinstance(rhs_op, tsi_query.LiteralOperation)
            else None
        )
        rhs_cast = (
            tsi_query.infer_literal_filter_cast(lhs_op)
            if isinstance(lhs_op, tsi_query.LiteralOperation)
            else None
        )
        return (
            process_operand(lhs_op, cast=lhs_cast),
            process_operand(rhs_op, cast=rhs_cast),
        )

    def process_operand(operand: tsi_query.Operand, cast: str | None = None) -> Any:
        if isinstance(operand, _OrmDatetimeLiteral):
            return operand.value
        if isinstance(operand, tsi_query.LiteralOperation):
            return _orm_literal_value(operand.literal_)
        elif isinstance(operand, tsi_query.GetFieldOperator):
            return _orm_field_value(table, row, operand.get_field_, cast_to=cast)
        elif isinstance(operand, tsi_query.ConvertOperation):
            value = process_operand(operand.convert_.input)
            convert_to = operand.convert_.to
            if convert_to == "exists":
                return value is not None
            return _ch_cast_json_value(_ch_to_string(value), convert_to)
        elif isinstance(
            operand,
            (
                tsi_query.AndOperation,
                tsi_query.OrOperation,
                tsi_query.NotOperation,
                tsi_query.EqOperation,
                tsi_query.GtOperation,
                tsi_query.LtOperation,
                tsi_query.GteOperation,
                tsi_query.LteOperation,
                tsi_query.InOperation,
                tsi_query.ContainsOperation,
            ),
        ):
            return process_operation(operand)
        else:
            raise TypeError(f"Unknown operand type: {operand}")

    return process_operation(query.expr_)


def _orm_is_dynamic_field(table: Table, field_name: str) -> bool:
    if field_name in table.json_cols:
        return True
    return any(field_name.startswith(col + ".") for col in table.json_cols)


def _orm_select(
    table: Table,
    rows: list[dict[str, Any]],
    *,
    project_id: str | None,
    fields: list[str] | None,
    query: tsi.Query | None,
    sort_by: list[SortBy] | None,
    limit: int | None,
    offset: int | None,
) -> list[dict[str, Any]]:
    """Mirror `Table.select()....prepare()` + `tuples_to_rows` on stored rows."""
    if limit is not None and limit < 0:
        raise ValueError("Limit must be non-negative")
    if offset is not None and offset < 0:
        raise ValueError("Offset must be non-negative")
    if sort_by:
        for o in sort_by:
            assert o.direction in {
                "ASC",
                "DESC",
                "asc",
                "desc",
            }, f"Invalid order_by direction: {o.direction}"

    matched = rows
    if project_id is not None:
        matched = [row for row in matched if row.get("project_id") == project_id]
    if query is not None:
        matched = [
            row for row in matched if _truthy(_orm_eval_query(table, row, query))
        ]

    if sort_by:
        # Dynamic (JSON) fields sort with an existence term first, then the
        # toFloat64OrNull cast, then the raw string — the ClickHouse
        # dynamic-field sort triple.
        sort_terms: list[tuple[tuple[str, str], str]] = []
        for clause in sort_by:
            if _orm_is_dynamic_field(table, clause.field):
                sort_terms.append(((clause.field, "exists"), "desc"))
                sort_terms.append(((clause.field, "double"), clause.direction))
                sort_terms.append(((clause.field, "value"), clause.direction))
            else:
                sort_terms.append(((clause.field, "value"), clause.direction))

        def sort_value(row: dict[str, Any], term: tuple[str, str]) -> Any:
            field_name, mode = term
            if mode == "exists":
                return 1 if _orm_field_exists(table, row, field_name) else 0
            if mode == "double":
                value = _orm_field_value(table, row, field_name)
                return _ch_to_float64_or_null(_ch_to_string(value))
            return _orm_field_value(table, row, field_name)

        matched = _ch_sorted_by_terms(matched, sort_terms, sort_value)

    # Field selection: default = all columns.
    fieldnames = fields or [c.name for c in table.cols]

    if any(f.lower() == "count(*)" for f in fieldnames):
        # Aggregate query: one result row (LIMIT/OFFSET apply to that row,
        # not the counted rows). count(*) counts every matched row;
        # non-aggregate fields take the last row's values (permissive
        # no-GROUP-BY behavior; callers only request count(*) alone);
        # no rows yields (0, NULL, ...).
        out: dict[str, Any] = {}
        last_row = matched[-1] if matched else None
        for field_name in fieldnames:
            if field_name.lower() == "count(*)":
                out[field_name] = len(matched)
            elif last_row is None:
                out[field_name] = None
            else:
                normalized = (
                    field_name[:-5] if field_name.endswith("_dump") else field_name
                )
                if normalized in table.col_types:
                    out[normalized] = copy.deepcopy(last_row.get(normalized))
                else:
                    out[field_name] = copy.deepcopy(
                        _orm_field_value(table, last_row, field_name)
                    )
        agg_rows = [out]
        if offset is not None:
            agg_rows = agg_rows[offset:]
        if limit is not None:
            agg_rows = agg_rows[:limit]
        return agg_rows

    if offset is not None:
        matched = matched[offset:]
    if limit is not None:
        matched = matched[:limit]

    result = []
    for row in matched:
        row_out: dict[str, Any] = {}
        for field_name in fieldnames:
            normalized = field_name[:-5] if field_name.endswith("_dump") else field_name
            if normalized in table.col_types:
                value = row.get(normalized)
                row_out[normalized] = copy.deepcopy(value)
            else:
                row_out[field_name] = copy.deepcopy(
                    _orm_field_value(table, row, field_name)
                )
        result.append(row_out)
    return result


# ---------------------------------------------------------------------------
# Feedback stats helpers (Python ports of methods/feedback_stats.py)
# ---------------------------------------------------------------------------


def _extract_stats_value(payload_str: str, json_path: str, value_type: str) -> Any:
    """Extract a value from a JSON payload string at a dot path."""
    try:
        obj = json.loads(payload_str)
    except (json.JSONDecodeError, TypeError):
        return None
    for part in json_path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
        if obj is None:
            return None
    if value_type == "numeric":
        try:
            return float(obj)
        except (TypeError, ValueError):
            return None
    if value_type == "boolean":
        if isinstance(obj, bool):
            return obj
        if isinstance(obj, str):
            if obj.lower() == "true":
                return True
            if obj.lower() == "false":
                return False
        return None
    return obj


def _parse_feedback_row_ts(created_at_str: str) -> datetime.datetime:
    """Parse a stored created_at string into a UTC datetime."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.datetime.strptime(created_at_str, fmt).replace(
                tzinfo=datetime.timezone.utc
            )
        except ValueError:
            continue
    return datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))


def _stats_bucket_key(
    ts: datetime.datetime, start: datetime.datetime, granularity: int
) -> datetime.datetime:
    offset = int((ts - start).total_seconds())
    bucket_offset = (offset // granularity) * granularity
    return start + datetime.timedelta(seconds=bucket_offset)


def _compute_stats_agg(
    values: list[float],
    agg: str,
) -> float | None:
    if not values:
        return None
    if agg == "avg":
        return statistics.mean(values)
    if agg == "sum":
        return math.fsum(values)
    if agg == "min":
        return min(values)
    if agg == "max":
        return max(values)
    if agg == "count":
        return float(len(values))
    return None


def _compute_stats_percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (pct / 100.0) * (len(s) - 1)
    f = int(k)
    c = f + 1
    if c >= len(s):
        return s[-1]
    return s[f] + (k - f) * (s[c] - s[f])
