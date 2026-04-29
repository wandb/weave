from __future__ import annotations

import datetime
import json
from collections.abc import Callable, Iterator
from enum import Enum
from functools import cache, cmp_to_key
from pathlib import Path
from typing import Any

from weave.shared import (
    compute_file_digest,
    compute_object_digest_result,
    compute_row_digest,
    compute_table_digest,
    refs_internal,
)
from weave.shared.trace_server_interface_util import extract_refs_from_values
from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import (
    constants,
    eval_results_helpers,
    object_creation_utils,
    usage_utils,
    validation,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.digest_validation import validate_expected_digest
from weave.trace_server.errors import NotFoundError, ObjectDeletedError
from weave.trace_server.feedback import (
    process_feedback_payload,
    validate_feedback_create_req,
    validate_feedback_purge_req,
)
from weave.trace_server.ids import generate_id
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.methods.evaluation_status import evaluation_status
from weave.trace_server.token_costs import validate_cost_purge_req
from weave.trace_server.trace_server_common import (
    get_prediction_inputs,
    make_derived_summary_fields,
    op_name_matches,
    scorer_read_res_from_obj,
)
from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
    EvaluateModelArgs,
    EvaluateModelDispatcher,
)

_DATETIME_TYPE = datetime.datetime

_UNSUPPORTED_TRACE_SERVER_METHODS = {
    "annotation_queue_add_calls",
    "annotation_queue_create",
    "annotation_queue_delete",
    "annotation_queue_read",
    "annotation_queue_update",
    "annotation_queue_items_query",
    "annotation_queues_query_stream",
    "annotation_queues_stats",
    "annotator_queue_items_progress_update",
    "call_stats",
    "calls_score",
    "calls_usage",
    "completions_create",
    "completions_create_stream",
    "dataset_create",
    "dataset_delete",
    "dataset_list",
    "dataset_read",
    "eval_results_query",
    "evaluate_model",
    "evaluation_create",
    "evaluation_delete",
    "evaluation_list",
    "evaluation_read",
    "evaluation_run_create",
    "evaluation_run_delete",
    "evaluation_run_finish",
    "evaluation_run_list",
    "evaluation_run_read",
    "evaluation_status",
    "feedback_payload_schema",
    "feedback_stats",
    "image_create",
    "model_create",
    "model_delete",
    "model_list",
    "model_read",
    "op_create",
    "op_delete",
    "op_list",
    "op_read",
    "otel_export",
    "prediction_create",
    "prediction_delete",
    "prediction_finish",
    "prediction_list",
    "prediction_read",
    "score_create",
    "score_delete",
    "score_list",
    "score_read",
    "trace_usage",
}


class FakeTraceServer(tsi.FullTraceServerInterface):
    """Test-only in-memory trace server for fast client and flow tests."""

    def __init__(
        self, evaluate_model_dispatcher: EvaluateModelDispatcher | None = None
    ) -> None:
        self._calls: dict[tuple[str, str], tsi.CallSchema] = {}
        self._objects: dict[tuple[str, str, str, str], tsi.ObjSchema] = {}
        self._tables: dict[tuple[str, str], list[tsi.TableRowSchema]] = {}
        self._row_values: dict[str, dict[str, Any]] = {}
        self._files: dict[tuple[str, str], bytes] = {}
        self._feedback: list[tsi.Feedback] = []
        self._costs: list[tsi.CostQueryOutput] = []
        self._cost_extra: dict[str, dict[str, Any]] = {}
        self._evaluation_runs: dict[tuple[str, str], tsi.EvaluationRunReadRes] = {}
        self._predictions: dict[tuple[str, str], tsi.PredictionReadRes] = {}
        self._scores: dict[tuple[str, str], tsi.ScoreReadRes] = {}
        self._score_prediction_ids: dict[tuple[str, str], str] = {}
        self._prediction_parent_ids: dict[tuple[str, str], str] = {}
        self._evaluate_model_dispatcher = evaluate_model_dispatcher
        self.remote_request_bytes_limit = 10_000_000

    def close(self) -> None:
        pass

    def get_call_processor(self) -> None:
        return None

    def get_feedback_processor(self) -> None:
        return None

    def __getattr__(self, name: str) -> Callable[..., Any]:
        if name not in _UNSUPPORTED_TRACE_SERVER_METHODS:
            raise AttributeError(name)

        def unsupported(*args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError(f"FakeTraceServer does not implement {name}")

        return unsupported

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        start = req.start
        call_id = start.id or generate_id()
        trace_id = start.trace_id or call_id
        inputs = _strip_if_too_large(start.inputs)
        attributes = _strip_if_too_large(start.attributes)
        call = tsi.CallSchema(
            id=call_id,
            project_id=start.project_id,
            op_name=start.op_name,
            display_name=start.display_name,
            trace_id=trace_id,
            parent_id=start.parent_id,
            thread_id=start.thread_id,
            turn_id=start.turn_id,
            started_at=start.started_at,
            attributes=attributes,
            inputs=inputs,
            wb_user_id=start.wb_user_id,
            wb_run_id=start.wb_run_id,
            wb_run_step=start.wb_run_step,
            summary=_jsonable(
                make_derived_summary_fields(
                    {},
                    start.op_name,
                    start.started_at,
                    None,
                    None,
                    start.display_name,
                )
            ),
        )
        self._calls[call.project_id, call.id] = _strip_call_large_values(call)
        return tsi.CallStartRes(id=call_id, trace_id=trace_id)

    def call_start_v2(self, req: tsi.CallStartV2Req) -> tsi.CallStartV2Res:
        res = self.call_start(tsi.CallStartReq(start=req.start))
        return tsi.CallStartV2Res(id=res.id, trace_id=res.trace_id)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        self._end_call(req.end)
        return tsi.CallEndRes()

    def call_end_v2(self, req: tsi.CallEndV2Req) -> tsi.CallEndV2Res:
        self._end_call(req.end)
        return tsi.CallEndV2Res()

    def _end_call(self, end: tsi.EndedCallSchemaForInsert) -> None:
        key = (end.project_id, end.id)
        call = self._calls.get(key)
        if call is None:
            return
        updated_call = call.model_copy(
            update={
                "ended_at": end.ended_at,
                "exception": end.exception,
                "output": _strip_if_too_large(end.output),
                "summary": _jsonable(
                    make_derived_summary_fields(
                        _strip_if_too_large(dict(end.summary)),
                        call.op_name,
                        call.started_at,
                        end.ended_at,
                        end.exception,
                        call.display_name,
                    )
                ),
                "wb_run_step_end": end.wb_run_step_end,
            }
        )
        self._calls[key] = _strip_call_large_values(updated_call)

    def calls_complete(
        self, req: tsi.CallsUpsertCompleteReq
    ) -> tsi.CallsUpsertCompleteRes:
        for complete in req.batch:
            inputs = _strip_if_too_large(complete.inputs)
            attributes = _strip_if_too_large(complete.attributes)
            output = _strip_if_too_large(complete.output)
            call = tsi.CallSchema(
                id=complete.id,
                project_id=complete.project_id,
                op_name=complete.op_name,
                display_name=complete.display_name,
                trace_id=complete.trace_id,
                parent_id=complete.parent_id,
                thread_id=complete.thread_id,
                turn_id=complete.turn_id,
                started_at=complete.started_at,
                attributes=attributes,
                inputs=inputs,
                ended_at=complete.ended_at,
                exception=complete.exception,
                output=output,
                summary=_jsonable(
                    make_derived_summary_fields(
                        _strip_if_too_large(dict(complete.summary)),
                        complete.op_name,
                        complete.started_at,
                        complete.ended_at,
                        complete.exception,
                        complete.display_name,
                    )
                ),
                wb_user_id=complete.wb_user_id,
                wb_run_id=complete.wb_run_id,
                wb_run_step=complete.wb_run_step,
                wb_run_step_end=complete.wb_run_step_end,
            )
            self._calls[call.project_id, call.id] = _strip_call_large_values(call)
        return tsi.CallsUpsertCompleteRes()

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        results: list[tsi.CallStartRes | tsi.CallEndRes] = []
        for item in req.batch:
            if item.mode == "start":
                results.append(self.call_start(item.req))
            elif item.mode == "end":
                results.append(self.call_end(item.req))
            else:
                raise NotImplementedError(f"FakeTraceServer does not support {item.mode}")
        return tsi.CallCreateBatchRes(res=results)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        call = self._calls.get((req.project_id, req.id))
        if call is not None and call.deleted_at is not None:
            call = None
        return tsi.CallReadRes(call=call)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        return tsi.CallsQueryRes(calls=list(self.calls_query_stream(req)))

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        _validate_calls_filter(req.filter)
        calls = [
            call
            for call in self._calls.values()
            if call.project_id == req.project_id and call.deleted_at is None
        ]
        calls = [call for call in calls if _matches_calls_filter(call, req.filter)]
        rows = [
            (call, self._call_query_row(call, req.expand_columns))
            for call in calls
        ]
        rows = [(call, row) for call, row in rows if _matches_query(row, req.query)]
        rows = _sort_items(rows, req.sort_by, lambda item: item[1])
        for call, _ in _page(rows, req.offset, req.limit):
            output_call = call
            if req.include_costs:
                output_call = self._call_with_costs(output_call)
            if req.include_feedback:
                output_call = self._call_with_feedback(output_call)
            if req.expand_columns:
                output_call = self._expanded_call(
                    output_call,
                    req.expand_columns,
                    bool(req.return_expanded_column_values),
                )
            yield self._project_call(output_call, req.columns, bool(req.include_costs))

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        if req.limit is not None and req.limit < 0:
            raise ValueError("Limit must be greater than or equal to 0")
        if req.filter is not None and req.filter.thread_ids == []:
            return tsi.CallsQueryStatsRes(count=0, total_storage_size_bytes=0)
        query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=req.filter,
            query=req.query,
            limit=req.limit,
        )
        return tsi.CallsQueryStatsRes(
            count=len(list(self.calls_query_stream(query_req))),
            total_storage_size_bytes=0,
        )

    def _call_query_row(
        self, call: tsi.CallSchema, expand_columns: list[str] | None = None
    ) -> dict[str, Any]:
        row = _dump(call)
        for path in expand_columns or []:
            _expand_path_for_query(row, path, self._read_ref_value)
        if call.display_name is not None:
            summary = dict(row.get("summary") or {})
            weave_summary = dict(summary.get("weave") or {})
            weave_summary["trace_name"] = call.display_name
            weave_summary["display_name"] = call.display_name
            summary["weave"] = weave_summary
            row["summary"] = summary
        grouped: dict[str, list[dict[str, Any]]] = {}
        for feedback in self._feedback_for_call(call):
            grouped.setdefault(feedback.feedback_type, []).append(_dump(feedback))
        row["feedback"] = grouped
        return row

    def _feedback_for_call(self, call: tsi.CallSchema) -> list[tsi.Feedback]:
        return [
            feedback
            for feedback in self._feedback
            if _feedback_matches_call(feedback, call)
        ]

    def _call_with_feedback(self, call: tsi.CallSchema) -> tsi.CallSchema:
        feedback = [_dump(item) for item in self._feedback_for_call(call)]
        summary = dict(call.summary or {})
        weave_summary = dict(summary.get("weave") or {})
        weave_summary["feedback"] = feedback
        summary["weave"] = weave_summary
        return call.model_copy(update={"summary": _jsonable(summary)})

    def _call_with_costs(self, call: tsi.CallSchema) -> tsi.CallSchema:
        summary = dict(call.summary or {})
        usage = summary.get("usage")
        if not isinstance(usage, dict):
            return call
        costs: dict[str, Any] = {}
        for llm_id, model_usage in usage.items():
            if not isinstance(model_usage, dict):
                continue
            cost_entry = self._cost_for_model(str(llm_id), call.started_at)
            if cost_entry is None:
                continue
            prompt_tokens = _token_count(model_usage, "prompt_tokens", "input_tokens")
            completion_tokens = _token_count(
                model_usage, "completion_tokens", "output_tokens"
            )
            cache_read_tokens = _token_count(
                model_usage, "cache_read_input_tokens", "cache_read_tokens"
            )
            cache_creation_tokens = _token_count(
                model_usage,
                "cache_creation_input_tokens",
                "cache_creation_tokens",
            )
            prompt_cost = float(cost_entry.get("prompt_token_cost") or 0)
            completion_cost = float(cost_entry.get("completion_token_cost") or 0)
            cache_read_cost = float(cost_entry.get("cache_read_input_token_cost") or 0)
            cache_creation_cost = float(
                cost_entry.get("cache_creation_input_token_cost") or 0
            )
            costs[str(llm_id)] = {
                **model_usage,
                **cost_entry,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": _token_count(model_usage, "total_tokens", ""),
                "cache_read_input_tokens": cache_read_tokens,
                "cache_creation_input_tokens": cache_creation_tokens,
                "prompt_tokens_total_cost": prompt_tokens * prompt_cost,
                "completion_tokens_total_cost": completion_tokens * completion_cost,
                "cache_read_input_tokens_total_cost": cache_read_tokens
                * cache_read_cost,
                "cache_creation_input_tokens_total_cost": cache_creation_tokens
                * cache_creation_cost,
            }
        if costs:
            weave_summary = dict(summary.get("weave") or {})
            weave_summary["costs"] = costs
            summary["weave"] = weave_summary
        return call.model_copy(update={"summary": _jsonable(summary)})

    def _cost_for_model(
        self, llm_id: str, effective_at: datetime.datetime
    ) -> dict[str, Any] | None:
        matching = []
        for cost in self._costs:
            if cost.llm_id != llm_id or cost.id is None:
                continue
            data = {**_dump(cost), **self._cost_extra.get(cost.id, {})}
            matching.append(data)
        if matching:
            return max(matching, key=lambda row: row.get("effective_date") or _EPOCH)
        return _default_cost_for_model(llm_id)

    def _expanded_call(
        self,
        call: tsi.CallSchema,
        expand_columns: list[str] | None,
        return_values: bool,
    ) -> tsi.CallSchema:
        if not expand_columns or not return_values:
            return call
        row = _dump(call)
        for path in expand_columns:
            _expand_path(row, path, self._read_ref_value)
        return call.model_copy(update=_call_update_from_row(row))

    def _read_ref_value(self, value: str) -> Any:
        try:
            parsed = refs_internal.parse_internal_uri(value)
        except refs_internal.InvalidInternalRef:
            return None
        if isinstance(parsed, refs_internal.InternalTableRef):
            return None
        resolved = self._read_ref(value)
        if isinstance(parsed, refs_internal.InternalObjectRef) and isinstance(
            resolved, dict
        ):
            return {"_ref": value, **resolved}
        return resolved

    def _project_call(
        self,
        call: tsi.CallSchema,
        columns: list[str] | None,
        include_costs: bool,
    ) -> tsi.CallSchema:
        if columns is None:
            return call

        keep_summary = include_costs or any(
            col in {"summary", "summary_dump"} or col.startswith("summary.")
            for col in columns
        )
        keep_ended_at = keep_summary or "ended_at" in columns
        updates: dict[str, Any] = {
            "attributes": {},
            "inputs": {},
            "output": None,
            "summary": call.summary if keep_summary else {},
            "ended_at": call.ended_at if keep_ended_at else None,
        }

        source = _dump(call)
        for col in columns:
            root = col.split(".", 1)[0]
            if root == "inputs":
                updates["inputs"] = call.inputs
            elif root in {"output", "output_dump"}:
                if col == "output":
                    updates["output"] = call.output
                else:
                    value = _get_path(source, col)
                    if value is None and isinstance(call.output, str):
                        updates["output"] = call.output
                    else:
                        updates["output"] = call.output
            elif root == "attributes":
                updates["attributes"] = call.attributes
            elif root in {"summary", "summary_dump"}:
                updates["summary"] = call.summary
            elif hasattr(call, root):
                updates[root] = getattr(call, root)
        return call.model_copy(update=updates)

    def call_stats(self, req: tsi.CallStatsReq) -> tsi.CallStatsRes:
        end = req.end or _now()
        granularity = req.granularity or 3600
        calls = [
            call
            for call in self._calls.values()
            if call.project_id == req.project_id
            and call.deleted_at is None
            and req.start <= call.started_at < end
            and _matches_calls_filter(call, req.filter)
        ]
        usage_values: dict[tuple[datetime.datetime, str, str], list[float]] = {}
        call_values: dict[tuple[datetime.datetime, str], list[float]] = {}
        for call in calls:
            bucket = _bucket_start(call.started_at, req.start, granularity)
            summary = call.summary if isinstance(call.summary, dict) else {}
            usage = summary.get("usage", {})
            if isinstance(usage, dict):
                for model, model_usage in usage.items():
                    if not isinstance(model_usage, dict):
                        continue
                    normalized = _normalize_usage_metrics(model_usage)
                    for metric in req.usage_metrics or []:
                        value = normalized.get(metric.metric, 0)
                        usage_values.setdefault(
                            (bucket, str(model), metric.metric), []
                        ).append(float(value))
            for metric in req.call_metrics or []:
                value = _call_metric_value(call, metric.metric)
                call_values.setdefault((bucket, metric.metric), []).append(float(value))

        usage_rows: dict[tuple[datetime.datetime, str], dict[str, Any]] = {}
        for (bucket, model, metric), values in usage_values.items():
            row = usage_rows.setdefault(
                (bucket, model), {"timestamp": bucket, "model": model}
            )
            _add_aggregations(
                row,
                metric,
                values,
                next(
                    spec
                    for spec in req.usage_metrics or []
                    if spec.metric == metric
                ),
            )

        call_rows: dict[datetime.datetime, dict[str, Any]] = {}
        for (bucket, metric), values in call_values.items():
            row = call_rows.setdefault(bucket, {"timestamp": bucket})
            _add_aggregations(
                row,
                metric,
                values,
                next(
                    spec
                    for spec in req.call_metrics or []
                    if spec.metric == metric
                ),
            )

        return tsi.CallStatsRes(
            start=req.start,
            end=end,
            granularity=granularity,
            timezone=req.timezone,
            usage_buckets=sorted(
                usage_rows.values(), key=lambda row: (row["timestamp"], row["model"])
            ),
            call_buckets=sorted(call_rows.values(), key=lambda row: row["timestamp"]),
        )

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        deleted_at = _now()
        count = 0
        to_delete = set(req.call_ids)
        changed = True
        while changed:
            changed = False
            for call in self._calls.values():
                if (
                    call.project_id == req.project_id
                    and call.deleted_at is None
                    and call.parent_id in to_delete
                    and call.id not in to_delete
                ):
                    to_delete.add(call.id)
                    changed = True

        for call_id in to_delete:
            key = (req.project_id, call_id)
            call = self._calls.get(key)
            if call is not None and call.deleted_at is None:
                self._calls[key] = call.model_copy(update={"deleted_at": deleted_at})
                count += 1
        return tsi.CallsDeleteRes(num_deleted=count)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        key = (req.project_id, req.call_id)
        call = self._calls.get(key)
        if call is not None:
            display_name = req.display_name or None
            self._calls[key] = call.model_copy(
                update={
                    "display_name": display_name,
                    "summary": _jsonable(
                        make_derived_summary_fields(
                            dict(call.summary or {}),
                            call.op_name,
                            call.started_at,
                            call.ended_at,
                            call.exception,
                            display_name,
                        )
                    ),
                }
            )
        return tsi.CallUpdateRes()

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        validation.object_id_validator(req.obj.object_id)
        digest_result = compute_object_digest_result(
            req.obj.val, req.obj.builtin_object_class
        )
        validate_expected_digest(
            expected=req.obj.expected_digest,
            actual=digest_result.digest,
            label=f"obj {req.obj.object_id!r}",
        )
        kind = _get_kind(digest_result.processed_val)
        object_key_prefix = (req.obj.project_id, kind, req.obj.object_id)
        version_index = len(
            [
                obj
                for key, obj in self._objects.items()
                if key[:3] == object_key_prefix
            ]
        )
        for key, obj in list(self._objects.items()):
            if key[:3] == object_key_prefix:
                aliases = [alias for alias in obj.aliases or [] if alias != "latest"]
                self._objects[key] = obj.model_copy(
                    update={"is_latest": 0, "aliases": aliases}
                )
        obj = tsi.ObjSchema(
            project_id=req.obj.project_id,
            object_id=req.obj.object_id,
            created_at=_now(),
            digest=digest_result.digest,
            version_index=version_index,
            is_latest=1,
            kind=kind,
            base_object_class=digest_result.base_object_class,
            leaf_object_class=digest_result.leaf_object_class,
            val=digest_result.processed_val,
            wb_user_id=req.obj.wb_user_id,
            size_bytes=_storage_size(digest_result.processed_val),
            tags=[],
            aliases=["latest"],
        )
        self._objects[(*object_key_prefix, obj.digest)] = obj
        return tsi.ObjCreateRes(digest=obj.digest, object_id=obj.object_id)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        obj = self._read_object_or_raise(
            req.project_id, None, req.object_id, req.digest
        )
        if obj is not None and req.metadata_only:
            obj = obj.model_copy(update={"val": {}})
        obj = _with_tags_aliases(obj, bool(req.include_tags_and_aliases))
        return tsi.ObjReadRes(obj=obj)

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        objs = [
            obj
            for obj in self._objects.values()
            if obj.project_id == req.project_id and obj.deleted_at is None
        ]
        objs = [obj for obj in objs if _matches_object_filter(obj, req.filter)]
        objs = _sort_items(objs, req.sort_by, _dump)
        objs = list(_page(objs, req.offset, req.limit))
        if req.metadata_only:
            objs = [obj.model_copy(update={"val": {}}) for obj in objs]
        objs = [
            _with_tags_aliases(obj, bool(req.include_tags_and_aliases))
            for obj in objs
        ]
        return tsi.ObjQueryRes(objs=objs)

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        return tsi.ObjDeleteRes(
            num_deleted=self._delete_object_versions(
                req.project_id, None, req.object_id, req.digests
            )
        )

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

    def evaluation_status(
        self, req: tsi.EvaluationStatusReq
    ) -> tsi.EvaluationStatusRes:
        return evaluation_status(self, req)

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        source_code = req.source_code or object_creation_utils.PLACEHOLDER_OP_SOURCE
        source_file_res = self.file_create(
            tsi.FileCreateReq(
                project_id=req.project_id,
                name=object_creation_utils.OP_SOURCE_FILE_NAME,
                content=source_code.encode("utf-8"),
            )
        )
        object_id = object_creation_utils.make_object_id(req.name, "Op")
        obj_result = self.obj_create(
            tsi.ObjCreateReq(
                obj=tsi.ObjSchemaForInsert(
                    project_id=req.project_id,
                    object_id=object_id,
                    val=object_creation_utils.build_op_val(source_file_res.digest),
                    wb_user_id=req.wb_user_id,
                )
            )
        )
        obj = self._read_object_or_raise(
            req.project_id, "op", object_id, obj_result.digest
        )
        return tsi.OpCreateRes(
            digest=obj.digest,
            object_id=object_id,
            version_index=obj.version_index,
        )

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        obj = self._read_object_or_raise(
            req.project_id, "op", req.object_id, req.digest
        )
        code = self._op_code(req.project_id, obj.val)
        return tsi.OpReadRes(
            object_id=obj.object_id,
            digest=obj.digest,
            version_index=obj.version_index,
            created_at=obj.created_at,
            code=code,
        )

    def op_list(self, req: tsi.OpListReq) -> Iterator[tsi.OpReadRes]:
        result = self.objs_query(
            tsi.ObjQueryReq(
                project_id=req.project_id,
                filter=tsi.ObjectVersionFilter(is_op=True, latest_only=True),
                limit=req.limit,
                offset=req.offset,
                metadata_only=False,
            )
        )
        for obj in result.objs:
            yield tsi.OpReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                code=self._op_code(req.project_id, obj.val),
            )

    def op_delete(self, req: tsi.OpDeleteReq) -> tsi.OpDeleteRes:
        return tsi.OpDeleteRes(
            num_deleted=self._delete_object_versions(
                req.project_id, "op", req.object_id, req.digests
            )
        )

    def dataset_create(self, req: tsi.DatasetCreateReq) -> tsi.DatasetCreateRes:
        object_id = object_creation_utils.make_object_id(req.name, "Dataset")
        table_res = self.table_create(
            tsi.TableCreateReq(
                table=tsi.TableSchemaForInsert(
                    project_id=req.project_id,
                    rows=req.rows,
                )
            )
        )
        table_ref = refs_internal.InternalTableRef(
            project_id=req.project_id,
            digest=table_res.digest,
        ).uri
        obj_result = self.obj_create(
            tsi.ObjCreateReq(
                obj=tsi.ObjSchemaForInsert(
                    project_id=req.project_id,
                    object_id=object_id,
                    val=object_creation_utils.build_dataset_val(
                        name=req.name,
                        description=req.description,
                        table_ref=table_ref,
                    ),
                    wb_user_id=req.wb_user_id,
                )
            )
        )
        obj = self._read_object_or_raise(
            req.project_id, "object", object_id, obj_result.digest
        )
        return tsi.DatasetCreateRes(
            digest=obj.digest,
            object_id=object_id,
            version_index=obj.version_index,
        )

    def dataset_read(self, req: tsi.DatasetReadReq) -> tsi.DatasetReadRes:
        obj = self._read_object_or_raise(
            req.project_id, "object", req.object_id, req.digest
        )
        val = obj.val if isinstance(obj.val, dict) else {}
        return tsi.DatasetReadRes(
            object_id=obj.object_id,
            digest=obj.digest,
            version_index=obj.version_index,
            created_at=obj.created_at,
            name=val.get("name", obj.object_id),
            description=val.get("description"),
            rows=val.get("rows", ""),
        )

    def dataset_list(self, req: tsi.DatasetListReq) -> Iterator[tsi.DatasetReadRes]:
        result = self.objs_query(
            tsi.ObjQueryReq(
                project_id=req.project_id,
                filter=tsi.ObjectVersionFilter(
                    base_object_classes=["Dataset"], is_op=False
                ),
                limit=req.limit,
                offset=req.offset,
            )
        )
        for obj in result.objs:
            val = obj.val if isinstance(obj.val, dict) else {}
            yield tsi.DatasetReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=val.get("name", obj.object_id),
                description=val.get("description"),
                rows=val.get("rows", ""),
            )

    def dataset_delete(self, req: tsi.DatasetDeleteReq) -> tsi.DatasetDeleteRes:
        return tsi.DatasetDeleteRes(
            num_deleted=self._delete_object_versions(
                req.project_id, "object", req.object_id, req.digests
            )
        )

    def scorer_create(self, req: tsi.ScorerCreateReq) -> tsi.ScorerCreateRes:
        object_id = object_creation_utils.make_object_id(req.name, "Scorer")
        score_op_res = self.op_create(
            tsi.OpCreateReq(
                project_id=req.project_id,
                name=f"{object_id}_score",
                source_code=req.op_source_code,
                wb_user_id=req.wb_user_id,
            )
        )
        summarize_op_res = self.op_create(
            tsi.OpCreateReq(
                project_id=req.project_id,
                name=f"{object_id}_summarize",
                source_code=object_creation_utils.PLACEHOLDER_SCORER_SUMMARIZE_OP_SOURCE,
                wb_user_id=req.wb_user_id,
            )
        )
        obj_result = self.obj_create(
            tsi.ObjCreateReq(
                obj=tsi.ObjSchemaForInsert(
                    project_id=req.project_id,
                    object_id=object_id,
                    val=object_creation_utils.build_scorer_val(
                        name=req.name,
                        description=req.description,
                        score_op_ref=score_op_res.digest,
                        summarize_op_ref=summarize_op_res.digest,
                    ),
                    wb_user_id=req.wb_user_id,
                )
            )
        )
        obj = self._read_object_or_raise(
            req.project_id, "object", object_id, obj_result.digest
        )
        scorer_ref = refs_internal.InternalObjectRef(
            project_id=req.project_id,
            name=object_id,
            version=obj.digest,
        ).uri
        return tsi.ScorerCreateRes(
            digest=obj.digest,
            object_id=object_id,
            version_index=obj.version_index,
            scorer=scorer_ref,
        )

    def scorer_read(self, req: tsi.ScorerReadReq) -> tsi.ScorerReadRes:
        obj = self._read_object_or_raise(
            req.project_id, "object", req.object_id, req.digest
        )
        return scorer_read_res_from_obj(obj)

    def scorer_list(self, req: tsi.ScorerListReq) -> Iterator[tsi.ScorerReadRes]:
        result = self.objs_query(
            tsi.ObjQueryReq(
                project_id=req.project_id,
                filter=tsi.ObjectVersionFilter(
                    base_object_classes=["Scorer"], is_op=False
                ),
                limit=req.limit,
                offset=req.offset,
            )
        )
        for obj in result.objs:
            yield scorer_read_res_from_obj(obj)

    def scorer_delete(self, req: tsi.ScorerDeleteReq) -> tsi.ScorerDeleteRes:
        return tsi.ScorerDeleteRes(
            num_deleted=self._delete_object_versions(
                req.project_id, "object", req.object_id, req.digests
            )
        )

    def evaluation_create(
        self, req: tsi.EvaluationCreateReq
    ) -> tsi.EvaluationCreateRes:
        object_id = object_creation_utils.make_object_id(req.name, "Evaluation")
        evaluate_op_res = self.op_create(
            tsi.OpCreateReq(
                project_id=req.project_id,
                name=f"{object_id}.evaluate",
                source_code=object_creation_utils.PLACEHOLDER_EVALUATE_OP_SOURCE,
                wb_user_id=req.wb_user_id,
            )
        )
        predict_and_score_op_res = self.op_create(
            tsi.OpCreateReq(
                project_id=req.project_id,
                name=f"{object_id}.predict_and_score",
                source_code=object_creation_utils.PLACEHOLDER_PREDICT_AND_SCORE_OP_SOURCE,
                wb_user_id=req.wb_user_id,
            )
        )
        summarize_op_res = self.op_create(
            tsi.OpCreateReq(
                project_id=req.project_id,
                name=f"{object_id}.summarize",
                source_code=object_creation_utils.PLACEHOLDER_EVALUATION_SUMMARIZE_OP_SOURCE,
                wb_user_id=req.wb_user_id,
            )
        )
        obj_result = self.obj_create(
            tsi.ObjCreateReq(
                obj=tsi.ObjSchemaForInsert(
                    project_id=req.project_id,
                    object_id=object_id,
                    val=object_creation_utils.build_evaluation_val(
                        name=req.name,
                        dataset_ref=req.dataset,
                        trials=req.trials,
                        description=req.description,
                        scorer_refs=req.scorers,
                        evaluation_name=req.evaluation_name,
                        metadata=None,
                        preprocess_model_input=None,
                        eval_attributes=req.eval_attributes,
                        evaluate_ref=evaluate_op_res.digest,
                        predict_and_score_ref=predict_and_score_op_res.digest,
                        summarize_ref=summarize_op_res.digest,
                    ),
                    wb_user_id=req.wb_user_id,
                )
            )
        )
        obj = self._read_object_or_raise(
            req.project_id, "object", object_id, obj_result.digest
        )
        evaluation_ref = refs_internal.InternalObjectRef(
            project_id=req.project_id,
            name=object_id,
            version=obj.digest,
        ).uri
        return tsi.EvaluationCreateRes(
            digest=obj.digest,
            object_id=object_id,
            version_index=obj.version_index,
            evaluation_ref=evaluation_ref,
        )

    def evaluation_read(self, req: tsi.EvaluationReadReq) -> tsi.EvaluationReadRes:
        obj = self._read_object_or_raise(
            req.project_id, "object", req.object_id, req.digest
        )
        return self._evaluation_read_res_from_obj(obj)

    def evaluation_list(
        self, req: tsi.EvaluationListReq
    ) -> Iterator[tsi.EvaluationReadRes]:
        result = self.objs_query(
            tsi.ObjQueryReq(
                project_id=req.project_id,
                filter=tsi.ObjectVersionFilter(
                    base_object_classes=["Evaluation"], is_op=False
                ),
                limit=req.limit,
                offset=req.offset,
            )
        )
        for obj in result.objs:
            yield self._evaluation_read_res_from_obj(obj)

    def evaluation_delete(
        self, req: tsi.EvaluationDeleteReq
    ) -> tsi.EvaluationDeleteRes:
        return tsi.EvaluationDeleteRes(
            num_deleted=self._delete_object_versions(
                req.project_id, "object", req.object_id, req.digests
            )
        )

    def model_create(self, req: tsi.ModelCreateReq) -> tsi.ModelCreateRes:
        source_file_res = self.file_create(
            tsi.FileCreateReq(
                project_id=req.project_id,
                name=object_creation_utils.OP_SOURCE_FILE_NAME,
                content=req.source_code.encode("utf-8"),
            )
        )
        object_id = object_creation_utils.make_object_id(req.name, "Model")
        obj_result = self.obj_create(
            tsi.ObjCreateReq(
                obj=tsi.ObjSchemaForInsert(
                    project_id=req.project_id,
                    object_id=object_id,
                    val=object_creation_utils.build_model_val(
                        name=req.name,
                        description=req.description,
                        source_file_digest=source_file_res.digest,
                        attributes=req.attributes,
                    ),
                    wb_user_id=req.wb_user_id,
                )
            )
        )
        obj = self._read_object_or_raise(
            req.project_id, "object", object_id, obj_result.digest
        )
        model_ref = refs_internal.InternalObjectRef(
            project_id=req.project_id,
            name=object_id,
            version=obj.digest,
        ).uri
        return tsi.ModelCreateRes(
            digest=obj.digest,
            object_id=object_id,
            version_index=obj.version_index,
            model_ref=model_ref,
        )

    def model_read(self, req: tsi.ModelReadReq) -> tsi.ModelReadRes:
        obj = self._read_object_or_raise(
            req.project_id, "object", req.object_id, req.digest
        )
        val = obj.val if isinstance(obj.val, dict) else {}
        source_code = self._op_code(req.project_id, val)
        return tsi.ModelReadRes(
            object_id=obj.object_id,
            digest=obj.digest,
            version_index=obj.version_index,
            created_at=obj.created_at,
            name=val.get("name", obj.object_id),
            description=val.get("description"),
            source_code=source_code,
            attributes={
                key: value
                for key, value in val.items()
                if key
                not in {"_type", "_class_name", "_bases", "name", "description", "files"}
            },
        )

    def model_list(self, req: tsi.ModelListReq) -> Iterator[tsi.ModelReadRes]:
        result = self.objs_query(
            tsi.ObjQueryReq(
                project_id=req.project_id,
                filter=tsi.ObjectVersionFilter(
                    base_object_classes=["Model"], is_op=False
                ),
                limit=req.limit,
                offset=req.offset,
            )
        )
        for obj in result.objs:
            yield self.model_read(
                tsi.ModelReadReq(
                    project_id=req.project_id,
                    object_id=obj.object_id,
                    digest=obj.digest,
                )
            )

    def model_delete(self, req: tsi.ModelDeleteReq) -> tsi.ModelDeleteRes:
        return tsi.ModelDeleteRes(
            num_deleted=self._delete_object_versions(
                req.project_id, "object", req.object_id, req.digests
            )
        )

    def evaluation_run_create(
        self, req: tsi.EvaluationRunCreateReq
    ) -> tsi.EvaluationRunCreateRes:
        run_id = generate_id()
        self._evaluation_runs[req.project_id, run_id] = tsi.EvaluationRunReadRes(
            evaluation_run_id=run_id,
            evaluation=req.evaluation,
            model=req.model,
            status="running",
            started_at=_now(),
            finished_at=None,
            summary=None,
        )
        return tsi.EvaluationRunCreateRes(evaluation_run_id=run_id)

    def evaluation_run_read(
        self, req: tsi.EvaluationRunReadReq
    ) -> tsi.EvaluationRunReadRes:
        run = self._evaluation_runs.get((req.project_id, req.evaluation_run_id))
        if run is None:
            raise NotFoundError(f"Evaluation run {req.evaluation_run_id} not found")
        return run

    def evaluation_run_list(
        self, req: tsi.EvaluationRunListReq
    ) -> Iterator[tsi.EvaluationRunReadRes]:
        runs = [
            run
            for (project_id, _), run in self._evaluation_runs.items()
            if project_id == req.project_id and _matches_evaluation_run_filter(run, req.filter)
        ]
        yield from _page(runs, req.offset, req.limit)

    def evaluation_run_delete(
        self, req: tsi.EvaluationRunDeleteReq
    ) -> tsi.EvaluationRunDeleteRes:
        count = 0
        for run_id in req.evaluation_run_ids:
            if self._evaluation_runs.pop((req.project_id, run_id), None) is not None:
                count += 1
        return tsi.EvaluationRunDeleteRes(num_deleted=count)

    def evaluation_run_finish(
        self, req: tsi.EvaluationRunFinishReq
    ) -> tsi.EvaluationRunFinishRes:
        key = (req.project_id, req.evaluation_run_id)
        run = self._evaluation_runs.get(key)
        if run is None:
            raise NotFoundError(f"Evaluation run {req.evaluation_run_id} not found")
        self._evaluation_runs[key] = run.model_copy(
            update={"status": "finished", "finished_at": _now(), "summary": req.summary}
        )
        return tsi.EvaluationRunFinishRes(success=True)

    def prediction_create(self, req: tsi.PredictionCreateReq) -> tsi.PredictionCreateRes:
        prediction_id = generate_id()
        inputs = req.inputs or {}
        self._predictions[req.project_id, prediction_id] = tsi.PredictionReadRes(
            prediction_id=prediction_id,
            model=req.model,
            inputs=inputs,
            output=req.output,
            evaluation_run_id=req.evaluation_run_id,
            wb_user_id=req.wb_user_id,
        )
        trace_id = prediction_id
        parent_id = None
        now = _now()
        if req.evaluation_run_id is not None:
            run = self._evaluation_runs.get((req.project_id, req.evaluation_run_id))
            if run is None:
                raise NotFoundError(f"Evaluation run {req.evaluation_run_id} not found")
            pas_id = generate_id()
            trace_id = req.evaluation_run_id
            parent_id = pas_id
            self._prediction_parent_ids[req.project_id, prediction_id] = pas_id
            self.call_start(
                tsi.CallStartReq(
                    start=tsi.StartedCallSchemaForInsert(
                        project_id=req.project_id,
                        id=pas_id,
                        trace_id=req.evaluation_run_id,
                        parent_id=req.evaluation_run_id,
                        op_name=constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                        started_at=now,
                        attributes={
                            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                                constants.EVALUATION_RUN_PREDICT_CALL_ID_ATTR_KEY: prediction_id,
                            }
                        },
                        inputs={
                            "self": run.evaluation,
                            "model": req.model,
                            "example": inputs,
                        },
                    )
                )
            )

        prediction_attrs = {
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.PREDICTION_ATTR_KEY: "true",
                constants.PREDICTION_MODEL_ATTR_KEY: req.model,
            }
        }
        if req.evaluation_run_id is not None:
            prediction_attrs[constants.WEAVE_ATTRIBUTES_NAMESPACE][
                constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
            ] = req.evaluation_run_id

        self.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=req.project_id,
                    id=prediction_id,
                    trace_id=trace_id,
                    parent_id=parent_id,
                    op_name=f"{_scorer_name(req.model)}.predict",
                    started_at=now,
                    attributes=prediction_attrs,
                    inputs={"self": req.model, "inputs": inputs},
                    wb_user_id=req.wb_user_id,
                )
            )
        )
        self.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=req.project_id,
                    id=prediction_id,
                    ended_at=now,
                    output=req.output,
                    summary={},
                )
            )
        )
        return tsi.PredictionCreateRes(prediction_id=prediction_id)

    def prediction_read(self, req: tsi.PredictionReadReq) -> tsi.PredictionReadRes:
        call = self._calls.get((req.project_id, req.prediction_id))
        if call is not None:
            return self._prediction_from_call(call)
        prediction = self._predictions.get((req.project_id, req.prediction_id))
        if prediction is None:
            raise NotFoundError(f"Prediction {req.prediction_id} not found")
        return prediction

    def prediction_list(
        self, req: tsi.PredictionListReq
    ) -> Iterator[tsi.PredictionReadRes]:
        predictions = {
            prediction.prediction_id: prediction
            for (project_id, _), prediction in self._predictions.items()
            if project_id == req.project_id
            and (
                req.evaluation_run_id is None
                or prediction.evaluation_run_id == req.evaluation_run_id
            )
        }
        for call in self._calls.values():
            if call.project_id != req.project_id or call.deleted_at is not None:
                continue
            if not _is_prediction_call(call):
                continue
            prediction = self._prediction_from_call(call)
            if (
                req.evaluation_run_id is None
                or prediction.evaluation_run_id == req.evaluation_run_id
            ):
                predictions[prediction.prediction_id] = prediction
        yield from _page(list(predictions.values()), req.offset, req.limit)

    def prediction_delete(self, req: tsi.PredictionDeleteReq) -> tsi.PredictionDeleteRes:
        count = 0
        for prediction_id in req.prediction_ids:
            if self._predictions.pop((req.project_id, prediction_id), None) is not None:
                self._prediction_parent_ids.pop((req.project_id, prediction_id), None)
                count += 1
        return tsi.PredictionDeleteRes(num_deleted=count)

    def prediction_finish(self, req: tsi.PredictionFinishReq) -> tsi.PredictionFinishRes:
        prediction = self._predictions.get((req.project_id, req.prediction_id))
        if prediction is None:
            raise NotFoundError(f"Prediction {req.prediction_id} not found")
        pas_id = self._prediction_parent_ids.get((req.project_id, req.prediction_id))
        if pas_id is not None:
            prediction_call = self._calls.get((req.project_id, req.prediction_id))
            model_latency = {"mean": 0.0}
            if (
                prediction_call is not None
                and prediction_call.ended_at is not None
                and prediction_call.started_at is not None
            ):
                model_latency = {
                    "mean": (
                        prediction_call.ended_at - prediction_call.started_at
                    ).total_seconds()
                }
            self.call_end(
                tsi.CallEndReq(
                    end=tsi.EndedCallSchemaForInsert(
                        project_id=req.project_id,
                        id=pas_id,
                        ended_at=_now(),
                        output={
                            "output": (
                                prediction_call.output
                                if prediction_call is not None
                                else prediction.output
                            ),
                            "scores": self._score_outputs_for_parent(
                                req.project_id, pas_id
                            ),
                            "model_latency": model_latency,
                        },
                        summary={},
                    )
                )
            )
        return tsi.PredictionFinishRes(success=True)

    def score_create(self, req: tsi.ScoreCreateReq) -> tsi.ScoreCreateRes:
        score_id = generate_id()
        self._scores[req.project_id, score_id] = tsi.ScoreReadRes(
            score_id=score_id,
            scorer=req.scorer,
            value=req.value,
            evaluation_run_id=req.evaluation_run_id,
            wb_user_id=req.wb_user_id,
        )
        self._score_prediction_ids[req.project_id, score_id] = req.prediction_id
        prediction_parent_id = self._prediction_parent_ids.get(
            (req.project_id, req.prediction_id)
        )
        prediction_call = self._calls.get((req.project_id, req.prediction_id))
        trace_id = req.evaluation_run_id or score_id
        parent_id = prediction_parent_id if req.evaluation_run_id else None
        now = _now()
        attrs = {
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.SCORE_ATTR_KEY: "true",
                constants.SCORE_PREDICTION_ID_ATTR_KEY: req.prediction_id,
                constants.SCORE_SCORER_ATTR_KEY: req.scorer,
            }
        }
        if req.evaluation_run_id is not None:
            attrs[constants.WEAVE_ATTRIBUTES_NAMESPACE][
                constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY
            ] = req.evaluation_run_id
        self.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=req.project_id,
                    id=score_id,
                    trace_id=trace_id,
                    parent_id=parent_id,
                    op_name=f"{_scorer_name(req.scorer)}.score",
                    started_at=now,
                    attributes=attrs,
                    inputs={
                        "self": req.scorer,
                        "inputs": (
                            get_prediction_inputs(prediction_call.inputs)
                            if prediction_call is not None
                            else {}
                        ),
                        "output": (
                            prediction_call.output
                            if prediction_call is not None
                            else None
                        ),
                    },
                    wb_user_id=req.wb_user_id,
                )
            )
        )
        self.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=req.project_id,
                    id=score_id,
                    ended_at=now,
                    output=req.value,
                    summary={},
                )
            )
        )
        return tsi.ScoreCreateRes(score_id=score_id)

    def score_read(self, req: tsi.ScoreReadReq) -> tsi.ScoreReadRes:
        score = self._scores.get((req.project_id, req.score_id))
        if score is None:
            raise NotFoundError(f"Score {req.score_id} not found")
        return score

    def score_list(self, req: tsi.ScoreListReq) -> Iterator[tsi.ScoreReadRes]:
        scores = [
            score
            for (project_id, _), score in self._scores.items()
            if project_id == req.project_id
            and (
                req.evaluation_run_id is None
                or score.evaluation_run_id == req.evaluation_run_id
            )
        ]
        yield from _page(scores, req.offset, req.limit)

    def score_delete(self, req: tsi.ScoreDeleteReq) -> tsi.ScoreDeleteRes:
        count = 0
        for score_id in req.score_ids:
            if self._scores.pop((req.project_id, score_id), None) is not None:
                self._score_prediction_ids.pop((req.project_id, score_id), None)
                count += 1
        return tsi.ScoreDeleteRes(num_deleted=count)

    def eval_results_query(
        self, req: tsi.EvalResultsQueryReq
    ) -> tsi.EvalResultsQueryRes:
        eval_results_helpers.validate_eval_results_request(req)
        evaluation_ids = eval_results_helpers.resolve_eval_root_ids(req)
        if not evaluation_ids:
            summary = tsi.EvalResultsSummaryRes() if req.include_summary else None
            return tsi.EvalResultsQueryRes(rows=[], total_rows=0, summary=summary)
        calls = [
            call
            for call in self._calls.values()
            if call.project_id == req.project_id and call.deleted_at is None
        ]
        return eval_results_helpers.eval_results_query(
            self, req, evaluation_ids, calls
        )

    def obj_add_tags(self, req: tsi.ObjAddTagsReq) -> tsi.ObjAddTagsRes:
        try:
            obj = self._read_object_or_raise(
                req.project_id, None, req.object_id, req.digest
            )
        except ObjectDeletedError as exc:
            raise NotFoundError(str(exc)) from exc
        tags = sorted({*(obj.tags or []), *req.tags})
        self._replace_object(obj.model_copy(update={"tags": tags}))
        return tsi.ObjAddTagsRes()

    def obj_remove_tags(self, req: tsi.ObjRemoveTagsReq) -> tsi.ObjRemoveTagsRes:
        try:
            obj = self._read_object_or_raise(
                req.project_id, None, req.object_id, req.digest
            )
        except ObjectDeletedError as exc:
            raise NotFoundError(str(exc)) from exc
        remove = set(req.tags)
        self._replace_object(
            obj.model_copy(
                update={"tags": [t for t in obj.tags or [] if t not in remove]}
            )
        )
        return tsi.ObjRemoveTagsRes()

    def obj_set_aliases(self, req: tsi.ObjSetAliasesReq) -> tsi.ObjSetAliasesRes:
        try:
            obj = self._read_object_or_raise(
                req.project_id, None, req.object_id, req.digest
            )
        except ObjectDeletedError as exc:
            raise NotFoundError(str(exc)) from exc
        requested = set(req.aliases)
        for key, existing in list(self._objects.items()):
            if (
                existing.project_id == req.project_id
                and existing.object_id == req.object_id
            ):
                aliases = [
                    alias
                    for alias in existing.aliases or []
                    if alias == "latest" or alias not in requested
                ]
                self._objects[key] = existing.model_copy(update={"aliases": aliases})
        aliases = sorted({*(obj.aliases or []), *requested})
        if obj.is_latest and "latest" not in aliases:
            aliases.append("latest")
            aliases.sort()
        self._replace_object(obj.model_copy(update={"aliases": aliases}))
        return tsi.ObjSetAliasesRes()

    def obj_remove_aliases(
        self, req: tsi.ObjRemoveAliasesReq
    ) -> tsi.ObjRemoveAliasesRes:
        for key, obj in list(self._objects.items()):
            if obj.project_id == req.project_id and obj.object_id == req.object_id:
                remove = set(req.aliases)
                self._objects[key] = obj.model_copy(
                    update={"aliases": [a for a in obj.aliases or [] if a not in remove]}
                )
        return tsi.ObjRemoveAliasesRes()

    def tags_list(self, req: tsi.TagsListReq) -> tsi.TagsListRes:
        tags = sorted(
            {
                tag
                for obj in self._objects.values()
                if obj.project_id == req.project_id and obj.deleted_at is None
                for tag in obj.tags or []
            }
        )
        return tsi.TagsListRes(tags=tags)

    def aliases_list(self, req: tsi.AliasesListReq) -> tsi.AliasesListRes:
        aliases = sorted(
            {
                alias
                for obj in self._objects.values()
                if obj.project_id == req.project_id and obj.deleted_at is None
                for alias in obj.aliases or []
                if alias != "latest"
            }
        )
        return tsi.AliasesListRes(aliases=aliases)

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        row_digests = [compute_row_digest(row) for row in req.table.rows]
        digest = compute_table_digest(row_digests)
        validate_expected_digest(
            expected=req.table.expected_digest,
            actual=digest,
            label=f"table ({len(req.table.rows)} rows)",
        )
        rows = [
            tsi.TableRowSchema(digest=row_digest, val=row, original_index=index)
            for index, (row_digest, row) in enumerate(
                zip(row_digests, req.table.rows, strict=True)
            )
        ]
        self._tables[req.table.project_id, digest] = rows
        self._row_values.update(dict(zip(row_digests, req.table.rows, strict=True)))
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
        rows = [
            tsi.TableRowSchema(
                digest=row_digest,
                val=self._row_values.get(row_digest, {}),
                original_index=index,
            )
            for index, row_digest in enumerate(req.row_digests)
        ]
        self._tables[req.project_id, digest] = rows
        return tsi.TableCreateFromDigestsRes(digest=digest)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        rows = list(self._tables.get((req.project_id, req.base_digest), []))
        values = [dict(row.val) for row in rows]
        for update in req.updates:
            if isinstance(update, tsi.TableAppendSpec):
                values.append(update.append.row)
            elif isinstance(update, tsi.TablePopSpec):
                values.pop(update.pop.index)
            elif isinstance(update, tsi.TableInsertSpec):
                values.insert(update.insert.index, update.insert.row)
            else:
                raise NotImplementedError("FakeTraceServer does not support table update")
        create_res = self.table_create(
            tsi.TableCreateReq(
                table=tsi.TableSchemaForInsert(project_id=req.project_id, rows=values)
            )
        )
        return tsi.TableUpdateRes(
            digest=create_res.digest, updated_row_digests=create_res.row_digests
        )

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        _validate_sort_fields(req.sort_by)
        rows = list(self._tables.get((req.project_id, req.digest), []))
        if req.filter and req.filter.row_digests is not None:
            wanted = set(req.filter.row_digests)
            rows = [row for row in rows if row.digest in wanted]
        rows = _sort_items(rows, req.sort_by, lambda row: row.val)
        return tsi.TableQueryRes(rows=list(_page(rows, req.offset, req.limit)))

    def table_query_stream(self, req: tsi.TableQueryReq) -> Iterator[tsi.TableRowSchema]:
        yield from self.table_query(req).rows

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        return tsi.TableQueryStatsRes(
            count=len(self._tables.get((req.project_id, req.digest), []))
        )

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        tables = []
        for digest in req.digests:
            table_key = (req.project_id, digest)
            if table_key not in self._tables:
                continue
            rows = self._tables[table_key]
            tables.append(
                tsi.TableStatsRow(
                    digest=digest,
                    count=len(rows),
                    storage_size_bytes=(
                        sum(_storage_size(row.val) for row in rows)
                        if req.include_storage_size
                        else None
                    ),
                )
            )
        return tsi.TableQueryStatsBatchRes(tables=tables)

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        for ref in req.refs:
            refs_internal.parse_internal_uri(ref)
        return tsi.RefsReadBatchRes(vals=[self._read_ref(ref) for ref in req.refs])

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        digest = compute_file_digest(req.content)
        validate_expected_digest(
            expected=req.expected_digest,
            actual=digest,
            label=f"file {req.name!r}",
        )
        self._files[req.project_id, digest] = req.content
        return tsi.FileCreateRes(digest=digest)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        return tsi.FileContentReadRes(content=self._files[req.project_id, req.digest])

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        return tsi.FilesStatsRes(
            total_size_bytes=sum(
                len(content)
                for (project_id, _), content in self._files.items()
                if project_id == req.project_id
            )
        )

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        validate_feedback_create_req(req, self)
        data = req.model_dump()
        data["id"] = req.id or generate_id()
        data["created_at"] = _now()
        data["wb_user_id"] = req.wb_user_id or "test_user"
        data["payload"] = process_feedback_payload(req)
        feedback = tsi.Feedback(
            **data,
        )
        self._feedback.append(feedback)
        return tsi.FeedbackCreateRes(
            id=feedback.id,
            created_at=feedback.created_at,
            wb_user_id=feedback.wb_user_id,
            payload=feedback.payload,
        )

    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        return tsi.FeedbackCreateBatchRes(
            res=[self.feedback_create(feedback_req) for feedback_req in req.batch]
        )

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        _validate_feedback_query_fields(req.query)
        rows = [
            feedback
            for feedback in self._feedback
            if feedback.project_id == req.project_id
            and _matches_query(_dump(feedback), req.query)
        ]
        rows = _sort_items(rows, req.sort_by, _dump)
        rows = list(_page(rows, req.offset, req.limit))
        if req.fields == ["count(*)"]:
            return tsi.FeedbackQueryRes(result=[{"count(*)": len(rows)}])
        return tsi.FeedbackQueryRes(
            result=[_project_fields(_dump(row), req.fields) for row in rows]
        )

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        validate_feedback_purge_req(req)
        self._feedback = [
            feedback
            for feedback in self._feedback
            if feedback.project_id != req.project_id
            or not _matches_query(_dump(feedback), req.query)
        ]
        return tsi.FeedbackPurgeRes()

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        self._feedback = [
            feedback for feedback in self._feedback if feedback.id != req.feedback_id
        ]
        res = self.feedback_create(
            tsi.FeedbackCreateReq(**req.model_dump(exclude={"feedback_id"}))
        )
        return tsi.FeedbackReplaceRes(
            id=res.id,
            created_at=res.created_at,
            wb_user_id=res.wb_user_id,
            payload=res.payload,
        )

    def feedback_stats(self, req: tsi.FeedbackStatsReq) -> tsi.FeedbackStatsRes:
        end = req.end or _now()
        granularity = req.granularity or 3600
        rows = _filter_feedback_window(self._feedback, req, end)
        if not req.metrics:
            return tsi.FeedbackStatsRes(
                start=req.start,
                end=end,
                granularity=granularity,
                timezone=req.timezone,
                buckets=[],
                window_stats={},
            )
        bucket_rows: dict[datetime.datetime, dict[str, Any]] = {}
        window_stats: dict[str, dict[str, float | None]] = {}
        for metric in req.metrics:
            slug = metric.json_path.replace(".", "_")
            values_by_bucket: dict[datetime.datetime, list[Any]] = {}
            all_values = []
            for feedback in rows:
                value = _get_path(feedback.payload, metric.json_path)
                if value is None:
                    continue
                bucket = _bucket_start(feedback.created_at, req.start, granularity)
                values_by_bucket.setdefault(bucket, []).append(value)
                all_values.append(value)
            window_stats[slug] = _feedback_aggregations(all_values, metric)
            for bucket, values in values_by_bucket.items():
                row = bucket_rows.setdefault(bucket, {"timestamp": bucket, "count": 0})
                row["count"] += len(values)
                for name, value in _feedback_aggregations(values, metric).items():
                    row[f"{name}_{slug}"] = value
        return tsi.FeedbackStatsRes(
            start=req.start,
            end=end,
            granularity=granularity,
            timezone=req.timezone,
            buckets=sorted(bucket_rows.values(), key=lambda row: row["timestamp"]),
            window_stats=window_stats,
        )

    def feedback_payload_schema(
        self, req: tsi.FeedbackPayloadSchemaReq
    ) -> tsi.FeedbackPayloadSchemaRes:
        end = req.end or _now()
        rows = _filter_feedback_window(self._feedback, req, end)
        path_types: dict[str, str] = {}
        for feedback in rows:
            for path, value in _flatten_payload(feedback.payload):
                path_types[path] = _feedback_value_type(value)
        return tsi.FeedbackPayloadSchemaRes(
            paths=[
                tsi.FeedbackPayloadPath(json_path=path, value_type=value_type)
                for path, value_type in sorted(path_types.items())
            ]
        )

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        ids = []
        created_at = _now()
        for llm_id, cost in req.costs.items():
            cost_id = generate_id()
            ids.append((cost_id, llm_id))
            effective_date = cost.effective_date or created_at
            cost_data = cost.model_dump()
            cost_data.update(
                {
                    "prompt_token_cost_unit": cost.prompt_token_cost_unit or "USD",
                    "completion_token_cost_unit": cost.completion_token_cost_unit
                    or "USD",
                    "effective_date": effective_date,
                    "provider_id": cost.provider_id or "default",
                }
            )
            self._costs.append(
                tsi.CostQueryOutput(
                    id=cost_id,
                    llm_id=llm_id,
                    **cost_data,
                )
            )
            self._cost_extra[cost_id] = {
                "created_at": created_at,
                "created_by": req.wb_user_id,
                "pricing_level": "project",
                "pricing_level_id": req.project_id,
                "cache_read_input_token_cost": cost.cache_read_input_token_cost,
                "cache_creation_input_token_cost": cost.cache_creation_input_token_cost,
            }
        return tsi.CostCreateRes(ids=ids)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        rows = [
            cost
            for cost in self._costs
            if _matches_query(self._cost_row(cost), req.query)
        ]
        rows = _sort_items(rows, req.sort_by, self._cost_row)
        rows = list(_page(rows, req.offset, req.limit))
        return tsi.CostQueryRes(results=rows)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        validate_cost_purge_req(req)
        self._costs = [
            cost
            for cost in self._costs
            if not _matches_query(self._cost_row(cost), req.query)
        ]
        return tsi.CostPurgeRes()

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        action = self._read_ref(req.action_ref)
        action_name = action.get("name", "action") if isinstance(action, dict) else "action"
        config = action.get("config", {}) if isinstance(action, dict) else {}
        target_words = config.get("target_words", []) if isinstance(config, dict) else []
        for call_id in req.call_ids:
            call = self._calls.get((req.project_id, call_id))
            if call is None:
                continue
            text = str(call.output)
            output = any(word in text for word in target_words)
            self.feedback_create(
                tsi.FeedbackCreateReq(
                    project_id=req.project_id,
                    weave_ref=refs_internal.InternalCallRef(
                        project_id=req.project_id, id=call_id
                    ).uri(),
                    feedback_type=f"wandb.runnable.{action_name}",
                    runnable_ref=req.action_ref,
                    payload={"output": output},
                    wb_user_id=req.wb_user_id,
                )
            )
        return tsi.ActionsExecuteBatchRes()

    def _cost_row(self, cost: tsi.CostQueryOutput) -> dict[str, Any]:
        row = _dump(cost)
        if cost.id is not None:
            row.update(self._cost_extra.get(cost.id, {}))
        return row

    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        return tsi.ProjectStatsRes(
            trace_storage_size_bytes=(
                sum(_storage_size(_dump(call)) for call in self._calls.values())
                if req.include_trace_storage_size
                else 0
            ),
            objects_storage_size_bytes=(
                sum(_storage_size(obj.val) for obj in self._objects.values())
                if req.include_object_storage_size
                else 0
            ),
            tables_storage_size_bytes=(
                sum(_storage_size(row.val) for rows in self._tables.values() for row in rows)
                if req.include_table_storage_size
                else 0
            ),
            files_storage_size_bytes=(
                sum(len(content) for content in self._files.values())
                if req.include_file_storage_size
                else 0
            ),
        )

    def trace_usage(self, req: tsi.TraceUsageReq) -> tsi.TraceUsageRes:
        calls = [
            call
            for call in self._calls.values()
            if call.project_id == req.project_id
            and call.deleted_at is None
            and _matches_calls_filter(call, req.filter)
            and _matches_query(_dump(call), req.query)
        ][: req.limit]
        return self._usage_response(calls, req.include_costs)

    def calls_usage(self, req: tsi.CallsUsageReq) -> tsi.CallsUsageRes:
        roots = [
            call
            for call in self._calls.values()
            if call.project_id == req.project_id
            and call.deleted_at is None
            and call.id in req.call_ids
        ]
        trace_ids = {call.trace_id for call in roots}
        calls = [
            call
            for call in self._calls.values()
            if call.project_id == req.project_id
            and call.deleted_at is None
            and call.trace_id in trace_ids
        ][: req.limit]
        res = self._usage_response(calls, req.include_costs)
        return tsi.CallsUsageRes(
            call_usage={call_id: res.call_usage.get(call_id, {}) for call_id in req.call_ids},
            unfinished_call_ids=res.unfinished_call_ids,
        )

    def threads_query_stream(self, req: tsi.ThreadsQueryReq) -> Iterator[tsi.ThreadSchema]:
        calls_by_thread: dict[str, list[tsi.CallSchema]] = {}
        for call in self._calls.values():
            if call.project_id == req.project_id and call.thread_id is not None:
                calls_by_thread.setdefault(call.thread_id, []).append(call)
        threads = []
        for thread_id, calls in calls_by_thread.items():
            calls.sort(key=lambda call: call.started_at)
            if req.filter and req.filter.thread_ids and thread_id not in req.filter.thread_ids:
                continue
            turn_calls = [call for call in calls if call.turn_id == call.id]
            durations = [
                (call.ended_at - call.started_at).total_seconds() * 1000
                for call in turn_calls
                if call.ended_at is not None
            ]
            first_turn = min(turn_calls, key=lambda call: call.started_at, default=None)
            last_turn = max(
                turn_calls,
                key=lambda call: call.ended_at or call.started_at,
                default=None,
            )
            threads.append(
                tsi.ThreadSchema(
                    thread_id=thread_id,
                    turn_count=len({call.turn_id for call in calls if call.turn_id}),
                    start_time=calls[0].started_at,
                    last_updated=max(call.ended_at or call.started_at for call in calls),
                    first_turn_id=first_turn.id if first_turn else None,
                    last_turn_id=last_turn.id if last_turn else None,
                    p50_turn_duration_ms=_percentile(durations, 50),
                    p99_turn_duration_ms=_percentile(durations, 99),
                )
            )
        threads = _sort_items(threads, req.sort_by, _dump)
        yield from _page(threads, req.offset, req.limit)

    def _resolve_object(
        self, project_id: str, kind: str | None, object_id: str, version: str
    ) -> tsi.ObjSchema | None:
        candidates = [
            obj
            for obj in self._objects.values()
            if obj.project_id == project_id
            and obj.object_id == object_id
            and obj.deleted_at is None
            and (kind is None or obj.kind == kind)
        ]
        if version == "latest":
            return next((obj for obj in candidates if obj.is_latest), None)
        if version.startswith("v") and version[1:].isdigit():
            index = int(version[1:])
            return next((obj for obj in candidates if obj.version_index == index), None)
        alias_match = next((obj for obj in candidates if version in (obj.aliases or [])), None)
        if alias_match is not None:
            return alias_match
        return next((obj for obj in candidates if obj.digest == version), None)

    def _replace_object(self, obj: tsi.ObjSchema) -> None:
        self._objects[obj.project_id, obj.kind, obj.object_id, obj.digest] = obj

    def _refresh_latest_object_aliases(
        self, project_id: str, kind: str | None, object_id: str
    ) -> None:
        live = [
            obj
            for obj in self._objects.values()
            if obj.project_id == project_id
            and obj.object_id == object_id
            and obj.deleted_at is None
            and (kind is None or obj.kind == kind)
        ]
        latest_digest = None
        if live:
            latest_digest = max(live, key=lambda obj: obj.version_index).digest
        for key, obj in list(self._objects.items()):
            if (
                obj.project_id != project_id
                or obj.object_id != object_id
                or (kind is not None and obj.kind != kind)
            ):
                continue
            aliases = [alias for alias in obj.aliases or [] if alias != "latest"]
            is_latest = int(
                obj.deleted_at is None
                and latest_digest is not None
                and obj.digest == latest_digest
            )
            if is_latest:
                aliases.append("latest")
            self._objects[key] = obj.model_copy(
                update={"is_latest": is_latest, "aliases": sorted(set(aliases))}
            )

    def _read_ref(self, ref: str) -> Any:
        try:
            parsed = refs_internal.parse_internal_uri(ref)
        except refs_internal.InvalidInternalRef:
            return None
        if isinstance(parsed, refs_internal.InternalTableRef):
            return [
                row.val
                for row in self._tables.get((parsed.project_id, parsed.digest), [])
            ]
        if isinstance(parsed, refs_internal.InternalCallRef):
            raise ValueError("Call refs not supported")  # noqa: TRY004
        if isinstance(parsed, refs_internal.InternalObjectRef):
            kind = "op" if isinstance(parsed, refs_internal.InternalOpRef) else "object"
            obj = self._resolve_object(
                parsed.project_id, kind, parsed.name, parsed.version
            )
            if obj is None:
                return None
            return _apply_ref_extra(obj.val, parsed.extra, self._tables)
        return None

    def _resolve_object_including_deleted(
        self, project_id: str, kind: str | None, object_id: str, version: str
    ) -> tsi.ObjSchema | None:
        candidates = [
            obj
            for obj in self._objects.values()
            if obj.project_id == project_id
            and obj.object_id == object_id
            and (kind is None or obj.kind == kind)
        ]
        if version == "latest":
            return next((obj for obj in candidates if obj.is_latest), None)
        if version.startswith("v") and version[1:].isdigit():
            index = int(version[1:])
            return next((obj for obj in candidates if obj.version_index == index), None)
        alias_match = next((obj for obj in candidates if version in (obj.aliases or [])), None)
        if alias_match is not None:
            return alias_match
        return next((obj for obj in candidates if obj.digest == version), None)

    def _read_object_or_raise(
        self, project_id: str, kind: str | None, object_id: str, version: str
    ) -> tsi.ObjSchema:
        obj = self._resolve_object_including_deleted(project_id, kind, object_id, version)
        if obj is None:
            raise NotFoundError(f"Obj {object_id}:{version} not found")
        if obj.deleted_at is not None:
            raise ObjectDeletedError(
                f"{object_id}:v{obj.version_index} was deleted at {obj.deleted_at}",
                deleted_at=obj.deleted_at,
            )
        return obj

    def _delete_object_versions(
        self,
        project_id: str,
        kind: str | None,
        object_id: str,
        digests: list[str] | None,
    ) -> int:
        if digests:
            if len(dict.fromkeys(digests)) > 100:
                raise ValueError("Please delete 100 or fewer objects at a time")
            matched = []
            missing = []
            for digest in dict.fromkeys(digests):
                obj = self._resolve_object(project_id, kind, object_id, digest)
                if obj is None:
                    missing.append(digest)
                else:
                    matched.append(obj)
            if missing:
                raise NotFoundError(
                    f"Delete request contains {len(dict.fromkeys(digests))} digests, "
                    f"but found {len(matched)} objects to delete. "
                    f"Diff digests: {set(missing)}"
                )
        else:
            matched = [
                obj
                for obj in self._objects.values()
                if obj.project_id == project_id
                and obj.object_id == object_id
                and obj.deleted_at is None
                and (kind is None or obj.kind == kind)
            ]
        if not matched:
            raise NotFoundError(f"Object {object_id} not found")
        deleted_at = _now()
        count = 0
        for obj in matched:
            if obj.deleted_at is None:
                self._replace_object(
                    obj.model_copy(
                        update={
                            "deleted_at": deleted_at,
                            "tags": [],
                            "aliases": [],
                            "is_latest": 0,
                        }
                    )
                )
                count += 1
        self._refresh_latest_object_aliases(project_id, kind, object_id)
        return count

    def _op_code(self, project_id: str, val: Any) -> str:
        if not isinstance(val, dict):
            return ""
        files = val.get("files", {})
        if not isinstance(files, dict):
            return ""
        file_digest = files.get(object_creation_utils.OP_SOURCE_FILE_NAME)
        if not isinstance(file_digest, str):
            return ""
        try:
            return self.file_content_read(
                tsi.FileContentReadReq(project_id=project_id, digest=file_digest)
            ).content.decode("utf-8")
        except KeyError:
            return ""

    def _evaluation_read_res_from_obj(
        self, obj: tsi.ObjSchema
    ) -> tsi.EvaluationReadRes:
        val = obj.val if isinstance(obj.val, dict) else {}
        return tsi.EvaluationReadRes(
            object_id=obj.object_id,
            digest=obj.digest,
            version_index=obj.version_index,
            created_at=obj.created_at,
            name=val.get("name", obj.object_id),
            description=val.get("description"),
            dataset=val.get("dataset", ""),
            scorers=val.get("scorers", []),
            trials=val.get("trials", 1),
            evaluation_name=val.get("evaluation_name"),
            evaluate_op=val.get("evaluate", ""),
            predict_and_score_op=val.get("predict_and_score", ""),
            summarize_op=val.get("summarize", ""),
        )

    def _eval_trials_for_run(
        self, req: tsi.EvalResultsQueryReq, evaluation_id: str
    ) -> Iterator[tuple[str, Any, tsi.EvalResultsTrial]]:
        scores_by_prediction: dict[str, dict[str, Any]] = {}
        score_ids_by_prediction: dict[str, dict[str, str]] = {}
        for (project_id, score_id), score in self._scores.items():
            if project_id != req.project_id or score.evaluation_run_id != evaluation_id:
                continue
            prediction_id = self._score_prediction_ids.get((project_id, score_id), "")
            scores_by_prediction.setdefault(prediction_id, {})[
                _scorer_name(score.scorer)
            ] = score.value
            score_ids_by_prediction.setdefault(prediction_id, {})[
                _scorer_name(score.scorer)
            ] = score_id

        for (project_id, prediction_id), prediction in self._predictions.items():
            if (
                project_id != req.project_id
                or prediction.evaluation_run_id != evaluation_id
            ):
                continue
            row_digest = compute_row_digest(prediction.inputs)
            pas_id = self._prediction_parent_ids.get(
                (project_id, prediction_id), prediction_id
            )
            yield (
                row_digest,
                prediction.inputs,
                tsi.EvalResultsTrial(
                    predict_and_score_call_id=pas_id,
                    predict_call_id=(
                        prediction_id if req.include_predict_and_score_children else None
                    ),
                    model_output=prediction.output,
                    scores=scores_by_prediction.get(prediction_id, {}),
                    scorer_call_ids=(
                        score_ids_by_prediction.get(prediction_id, {})
                        if req.include_predict_and_score_children
                        else {}
                    ),
                ),
            )

        for call in self._calls.values():
            if (
                call.project_id != req.project_id
                or call.deleted_at is not None
                or call.parent_id != evaluation_id
                or call.op_name
                not in {"Evaluation.predict_and_score", "Evaluation.predictAndScore"}
            ):
                continue
            example = call.inputs.get("example") if isinstance(call.inputs, dict) else {}
            row_digest = compute_row_digest(example)
            raw_row = self._eval_raw_row(example, req.resolve_row_refs)
            output = call.output if isinstance(call.output, dict) else {}
            yield (
                row_digest,
                raw_row,
                tsi.EvalResultsTrial(
                    predict_and_score_call_id=call.id,
                    model_output=output.get("output"),
                    scores=output.get("scores", {}),
                    model_latency_seconds=_get_path(output, "model_latency.mean"),
                    total_tokens=_get_path(call.summary or {}, "usage.total_tokens"),
                ),
            )

    def _eval_raw_row(self, example: Any, resolve_refs: bool) -> Any:
        if isinstance(example, str) and resolve_refs:
            return self._read_ref(example)
        return example

    def _prediction_from_call(self, call: tsi.CallSchema) -> tsi.PredictionReadRes:
        attrs = _weave_attrs(call)
        evaluation_run_id = attrs.get(constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY)
        if evaluation_run_id is None and call.parent_id is not None:
            parent = self._calls.get((call.project_id, call.parent_id))
            if parent is not None and _is_predict_and_score_call(parent):
                evaluation_run_id = parent.parent_id
        return tsi.PredictionReadRes(
            prediction_id=call.id,
            model=attrs.get(constants.PREDICTION_MODEL_ATTR_KEY, ""),
            inputs=get_prediction_inputs(call.inputs),
            output=call.output,
            evaluation_run_id=evaluation_run_id,
            wb_user_id=call.wb_user_id,
        )

    def _score_outputs_for_parent(self, project_id: str, parent_id: str) -> dict[str, Any]:
        scores: dict[str, Any] = {}
        for call in self._calls.values():
            if (
                call.project_id != project_id
                or call.deleted_at is not None
                or call.parent_id != parent_id
                or call.output is None
                or not _is_score_call(call)
            ):
                continue
            scores[_score_key_from_call(call)] = call.output
        return scores

    def _eval_summary(
        self, rows: list[tsi.EvalResultsRow]
    ) -> tsi.EvalResultsSummaryRes:
        summaries: dict[str, tsi.EvalResultsEvaluationSummary] = {}
        values: dict[tuple[str, str, str | None], list[Any]] = {}
        for row in rows:
            for row_eval in row.evaluations:
                summary = summaries.setdefault(
                    row_eval.evaluation_call_id,
                    tsi.EvalResultsEvaluationSummary(
                        evaluation_call_id=row_eval.evaluation_call_id
                    ),
                )
                summary.trial_count += len(row_eval.trials)
                for trial in row_eval.trials:
                    for scorer_key, score_value in trial.scores.items():
                        for path, leaf in _flatten_score_value(score_value):
                            values.setdefault(
                                (row_eval.evaluation_call_id, scorer_key, path), []
                            ).append(leaf)
        for (evaluation_id, scorer_key, path), score_values in values.items():
            summaries[evaluation_id].scorer_stats.append(
                _score_stats(scorer_key, path, score_values)
            )
        return tsi.EvalResultsSummaryRes(
            row_count=len(rows), evaluations=list(summaries.values())
        )

    def _usage_response(
        self, calls: list[tsi.CallSchema], include_costs: bool
    ) -> tsi.TraceUsageRes:
        usage_calls = [
            usage_utils.UsageCall(
                id=call.id,
                parent_id=call.parent_id,
                summary=call.summary,
            )
            for call in calls
        ]
        return tsi.TraceUsageRes(
            call_usage=usage_utils.aggregate_usage_with_descendants(
                usage_calls, include_costs
            ),
            unfinished_call_ids=sorted(
                call.id for call in calls if call.ended_at is None
            ),
        )


def _now() -> datetime.datetime:
    return _DATETIME_TYPE.now(datetime.timezone.utc)


def _dump(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(item)


def _strip_if_too_large(value: Any) -> Any:
    if _storage_size(value) > ch_settings.CLICKHOUSE_SINGLE_ROW_INSERT_BYTES_LIMIT:
        return json.loads(ch_settings.ENTITY_TOO_LARGE_PAYLOAD)
    return value


def _strip_call_large_values(call: tsi.CallSchema) -> tsi.CallSchema:
    fields = ["inputs", "output", "attributes", "summary"]
    values = {field: getattr(call, field) for field in fields}
    sizes = {field: _storage_size(value) for field, value in values.items()}
    total_size = sum(sizes.values())
    if total_size <= ch_settings.CLICKHOUSE_SINGLE_ROW_INSERT_BYTES_LIMIT:
        return call

    stripped = dict(values)
    too_large = json.loads(ch_settings.ENTITY_TOO_LARGE_PAYLOAD)
    replacement_size = _storage_size(too_large)
    for field, size in sorted(sizes.items(), key=lambda item: item[1], reverse=True):
        if total_size <= ch_settings.CLICKHOUSE_SINGLE_ROW_INSERT_BYTES_LIMIT:
            break
        stripped[field] = too_large
        total_size -= size - replacement_size
    return call.model_copy(update=stripped)


def _storage_size(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, default=str).encode())


def _bucket_start(
    value: datetime.datetime, start: datetime.datetime, granularity: int
) -> datetime.datetime:
    delta = value - start
    bucket = int(delta.total_seconds() // granularity) * granularity
    return start + datetime.timedelta(seconds=bucket)


def _normalize_usage_metrics(usage: dict[str, Any]) -> dict[str, float]:
    input_tokens = _safe_float(usage.get("prompt_tokens")) + _safe_float(
        usage.get("input_tokens")
    )
    output_tokens = _safe_float(usage.get("completion_tokens")) + _safe_float(
        usage.get("output_tokens")
    )
    total_tokens = _safe_float(usage.get("total_tokens")) or input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cache_read_input_tokens": _safe_float(usage.get("cache_read_input_tokens")),
        "cache_creation_input_tokens": _safe_float(
            usage.get("cache_creation_input_tokens")
        ),
        "input_cost": _safe_float(usage.get("prompt_tokens_total_cost")),
        "output_cost": _safe_float(usage.get("completion_tokens_total_cost")),
        "total_cost": _safe_float(usage.get("total_cost")),
    }


def _call_metric_value(call: tsi.CallSchema, metric: str) -> float:
    if metric == "call_count":
        return 1.0
    if metric == "error_count":
        return 1.0 if call.exception else 0.0
    if metric == "latency_ms" and call.ended_at is not None:
        return (call.ended_at - call.started_at).total_seconds() * 1000
    return 0.0


def _add_aggregations(row: dict[str, Any], metric: str, values: list[float], spec: Any) -> None:
    aggregations = spec.aggregations or []
    row["count"] = max(row.get("count", 0), len(values))
    for aggregation in aggregations:
        if aggregation == tsi.AggregationType.SUM:
            row[f"sum_{metric}"] = sum(values)
        elif aggregation == tsi.AggregationType.AVG:
            row[f"avg_{metric}"] = sum(values) / len(values) if values else None
        elif aggregation == tsi.AggregationType.MIN:
            row[f"min_{metric}"] = min(values) if values else None
        elif aggregation == tsi.AggregationType.MAX:
            row[f"max_{metric}"] = max(values) if values else None
        elif aggregation == tsi.AggregationType.COUNT:
            row[f"count_{metric}"] = len(values)
    for percentile in spec.percentiles or []:
        row[f"p{int(percentile)}_{metric}"] = _percentile(values, percentile)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (percentile / 100) * (len(sorted_values) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _safe_float(value: Any) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _token_count(usage: dict[str, Any], primary: str, fallback: str) -> int:
    return int(_safe_float(usage.get(primary) or usage.get(fallback)))


_EPOCH = _DATETIME_TYPE(1970, 1, 1, tzinfo=datetime.timezone.utc)


@cache
def _default_costs() -> dict[str, dict[str, Any]]:
    path = Path(__file__).parents[3] / "weave/trace_server/costs/cost_checkpoint.json"
    raw = json.loads(path.read_text())
    loaded: dict[str, dict[str, Any]] = {}
    for model, entries in raw.items():
        if not entries:
            continue
        entry = entries[0]
        created_at = entry.get("created_at")
        loaded[model] = {
            "prompt_token_cost": entry.get("input", 0),
            "completion_token_cost": entry.get("output", 0),
            "prompt_token_cost_unit": "USD",
            "completion_token_cost_unit": "USD",
            "effective_date": created_at,
            "provider_id": entry.get("provider", "default"),
            "pricing_level": "default",
            "pricing_level_id": "default",
            "created_at": created_at,
            "created_by": "system",
            "cache_read_input_token_cost": 0.0,
            "cache_creation_input_token_cost": 0.0,
        }
    return loaded


def _default_cost_for_model(llm_id: str) -> dict[str, Any] | None:
    return _default_costs().get(llm_id)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {_jsonable_key(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, _DATETIME_TYPE):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _jsonable_key(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _get_kind(val: Any) -> str:
    if isinstance(val, dict):
        if val.get("weave_type", {}).get("type") == "Op":
            return "op"
        if val.get("_type") == "Op":
            return "op"
    return "object"


def _matches_calls_filter(call: tsi.CallSchema, filters: tsi.CallsFilter | None) -> bool:
    if filters is None:
        return True
    if filters.op_names is not None and len(filters.op_names) > 0 and not any(
        _op_filter_matches(call.op_name, expected) for expected in filters.op_names
    ):
        return False
    checks = [
        (filters.parent_ids, call.parent_id),
        (filters.trace_ids, call.trace_id),
        (filters.call_ids, call.id),
        (filters.thread_ids, call.thread_id),
        (filters.turn_ids, call.turn_id),
        (filters.wb_user_ids, call.wb_user_id),
        (filters.wb_run_ids, call.wb_run_id),
    ]
    if any(
        values is not None and len(values) > 0 and value not in values
        for values, value in checks
    ):
        return False
    if filters.trace_roots_only and call.parent_id is not None:
        return False
    if filters.input_refs:
        refs = set(extract_refs_from_values(call.inputs))
        if not _refs_intersect(refs, filters.input_refs):
            return False
    if filters.output_refs:
        refs = set(extract_refs_from_values(call.output))
        if not _refs_intersect(refs, filters.output_refs):
            return False
    return True


def _validate_calls_filter(filters: tsi.CallsFilter | None) -> None:
    if filters is None:
        return
    for field in (
        "call_ids",
        "op_names",
        "input_refs",
        "output_refs",
        "parent_ids",
        "trace_ids",
    ):
        value = getattr(filters, field)
        if value is not None and len(value) > 1000:
            raise ValueError(
                f"Parameter: '{field}' request length is greater than max length (1000). Actual length: {len(value)}"
            )


def _refs_intersect(actual_refs: set[str], expected_refs: list[str]) -> bool:
    for actual in actual_refs:
        for expected in expected_refs:
            if _ref_matches(actual, expected):
                return True
    return False


def _ref_matches(actual: str, expected: str) -> bool:
    if actual == expected:
        return True
    if expected.endswith(":*"):
        return _ref_kind_and_name(actual) == _ref_kind_and_name(expected[:-2])
    return False


def _ref_kind_and_name(ref: str) -> tuple[str, str] | None:
    for kind in ("object", "op"):
        marker = f"/{kind}/"
        if marker not in ref:
            continue
        tail = ref.split(marker, 1)[1]
        name = tail.split(":", 1)[0]
        return kind, name
    return None


def _op_filter_matches(op_name: str, expected: str) -> bool:
    if expected.endswith(":*"):
        try:
            parsed_expected = refs_internal.parse_internal_uri(expected[:-2] + ":latest")
            parsed_actual = refs_internal.parse_internal_uri(op_name)
        except refs_internal.InvalidInternalRef:
            return op_name.startswith(expected[:-1])
        return (
            isinstance(parsed_expected, refs_internal.InternalOpRef)
            and isinstance(parsed_actual, refs_internal.InternalOpRef)
            and parsed_expected.name == parsed_actual.name
            and parsed_expected.project_id == parsed_actual.project_id
        )
    if expected.startswith(refs_internal.WEAVE_INTERNAL_SCHEME):
        return op_name == expected
    return op_name_matches(op_name, expected)


def _matches_object_filter(
    obj: tsi.ObjSchema, filters: tsi.ObjectVersionFilter | None
) -> bool:
    if filters is None:
        return True
    if filters.object_ids is not None and obj.object_id not in filters.object_ids:
        return False
    if filters.latest_only and not obj.is_latest:
        return False
    if filters.is_op is not None and (obj.kind == "op") != filters.is_op:
        return False
    if (
        filters.base_object_classes is not None
        and obj.base_object_class not in filters.base_object_classes
    ):
        return False
    if (
        filters.exclude_base_object_classes is not None
        and obj.base_object_class in filters.exclude_base_object_classes
    ):
        return False
    if (
        filters.leaf_object_classes is not None
        and obj.leaf_object_class not in filters.leaf_object_classes
    ):
        return False
    if filters.tags is not None and filters.tags and not set(filters.tags).intersection(
        obj.tags or []
    ):
        return False
    if (
        filters.aliases is not None
        and filters.aliases
        and not set(filters.aliases).intersection(obj.aliases or [])
    ):
        return False
    return True


def _with_tags_aliases(obj: tsi.ObjSchema, include: bool) -> tsi.ObjSchema:
    if include:
        return obj
    return obj.model_copy(update={"tags": None, "aliases": None})


def _matches_evaluation_run_filter(
    run: tsi.EvaluationRunReadRes, filters: tsi.EvaluationRunFilter | None
) -> bool:
    if filters is None:
        return True
    if filters.evaluations is not None and run.evaluation not in filters.evaluations:
        return False
    if filters.models is not None and run.model not in filters.models:
        return False
    if (
        filters.evaluation_run_ids is not None
        and run.evaluation_run_id not in filters.evaluation_run_ids
    ):
        return False
    return True


def _weave_attrs(call: tsi.CallSchema) -> dict[str, Any]:
    if not isinstance(call.attributes, dict):
        return {}
    attrs = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})
    return attrs if isinstance(attrs, dict) else {}


def _is_true_attr(value: Any) -> bool:
    return value is True or value == "true"


def _is_prediction_call(call: tsi.CallSchema) -> bool:
    return _is_true_attr(_weave_attrs(call).get(constants.PREDICTION_ATTR_KEY))


def _is_score_call(call: tsi.CallSchema) -> bool:
    attrs = _weave_attrs(call)
    if _is_true_attr(attrs.get(constants.SCORE_ATTR_KEY)):
        return True
    call_attrs = call.attributes if isinstance(call.attributes, dict) else {}
    eval_meta = call_attrs.get("_weave_eval_meta", {})
    return isinstance(eval_meta, dict) and bool(eval_meta.get("score"))


def _is_predict_and_score_call(call: tsi.CallSchema) -> bool:
    return any(
        op_name_matches(call.op_name, expected)
        for expected in constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAMES
    )


def _score_key_from_call(call: tsi.CallSchema) -> str:
    scorer_ref = _weave_attrs(call).get(constants.SCORE_SCORER_ATTR_KEY)
    if isinstance(scorer_ref, str) and scorer_ref:
        return _scorer_name(scorer_ref)
    if call.op_name and call.op_name.endswith(".score"):
        return call.op_name[: -len(".score")].rsplit("/", 1)[-1]
    return _scorer_name(call.op_name or "unknown")


def _scorer_name(ref: str) -> str:
    if "/object/" in ref:
        ref = ref.rsplit("/object/", 1)[1]
    if "/op/" in ref:
        ref = ref.rsplit("/op/", 1)[1]
    if ":" in ref:
        ref = ref.split(":", 1)[0]
    return ref.rsplit("/", 1)[-1]


def _flatten_score_value(value: Any, prefix: str | None = None) -> Iterator[tuple[str | None, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            child_prefix = str(key) if prefix is None else f"{prefix}.{key}"
            yield from _flatten_score_value(item, child_prefix)
    else:
        yield prefix, value


def _score_stats(
    scorer_key: str, path: str | None, values: list[Any]
) -> tsi.EvalResultsScorerStats:
    numeric_values = [
        float(value)
        for value in values
        if isinstance(value, int | float) and not isinstance(value, bool)
    ]
    bool_values = [value for value in values if isinstance(value, bool)]
    text_values = [value for value in values if isinstance(value, str)]
    if bool_values:
        value_type = "binary"
    elif numeric_values:
        value_type = "continuous"
    elif text_values:
        value_type = "text"
    else:
        value_type = None
    pass_known_count = len(bool_values)
    pass_true_count = sum(1 for value in bool_values if value)
    return tsi.EvalResultsScorerStats(
        scorer_key=scorer_key,
        path=path,
        value_type=value_type,
        trial_count=len(values),
        numeric_count=len(numeric_values),
        numeric_mean=(
            sum(numeric_values) / len(numeric_values) if numeric_values else None
        ),
        pass_true_count=pass_true_count,
        pass_known_count=pass_known_count,
        pass_rate=(
            pass_true_count / pass_known_count if pass_known_count else None
        ),
        pass_signal_coverage=(
            pass_known_count / len(values) if values else None
        ),
    )


def _feedback_matches_call(feedback: tsi.Feedback, call: tsi.CallSchema) -> bool:
    try:
        parsed = refs_internal.parse_internal_uri(feedback.weave_ref)
    except refs_internal.InvalidInternalRef:
        return False
    if (
        isinstance(parsed, refs_internal.InternalCallRef)
        and parsed.project_id == call.project_id
        and parsed.id == call.id
    ):
        return True
    return False


def _validate_feedback_query_fields(query: tsi.Query | None) -> None:
    allowed = {
        "id",
        "project_id",
        "weave_ref",
        "wb_user_id",
        "creator",
        "created_at",
        "feedback_type",
        "payload",
        "annotation_ref",
        "runnable_ref",
        "call_ref",
        "trigger_ref",
        "queue_id",
    }
    for field in _query_get_fields(query.expr_ if query is not None else None):
        top = field.split(".", 1)[0]
        if top not in allowed:
            raise ValueError(f"Unknown field: {field}")


def _query_get_fields(operand: Any) -> Iterator[str]:
    if operand is None:
        return
    if isinstance(operand, list):
        for item in operand:
            yield from _query_get_fields(item)
        return
    if hasattr(operand, "get_field_"):
        yield operand.get_field_
    for value in getattr(operand, "__dict__", {}).values():
        yield from _query_get_fields(value)


def _filter_feedback_window(
    feedback_rows: list[tsi.Feedback],
    req: tsi.FeedbackStatsReq | tsi.FeedbackPayloadSchemaReq,
    end: datetime.datetime,
) -> list[tsi.Feedback]:
    return [
        feedback
        for feedback in feedback_rows
        if feedback.project_id == req.project_id
        and req.start <= feedback.created_at < end
        and (req.feedback_type is None or feedback.feedback_type == req.feedback_type)
        and (
            req.trigger_ref is None
            or feedback.trigger_ref == req.trigger_ref
            or (
                feedback.trigger_ref is not None
                and feedback.trigger_ref.startswith(req.trigger_ref)
            )
        )
    ]


def _feedback_aggregations(
    values: list[Any], metric: tsi.FeedbackMetricSpec
) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    numeric_values = [
        float(value)
        for value in values
        if isinstance(value, int | float) and not isinstance(value, bool)
    ]
    bool_values = [value for value in values if isinstance(value, bool)]
    for aggregation in metric.aggregations:
        if aggregation == tsi.AggregationType.COUNT:
            result["count"] = float(len(values))
        elif aggregation == tsi.AggregationType.AVG:
            result["avg"] = (
                sum(numeric_values) / len(numeric_values) if numeric_values else None
            )
        elif aggregation == tsi.AggregationType.MIN:
            result["min"] = min(numeric_values) if numeric_values else None
        elif aggregation == tsi.AggregationType.MAX:
            result["max"] = max(numeric_values) if numeric_values else None
        elif aggregation == tsi.AggregationType.SUM:
            result["sum"] = sum(numeric_values)
        elif aggregation == tsi.AggregationType.COUNT_TRUE:
            result["count_true"] = float(sum(1 for value in bool_values if value))
        elif aggregation == tsi.AggregationType.COUNT_FALSE:
            result["count_false"] = float(sum(1 for value in bool_values if not value))
    for percentile in metric.percentiles:
        result[f"p{int(percentile)}"] = _percentile(numeric_values, percentile)
    return result


def _flatten_payload(value: Any, prefix: str | None = None) -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            path = str(key) if prefix is None else f"{prefix}.{key}"
            yield from _flatten_payload(item, path)
    elif prefix is not None:
        yield prefix, value


def _feedback_value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "numeric"
    return "categorical"


def _matches_query(row: dict[str, Any], query: tsi.Query | None) -> bool:
    if query is None:
        return True
    return bool(_eval_operand(query.expr_, row))


def _eval_operand(operand: tsi_query.Operand, row: dict[str, Any]) -> Any:
    if isinstance(operand, list | tuple):
        return [_eval_operand(item, row) for item in operand]
    if hasattr(operand, "literal_"):
        return operand.literal_
    if hasattr(operand, "get_field_"):
        return _get_path(row, operand.get_field_)
    if hasattr(operand, "convert_"):
        value = _eval_operand(operand.convert_.input, row)
        return _convert_value(value, operand.convert_.to)
    if hasattr(operand, "and_"):
        return all(_eval_operand(item, row) for item in operand.and_)
    if hasattr(operand, "or_"):
        return any(_eval_operand(item, row) for item in operand.or_)
    if hasattr(operand, "not_"):
        if isinstance(operand.not_, list | tuple):
            values = [_eval_operand(item, row) for item in operand.not_]
            if any(value is None for value in values):
                return False
            return not any(values)
        value = _eval_operand(operand.not_, row)
        return False if value is None else not value
    if hasattr(operand, "eq_"):
        left, right = operand.eq_
        return _compare_values(_eval_operand(left, row), _eval_operand(right, row), "eq")
    if hasattr(operand, "gt_"):
        left, right = operand.gt_
        return _compare_values(_eval_operand(left, row), _eval_operand(right, row), "gt")
    if hasattr(operand, "gte_"):
        left, right = operand.gte_
        return _compare_values(
            _eval_operand(left, row), _eval_operand(right, row), "gte"
        )
    if hasattr(operand, "lt_"):
        left, right = operand.lt_
        return _compare_values(_eval_operand(left, row), _eval_operand(right, row), "lt")
    if hasattr(operand, "lte_"):
        left, right = operand.lte_
        return _compare_values(
            _eval_operand(left, row), _eval_operand(right, row), "lte"
        )
    if hasattr(operand, "in_"):
        left, right = operand.in_
        return _eval_operand(left, row) in _eval_operand(right, row)
    if hasattr(operand, "contains_"):
        spec = operand.contains_
        value = str(_eval_operand(spec.input, row))
        substr = str(_eval_operand(spec.substr, row))
        if spec.case_insensitive:
            value = value.lower()
            substr = substr.lower()
        return substr in value
    return operand


def _convert_value(value: Any, target: str) -> Any:
    if value is None:
        return None
    if target in {"int", "long"}:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if target in {"double", "float"}:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if target in {"bool", "boolean"}:
        return bool(value)
    if target in {"string", "str"}:
        return str(value)
    return value


def _compare_values(left: Any, right: Any, op: str) -> bool:
    if isinstance(left, list):
        return any(_compare_values(item, right, op) for item in left)
    if isinstance(right, list):
        return any(_compare_values(left, item, op) for item in right)
    if op == "eq" and ((left is None and right == "") or (right is None and left == "")):
        return True
    if (left is None or right is None) and op != "eq":
        return None
    left, right = _normalize_compare_values(left, right)
    try:
        if op == "eq":
            return left == right
        if op == "gt":
            return left > right
        if op == "gte":
            return left >= right
        if op == "lt":
            return left < right
        if op == "lte":
            return left <= right
    except TypeError:
        return None
    return False


def _normalize_compare_values(left: Any, right: Any) -> tuple[Any, Any]:
    if isinstance(left, bool) and isinstance(right, str):
        return str(left).lower(), right
    if isinstance(right, bool) and isinstance(left, str):
        return left, str(right).lower()
    if isinstance(left, _DATETIME_TYPE) and isinstance(right, int | float):
        return left.timestamp(), right
    if isinstance(right, _DATETIME_TYPE) and isinstance(left, int | float):
        return left, right.timestamp()
    if isinstance(left, int | float) and isinstance(right, str):
        parsed = _parse_number(right)
        if parsed is not None:
            return left, parsed
    if isinstance(right, int | float) and isinstance(left, str):
        parsed = _parse_number(left)
        if parsed is not None:
            return parsed, right
    return left, right


def _parse_number(value: str) -> int | float | None:
    try:
        parsed = float(value)
    except ValueError:
        return None
    return int(parsed) if parsed.is_integer() else parsed


def _sort_items(
    items: list[Any], sort_by: list[Any] | None, row_fn: Callable[[Any], dict[str, Any]]
) -> list[Any]:
    if not sort_by:
        return items
    sorted_items = list(items)
    for sort in reversed(sort_by):
        sort_field = sort.field
        sort_direction = sort.direction
        sorted_items.sort(
            key=cmp_to_key(
                lambda left, right, sort_field=sort_field, sort_direction=sort_direction: _compare_sort_values(
                    _get_path(row_fn(left), sort_field),
                    _get_path(row_fn(right), sort_field),
                    sort_direction,
                )
            ),
        )
    return sorted_items


def _compare_sort_values(left: Any, right: Any, direction: str) -> int:
    left_key = _sort_key(left)
    right_key = _sort_key(right)
    if left_key[:2] != right_key[:2]:
        return (left_key[:2] > right_key[:2]) - (left_key[:2] < right_key[:2])
    left_value = left_key[2]
    right_value = right_key[2]
    result = (left_value > right_value) - (left_value < right_value)
    return -result if direction == "desc" else result


def _sort_key(value: Any) -> tuple[int, int, Any]:
    if value is None:
        return (1, 0, "")
    if isinstance(value, _DATETIME_TYPE):
        return (0, 0, value.timestamp())
    if isinstance(value, int | float):
        return (0, 0, float(value))
    if isinstance(value, str):
        return (0, 1, value)
    return (0, 2, str(value))


def _page(items: list[Any], offset: int | None, limit: int | None) -> Iterator[Any]:
    start = offset or 0
    stop = None if limit is None else start + limit
    yield from items[start:stop]


def _validate_sort_fields(sort_by: list[Any] | None) -> None:
    for sort in sort_by or []:
        field = sort.field
        if (
            not field
            or field.startswith(".")
            or field.endswith(".")
            or ".." in field
        ):
            raise ValueError(f"Invalid sort field: {field}")


def _call_update_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        field: row[field]
        for field in (
            "attributes",
            "inputs",
            "output",
            "summary",
            "ended_at",
        )
        if field in row
    }


def _expand_path(
    row: dict[str, Any], path: str, read_ref: Callable[[str], Any]
) -> None:
    value = _get_path(row, path)
    if not isinstance(value, str) or not refs_internal.string_will_be_interpreted_as_ref(
        value
    ):
        return
    expanded = read_ref(value)
    if expanded is not None:
        _assign_path(row, path, expanded)


def _expand_path_for_query(
    row: dict[str, Any], path: str, read_ref: Callable[[str], Any]
) -> None:
    value = _get_path(row, path)
    if isinstance(value, str) and refs_internal.string_will_be_interpreted_as_ref(value):
        _assign_path(row, path, read_ref(value))
    elif value is not None:
        _assign_path(row, path, None)


def _assign_path(row: dict[str, Any], path: str, value: Any) -> None:
    parts = _split_path(path)
    current = row
    for part in parts[:-1]:
        key = part
        if part.startswith("[") and part.endswith("]"):
            key = part[1:-1]
        next_value = current.get(key)
        if not isinstance(next_value, dict):
            next_value = {}
            current[key] = next_value
        current = next_value
    final = parts[-1]
    if final.startswith("[") and final.endswith("]"):
        final = final[1:-1]
    current[final] = value


def _project_fields(row: dict[str, Any], fields: list[str] | None) -> dict[str, Any]:
    if fields is None:
        return row
    if fields == ["count(*)"]:
        return {"count(*)": 1}
    return {field: _get_path(row, field) for field in fields}


def _get_path(value: Any, path: str) -> Any:
    return _get_path_parts(value, _split_path(path))


def _split_path(path: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    bracket_depth = 0
    index = 0
    while index < len(path):
        char = path[index]
        if char == "\\" and index + 1 < len(path):
            current.append(path[index + 1])
            index += 2
            continue
        if char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)
        if char == "." and bracket_depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1
    parts.append("".join(current))
    return parts


def _get_path_parts(value: Any, parts: list[str]) -> Any:
    current = value
    for index, part in enumerate(parts):
        if current is None:
            return None
        rest = parts[index + 1 :]
        if isinstance(current, list):
            if part.isdigit():
                item_index = int(part)
                if item_index >= len(current):
                    return None
                current = current[item_index]
                continue
            values = [_get_path_parts(item, [part, *rest]) for item in current]
            flattened = []
            for item in values:
                if isinstance(item, list):
                    flattened.extend(item)
                elif item is not None:
                    flattened.append(item)
            return flattened
        if isinstance(current, dict):
            if part.startswith("[") and part.endswith("]"):
                key = part[1:-1]
                if key == "*":
                    current = list(current.values())
                else:
                    current = current.get(key)
            else:
                current = current.get(part)
        else:
            current = getattr(current, part, None)
    return current


def _apply_ref_extra(
    value: Any,
    extra: list[str],
    tables: dict[tuple[str, str], list[tsi.TableRowSchema]],
) -> Any:
    current = value
    for edge, edge_value in zip(extra[0::2], extra[1::2], strict=True):
        if edge in {refs_internal.DICT_KEY_EDGE_NAME, refs_internal.OBJECT_ATTR_EDGE_NAME}:
            if isinstance(current, dict) and edge_value in current:
                current = current[edge_value]
            else:
                current = _get_path(current, edge_value)
        elif edge == refs_internal.LIST_INDEX_EDGE_NAME:
            current = current[int(edge_value)]
        elif edge == refs_internal.TABLE_ROW_ID_EDGE_NAME:
            if isinstance(current, str):
                table_ref = refs_internal.parse_internal_uri(current)
                if isinstance(table_ref, refs_internal.InternalTableRef):
                    rows = tables.get((table_ref.project_id, table_ref.digest), [])
                    current = next(
                        (row.val for row in rows if row.digest == edge_value), None
                    )
            elif isinstance(current, list):
                current = next(
                    (
                        item
                        for item in current
                        if isinstance(item, dict) and item.get("digest") == edge_value
                    ),
                    None,
                )
    return current
