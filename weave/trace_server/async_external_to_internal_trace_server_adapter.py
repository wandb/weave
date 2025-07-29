"""
Async version of external_to_internal_trace_server_adapter.

This adapter handles ID and reference conversions for async trace servers,
providing the same functionality as the sync version but with async methods.
"""

import typing
from collections.abc import AsyncIterator
from typing import Callable, TypeVar

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.async_trace_server_interface import AsyncTraceServerInterface
from weave.trace_server.external_to_internal_trace_server_adapter import IdConverter
from weave.trace_server.trace_server_converter import (
    universal_ext_to_int_ref_converter,
    universal_int_to_ext_ref_converter,
)

A = TypeVar("A")
B = TypeVar("B")


class AsyncExternalTraceServer(AsyncTraceServerInterface):
    """
    Async version of ExternalTraceServer.
    
    Used to adapt the internal async trace server to the external async trace server.
    This is done by converting the project_id, run_id, and user_id to their
    internal representations before calling the internal trace server and
    converting them back to their external representations before returning
    them to the caller. Additionally, we convert references to their internal
    representations before calling the internal trace server and convert them
    back to their external representations before returning them to the caller.
    """

    _internal_trace_server: AsyncTraceServerInterface
    _idc: IdConverter

    def __init__(
        self, internal_trace_server: AsyncTraceServerInterface, id_converter: IdConverter
    ):
        """
        Initialize the async external trace server adapter.

        Args:
            internal_trace_server: The internal async trace server implementation.
            id_converter: The ID converter for project, run, and user ID translations.
        """
        self._internal_trace_server = internal_trace_server
        self._idc = id_converter

    def __getattr__(self, name: str) -> typing.Any:
        return getattr(self._internal_trace_server, name)

    async def _ref_apply(self, method: Callable[[A], typing.Awaitable[B]], req: A) -> B:
        """Apply reference conversion to async method calls."""
        req_conv = universal_ext_to_int_ref_converter(
            req, self._idc.ext_to_int_project_id
        )
        res = await method(req_conv)
        res_conv = universal_int_to_ext_ref_converter(
            res, self._idc.int_to_ext_project_id
        )
        return res_conv

    async def _stream_ref_apply(
        self, method: Callable[[A], AsyncIterator[B]], req: A
    ) -> AsyncIterator[B]:
        """Apply reference conversion to async streaming method calls."""
        req_conv = universal_ext_to_int_ref_converter(
            req, self._idc.ext_to_int_project_id
        )
        res = method(req_conv)

        int_to_ext_project_cache = {}

        def cached_int_to_ext_project_id(project_id: str) -> typing.Optional[str]:
            if project_id not in int_to_ext_project_cache:
                int_to_ext_project_cache[project_id] = self._idc.int_to_ext_project_id(
                    project_id
                )
            return int_to_ext_project_cache[project_id]

        async for item in res:
            yield universal_int_to_ext_ref_converter(item, cached_int_to_ext_project_id)

    # Standard API Below:
    def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        """Non-async method passthrough."""
        return self._internal_trace_server.ensure_project_exists(entity, project)

    async def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return await self._ref_apply(self._internal_trace_server.otel_export, req)

    async def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        req.start.project_id = self._idc.ext_to_int_project_id(req.start.project_id)
        if req.start.wb_run_id is not None:
            req.start.wb_run_id = self._idc.ext_to_int_run_id(req.start.wb_run_id)
        if req.start.wb_user_id is not None:
            req.start.wb_user_id = self._idc.ext_to_int_user_id(req.start.wb_user_id)
        return await self._ref_apply(self._internal_trace_server.call_start, req)

    async def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        req.end.project_id = self._idc.ext_to_int_project_id(req.end.project_id)
        return await self._ref_apply(self._internal_trace_server.call_end, req)

    async def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = await self._ref_apply(self._internal_trace_server.call_read, req)
        if res.call is None:
            return res
        if res.call.project_id != req.project_id:
            raise ValueError("Internal Error - Project Mismatch")
        res.call.project_id = original_project_id
        if res.call.wb_run_id is not None:
            res.call.wb_run_id = self._idc.int_to_ext_run_id(res.call.wb_run_id)
        if res.call.wb_user_id is not None:
            res.call.wb_user_id = self._idc.int_to_ext_user_id(res.call.wb_user_id)
        return res

    async def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        if req.filter is not None:
            if req.filter.wb_run_ids is not None:
                req.filter.wb_run_ids = [
                    self._idc.ext_to_int_run_id(run_id)
                    for run_id in req.filter.wb_run_ids
                ]
            if req.filter.wb_user_ids is not None:
                req.filter.wb_user_ids = [
                    self._idc.ext_to_int_user_id(user_id)
                    for user_id in req.filter.wb_user_ids
                ]

        res = await self._ref_apply(self._internal_trace_server.calls_query, req)
        for call in res.calls:
            call.project_id = original_project_id
            if call.wb_run_id is not None:
                call.wb_run_id = self._idc.int_to_ext_run_id(call.wb_run_id)
            if call.wb_user_id is not None:
                call.wb_user_id = self._idc.int_to_ext_user_id(call.wb_user_id)
        return res

    async def calls_query_stream(self, req: tsi.CallsQueryReq) -> AsyncIterator[tsi.CallSchema]:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        if req.filter is not None:
            if req.filter.wb_run_ids is not None:
                req.filter.wb_run_ids = [
                    self._idc.ext_to_int_run_id(run_id)
                    for run_id in req.filter.wb_run_ids
                ]
            if req.filter.wb_user_ids is not None:
                req.filter.wb_user_ids = [
                    self._idc.ext_to_int_user_id(user_id)
                    for user_id in req.filter.wb_user_ids
                ]

        async for call in self._stream_ref_apply(self._internal_trace_server.calls_query_stream, req):
            call.project_id = original_project_id
            if call.wb_run_id is not None:
                call.wb_run_id = self._idc.int_to_ext_run_id(call.wb_run_id)
            if call.wb_user_id is not None:
                call.wb_user_id = self._idc.int_to_ext_user_id(call.wb_user_id)
            yield call

    async def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return await self._internal_trace_server.calls_delete(req)

    async def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.filter is not None:
            if req.filter.wb_run_ids is not None:
                req.filter.wb_run_ids = [
                    self._idc.ext_to_int_run_id(run_id)
                    for run_id in req.filter.wb_run_ids
                ]
            if req.filter.wb_user_ids is not None:
                req.filter.wb_user_ids = [
                    self._idc.ext_to_int_user_id(user_id)
                    for user_id in req.filter.wb_user_ids
                ]
        return await self._internal_trace_server.calls_query_stats(req)

    async def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return await self._ref_apply(self._internal_trace_server.call_update, req)

    async def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        # Handle batch processing with ID conversions
        for item in req.batch:
            if item.mode == "start":
                item.req.start.project_id = self._idc.ext_to_int_project_id(item.req.start.project_id)
                if item.req.start.wb_run_id is not None:
                    item.req.start.wb_run_id = self._idc.ext_to_int_run_id(item.req.start.wb_run_id)
                if item.req.start.wb_user_id is not None:
                    item.req.start.wb_user_id = self._idc.ext_to_int_user_id(item.req.start.wb_user_id)
            elif item.mode == "end":
                item.req.end.project_id = self._idc.ext_to_int_project_id(item.req.end.project_id)
        
        return await self._ref_apply(self._internal_trace_server.call_start_batch, req)

    # Op API - placeholder implementations
    async def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        return await self._ref_apply(self._internal_trace_server.op_create, req)

    async def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        return await self._ref_apply(self._internal_trace_server.op_read, req)

    async def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        return await self._ref_apply(self._internal_trace_server.ops_query, req)

    # Cost API
    async def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return await self._internal_trace_server.cost_create(req)

    async def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._internal_trace_server.cost_query(req)

    async def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._internal_trace_server.cost_purge(req)

    # Obj API
    async def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        req.obj.project_id = self._idc.ext_to_int_project_id(req.obj.project_id)
        if req.obj.wb_user_id is not None:
            req.obj.wb_user_id = self._idc.ext_to_int_user_id(req.obj.wb_user_id)
        return await self._ref_apply(self._internal_trace_server.obj_create, req)

    async def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._ref_apply(self._internal_trace_server.obj_read, req)

    async def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._ref_apply(self._internal_trace_server.objs_query, req)

    async def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._internal_trace_server.obj_delete(req)

    # Table API
    async def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        req.table.project_id = self._idc.ext_to_int_project_id(req.table.project_id)
        return await self._ref_apply(self._internal_trace_server.table_create, req)

    async def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._ref_apply(self._internal_trace_server.table_update, req)

    async def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._ref_apply(self._internal_trace_server.table_query, req)

    async def table_query_stream(self, req: tsi.TableQueryReq) -> AsyncIterator[tsi.TableRowSchema]:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        async for item in self._stream_ref_apply(self._internal_trace_server.table_query_stream, req):
            yield item

    async def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._internal_trace_server.table_query_stats(req)

    async def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._internal_trace_server.table_query_stats_batch(req)

    # Ref API
    async def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return await self._ref_apply(self._internal_trace_server.refs_read_batch, req)

    # File API
    async def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._internal_trace_server.file_create(req)

    async def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._internal_trace_server.file_content_read(req)

    async def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._internal_trace_server.files_stats(req)

    # Feedback API
    async def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return await self._internal_trace_server.feedback_create(req)

    async def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._internal_trace_server.feedback_query(req)

    async def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._internal_trace_server.feedback_purge(req)

    async def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return await self._internal_trace_server.feedback_replace(req)

    # Action API
    async def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return await self._ref_apply(self._internal_trace_server.actions_execute_batch, req)

    # Execute LLM API
    async def completions_create(self, req: tsi.CompletionsCreateReq) -> tsi.CompletionsCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return await self._internal_trace_server.completions_create(req)

    async def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> AsyncIterator[dict[str, typing.Any]]:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        async for item in self._internal_trace_server.completions_create_stream(req):
            yield item

    # Project statistics API
    async def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._internal_trace_server.project_stats(req)

    # Thread API
    async def threads_query_stream(self, req: tsi.ThreadsQueryReq) -> AsyncIterator[tsi.ThreadSchema]:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        async for item in self._internal_trace_server.threads_query_stream(req):
            yield item

    # Evaluation API
    async def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        return await self._internal_trace_server.evaluate_model(req)

    async def evaluation_status(self, req: tsi.EvaluationStatusReq) -> tsi.EvaluationStatusRes:
        return await self._internal_trace_server.evaluation_status(req)

    # Context manager for batching
    def call_batch(self):
        """Forward to internal server's call_batch method."""
        return self._internal_trace_server.call_batch()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return None
