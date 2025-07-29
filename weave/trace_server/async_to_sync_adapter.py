"""
Adapter that wraps an async AsyncTraceServerInterface to provide sync interface.

This adapter uses asyncio.run() to run async operations synchronously,
providing backward compatibility for code that expects synchronous interfaces.
"""

import asyncio
import typing
from typing import Iterator

from . import trace_server_interface as tsi
from .async_trace_server_interface import AsyncTraceServerInterface


def _run_async(coro):
    """
    Run an async coroutine synchronously.
    
    Handles cases where there might already be a running event loop.
    """
    try:
        # Try to get the current event loop
        loop = asyncio.get_running_loop()
        if loop.is_running():
            # If we're already in an async context, we need to use a different approach
            # This is a more complex case that might require thread pools
            import concurrent.futures
            import threading
            
            def run_in_thread():
                # Create a new event loop in a separate thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
        else:
            # Loop exists but not running, use it
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(coro)


class AsyncToSyncAdapter(tsi.TraceServerInterface):
    """
    Adapter that wraps an async AsyncTraceServerInterface to provide sync interface.
    
    Uses asyncio.run() to run async operations synchronously for backward compatibility.
    """

    def __init__(self, async_server: AsyncTraceServerInterface):
        """
        Initialize the adapter with an async trace server.

        Args:
            async_server: The async trace server implementation to wrap.
        """
        self._async_server = async_server

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        """Non-async method passthrough."""
        return self._async_server.ensure_project_exists(entity, project)

    # OTEL API
    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        return _run_async(self._async_server.otel_export(req))

    # Call API
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        return _run_async(self._async_server.call_start(req))

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        return _run_async(self._async_server.call_end(req))

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        return _run_async(self._async_server.call_read(req))

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        return _run_async(self._async_server.calls_query(req))

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        """Convert async iterator to sync iterator."""
        async def _collect_items():
            items = []
            async for item in self._async_server.calls_query_stream(req):
                items.append(item)
            return items
        
        items = _run_async(_collect_items())
        return iter(items)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        return _run_async(self._async_server.calls_delete(req))

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        return _run_async(self._async_server.calls_query_stats(req))

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        return _run_async(self._async_server.call_update(req))

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        return _run_async(self._async_server.call_start_batch(req))

    # Op API
    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        return _run_async(self._async_server.op_create(req))

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        return _run_async(self._async_server.op_read(req))

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        return _run_async(self._async_server.ops_query(req))

    # Cost API
    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        return _run_async(self._async_server.cost_create(req))

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        return _run_async(self._async_server.cost_query(req))

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        return _run_async(self._async_server.cost_purge(req))

    # Obj API
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        return _run_async(self._async_server.obj_create(req))

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return _run_async(self._async_server.obj_read(req))

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        return _run_async(self._async_server.objs_query(req))

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        return _run_async(self._async_server.obj_delete(req))

    # Table API
    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        return _run_async(self._async_server.table_create(req))

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        return _run_async(self._async_server.table_update(req))

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return _run_async(self._async_server.table_query(req))

    def table_query_stream(self, req: tsi.TableQueryReq) -> Iterator[tsi.TableRowSchema]:
        """Convert async iterator to sync iterator."""
        async def _collect_items():
            items = []
            async for item in self._async_server.table_query_stream(req):
                items.append(item)
            return items
        
        items = _run_async(_collect_items())
        return iter(items)

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        return _run_async(self._async_server.table_query_stats(req))

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        return _run_async(self._async_server.table_query_stats_batch(req))

    # Ref API
    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return _run_async(self._async_server.refs_read_batch(req))

    # File API
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        return _run_async(self._async_server.file_create(req))

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        return _run_async(self._async_server.file_content_read(req))

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        return _run_async(self._async_server.files_stats(req))

    # Feedback API
    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        return _run_async(self._async_server.feedback_create(req))

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        return _run_async(self._async_server.feedback_query(req))

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        return _run_async(self._async_server.feedback_purge(req))

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        return _run_async(self._async_server.feedback_replace(req))

    # Action API
    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        return _run_async(self._async_server.actions_execute_batch(req))

    # Execute LLM API
    def completions_create(self, req: tsi.CompletionsCreateReq) -> tsi.CompletionsCreateRes:
        return _run_async(self._async_server.completions_create(req))

    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, typing.Any]]:
        """Convert async iterator to sync iterator."""
        async def _collect_items():
            items = []
            async for item in self._async_server.completions_create_stream(req):
                items.append(item)
            return items
        
        items = _run_async(_collect_items())
        return iter(items)

    # Project statistics API
    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        return _run_async(self._async_server.project_stats(req))

    # Thread API
    def threads_query_stream(self, req: tsi.ThreadsQueryReq) -> Iterator[tsi.ThreadSchema]:
        """Convert async iterator to sync iterator."""
        async def _collect_items():
            items = []
            async for item in self._async_server.threads_query_stream(req):
                items.append(item)
            return items
        
        items = _run_async(_collect_items())
        return iter(items)

    # Evaluation API
    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        return _run_async(self._async_server.evaluate_model(req))

    def evaluation_status(self, req: tsi.EvaluationStatusReq) -> tsi.EvaluationStatusRes:
        return _run_async(self._async_server.evaluation_status(req))

    # Context manager for batching
    def call_batch(self):
        """Forward to async server's call_batch method."""
        return self._async_server.call_batch()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return None 