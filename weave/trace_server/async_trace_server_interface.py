from collections.abc import Iterator
from typing import Any, Protocol

# Import all the request/response types from the sync interface
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


class AsyncTraceServerInterface(Protocol):
    """Async version of TraceServerInterface.

    This protocol defines the same interface as TraceServerInterface but with
    async methods. It can be used for FastAPI endpoints that need to be async
    for better performance.
    """

    async def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes: ...

    # OTEL API
    async def otel_export(self, req: OtelExportReq) -> OtelExportRes: ...

    # Call API
    async def call_start(self, req: CallStartReq) -> CallStartRes: ...
    async def call_end(self, req: CallEndReq) -> CallEndRes: ...
    async def call_read(self, req: CallReadReq) -> CallReadRes: ...
    async def calls_query(self, req: CallsQueryReq) -> CallsQueryRes: ...
    async def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]: ...
    async def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes: ...
    async def calls_query_stats(
        self, req: CallsQueryStatsReq
    ) -> CallsQueryStatsRes: ...
    async def call_update(self, req: CallUpdateReq) -> CallUpdateRes: ...
    async def call_start_batch(self, req: CallCreateBatchReq) -> CallCreateBatchRes: ...

    # Op API
    async def op_create(self, req: OpCreateReq) -> OpCreateRes: ...
    async def op_read(self, req: OpReadReq) -> OpReadRes: ...
    async def ops_query(self, req: OpQueryReq) -> OpQueryRes: ...

    # Cost API
    async def cost_create(self, req: CostCreateReq) -> CostCreateRes: ...
    async def cost_query(self, req: CostQueryReq) -> CostQueryRes: ...
    async def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes: ...

    # Obj API
    async def obj_create(self, req: ObjCreateReq) -> ObjCreateRes: ...
    async def obj_read(self, req: ObjReadReq) -> ObjReadRes: ...
    async def objs_query(self, req: ObjQueryReq) -> ObjQueryRes: ...
    async def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes: ...

    # Table API
    async def table_create(self, req: TableCreateReq) -> TableCreateRes: ...
    async def table_update(self, req: TableUpdateReq) -> TableUpdateRes: ...
    async def table_query(self, req: TableQueryReq) -> TableQueryRes: ...
    async def table_query_stream(
        self, req: TableQueryReq
    ) -> Iterator[TableRowSchema]: ...
    async def table_query_stats(
        self, req: TableQueryStatsReq
    ) -> TableQueryStatsRes: ...
    async def table_query_stats_batch(
        self, req: TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchRes: ...

    # Ref API
    async def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes: ...

    # File API
    async def file_create(self, req: FileCreateReq) -> FileCreateRes: ...
    async def file_content_read(
        self, req: FileContentReadReq
    ) -> FileContentReadRes: ...
    async def files_stats(self, req: FilesStatsReq) -> FilesStatsRes: ...

    # Feedback API
    async def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes: ...
    async def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes: ...
    async def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes: ...
    async def feedback_replace(self, req: FeedbackReplaceReq) -> FeedbackReplaceRes: ...

    # Action API
    async def actions_execute_batch(
        self, req: ActionsExecuteBatchReq
    ) -> ActionsExecuteBatchRes: ...

    # Execute LLM API
    async def completions_create(
        self, req: CompletionsCreateReq
    ) -> CompletionsCreateRes: ...

    # Execute LLM API (Streaming)
    # Returns an iterator of JSON-serializable chunks that together form the streamed
    # response from the model provider. Each element must be a dictionary that can
    # be serialized with ``json.dumps``.
    async def completions_create_stream(
        self, req: CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]: ...

    # Project statistics API
    async def project_stats(self, req: ProjectStatsReq) -> ProjectStatsRes: ...
