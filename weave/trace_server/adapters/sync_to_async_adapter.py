import asyncio
from collections.abc import Iterator
from typing import Any

from weave.trace_server.async_trace_server_interface import AsyncTraceServerInterface
from weave.trace_server.trace_server_interface import (
    ActionsExecuteBatchReq,
    ActionsExecuteBatchRes,
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
    CallCreateBatchReq,
    CallCreateBatchRes,
    CompletionsCreateReq,
    CompletionsCreateRes,
    CostCreateReq,
    CostCreateRes,
    CostPurgeReq,
    CostPurgeRes,
    CostQueryReq,
    CostQueryRes,
    EnsureProjectExistsRes,
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
    TraceServerInterface,
)


class SyncToAsyncAdapter:
    """Adapter that wraps a sync TraceServerInterface to provide async methods.
    
    This allows existing sync server implementations to be used in async contexts
    by running them in a thread pool executor.
    """

    def __init__(self, sync_server: TraceServerInterface):
        self.sync_server = sync_server

    async def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.sync_server.ensure_project_exists, entity, project
        )

    # OTEL API
    async def otel_export(self, req: OtelExportReq) -> OtelExportRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.otel_export, req)

    # Call API
    async def call_start(self, req: CallStartReq) -> CallStartRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.call_start, req)

    async def call_end(self, req: CallEndReq) -> CallEndRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.call_end, req)

    async def call_read(self, req: CallReadReq) -> CallReadRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.call_read, req)

    async def calls_query(self, req: CallsQueryReq) -> CallsQueryRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.calls_query, req)

    async def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]:
        # Note: This is tricky for streaming. For now, we'll execute in thread pool
        # and return the iterator. In a real implementation, you might want to
        # convert this to an async generator.
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.calls_query_stream, req)

    async def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.calls_delete, req)

    async def calls_query_stats(self, req: CallsQueryStatsReq) -> CallsQueryStatsRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.calls_query_stats, req)

    async def call_update(self, req: CallUpdateReq) -> CallUpdateRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.call_update, req)

    async def call_start_batch(self, req: CallCreateBatchReq) -> CallCreateBatchRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.call_start_batch, req)

    # Op API
    async def op_create(self, req: OpCreateReq) -> OpCreateRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.op_create, req)

    async def op_read(self, req: OpReadReq) -> OpReadRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.op_read, req)

    async def ops_query(self, req: OpQueryReq) -> OpQueryRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.ops_query, req)

    # Cost API
    async def cost_create(self, req: CostCreateReq) -> CostCreateRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.cost_create, req)

    async def cost_query(self, req: CostQueryReq) -> CostQueryRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.cost_query, req)

    async def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.cost_purge, req)

    # Obj API
    async def obj_create(self, req: ObjCreateReq) -> ObjCreateRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.obj_create, req)

    async def obj_read(self, req: ObjReadReq) -> ObjReadRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.obj_read, req)

    async def objs_query(self, req: ObjQueryReq) -> ObjQueryRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.objs_query, req)

    async def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.obj_delete, req)

    # Table API
    async def table_create(self, req: TableCreateReq) -> TableCreateRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.table_create, req)

    async def table_update(self, req: TableUpdateReq) -> TableUpdateRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.table_update, req)

    async def table_query(self, req: TableQueryReq) -> TableQueryRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.table_query, req)

    async def table_query_stream(self, req: TableQueryReq) -> Iterator[TableRowSchema]:
        # Note: Same caveat as calls_query_stream for streaming operations
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.table_query_stream, req)

    async def table_query_stats(self, req: TableQueryStatsReq) -> TableQueryStatsRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.table_query_stats, req)

    async def table_query_stats_batch(
        self, req: TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.table_query_stats_batch, req)

    # Ref API
    async def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.refs_read_batch, req)

    # File API
    async def file_create(self, req: FileCreateReq) -> FileCreateRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.file_create, req)

    async def file_content_read(self, req: FileContentReadReq) -> FileContentReadRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.file_content_read, req)

    async def files_stats(self, req: FilesStatsReq) -> FilesStatsRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.files_stats, req)

    # Feedback API
    async def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.feedback_create, req)

    async def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.feedback_query, req)

    async def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.feedback_purge, req)

    async def feedback_replace(self, req: FeedbackReplaceReq) -> FeedbackReplaceRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.feedback_replace, req)

    # Action API
    async def actions_execute_batch(
        self, req: ActionsExecuteBatchReq
    ) -> ActionsExecuteBatchRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.actions_execute_batch, req)

    # Execute LLM API
    async def completions_create(self, req: CompletionsCreateReq) -> CompletionsCreateRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.completions_create, req)

    async def completions_create_stream(
        self, req: CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        # Note: Same caveat as other streaming operations
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.completions_create_stream, req)

    # Project statistics API
    async def project_stats(self, req: ProjectStatsReq) -> ProjectStatsRes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_server.project_stats, req)