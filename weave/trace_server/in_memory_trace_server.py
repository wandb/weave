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
import threading
from dataclasses import dataclass, field
from typing import Any, cast

from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans

from weave.shared import refs_internal as ri
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
from weave.trace_server.errors import (
    InvalidRequest,
    RequestTooLarge,
)
from weave.trace_server.opentelemetry.helpers import AttributePathConflictError
from weave.trace_server.opentelemetry.python_spans import Resource, Span
from weave.trace_server.ttl_settings import (
    RETENTION_DAYS_NO_TTL,
    compute_expire_at,
    invalidate_ttl_cache,
)
from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
    EvaluateModelDispatcher,
)

MAX_OTEL_ERROR_MESSAGES = 20


def _ensure_tz(dt: datetime.datetime) -> datetime.datetime:
    """Coerce a datetime to tz-aware UTC (naive datetimes are UTC wall time)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


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
