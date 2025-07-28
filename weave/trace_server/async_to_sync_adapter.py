import asyncio
from collections.abc import Iterator
from typing import Any

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


class AsyncToSyncAdapter(TraceServerInterface):
    """
    Adapter that wraps an async AsyncTraceServerInterface to provide sync interface.
    
    All async methods are executed using asyncio.run to block until completion.
    """

    def __init__(self, async_server: AsyncTraceServerInterface):
        """
        Initialize the adapter.
        
        Args:
            async_server: The async server to wrap
        """
        self._async_server = async_server

    def _run_async(self, coro):
        """Run an async coroutine synchronously."""
        return asyncio.run(coro)

    def _sync_iterator_from_async(self, async_iterator):
        """Convert an async iterator to a sync iterator."""
        async def collect_items():
            items = []
            async for item in async_iterator:
                items.append(item)
            return items
        
        items = self._run_async(collect_items())
        return iter(items)

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes:
        return self._run_async(
            self._async_server.ensure_project_exists(entity, project)
        )

    # OTEL API
    def otel_export(self, req: OtelExportReq) -> OtelExportRes:
        return self._run_async(self._async_server.otel_export(req))

    # Call API
    def call_start(self, req: CallStartReq) -> CallStartRes:
        return self._run_async(self._async_server.call_start(req))

    def call_end(self, req: CallEndReq) -> CallEndRes:
        return self._run_async(self._async_server.call_end(req))

    def call_read(self, req: CallReadReq) -> CallReadRes:
        return self._run_async(self._async_server.call_read(req))

    def calls_query(self, req: CallsQueryReq) -> CallsQueryRes:
        return self._run_async(self._async_server.calls_query(req))

    def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]:
        async_iterator = self._run_async(self._async_server.calls_query_stream(req))
        return self._sync_iterator_from_async(async_iterator)

    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes:
        return self._run_async(self._async_server.calls_delete(req))

    def calls_query_stats(self, req: CallsQueryStatsReq) -> CallsQueryStatsRes:
        return self._run_async(self._async_server.calls_query_stats(req))

    def call_update(self, req: CallUpdateReq) -> CallUpdateRes:
        return self._run_async(self._async_server.call_update(req))

    def call_start_batch(self, req: CallCreateBatchReq) -> CallCreateBatchRes:
        return self._run_async(self._async_server.call_start_batch(req))

    # Op API
    def op_create(self, req: OpCreateReq) -> OpCreateRes:
        return self._run_async(self._async_server.op_create(req))

    def op_read(self, req: OpReadReq) -> OpReadRes:
        return self._run_async(self._async_server.op_read(req))

    def ops_query(self, req: OpQueryReq) -> OpQueryRes:
        return self._run_async(self._async_server.ops_query(req))

    # Cost API
    def cost_create(self, req: CostCreateReq) -> CostCreateRes:
        return self._run_async(self._async_server.cost_create(req))

    def cost_query(self, req: CostQueryReq) -> CostQueryRes:
        return self._run_async(self._async_server.cost_query(req))

    def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes:
        return self._run_async(self._async_server.cost_purge(req))

    # Obj API
    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes:
        return self._run_async(self._async_server.obj_create(req))

    def obj_read(self, req: ObjReadReq) -> ObjReadRes:
        return self._run_async(self._async_server.obj_read(req))

    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes:
        return self._run_async(self._async_server.objs_query(req))

    def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes:
        return self._run_async(self._async_server.obj_delete(req))

    # Table API
    def table_create(self, req: TableCreateReq) -> TableCreateRes:
        return self._run_async(self._async_server.table_create(req))

    def table_update(self, req: TableUpdateReq) -> TableUpdateRes:
        return self._run_async(self._async_server.table_update(req))

    def table_query(self, req: TableQueryReq) -> TableQueryRes:
        return self._run_async(self._async_server.table_query(req))

    def table_query_stream(self, req: TableQueryReq) -> Iterator[TableRowSchema]:
        async_iterator = self._run_async(self._async_server.table_query_stream(req))
        return self._sync_iterator_from_async(async_iterator)

    def table_query_stats(self, req: TableQueryStatsReq) -> TableQueryStatsRes:
        return self._run_async(self._async_server.table_query_stats(req))

    def table_query_stats_batch(
        self, req: TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchRes:
        return self._run_async(self._async_server.table_query_stats_batch(req))

    # Ref API
    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes:
        return self._run_async(self._async_server.refs_read_batch(req))

    # File API
    def file_create(self, req: FileCreateReq) -> FileCreateRes:
        return self._run_async(self._async_server.file_create(req))

    def file_content_read(self, req: FileContentReadReq) -> FileContentReadRes:
        return self._run_async(self._async_server.file_content_read(req))

    def files_stats(self, req: FilesStatsReq) -> FilesStatsRes:
        return self._run_async(self._async_server.files_stats(req))

    # Feedback API
    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes:
        return self._run_async(self._async_server.feedback_create(req))

    def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes:
        return self._run_async(self._async_server.feedback_query(req))

    def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes:
        return self._run_async(self._async_server.feedback_purge(req))

    def feedback_replace(self, req: FeedbackReplaceReq) -> FeedbackReplaceRes:
        return self._run_async(self._async_server.feedback_replace(req))

    # Action API
    def actions_execute_batch(
        self, req: ActionsExecuteBatchReq
    ) -> ActionsExecuteBatchRes:
        return self._run_async(self._async_server.actions_execute_batch(req))

    # Execute LLM API
    def completions_create(self, req: CompletionsCreateReq) -> CompletionsCreateRes:
        return self._run_async(self._async_server.completions_create(req))

    # Execute LLM API (Streaming)
    def completions_create_stream(
        self, req: CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        async_iterator = self._run_async(self._async_server.completions_create_stream(req))
        return self._sync_iterator_from_async(async_iterator)

    # Project statistics API
    def project_stats(self, req: ProjectStatsReq) -> ProjectStatsRes:
        return self._run_async(self._async_server.project_stats(req))

    # Thread API
    def threads_query_stream(self, req: ThreadsQueryReq) -> Iterator[ThreadSchema]:
        async_iterator = self._run_async(self._async_server.threads_query_stream(req))
        return self._sync_iterator_from_async(async_iterator)

    # Evaluation API
    def evaluate_model(self, req: EvaluateModelReq) -> EvaluateModelRes:
        return self._run_async(self._async_server.evaluate_model(req))

    def evaluation_status(self, req: EvaluationStatusReq) -> EvaluationStatusRes:
        return self._run_async(self._async_server.evaluation_status(req))
