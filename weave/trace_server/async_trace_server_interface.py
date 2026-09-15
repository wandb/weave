"""Async twins of the trace server protocols.

One protocol per sync protocol in `trace_server_interface`, with every method
`async def` and every `Iterator` return an `AsyncIterator`. The drift test in
`tests/trace_server/test_async_trace_server_interface.py` regenerates the
expected shape from the sync protocols, so the two cannot diverge silently.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from weave.trace_server.agents import types as agent_types
from weave.trace_server.trace_server_interface import (
    AliasesListReq,
    AliasesListRes,
    AnnotationQueueAddCallsReq,
    AnnotationQueueAddCallsRes,
    AnnotationQueueCreateReq,
    AnnotationQueueCreateRes,
    AnnotationQueueDeleteReq,
    AnnotationQueueDeleteRes,
    AnnotationQueueItemsQueryReq,
    AnnotationQueueItemsQueryRes,
    AnnotationQueueReadReq,
    AnnotationQueueReadRes,
    AnnotationQueueSchema,
    AnnotationQueuesQueryReq,
    AnnotationQueuesStatsReq,
    AnnotationQueuesStatsRes,
    AnnotationQueueUpdateReq,
    AnnotationQueueUpdateRes,
    AnnotatorQueueItemsProgressUpdateReq,
    AnnotatorQueueItemsProgressUpdateRes,
    CallCreateBatchReq,
    CallCreateBatchRes,
    CallEndReq,
    CallEndRes,
    CallEndV2Req,
    CallEndV2Res,
    CallReadReq,
    CallReadRes,
    CallSchema,
    CallsDeleteReq,
    CallsDeleteRes,
    CallsQueryReq,
    CallsQueryRes,
    CallsQueryStatsReq,
    CallsQueryStatsRes,
    CallsScoreReq,
    CallsScoreRes,
    CallStartReq,
    CallStartRes,
    CallStartV2Req,
    CallStartV2Res,
    CallStatsReq,
    CallStatsRes,
    CallsUpsertCompleteReq,
    CallsUpsertCompleteRes,
    CallsUsageReq,
    CallsUsageRes,
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
    CustomRuntimeApplyReq,
    CustomRuntimeApplyRes,
    DatasetCreateReq,
    DatasetCreateRes,
    DatasetDeleteReq,
    DatasetDeleteRes,
    DatasetListReq,
    DatasetReadReq,
    DatasetReadRes,
    DatasetSourcesLinkDeleteReq,
    DatasetSourcesLinkDeleteRes,
    DatasetSourcesLinkReq,
    DatasetSourcesLinkRes,
    DatasetSourcesQueryReq,
    DatasetSourcesQueryRes,
    EvalResultsQueryReq,
    EvalResultsQueryRes,
    EvaluateModelReq,
    EvaluateModelRes,
    EvaluationCreateReq,
    EvaluationCreateRes,
    EvaluationDeleteReq,
    EvaluationDeleteRes,
    EvaluationListReq,
    EvaluationReadReq,
    EvaluationReadRes,
    EvaluationRunCreateReq,
    EvaluationRunCreateRes,
    EvaluationRunDeleteReq,
    EvaluationRunDeleteRes,
    EvaluationRunFinishReq,
    EvaluationRunFinishRes,
    EvaluationRunListReq,
    EvaluationRunReadReq,
    EvaluationRunReadRes,
    EvaluationStatusReq,
    EvaluationStatusRes,
    ExportStartReq,
    ExportStartRes,
    ExportStatusReq,
    ExportStatusRes,
    FeedbackAggregateReq,
    FeedbackAggregateRes,
    FeedbackCreateBatchReq,
    FeedbackCreateBatchRes,
    FeedbackCreateReq,
    FeedbackCreateRes,
    FeedbackPayloadSchemaReq,
    FeedbackPayloadSchemaRes,
    FeedbackPurgeReq,
    FeedbackPurgeRes,
    FeedbackQueryReq,
    FeedbackQueryRes,
    FeedbackReplaceReq,
    FeedbackReplaceRes,
    FeedbackStatsReq,
    FeedbackStatsRes,
    FileContentReadReq,
    FileContentReadRes,
    FileCreateReq,
    FileCreateRes,
    FilesStatsReq,
    FilesStatsRes,
    ImageGenerationCreateReq,
    ImageGenerationCreateRes,
    ModelCreateReq,
    ModelCreateRes,
    ModelDeleteReq,
    ModelDeleteRes,
    ModelListReq,
    ModelReadReq,
    ModelReadRes,
    ObjAddTagsReq,
    ObjAddTagsRes,
    ObjCreateReq,
    ObjCreateRes,
    ObjDeleteReq,
    ObjDeleteRes,
    ObjQueryReq,
    ObjQueryRes,
    ObjReadReq,
    ObjReadRes,
    ObjRemoveAliasesReq,
    ObjRemoveAliasesRes,
    ObjRemoveTagsReq,
    ObjRemoveTagsRes,
    ObjSetAliasesReq,
    ObjSetAliasesRes,
    OpCreateReq,
    OpCreateRes,
    OpDeleteReq,
    OpDeleteRes,
    OpListReq,
    OpReadReq,
    OpReadRes,
    OTelExportReq,
    OTelExportRes,
    PredictionCreateReq,
    PredictionCreateRes,
    PredictionDeleteReq,
    PredictionDeleteRes,
    PredictionFinishReq,
    PredictionFinishRes,
    PredictionListReq,
    PredictionReadReq,
    PredictionReadRes,
    ProjectStatsReq,
    ProjectStatsRes,
    ProjectTTLSettingsReadReq,
    ProjectTTLSettingsReadRes,
    ProjectTTLSettingsUpdateReq,
    ProjectTTLSettingsUpdateRes,
    RefsReadBatchReq,
    RefsReadBatchRes,
    RescoreReq,
    RescoreRes,
    ScoreCreateReq,
    ScoreCreateRes,
    ScoreDeleteReq,
    ScoreDeleteRes,
    ScoreListReq,
    ScorerCreateReq,
    ScorerCreateRes,
    ScorerDeleteReq,
    ScorerDeleteRes,
    ScoreReadReq,
    ScoreReadRes,
    ScorerListReq,
    ScorerReadReq,
    ScorerReadRes,
    SourceDatasetsQueryReq,
    SourceDatasetsQueryRes,
    TableCreateFromDigestsReq,
    TableCreateFromDigestsRes,
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
    TagsListReq,
    TagsListRes,
    ThreadSchema,
    ThreadsQueryReq,
    TraceUsageReq,
    TraceUsageRes,
)


class AsyncTraceServerInterface(Protocol):
    """Async twin of `tsi.TraceServerInterface`. Generated from its AST; see the drift test."""

    async def otel_export(self, req: OTelExportReq) -> OTelExportRes: ...

    async def genai_otel_export(
        self,
        req: agent_types.GenAIOTelExportReq,
        *,
        enable_llm_powered_features: bool = True,
    ) -> agent_types.GenAIOTelExportRes: ...

    async def agent_spans_query(
        self, req: agent_types.AgentSpansQueryReq
    ) -> agent_types.AgentSpansQueryRes: ...

    async def agent_spans_stats(
        self, req: agent_types.AgentSpanStatsReq
    ) -> agent_types.AgentSpanStatsRes: ...

    async def agent_custom_attrs_schema(
        self, req: agent_types.AgentCustomAttrsSchemaReq
    ) -> agent_types.AgentCustomAttrsSchemaRes: ...

    async def agent_agents_query(
        self, req: agent_types.AgentsQueryReq
    ) -> agent_types.AgentsQueryRes: ...

    async def agent_versions_query(
        self, req: agent_types.AgentVersionsQueryReq
    ) -> agent_types.AgentVersionsQueryRes: ...

    async def agent_search(
        self, req: agent_types.AgentSearchReq
    ) -> agent_types.AgentSearchRes: ...

    async def agent_traces_chat(
        self, req: agent_types.AgentTraceChatReq
    ) -> agent_types.AgentTraceChatRes: ...

    async def agent_conversation_chat(
        self, req: agent_types.AgentConversationChatReq
    ) -> agent_types.AgentConversationChatRes: ...

    async def agent_conversation_spans(
        self, req: agent_types.AgentConversationSpansReq
    ) -> agent_types.AgentConversationSpansRes: ...

    async def call_start(self, req: CallStartReq) -> CallStartRes: ...

    async def call_end(self, req: CallEndReq) -> CallEndRes: ...

    async def call_read(self, req: CallReadReq) -> CallReadRes: ...

    async def calls_query(self, req: CallsQueryReq) -> CallsQueryRes: ...

    def calls_query_stream(self, req: CallsQueryReq) -> AsyncIterator[CallSchema]: ...

    async def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes: ...

    async def calls_query_stats(
        self, req: CallsQueryStatsReq
    ) -> CallsQueryStatsRes: ...

    async def call_stats(self, req: CallStatsReq) -> CallStatsRes: ...

    async def trace_usage(self, req: TraceUsageReq) -> TraceUsageRes: ...

    async def calls_usage(self, req: CallsUsageReq) -> CallsUsageRes: ...

    async def call_update(self, req: CallUpdateReq) -> CallUpdateRes: ...

    async def call_start_batch(self, req: CallCreateBatchReq) -> CallCreateBatchRes: ...

    async def cost_create(self, req: CostCreateReq) -> CostCreateRes: ...

    async def cost_query(self, req: CostQueryReq) -> CostQueryRes: ...

    async def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes: ...

    async def obj_create(self, req: ObjCreateReq) -> ObjCreateRes: ...

    async def obj_read(self, req: ObjReadReq) -> ObjReadRes: ...

    async def objs_query(self, req: ObjQueryReq) -> ObjQueryRes: ...

    async def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes: ...

    async def obj_add_tags(self, req: ObjAddTagsReq) -> ObjAddTagsRes: ...

    async def obj_remove_tags(self, req: ObjRemoveTagsReq) -> ObjRemoveTagsRes: ...

    async def obj_set_aliases(self, req: ObjSetAliasesReq) -> ObjSetAliasesRes: ...

    async def obj_remove_aliases(
        self, req: ObjRemoveAliasesReq
    ) -> ObjRemoveAliasesRes: ...

    async def tags_list(self, req: TagsListReq) -> TagsListRes: ...

    async def aliases_list(self, req: AliasesListReq) -> AliasesListRes: ...

    async def table_create(self, req: TableCreateReq) -> TableCreateRes: ...

    async def table_create_from_digests(
        self, req: TableCreateFromDigestsReq
    ) -> TableCreateFromDigestsRes: ...

    async def table_update(self, req: TableUpdateReq) -> TableUpdateRes: ...

    async def table_query(self, req: TableQueryReq) -> TableQueryRes: ...

    def table_query_stream(
        self, req: TableQueryReq
    ) -> AsyncIterator[TableRowSchema]: ...

    async def table_query_stats(
        self, req: TableQueryStatsReq
    ) -> TableQueryStatsRes: ...

    async def table_query_stats_batch(
        self, req: TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchRes: ...

    async def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes: ...

    async def file_create(self, req: FileCreateReq) -> FileCreateRes: ...

    async def file_content_read(
        self, req: FileContentReadReq
    ) -> FileContentReadRes: ...

    async def files_stats(self, req: FilesStatsReq) -> FilesStatsRes: ...

    async def export_start(self, req: ExportStartReq) -> ExportStartRes: ...

    async def export_status(self, req: ExportStatusReq) -> ExportStatusRes: ...

    async def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes: ...

    async def feedback_create_batch(
        self, req: FeedbackCreateBatchReq
    ) -> FeedbackCreateBatchRes: ...

    async def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes: ...

    async def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes: ...

    async def feedback_replace(self, req: FeedbackReplaceReq) -> FeedbackReplaceRes: ...

    async def feedback_stats(self, req: FeedbackStatsReq) -> FeedbackStatsRes: ...

    async def feedback_aggregate(
        self, req: FeedbackAggregateReq
    ) -> FeedbackAggregateRes: ...

    async def feedback_payload_schema(
        self, req: FeedbackPayloadSchemaReq
    ) -> FeedbackPayloadSchemaRes: ...

    async def completions_create(
        self, req: CompletionsCreateReq
    ) -> CompletionsCreateRes: ...

    def completions_create_stream(
        self, req: CompletionsCreateReq
    ) -> AsyncIterator[dict[str, Any]]: ...

    async def image_create(
        self, req: ImageGenerationCreateReq
    ) -> ImageGenerationCreateRes: ...

    async def project_stats(self, req: ProjectStatsReq) -> ProjectStatsRes: ...

    async def project_ttl_settings_read(
        self, req: ProjectTTLSettingsReadReq
    ) -> ProjectTTLSettingsReadRes: ...

    async def project_ttl_settings_update(
        self, req: ProjectTTLSettingsUpdateReq
    ) -> ProjectTTLSettingsUpdateRes: ...

    def threads_query_stream(
        self, req: ThreadsQueryReq
    ) -> AsyncIterator[ThreadSchema]: ...

    async def annotation_queue_create(
        self, req: AnnotationQueueCreateReq
    ) -> AnnotationQueueCreateRes: ...

    def annotation_queues_query_stream(
        self, req: AnnotationQueuesQueryReq
    ) -> AsyncIterator[AnnotationQueueSchema]: ...

    async def annotation_queue_read(
        self, req: AnnotationQueueReadReq
    ) -> AnnotationQueueReadRes: ...

    async def annotation_queue_delete(
        self, req: AnnotationQueueDeleteReq
    ) -> AnnotationQueueDeleteRes: ...

    async def annotation_queue_update(
        self, req: AnnotationQueueUpdateReq
    ) -> AnnotationQueueUpdateRes: ...

    async def annotation_queue_add_calls(
        self, req: AnnotationQueueAddCallsReq
    ) -> AnnotationQueueAddCallsRes: ...

    async def annotation_queues_stats(
        self, req: AnnotationQueuesStatsReq
    ) -> AnnotationQueuesStatsRes: ...

    async def annotation_queue_items_query(
        self, req: AnnotationQueueItemsQueryReq
    ) -> AnnotationQueueItemsQueryRes: ...

    async def annotator_queue_items_progress_update(
        self, req: AnnotatorQueueItemsProgressUpdateReq
    ) -> AnnotatorQueueItemsProgressUpdateRes: ...

    async def dataset_sources_link(
        self, req: DatasetSourcesLinkReq
    ) -> DatasetSourcesLinkRes: ...

    async def dataset_sources_link_delete(
        self, req: DatasetSourcesLinkDeleteReq
    ) -> DatasetSourcesLinkDeleteRes: ...

    async def dataset_sources_query(
        self, req: DatasetSourcesQueryReq
    ) -> DatasetSourcesQueryRes: ...

    async def source_datasets_query(
        self, req: SourceDatasetsQueryReq
    ) -> SourceDatasetsQueryRes: ...

    async def evaluate_model(self, req: EvaluateModelReq) -> EvaluateModelRes: ...

    async def evaluation_status(
        self, req: EvaluationStatusReq
    ) -> EvaluationStatusRes: ...

    async def rescore(self, req: RescoreReq) -> RescoreRes: ...

    async def calls_score(self, req: CallsScoreReq) -> CallsScoreRes: ...


class AsyncObjectInterface(Protocol):
    """Async twin of `tsi.ObjectInterface`. Generated from its AST; see the drift test."""

    async def calls_complete(
        self, req: CallsUpsertCompleteReq
    ) -> CallsUpsertCompleteRes: ...

    async def call_start_v2(self, req: CallStartV2Req) -> CallStartV2Res: ...

    async def call_end_v2(self, req: CallEndV2Req) -> CallEndV2Res: ...

    async def op_create(self, req: OpCreateReq) -> OpCreateRes: ...

    async def op_read(self, req: OpReadReq) -> OpReadRes: ...

    def op_list(self, req: OpListReq) -> AsyncIterator[OpReadRes]: ...

    async def op_delete(self, req: OpDeleteReq) -> OpDeleteRes: ...

    async def dataset_create(self, req: DatasetCreateReq) -> DatasetCreateRes: ...

    async def dataset_read(self, req: DatasetReadReq) -> DatasetReadRes: ...

    def dataset_list(self, req: DatasetListReq) -> AsyncIterator[DatasetReadRes]: ...

    async def dataset_delete(self, req: DatasetDeleteReq) -> DatasetDeleteRes: ...

    async def custom_runtime_apply(
        self, req: CustomRuntimeApplyReq
    ) -> CustomRuntimeApplyRes: ...

    async def scorer_create(self, req: ScorerCreateReq) -> ScorerCreateRes: ...

    async def scorer_read(self, req: ScorerReadReq) -> ScorerReadRes: ...

    def scorer_list(self, req: ScorerListReq) -> AsyncIterator[ScorerReadRes]: ...

    async def scorer_delete(self, req: ScorerDeleteReq) -> ScorerDeleteRes: ...

    async def evaluation_create(
        self, req: EvaluationCreateReq
    ) -> EvaluationCreateRes: ...

    async def evaluation_read(self, req: EvaluationReadReq) -> EvaluationReadRes: ...

    def evaluation_list(
        self, req: EvaluationListReq
    ) -> AsyncIterator[EvaluationReadRes]: ...

    async def evaluation_delete(
        self, req: EvaluationDeleteReq
    ) -> EvaluationDeleteRes: ...

    async def model_create(self, req: ModelCreateReq) -> ModelCreateRes: ...

    async def model_read(self, req: ModelReadReq) -> ModelReadRes: ...

    def model_list(self, req: ModelListReq) -> AsyncIterator[ModelReadRes]: ...

    async def model_delete(self, req: ModelDeleteReq) -> ModelDeleteRes: ...

    async def evaluation_run_create(
        self, req: EvaluationRunCreateReq
    ) -> EvaluationRunCreateRes: ...

    async def evaluation_run_read(
        self, req: EvaluationRunReadReq
    ) -> EvaluationRunReadRes: ...

    def evaluation_run_list(
        self, req: EvaluationRunListReq
    ) -> AsyncIterator[EvaluationRunReadRes]: ...

    async def evaluation_run_delete(
        self, req: EvaluationRunDeleteReq
    ) -> EvaluationRunDeleteRes: ...

    async def evaluation_run_finish(
        self, req: EvaluationRunFinishReq
    ) -> EvaluationRunFinishRes: ...

    async def prediction_create(
        self, req: PredictionCreateReq
    ) -> PredictionCreateRes: ...

    async def prediction_read(self, req: PredictionReadReq) -> PredictionReadRes: ...

    def prediction_list(
        self, req: PredictionListReq
    ) -> AsyncIterator[PredictionReadRes]: ...

    async def prediction_delete(
        self, req: PredictionDeleteReq
    ) -> PredictionDeleteRes: ...

    async def prediction_finish(
        self, req: PredictionFinishReq
    ) -> PredictionFinishRes: ...

    async def score_create(self, req: ScoreCreateReq) -> ScoreCreateRes: ...

    async def score_read(self, req: ScoreReadReq) -> ScoreReadRes: ...

    def score_list(self, req: ScoreListReq) -> AsyncIterator[ScoreReadRes]: ...

    async def score_delete(self, req: ScoreDeleteReq) -> ScoreDeleteRes: ...

    async def eval_results_query(
        self, req: EvalResultsQueryReq
    ) -> EvalResultsQueryRes: ...


class AsyncFullTraceServerInterface(
    AsyncTraceServerInterface, AsyncObjectInterface, Protocol
):
    """Async twin of `tsi.FullTraceServerInterface`."""
