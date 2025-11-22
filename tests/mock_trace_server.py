"""Mock Trace Server for testing without real database backends.

This module provides an in-memory mock implementation of the TraceServerInterface
that can be used in tests to avoid dependencies on ClickHouse or SQLite.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id


class MockTraceServer:
    """In-memory mock implementation of TraceServerInterface.

    Stores all data in memory dictionaries for fast, isolated testing.
    """

    def __init__(self):
        # Storage
        self.calls: dict[str, tsi.CallSchema] = {}
        self.objs: dict[str, dict[str, Any]] = {}
        self.tables: dict[str, dict[str, Any]] = {}
        self.files: dict[str, bytes] = {}
        self.feedback: dict[str, tsi.FeedbackDict] = {}
        self.costs: dict[str, Any] = {}
        self.projects: set[str] = set()

        # Track latest timestamps for ordering
        self.call_order: list[str] = []

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        project_id = f"{entity}/{project}"
        self.projects.add(project_id)
        return tsi.EnsureProjectExistsRes(project_name=project)

    # OTEL API
    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        return tsi.OtelExportRes()

    # Call API
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        call_id = req.start.id or generate_id()
        trace_id = req.start.trace_id or call_id

        call = tsi.CallSchema(
            id=call_id,
            project_id=req.start.project_id,
            op_name=req.start.op_name,
            display_name=req.start.display_name,
            trace_id=trace_id,
            parent_id=req.start.parent_id,
            thread_id=req.start.thread_id,
            turn_id=req.start.turn_id,
            started_at=req.start.started_at,
            attributes=req.start.attributes or {},
            inputs=req.start.inputs,
            ended_at=None,
            exception=None,
            output=None,
            summary=None,
            wb_user_id=req.start.wb_user_id,
            wb_run_id=req.start.wb_run_id,
            wb_run_step=req.start.wb_run_step,
            wb_run_step_end=None,
            deleted_at=None,
        )

        self.calls[call_id] = call
        self.call_order.append(call_id)

        return tsi.CallStartRes(
            id=call_id,
            trace_id=trace_id,
        )

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        if req.end.id not in self.calls:
            raise tsi.NotFoundError(f"Call {req.end.id} not found")

        call = self.calls[req.end.id]
        call.ended_at = req.end.ended_at
        call.exception = req.end.exception
        call.output = req.end.output
        call.summary = req.end.summary
        call.wb_run_step_end = req.end.wb_run_step_end

        return tsi.CallEndRes()

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        if req.id not in self.calls:
            raise tsi.NotFoundError(f"Call {req.id} not found")

        return tsi.CallReadRes(call=self.calls[req.id])

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        calls = list(self.calls_query_stream(req))
        return tsi.CallsQueryRes(calls=calls)

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        # Filter calls by project_id
        filtered_calls = [
            call for call in self.calls.values()
            if call.project_id == req.project_id
        ]

        # Apply filters if provided
        if req.filter:
            filtered_calls = self._apply_call_filters(filtered_calls, req.filter)

        # Sort by started_at (most recent first by default)
        filtered_calls.sort(key=lambda c: c.started_at, reverse=True)

        # Apply limit and offset
        offset = req.offset or 0
        limit = req.limit

        if limit is not None:
            filtered_calls = filtered_calls[offset:offset + limit]
        else:
            filtered_calls = filtered_calls[offset:]

        for call in filtered_calls:
            yield call

    def _apply_call_filters(
        self, calls: list[tsi.CallSchema], filter_dict: dict[str, Any]
    ) -> list[tsi.CallSchema]:
        """Apply filters to calls list."""
        filtered = calls

        # Filter by op_names
        if "op_names" in filter_dict:
            op_names = filter_dict["op_names"]
            filtered = [c for c in filtered if c.op_name in op_names]

        # Filter by trace_ids
        if "trace_ids" in filter_dict:
            trace_ids = filter_dict["trace_ids"]
            filtered = [c for c in filtered if c.trace_id in trace_ids]

        # Filter by parent_ids
        if "parent_ids" in filter_dict:
            parent_ids = filter_dict["parent_ids"]
            filtered = [c for c in filtered if c.parent_id in parent_ids]

        # Filter by call_ids
        if "call_ids" in filter_dict:
            call_ids = filter_dict["call_ids"]
            filtered = [c for c in filtered if c.id in call_ids]

        return filtered

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        deleted_count = 0
        for call_id in req.call_ids:
            if call_id in self.calls:
                del self.calls[call_id]
                if call_id in self.call_order:
                    self.call_order.remove(call_id)
                deleted_count += 1

        return tsi.CallsDeleteRes()

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        # Simple implementation - just return count
        calls = [c for c in self.calls.values() if c.project_id == req.project_id]
        return tsi.CallsQueryStatsRes(count=len(calls))

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        if req.call_id not in self.calls:
            raise tsi.NotFoundError(f"Call {req.call_id} not found")

        call = self.calls[req.call_id]
        if req.display_name is not None:
            call.display_name = req.display_name

        return tsi.CallUpdateRes()

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        results = []
        for start_req in req.batch:
            result = self.call_start(tsi.CallStartReq(start=start_req))
            results.append(result)
        return tsi.CallCreateBatchRes(results=results)

    # Cost API
    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        cost_id = generate_id()
        self.costs[cost_id] = {
            "id": cost_id,
            "project_id": req.project_id,
            "llm_id": req.llm_id,
            "cost": req.cost,
        }
        return tsi.CostCreateRes(id=cost_id)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        costs = [
            c for c in self.costs.values()
            if c["project_id"] == req.project_id
        ]
        return tsi.CostQueryRes(results=costs)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        to_delete = [
            cid for cid, c in self.costs.items()
            if c["project_id"] == req.project_id
        ]
        for cid in to_delete:
            del self.costs[cid]
        return tsi.CostPurgeRes()

    # Obj API
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        key = f"{req.obj.project_id}:{req.obj.object_id}:{req.obj.digest}"
        self.objs[key] = {
            "project_id": req.obj.project_id,
            "object_id": req.obj.object_id,
            "digest": req.obj.digest,
            "val": req.obj.val,
            "created_at": datetime.datetime.now(tz=datetime.timezone.utc),
        }
        return tsi.ObjCreateRes(digest=req.obj.digest)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        key = f"{req.project_id}:{req.object_id}:{req.digest}"
        if key not in self.objs:
            raise tsi.NotFoundError(f"Object {key} not found")

        obj_data = self.objs[key]
        return tsi.ObjReadRes(
            obj=tsi.ObjSchema(
                project_id=obj_data["project_id"],
                object_id=obj_data["object_id"],
                created_at=obj_data["created_at"],
                digest=obj_data["digest"],
                version_index=0,
                is_latest=1,
                val=obj_data["val"],
            )
        )

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        objs = []
        for obj_data in self.objs.values():
            if obj_data["project_id"] != req.project_id:
                continue

            # Apply filters
            if req.filter:
                if "object_ids" in req.filter and obj_data["object_id"] not in req.filter["object_ids"]:
                    continue

            objs.append(
                tsi.ObjSchema(
                    project_id=obj_data["project_id"],
                    object_id=obj_data["object_id"],
                    created_at=obj_data["created_at"],
                    digest=obj_data["digest"],
                    version_index=0,
                    is_latest=1,
                    val=obj_data["val"],
                )
            )

        return tsi.ObjQueryRes(objs=objs)

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        # Delete all versions of the object
        to_delete = [
            key for key in self.objs.keys()
            if key.startswith(f"{req.project_id}:{req.object_id}:")
        ]
        for key in to_delete:
            del self.objs[key]
        return tsi.ObjDeleteRes()

    # Table API
    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        digest = generate_id()
        key = f"{req.table.project_id}:{digest}"

        self.tables[key] = {
            "project_id": req.table.project_id,
            "digest": digest,
            "rows": req.table.rows,
        }

        return tsi.TableCreateRes(digest=digest)

    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes:
        # Combine rows from multiple tables
        all_rows = []
        for digest in req.digests:
            key = f"{req.project_id}:{digest}"
            if key in self.tables:
                all_rows.extend(self.tables[key]["rows"])

        # Create new table with combined rows
        new_digest = generate_id()
        key = f"{req.project_id}:{new_digest}"
        self.tables[key] = {
            "project_id": req.project_id,
            "digest": new_digest,
            "rows": all_rows,
        }

        return tsi.TableCreateFromDigestsRes(digest=new_digest)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        key = f"{req.project_id}:{req.base_digest}"
        if key not in self.tables:
            raise tsi.NotFoundError(f"Table {key} not found")

        # Create new version with updated rows
        new_digest = generate_id()
        new_key = f"{req.project_id}:{new_digest}"

        base_rows = self.tables[key]["rows"].copy()
        base_rows.extend(req.updates)

        self.tables[new_key] = {
            "project_id": req.project_id,
            "digest": new_digest,
            "rows": base_rows,
        }

        return tsi.TableUpdateRes(digest=new_digest)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        key = f"{req.project_id}:{req.digest}"
        if key not in self.tables:
            raise tsi.NotFoundError(f"Table {key} not found")

        table_data = self.tables[key]
        rows = []

        for row in table_data["rows"]:
            rows.append(tsi.TableRowSchema(digest=req.digest, val=row))

        # Apply limit and offset
        offset = req.offset or 0
        limit = req.limit

        if limit is not None:
            rows = rows[offset:offset + limit]
        else:
            rows = rows[offset:]

        return tsi.TableQueryRes(rows=rows)

    def table_query_stream(self, req: tsi.TableQueryReq) -> Iterator[tsi.TableRowSchema]:
        result = self.table_query(req)
        for row in result.rows:
            yield row

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        key = f"{req.project_id}:{req.digest}"
        if key not in self.tables:
            return tsi.TableQueryStatsRes(count=0)

        return tsi.TableQueryStatsRes(count=len(self.tables[key]["rows"]))

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        results = []
        for digest in req.digests:
            stats = self.table_query_stats(
                tsi.TableQueryStatsReq(project_id=req.project_id, digest=digest)
            )
            results.append(stats)
        return tsi.TableQueryStatsBatchRes(results=results)

    # Ref API
    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        vals = []
        for ref in req.refs:
            # Simple implementation - just return the ref URI as the value
            vals.append(ref)
        return tsi.RefsReadBatchRes(vals=vals)

    # File API
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        digest = generate_id()
        key = f"{req.project_id}:{digest}"
        self.files[key] = req.content
        return tsi.FileCreateRes(digest=digest)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        key = f"{req.project_id}:{req.digest}"
        if key not in self.files:
            raise tsi.NotFoundError(f"File {key} not found")

        return tsi.FileContentReadRes(content=self.files[key])

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        # Count files for this project
        count = sum(
            1 for k in self.files.keys()
            if k.startswith(f"{req.project_id}:")
        )
        return tsi.FilesStatsRes(count=count)

    # Feedback API
    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        feedback_id = generate_id()
        self.feedback[feedback_id] = {
            "id": feedback_id,
            "project_id": req.project_id,
            "weave_ref": req.weave_ref,
            "feedback_type": req.feedback_type,
            "payload": req.payload or {},
            "creator": req.creator,
            "created_at": datetime.datetime.now(tz=datetime.timezone.utc),
            "wb_user_id": req.wb_user_id,
        }
        return tsi.FeedbackCreateRes(id=feedback_id)

    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        results = []
        for fb_req in req.batch:
            result = self.feedback_create(fb_req)
            results.append(result)
        return tsi.FeedbackCreateBatchRes(results=results)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        feedback_list = []

        for fb in self.feedback.values():
            if fb["project_id"] != req.project_id:
                continue

            # Apply filters
            if req.query and "weave_ref" in req.query:
                if fb["weave_ref"] != req.query["weave_ref"]:
                    continue

            feedback_list.append(fb)

        return tsi.FeedbackQueryRes(result=feedback_list)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        to_delete = [
            fid for fid, fb in self.feedback.items()
            if fb["project_id"] == req.project_id and fb["weave_ref"] == req.query["weave_ref"]
        ]
        for fid in to_delete:
            del self.feedback[fid]
        return tsi.FeedbackPurgeRes()

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        # Delete existing feedback and create new one
        self.feedback_purge(
            tsi.FeedbackPurgeReq(
                project_id=req.project_id,
                query={"weave_ref": req.weave_ref},
            )
        )
        result = self.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=req.project_id,
                weave_ref=req.weave_ref,
                feedback_type=req.feedback_type,
                payload=req.payload,
                creator=req.creator,
                wb_user_id=req.wb_user_id,
            )
        )
        return tsi.FeedbackReplaceRes(id=result.id)

    # Action API
    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        # Mock implementation - just return empty results
        return tsi.ActionsExecuteBatchRes(results=[])

    # Execute LLM API
    def completions_create(self, req: tsi.CompletionsCreateReq) -> tsi.CompletionsCreateRes:
        # Mock implementation - return empty response
        return tsi.CompletionsCreateRes(
            response={"choices": [{"message": {"content": "mock response"}}]}
        )

    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        # Mock implementation - yield a single chunk
        yield {"choices": [{"delta": {"content": "mock"}}]}

    # Execute Image Generation API
    def image_create(
        self, req: tsi.ImageGenerationCreateReq
    ) -> tsi.ImageGenerationCreateRes:
        # Mock implementation
        return tsi.ImageGenerationCreateRes(response={"data": []})

    # Project statistics API
    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        # Count calls for this project
        call_count = sum(
            1 for c in self.calls.values()
            if c.project_id == req.project_id
        )
        return tsi.ProjectStatsRes(call_count=call_count)

    # Thread API
    def threads_query_stream(self, req: tsi.ThreadsQueryReq) -> Iterator[tsi.ThreadSchema]:
        # Mock implementation - no threads
        return iter([])

    # Evaluation API
    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        # Mock implementation
        eval_id = generate_id()
        return tsi.EvaluateModelRes(evaluation_id=eval_id)

    def evaluation_status(self, req: tsi.EvaluationStatusReq) -> tsi.EvaluationStatusRes:
        # Mock implementation - always return completed
        return tsi.EvaluationStatusRes(status="completed")
