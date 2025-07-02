import asyncio
from collections.abc import Coroutine, Iterator
from typing import Any

from weave.trace_server.async_trace_server_interface import AsyncTraceServerInterface
from weave.trace_server.trace_server_interface import (
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
    TableQueryStatsBatchReq,
    TableQueryStatsBatchRes,
    TableQueryStatsReq,
    TableQueryStatsRes,
    TableRowSchema,
    TableUpdateReq,
    TableUpdateRes,
)


def _run_async(coro: Coroutine[Any, Any, Any] | Any) -> Any:
    """Helper to run async coroutine from sync context.

    Handles both cases where there is an existing event loop and where there isn't.
    Also handles cases where the method might return a result directly instead of a coroutine.
    """
    # If it's not a coroutine, just return it directly
    if not asyncio.iscoroutine(coro):
        return coro

    try:
        # Check if we're already in an async context
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No event loop running, we can use asyncio.run
        return asyncio.run(coro)

    # We're in an async context, run in a new thread with its own event loop
    import concurrent.futures

    def run_in_thread() -> Any:
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_in_thread)
        return future.result()


class AsyncToSyncAdapter:
    """Adapter that wraps an async AsyncTraceServerInterface to provide sync methods.

    This allows async server implementations to be used in sync contexts
    like the existing WeaveClient.
    """

    def __init__(self, async_server: AsyncTraceServerInterface):
        self.async_server = async_server

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes:
        return _run_async(self.async_server.ensure_project_exists(entity, project))

    # OTEL API
    def otel_export(self, req: OtelExportReq) -> OtelExportRes:
        return _run_async(self.async_server.otel_export(req))

    # Call API
    def call_start(self, req: CallStartReq) -> CallStartRes:
        return _run_async(self.async_server.call_start(req))

    def call_end(self, req: CallEndReq) -> CallEndRes:
        return _run_async(self.async_server.call_end(req))

    def call_read(self, req: CallReadReq) -> CallReadRes:
        return _run_async(self.async_server.call_read(req))

    def calls_query(self, req: CallsQueryReq) -> CallsQueryRes:
        return _run_async(self.async_server.calls_query(req))

    def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]:
        return _run_async(self.async_server.calls_query_stream(req))

    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes:
        return _run_async(self.async_server.calls_delete(req))

    def calls_query_stats(self, req: CallsQueryStatsReq) -> CallsQueryStatsRes:
        return _run_async(self.async_server.calls_query_stats(req))

    def call_update(self, req: CallUpdateReq) -> CallUpdateRes:
        return _run_async(self.async_server.call_update(req))

    def call_start_batch(self, req: CallCreateBatchReq) -> CallCreateBatchRes:
        return _run_async(self.async_server.call_start_batch(req))

    # Op API
    def op_create(self, req: OpCreateReq) -> OpCreateRes:
        return _run_async(self.async_server.op_create(req))

    def op_read(self, req: OpReadReq) -> OpReadRes:
        return _run_async(self.async_server.op_read(req))

    def ops_query(self, req: OpQueryReq) -> OpQueryRes:
        return _run_async(self.async_server.ops_query(req))

    # Cost API
    def cost_create(self, req: CostCreateReq) -> CostCreateRes:
        return _run_async(self.async_server.cost_create(req))

    def cost_query(self, req: CostQueryReq) -> CostQueryRes:
        return _run_async(self.async_server.cost_query(req))

    def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes:
        return _run_async(self.async_server.cost_purge(req))

    # Obj API
    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes:
        return _run_async(self.async_server.obj_create(req))

    def obj_read(self, req: ObjReadReq) -> ObjReadRes:
        return _run_async(self.async_server.obj_read(req))

    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes:
        return _run_async(self.async_server.objs_query(req))

    def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes:
        return _run_async(self.async_server.obj_delete(req))

    # Table API
    def table_create(self, req: TableCreateReq) -> TableCreateRes:
        return _run_async(self.async_server.table_create(req))

    def table_update(self, req: TableUpdateReq) -> TableUpdateRes:
        return _run_async(self.async_server.table_update(req))

    def table_query(self, req: TableQueryReq) -> TableQueryRes:
        return _run_async(self.async_server.table_query(req))

    def table_query_stream(self, req: TableQueryReq) -> Iterator[TableRowSchema]:
        return _run_async(self.async_server.table_query_stream(req))

    def table_query_stats(self, req: TableQueryStatsReq) -> TableQueryStatsRes:
        return _run_async(self.async_server.table_query_stats(req))

    def table_query_stats_batch(
        self, req: TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchRes:
        return _run_async(self.async_server.table_query_stats_batch(req))

    # Ref API
    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes:
        return _run_async(self.async_server.refs_read_batch(req))

    # File API
    def file_create(self, req: FileCreateReq) -> FileCreateRes:
        return _run_async(self.async_server.file_create(req))

    def file_content_read(self, req: FileContentReadReq) -> FileContentReadRes:
        return _run_async(self.async_server.file_content_read(req))

    def files_stats(self, req: FilesStatsReq) -> FilesStatsRes:
        return _run_async(self.async_server.files_stats(req))

    # Feedback API
    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes:
        return _run_async(self.async_server.feedback_create(req))

    def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes:
        return _run_async(self.async_server.feedback_query(req))

    def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes:
        return _run_async(self.async_server.feedback_purge(req))

    def feedback_replace(self, req: FeedbackReplaceReq) -> FeedbackReplaceRes:
        return _run_async(self.async_server.feedback_replace(req))

    # Action API
    def actions_execute_batch(
        self, req: ActionsExecuteBatchReq
    ) -> ActionsExecuteBatchRes:
        return _run_async(self.async_server.actions_execute_batch(req))

    # Execute LLM API
    def completions_create(self, req: CompletionsCreateReq) -> CompletionsCreateRes:
        return _run_async(self.async_server.completions_create(req))

    def completions_create_stream(
        self, req: CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        return _run_async(self.async_server.completions_create_stream(req))

    # Project statistics API
    def project_stats(self, req: ProjectStatsReq) -> ProjectStatsRes:
        return _run_async(self.async_server.project_stats(req))
