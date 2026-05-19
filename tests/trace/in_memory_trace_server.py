from __future__ import annotations

import datetime
import itertools
import threading
from collections.abc import Iterator
from typing import Any

from weave.trace_server import trace_server_interface as tsi

DIGEST_PREFIX = "in-memory-digest"
ROW_DIGEST_PREFIX = "in-memory-row"


class InMemoryTraceServer:
    """Small in-memory trace server for client-contract tests."""

    def __init__(self) -> None:
        self._calls: dict[str, tsi.CallSchema] = {}
        self._call_order: list[str] = []
        self._pending_ends: dict[str, tsi.EndedCallSchemaForInsert] = {}
        self._objects: dict[tuple[str, str, str], tsi.ObjSchema] = {}
        self._refs: dict[str, Any] = {}
        self._tables: dict[tuple[str, str], list[tsi.TableRowSchema]] = {}
        self.feedback: list[tsi.FeedbackCreateReq] = []
        self._counter = itertools.count(1)
        self._lock = threading.Lock()

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        start = req.start
        call_id = start.id or self._next_digest()
        trace_id = start.trace_id or self._next_digest()
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
            attributes=start.attributes,
            inputs=start.inputs,
            wb_run_id=start.wb_run_id,
            wb_run_step=start.wb_run_step,
        )
        with self._lock:
            self._calls[call_id] = call
            self._call_order.append(call_id)
            if pending_end := self._pending_ends.pop(call_id, None):
                self._apply_call_end(call, pending_end)
        return tsi.CallStartRes(id=call_id, trace_id=trace_id)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        end = req.end
        with self._lock:
            call = self._calls.get(end.id)
            if call is None:
                self._pending_ends[end.id] = end
            else:
                self._apply_call_end(call, end)
        return tsi.CallEndRes()

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        calls = self._filtered_calls(req.filter)
        offset = req.offset or 0
        limit = req.limit
        selected = calls[offset:] if limit is None else calls[offset : offset + limit]
        yield from (call.model_copy(deep=True) for call in selected)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        return tsi.CallsQueryStatsRes(count=len(self._filtered_calls(req.filter)))

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        obj = req.obj
        digest = obj.expected_digest or self._next_digest()
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        schema = tsi.ObjSchema(
            project_id=obj.project_id,
            object_id=obj.object_id,
            created_at=now,
            digest=digest,
            version_index=0,
            is_latest=1,
            kind="object",
            base_object_class=obj.builtin_object_class or obj.set_base_object_class,
            val=obj.val,
        )
        with self._lock:
            self._objects[obj.project_id, obj.object_id, digest] = schema
            self._store_ref(obj.project_id, "object", obj.object_id, digest, obj.val)
            self._store_ref(obj.project_id, "op", obj.object_id, digest, obj.val)
        return tsi.ObjCreateRes(digest=digest, object_id=obj.object_id)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        obj = self._objects[req.project_id, req.object_id, req.digest]
        if req.metadata_only:
            obj = obj.model_copy(update={"val": None})
        return tsi.ObjReadRes(obj=obj.model_copy(deep=True))

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return tsi.RefsReadBatchRes(
            vals=[self._refs[self._base_ref(ref)] for ref in req.refs]
        )

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        table = req.table
        digest = table.expected_digest or self._next_digest()
        row_digests = [f"{ROW_DIGEST_PREFIX}-{next(self._counter)}" for _ in table.rows]
        rows = [
            tsi.TableRowSchema(digest=row_digest, val=row, original_index=index)
            for index, (row_digest, row) in enumerate(
                zip(row_digests, table.rows, strict=True)
            )
        ]
        with self._lock:
            self._tables[table.project_id, digest] = rows
            self._refs[f"weave:///{table.project_id}/table/{digest}"] = table.rows
        return tsi.TableCreateRes(digest=digest, row_digests=row_digests)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        rows = self._tables[req.project_id, req.digest]
        offset = req.offset or 0
        limit = req.limit
        selected = rows[offset:] if limit is None else rows[offset : offset + limit]
        yield from (row.model_copy(deep=True) for row in selected)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return tsi.TableQueryRes(rows=list(self.table_query_stream(req)))

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        return tsi.FileCreateRes(digest=req.expected_digest or self._next_digest())

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        with self._lock:
            self.feedback.append(req)
        return tsi.FeedbackCreateRes(
            id=req.id or self._next_digest(),
            created_at=datetime.datetime.now(tz=datetime.timezone.utc),
            wb_user_id=req.wb_user_id or "",
            payload={},
        )

    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        return tsi.FeedbackCreateBatchRes(
            res=[self.feedback_create(item) for item in req.batch]
        )

    def close(self) -> None:
        pass

    def _filtered_calls(
        self, call_filter: tsi.CallsFilter | None
    ) -> list[tsi.CallSchema]:
        with self._lock:
            calls = [self._calls[call_id] for call_id in self._call_order]
        if call_filter is None:
            return calls

        if call_filter.call_ids is not None:
            calls = [call for call in calls if call.id in call_filter.call_ids]
        if call_filter.trace_ids is not None:
            calls = [call for call in calls if call.trace_id in call_filter.trace_ids]
        if call_filter.parent_ids is not None:
            calls = [call for call in calls if call.parent_id in call_filter.parent_ids]
        if call_filter.op_names is not None:
            calls = [
                call
                for call in calls
                if any(
                    self._matches_op_name(call.op_name, name)
                    for name in call_filter.op_names
                )
            ]
        if call_filter.trace_roots_only:
            calls = [call for call in calls if call.parent_id is None]
        return calls

    def _next_digest(self) -> str:
        return f"{DIGEST_PREFIX}-{next(self._counter)}"

    def _store_ref(
        self, project_id: str, ref_type: str, object_id: str, digest: str, val: Any
    ) -> None:
        self._refs[f"weave:///{project_id}/{ref_type}/{object_id}:{digest}"] = val

    @staticmethod
    def _base_ref(ref: str) -> str:
        if "/object/" in ref:
            prefix, suffix = ref.split("/object/", maxsplit=1)
            name_digest = suffix.split("/", maxsplit=1)[0]
            return f"{prefix}/object/{name_digest}"
        if "/op/" in ref:
            prefix, suffix = ref.split("/op/", maxsplit=1)
            name_digest = suffix.split("/", maxsplit=1)[0]
            return f"{prefix}/op/{name_digest}"
        return ref

    @staticmethod
    def _matches_op_name(stored_op_name: str, requested_op_name: str) -> bool:
        stored_name = stored_op_name.rsplit("/", maxsplit=1)[-1].split(":", maxsplit=1)[
            0
        ]
        return requested_op_name in {stored_op_name, stored_name}

    @staticmethod
    def _apply_call_end(
        call: tsi.CallSchema, end: tsi.EndedCallSchemaForInsert
    ) -> None:
        call.ended_at = end.ended_at
        call.output = end.output
        call.summary = end.summary
        call.exception = end.exception
        call.wb_run_step_end = end.wb_run_step_end
