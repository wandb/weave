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
import threading
from dataclasses import dataclass, field
from typing import Any, cast

from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans

from weave.shared import refs_internal as ri
from weave.shared.digest import (
    compute_object_digest_result,
)
from weave.shared.trace_server_interface_util import (
    assert_non_null_wb_user_id,
    extract_refs_from_values,
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
    InvalidRequest,
    NotFoundError,
    ObjectDeletedError,
    ObjectNameTypeCollision,
    RequestTooLarge,
)
from weave.trace_server.opentelemetry.helpers import AttributePathConflictError
from weave.trace_server.opentelemetry.python_spans import Resource, Span
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

MAX_OTEL_ERROR_MESSAGES = 20


def _ensure_tz(dt: datetime.datetime) -> datetime.datetime:
    """Coerce a datetime to tz-aware UTC (naive datetimes are UTC wall time)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def _value_rank(value: Any) -> int:
    # Legacy storage-class ranks (NULL < numeric < text), used by the
    # remaining generic sorters until they move to _ch_sorted_by_terms.
    if value is None:
        return 0
    if isinstance(value, (bool, int, float)):
        return 1
    return 2


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
