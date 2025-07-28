import asyncio
from collections.abc import AsyncGenerator
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import Any, Optional

from .async_trace_server_interface import AsyncTraceServerInterface
from .trace_server_interface import (
    ActionsExecuteBatchReq,
    ActionsExecuteBatchRes,
    CallCreateBatchReq,
    CallCreateBatchRes,
    CallEndReq,
    CallEndRes,
    CallReadReq,
    CallReadRes,
    CallSchema,
    CallsDeleteReq,
    CallsDeleteRes,
    CallsQueryReq,
    CallsQueryRes,
    CallsQueryStatsReq,
    CallsQueryStatsRes,
    CallStartReq,
    CallStartRes,
    CallUpdateReq,
    CallUpdateRes,
    CompletionsCreateReq,
    CompletionsCreateRes,
    CostCreateReq,
    CostCreateRes,
    CostPurgeReq,
    CostPurgeRes,
    CostQueryReq,
    CostQueryRes,
    EnsureProjectExistsRes,
    EvaluateModelReq,
    EvaluateModelRes,
    EvaluationStatusReq,
    EvaluationStatusRes,
    FeedbackCreateReq,
    FeedbackCreateRes,
    FeedbackPurgeReq,
    FeedbackPurgeRes,
    FeedbackQueryReq,
    FeedbackQueryRes,
    FeedbackReplaceReq,
    FeedbackReplaceRes,
    FileContentReadReq,
    FileContentReadRes,
    FileCreateReq,
    FileCreateRes,
    FilesStatsReq,
    FilesStatsRes,
    ObjCreateReq,
    ObjCreateRes,
    ObjDeleteReq,
    ObjDeleteRes,
    ObjQueryReq,
    ObjQueryRes,
    ObjReadReq,
    ObjReadRes,
    OpCreateReq,
    OpCreateRes,
    OpQueryReq,
    OpQueryRes,
    OpReadReq,
    OpReadRes,
    OtelExportReq,
    OtelExportRes,
    ProjectStatsReq,
    ProjectStatsRes,
    RefsReadBatchReq,
    RefsReadBatchRes,
    TableCreateReq,
    TableCreateRes,
    TableQueryReq,
    TableQueryRes,
    TableQueryStatsReq,
    TableQueryStatsRes,
    TableQueryStatsBatchReq,
    TableQueryStatsBatchRes,
    TableRowSchema,
    TableUpdateReq,
    TableUpdateRes,
    ThreadSchema,
    ThreadsQueryReq,
    TraceServerInterface,
)


class SyncToAsyncAdapter(AsyncTraceServerInterface):
    """
    Adapter that wraps a sync TraceServerInterface to provide async interface.
    
    All sync methods are executed in a ThreadPoolExecutor to avoid blocking
    the async event loop.
    """

    def __init__(
        self, sync_server: TraceServerInterface, executor: Optional[Executor] = None
    ):
        """
        Initialize the adapter.
        
        Args:
            sync_server: The sync server to wrap
            executor: Optional executor, defaults to ThreadPoolExecutor
        """
        self._sync_server = sync_server
        self._executor = executor or ThreadPoolExecutor()

    async def _run_in_executor(self, func, *args):
        """Run a sync function in the executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func, *args)

    async def _async_iterator_from_sync(self, sync_iterator):
        """Convert a sync iterator to an async iterator."""
        loop = asyncio.get_event_loop()
        
        def get_next_item():
            try:
                return next(sync_iterator)
            except StopIteration:
                return StopIteration
        
        while True:
            item = await loop.run_in_executor(self._executor, get_next_item)
            if item is StopIteration:
                break
            yield item

    async def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes:
        return await self._run_in_executor(
            self._sync_server.ensure_project_exists, entity, project
        )

    # OTEL API
    async def otel_export(self, req: OtelExportReq) -> OtelExportRes:
        return await self._run_in_executor(self._sync_server.otel_export, req)

    # Call API
    async def call_start(self, req: CallStartReq) -> CallStartRes:
        return await self._run_in_executor(self._sync_server.call_start, req)

    async def call_end(self, req: CallEndReq) -> CallEndRes:
        return await self._run_in_executor(self._sync_server.call_end, req)

    async def call_read(self, req: CallReadReq) -> CallReadRes:
        return await self._run_in_executor(self._sync_server.call_read, req)

    async def calls_query(self, req: CallsQueryReq) -> CallsQueryRes:
        return await self._run_in_executor(self._sync_server.calls_query, req)

    async def calls_query_stream(self, req: CallsQueryReq) -> AsyncGenerator[CallSchema]:
        sync_iterator = await self._run_in_executor(
            self._sync_server.calls_query_stream, req
        )
        async for item in self._async_iterator_from_sync(sync_iterator):
            yield item

    async def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes:
        return await self._run_in_executor(self._sync_server.calls_delete, req)

    async def calls_query_stats(self, req: CallsQueryStatsReq) -> CallsQueryStatsRes:
        return await self._run_in_executor(self._sync_server.calls_query_stats, req)

    async def call_update(self, req: CallUpdateReq) -> CallUpdateRes:
        return await self._run_in_executor(self._sync_server.call_update, req)

    async def call_start_batch(self, req: CallCreateBatchReq) -> CallCreateBatchRes:
        return await self._run_in_executor(self._sync_server.call_start_batch, req)

    # Op API
    async def op_create(self, req: OpCreateReq) -> OpCreateRes:
        return await self._run_in_executor(self._sync_server.op_create, req)

    async def op_read(self, req: OpReadReq) -> OpReadRes:
        return await self._run_in_executor(self._sync_server.op_read, req)

    async def ops_query(self, req: OpQueryReq) -> OpQueryRes:
        return await self._run_in_executor(self._sync_server.ops_query, req)

    # Cost API
    async def cost_create(self, req: CostCreateReq) -> CostCreateRes:
        return await self._run_in_executor(self._sync_server.cost_create, req)

    async def cost_query(self, req: CostQueryReq) -> CostQueryRes:
        return await self._run_in_executor(self._sync_server.cost_query, req)

    async def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes:
        return await self._run_in_executor(self._sync_server.cost_purge, req)

    # Obj API
    async def obj_create(self, req: ObjCreateReq) -> ObjCreateRes:
        return await self._run_in_executor(self._sync_server.obj_create, req)

    async def obj_read(self, req: ObjReadReq) -> ObjReadRes:
        return await self._run_in_executor(self._sync_server.obj_read, req)

    async def objs_query(self, req: ObjQueryReq) -> ObjQueryRes:
        return await self._run_in_executor(self._sync_server.objs_query, req)

    async def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes:
        return await self._run_in_executor(self._sync_server.obj_delete, req)

    # Table API
    async def table_create(self, req: TableCreateReq) -> TableCreateRes:
        return await self._run_in_executor(self._sync_server.table_create, req)

    async def table_update(self, req: TableUpdateReq) -> TableUpdateRes:
        return await self._run_in_executor(self._sync_server.table_update, req)

    async def table_query(self, req: TableQueryReq) -> TableQueryRes:
        return await self._run_in_executor(self._sync_server.table_query, req)

    async def table_query_stream(self, req: TableQueryReq) -> AsyncGenerator[TableRowSchema]:
        sync_iterator = await self._run_in_executor(
            self._sync_server.table_query_stream, req
        )
        async for item in self._async_iterator_from_sync(sync_iterator):
            yield item

    async def table_query_stats(self, req: TableQueryStatsReq) -> TableQueryStatsRes:
        return await self._run_in_executor(self._sync_server.table_query_stats, req)

    async def table_query_stats_batch(
        self, req: TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchRes:
        return await self._run_in_executor(
            self._sync_server.table_query_stats_batch, req
        )

    # Ref API
    async def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes:
        return await self._run_in_executor(self._sync_server.refs_read_batch, req)

    # File API
    async def file_create(self, req: FileCreateReq) -> FileCreateRes:
        return await self._run_in_executor(self._sync_server.file_create, req)

    async def file_content_read(self, req: FileContentReadReq) -> FileContentReadRes:
        return await self._run_in_executor(self._sync_server.file_content_read, req)

    async def files_stats(self, req: FilesStatsReq) -> FilesStatsRes:
        return await self._run_in_executor(self._sync_server.files_stats, req)

    # Feedback API
    async def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes:
        return await self._run_in_executor(self._sync_server.feedback_create, req)

    async def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes:
        return await self._run_in_executor(self._sync_server.feedback_query, req)

    async def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes:
        return await self._run_in_executor(self._sync_server.feedback_purge, req)

    async def feedback_replace(self, req: FeedbackReplaceReq) -> FeedbackReplaceRes:
        return await self._run_in_executor(self._sync_server.feedback_replace, req)

    # Action API
    async def actions_execute_batch(
        self, req: ActionsExecuteBatchReq
    ) -> ActionsExecuteBatchRes:
        return await self._run_in_executor(self._sync_server.actions_execute_batch, req)

    # Execute LLM API
    async def completions_create(self, req: CompletionsCreateReq) -> CompletionsCreateRes:
        return await self._run_in_executor(self._sync_server.completions_create, req)

    # Execute LLM API (Streaming)
    async def completions_create_stream(
        self, req: CompletionsCreateReq
    ) -> AsyncGenerator[dict[str, Any]]:
        sync_iterator = await self._run_in_executor(
            self._sync_server.completions_create_stream, req
        )
        async for item in self._async_iterator_from_sync(sync_iterator):
            yield item

    # Project statistics API
    async def project_stats(self, req: ProjectStatsReq) -> ProjectStatsRes:
        return await self._run_in_executor(self._sync_server.project_stats, req)

    # Thread API
    async def threads_query_stream(self, req: ThreadsQueryReq) -> AsyncGenerator[ThreadSchema]:
        sync_iterator = await self._run_in_executor(
            self._sync_server.threads_query_stream, req
        )
        async for item in self._async_iterator_from_sync(sync_iterator):
            yield item

    # Evaluation API
    async def evaluate_model(self, req: EvaluateModelReq) -> EvaluateModelRes:
        return await self._run_in_executor(self._sync_server.evaluate_model, req)

    async def evaluation_status(self, req: EvaluationStatusReq) -> EvaluationStatusRes:
        return await self._run_in_executor(self._sync_server.evaluation_status, req)
