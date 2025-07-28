import datetime
from collections.abc import AsyncIterator
from typing import Any, Protocol

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
)


class AsyncTraceServerInterface(Protocol):
    """
    Async version of TraceServerInterface protocol.
    
    All methods are async and streaming methods return AsyncIterator instead of Iterator.
    """
    async def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes:
        return EnsureProjectExistsRes(project_name=project)

    # OTEL API
    async def otel_export(self, req: OtelExportReq) -> OtelExportRes: ...

    # Call API
    async def call_start(self, req: CallStartReq) -> CallStartRes: ...
    async def call_end(self, req: CallEndReq) -> CallEndRes: ...
    async def call_read(self, req: CallReadReq) -> CallReadRes: ...
    async def calls_query(self, req: CallsQueryReq) -> CallsQueryRes: ...
    async def calls_query_stream(self, req: CallsQueryReq) -> AsyncIterator[CallSchema]: ...
    async def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes: ...
    async def calls_query_stats(self, req: CallsQueryStatsReq) -> CallsQueryStatsRes: ...

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
    async def table_query_stream(self, req: TableQueryReq) -> AsyncIterator[TableRowSchema]: ...
    async def table_query_stats(self, req: TableQueryStatsReq) -> TableQueryStatsRes: ...
    async def table_query_stats_batch(
        self, req: TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchRes: ...

    # Ref API
    async def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes: ...

    # File API
    async def file_create(self, req: FileCreateReq) -> FileCreateRes: ...
    async def file_content_read(self, req: FileContentReadReq) -> FileContentReadRes: ...
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
    async def completions_create(self, req: CompletionsCreateReq) -> CompletionsCreateRes: ...

    # Execute LLM API (Streaming)
    async def completions_create_stream(
        self, req: CompletionsCreateReq
    ) -> AsyncIterator[dict[str, Any]]: ...

    # Project statistics API
    async def project_stats(self, req: ProjectStatsReq) -> ProjectStatsRes: ...

    # Thread API
    async def threads_query_stream(self, req: ThreadsQueryReq) -> AsyncIterator[ThreadSchema]: ...

    # Evaluation API
    async def evaluate_model(self, req: EvaluateModelReq) -> EvaluateModelRes: ...
    async def evaluation_status(self, req: EvaluationStatusReq) -> EvaluationStatusRes: ... 