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
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from operator import attrgetter
from typing import Any, cast

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
from weave.trace_server import trace_server_interface as tsi
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
    InvalidFieldError,
    InvalidRequest,
    NotFoundError,
    ObjectDeletedError,
    ObjectNameTypeCollision,
    RequestTooLarge,
)
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.interface.feedback_types import (
    MULTI_VALUE_FEEDBACK_TYPES,
)
from weave.trace_server.opentelemetry.helpers import AttributePathConflictError
from weave.trace_server.opentelemetry.python_spans import Resource, Span
from weave.trace_server.orm import split_escaped_field_path
from weave.trace_server.trace_server_common import (
    apply_tags_and_synth_latest_in_place,
    assert_parameter_length_less_than_max,
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
