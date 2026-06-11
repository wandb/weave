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

import datetime
import json
import logging
import math
import re
import statistics
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import lru_cache
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
    assert_non_null_wb_user_id,
    extract_refs_from_values,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.stats_query_base import (
    GRANULARITY_1H,
    auto_select_granularity_seconds,
    ensure_max_buckets,
)
from weave.trace_server.ch_sentinel_values import EXPIRE_AT_NEVER

# Completion request preparation (prompt resolution, provider/secret setup) is
# backend-agnostic business logic that currently lives in the ClickHouse
# module; import it rather than fork it.
from weave.trace_server.clickhouse_trace_server_settings import (
    MAX_DELETE_CALLS_COUNT,
)
from weave.trace_server.common_interface import SortBy
from weave.trace_server.digest_validation import validate_expected_digest
from weave.trace_server.errors import (
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
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.opentelemetry.helpers import AttributePathConflictError
from weave.trace_server.opentelemetry.python_spans import Resource, Span
from weave.trace_server.orm import Table, split_escaped_field_path
from weave.trace_server.token_costs import (
    DEFAULT_PRICING_LEVEL_ID,
    LLM_TOKEN_PRICES_TABLE,
    PRICING_LEVELS,
    validate_cost_purge_req,
)
from weave.trace_server.trace_server_common import (
    apply_tags_and_synth_latest_in_place,
    digest_is_content_hash,
    digest_is_version_like,
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


def _ensure_tz(dt: datetime.datetime) -> datetime.datetime:
    """Coerce a datetime to tz-aware UTC (naive datetimes are UTC wall time)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


# ---------------------------------------------------------------------------
# Generic JSON value helpers (dict-shaped doc traversal + stable ordering)
# ---------------------------------------------------------------------------


def _minify_json(val: Any) -> str:
    """JSON text with minified separators, as the backends store dumps."""
    return json.dumps(val, separators=(",", ":"))


def _json_deep_copy(val: Any) -> Any:
    """Deep-copy a JSON-shaped value (dict/list/scalars).

    Every returned call/row copies its payloads through here, making this the
    hottest read-path allocation. copy.deepcopy works but its generic
    machinery (memo dict, reduce protocol, class dispatch) measures 1.6-4x
    slower on representative payloads. Plain recursion is safe because the
    write path normalizes all stored payloads to JSON shapes via
    json.dumps/json.loads.
    """
    if isinstance(val, dict):
        return {k: _json_deep_copy(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_json_deep_copy(v) for v in val]
    return val


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


_CH_INT64_RE = re.compile(r"^[+-]?\d+$")


def _to_int64_or_null(value: Any) -> int | None:
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


def _to_float64_or_null(value: Any) -> float | None:
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


def _to_uint8_or_null(value: Any) -> int | None:
    """ClickHouse toUInt8OrNull over a string expression."""
    parsed = _to_int64_or_null(value)
    if parsed is None or parsed < 0 or parsed > 255:
        return None
    return parsed


def _ch_cast_json_value(value: str | None, cast_to: str | None) -> Any:
    """Mirror clickhouse_cast_json_value applied to a JSON_VALUE string."""
    if cast_to is None or cast_to == "string":
        return value
    if cast_to == "int":
        return _to_int64_or_null(value)
    if cast_to in {"double", "float"}:
        return _to_float64_or_null(value)
    if cast_to == "bool":
        if value == "true":
            return 1
        if value == "false":
            return 0
        return _to_uint8_or_null(value)
    raise ValueError(f"Unknown cast: {cast_to}")


def _to_ch_string(value: Any) -> str | None:
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
    terms: list[tuple[Any, str]],
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


class _OrderableOrNone:  # noqa: PLW1641 (sort key; never hashed)
    """Sort key wrapper: None compares equal to everything (its final
    position is decided by the stable NULLs-last pass).
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _OrderableOrNone):
            return NotImplemented
        return self.value == other.value


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
        # Calls keyed by id (unique per call in practice; reads filter by
        # project_id, mirroring ClickHouse reads scoped by (project_id, id)).
        self._calls: dict[str, _CallRec] = {}
        # Objects keyed by (project_id, kind, object_id, digest), insertion
        # ordered (rowid order matters for version_index and tie-breaks).
        self._objs: dict[tuple[str, str, str, str], _ObjRec] = {}
        # Tables keyed by (project_id, digest) -> ordered row digests.
        self._tables: dict[tuple[str, str], list[str]] = {}
        # Table rows keyed by digest (content-addressed, first-writer-wins:
        # first writer wins, reads filter on project_id).
        self._table_rows: dict[str, _TableRowRec] = {}
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
                    otel_dump=_json_deep_copy(call.otel_dump),
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
                self._calls[rec.id] = rec
        return tsi.CallsUpsertCompleteRes()

    def call_start_v2(self, req: tsi.CallStartV2Req) -> tsi.CallStartV2Res:
        res = self.call_start(tsi.CallStartReq(start=req.start))
        return tsi.CallStartV2Res(id=res.id, trace_id=res.trace_id)

    def call_end_v2(self, req: tsi.CallEndV2Req) -> tsi.CallEndV2Res:
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
            existing = self._calls.get(req.start.id)
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
                existing.otel_dump = _json_deep_copy(req.start.otel_dump)
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
                    otel_dump=_json_deep_copy(req.start.otel_dump),
                    otel_dump_len=(
                        len(json.dumps(req.start.otel_dump))
                        if req.start.otel_dump is not None
                        else None
                    ),
                    expire_at=expire_at,
                    attributes_len=len(attributes_json),
                    inputs_len=len(inputs_json),
                )
                self._calls[rec.id] = rec

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
            rec = self._calls.get(req.end.id)
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
                self._calls[rec.id] = rec
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
                rec = self._calls.get(call_id)
                if rec is not None and rec.deleted_at is None:
                    rec.deleted_at = deleted_at

        return tsi.CallsDeleteRes(num_deleted=len(all_ids))

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        assert_non_null_wb_user_id(req)
        if req.display_name is None:
            raise ValueError("One of [display_name] is required for call update")

        with self.lock:
            rec = self._calls.get(req.call_id)
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
            val={} if metadata_only else _json_deep_copy(rec.val),
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
                if row_digest not in self._table_rows:
                    self._table_rows[row_digest] = _TableRowRec(
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
                if row_digest not in self._table_rows:
                    self._table_rows[row_digest] = _TableRowRec(
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
                row_rec = self._table_rows.get(row_digest)
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
                    val=_json_deep_copy(val),
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
                        if (rec := self._table_rows.get(row_digest)) is not None
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
                rec = self._table_rows.get(digest)
                if rec is not None and rec.project_id == project_id:
                    result[digest] = _json_deep_copy(rec.val)
            return result

    def _table_row_read(self, project_id: str, row_digest: str) -> tsi.TableRowSchema:
        with self.lock:
            rec = self._table_rows.get(row_digest)
            if rec is None or rec.project_id != project_id:
                raise NotFoundError(f"Row {row_digest} not found")
            return tsi.TableRowSchema(digest=row_digest, val=_json_deep_copy(rec.val))

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
        """Compute feedback stats with in-memory rows + Python aggregation."""
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
        with self.lock:
            rows = [
                row for row in self._feedback if _feedback_aggregate_matches(row, req)
            ]

        bucketed = req.time_bucket_seconds is not None
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for row in rows:
            key: list[Any] = []
            if bucketed:
                epoch_s = row["created_at"].timestamp()
                bucket_start_s = (
                    int(epoch_s // req.time_bucket_seconds) * req.time_bucket_seconds
                )
                key.append(bucket_start_s * 1000)
            for dimension in req.group_by:
                key.append(_feedback_aggregate_dimension(row, dimension))
            groups.setdefault(tuple(key), []).append(row)

        if not bucketed and not req.group_by:
            # No GROUP BY keys: ClickHouse global aggregation always yields
            # one row, even over an empty selection.
            groups.setdefault((), [])

        # ORDER BY bucket for a time series; otherwise by the group_by
        # dimensions for a deterministic row order.
        if bucketed:
            ordered_keys = sorted(groups, key=lambda key: key[0])
        else:
            ordered_keys = sorted(groups)

        buckets: list[tsi.FeedbackAggregateBucket] = []
        for key in ordered_keys:
            group_rows = groups[key]
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
            dims = key[1:] if bucketed else key
            buckets.append(
                tsi.FeedbackAggregateBucket(
                    time_bucket_start_ms=key[0] if bucketed else None,
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
    # OTel export
    # ------------------------------------------------------------------

    def otel_export(self, req: tsi.OTelExportReq) -> tsi.OTelExportRes:
        calls: list[dict[str, object]] = []
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
                            {
                                "mode": "start",
                                "req": tsi.CallStartReq(start=start_call),
                            },
                            {"mode": "end", "req": tsi.CallEndReq(end=end_call)},
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
            return _ch_position(lhs, rhs, operation.contains_.case_insensitive)
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
            return _ch_cast_json_value(_to_ch_string(value), convert_to)
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
                return _to_float64_or_null(_to_ch_string(value))
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
                    out[normalized] = _json_deep_copy(last_row.get(normalized))
                else:
                    out[field_name] = _json_deep_copy(
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
        out: dict[str, Any] = {}
        for field_name in fieldnames:
            normalized = field_name[:-5] if field_name.endswith("_dump") else field_name
            if normalized in table.col_types:
                value = row.get(normalized)
                out[normalized] = _json_deep_copy(value)
            else:
                out[field_name] = _json_deep_copy(
                    _orm_field_value(table, row, field_name)
                )
        result.append(out)
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
