"""
Adapter that wraps a synchronous TraceServerInterface to provide async interface.

This adapter uses asyncio.to_thread() to run blocking sync operations in a thread pool,
preventing them from blocking the main event loop in async contexts like FastAPI.
"""

import asyncio
import functools
import typing
from typing import AsyncIterator

from . import trace_server_interface as tsi
from .async_trace_server_interface import AsyncTraceServerInterface


class SyncToAsyncAdapter(AsyncTraceServerInterface):
    """
    Adapter that wraps a sync TraceServerInterface to provide async interface.
    
    Uses asyncio.to_thread() to run blocking operations in a thread pool.
    """

    def __init__(self, sync_server: tsi.TraceServerInterface):
        """
        Initialize the adapter with a synchronous trace server.

        Args:
            sync_server: The synchronous trace server implementation to wrap.
        """
        self._sync_server = sync_server

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        """Non-async method since it's typically fast and doesn't need async handling."""
        return self._sync_server.ensure_project_exists(entity, project)

    # OTEL API
    async def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        return await asyncio.to_thread(self._sync_server.otel_export, req)

    # Call API
    async def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        return await asyncio.to_thread(self._sync_server.call_start, req)

    async def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        return await asyncio.to_thread(self._sync_server.call_end, req)

    async def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        return await asyncio.to_thread(self._sync_server.call_read, req)

    async def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        return await asyncio.to_thread(self._sync_server.calls_query, req)

    async def calls_query_stream(self, req: tsi.CallsQueryReq) -> AsyncIterator[tsi.CallSchema]:
        """Convert sync iterator to async iterator."""
        def _get_sync_iterator():
            return self._sync_server.calls_query_stream(req)
        
        sync_iterator = await asyncio.to_thread(_get_sync_iterator)
        
        # Convert sync iterator to async iterator
        for item in sync_iterator:
            yield item
            # Yield control to allow other tasks to run
            await asyncio.sleep(0)

    async def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        return await asyncio.to_thread(self._sync_server.calls_delete, req)

    async def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        return await asyncio.to_thread(self._sync_server.calls_query_stats, req)

    async def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        return await asyncio.to_thread(self._sync_server.call_update, req)

    async def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        return await asyncio.to_thread(self._sync_server.call_start_batch, req)

    # Op API
    async def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        return await asyncio.to_thread(self._sync_server.op_create, req)

    async def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        return await asyncio.to_thread(self._sync_server.op_read, req)

    async def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        return await asyncio.to_thread(self._sync_server.ops_query, req)

    # Cost API
    async def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        return await asyncio.to_thread(self._sync_server.cost_create, req)

    async def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        return await asyncio.to_thread(self._sync_server.cost_query, req)

    async def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        return await asyncio.to_thread(self._sync_server.cost_purge, req)

    # Obj API
    async def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        return await asyncio.to_thread(self._sync_server.obj_create, req)

    async def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return await asyncio.to_thread(self._sync_server.obj_read, req)

    async def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        return await asyncio.to_thread(self._sync_server.objs_query, req)

    async def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        return await asyncio.to_thread(self._sync_server.obj_delete, req)

    # Table API
    async def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        return await asyncio.to_thread(self._sync_server.table_create, req)

    async def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        return await asyncio.to_thread(self._sync_server.table_update, req)

    async def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return await asyncio.to_thread(self._sync_server.table_query, req)

    async def table_query_stream(self, req: tsi.TableQueryReq) -> AsyncIterator[tsi.TableRowSchema]:
        """Convert sync iterator to async iterator."""
        def _get_sync_iterator():
            return self._sync_server.table_query_stream(req)
        
        sync_iterator = await asyncio.to_thread(_get_sync_iterator)
        
        # Convert sync iterator to async iterator
        for item in sync_iterator:
            yield item
            # Yield control to allow other tasks to run
            await asyncio.sleep(0)

    async def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        return await asyncio.to_thread(self._sync_server.table_query_stats, req)

    async def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        return await asyncio.to_thread(self._sync_server.table_query_stats_batch, req)

    # Ref API
    async def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return await asyncio.to_thread(self._sync_server.refs_read_batch, req)

    # File API
    async def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        return await asyncio.to_thread(self._sync_server.file_create, req)

    async def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        return await asyncio.to_thread(self._sync_server.file_content_read, req)

    async def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        return await asyncio.to_thread(self._sync_server.files_stats, req)

    # Feedback API
    async def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        return await asyncio.to_thread(self._sync_server.feedback_create, req)

    async def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        return await asyncio.to_thread(self._sync_server.feedback_query, req)

    async def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        return await asyncio.to_thread(self._sync_server.feedback_purge, req)

    async def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        return await asyncio.to_thread(self._sync_server.feedback_replace, req)

    # Action API
    async def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        return await asyncio.to_thread(self._sync_server.actions_execute_batch, req)

    # Execute LLM API
    async def completions_create(self, req: tsi.CompletionsCreateReq) -> tsi.CompletionsCreateRes:
        return await asyncio.to_thread(self._sync_server.completions_create, req)

    async def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> AsyncIterator[dict[str, typing.Any]]:
        """Convert sync iterator to async iterator."""
        def _get_sync_iterator():
            return self._sync_server.completions_create_stream(req)
        
        sync_iterator = await asyncio.to_thread(_get_sync_iterator)
        
        # Convert sync iterator to async iterator
        for item in sync_iterator:
            yield item
            # Yield control to allow other tasks to run
            await asyncio.sleep(0)

    # Project statistics API
    async def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        return await asyncio.to_thread(self._sync_server.project_stats, req)

    # Thread API
    async def threads_query_stream(self, req: tsi.ThreadsQueryReq) -> AsyncIterator[tsi.ThreadSchema]:
        """Convert sync iterator to async iterator."""
        def _get_sync_iterator():
            return self._sync_server.threads_query_stream(req)
        
        sync_iterator = await asyncio.to_thread(_get_sync_iterator)
        
        # Convert sync iterator to async iterator
        for item in sync_iterator:
            yield item
            # Yield control to allow other tasks to run
            await asyncio.sleep(0)

    # Evaluation API
    async def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        return await asyncio.to_thread(self._sync_server.evaluate_model, req)

    async def evaluation_status(self, req: tsi.EvaluationStatusReq) -> tsi.EvaluationStatusRes:
        return await asyncio.to_thread(self._sync_server.evaluation_status, req)

    # Context manager for batching
    def call_batch(self):
        """Forward to sync server's call_batch method."""
        return self._sync_server.call_batch()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return None 