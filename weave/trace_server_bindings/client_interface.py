from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any, Protocol

from weave.trace_server_bindings.models import (
    CallsQueryRes,
    DatasetSourcesLinkDeleteRes,
    EnsureProjectExistsRes,
    FileContentReadRes,
)
from weave.vendor.weave_server_sdk.types import (
    AgentQueryParams,
    AgentQueryResponse,
    AgentSearchParams,
    AgentSearchResponse,
    AgentTraceChatRes,
    AnnotationQueueCreateParams,
    AnnotationQueueCreateResponse,
    AnnotationQueueDeleteParams,
    AnnotationQueueDeleteResponse,
    AnnotationQueueQueryParams,
    AnnotationQueueReadParams,
    AnnotationQueueReadResponse,
    AnnotationQueueSchema,
    AnnotationQueueStatsParams,
    AnnotationQueueStatsResponse,
    AnnotationQueueUpdateParams,
    AnnotationQueueUpdateResponse,
    CallDeleteParams,
    CallDeleteResponse,
    CallEndParams,
    CallQueryStatsParams,
    CallQueryStatsResponse,
    CallReadParams,
    CallReadResponse,
    CallScoreParams,
    CallStartParams,
    CallStartResponse,
    CallStatsParams,
    CallStatsResponse,
    CallStreamQueryParams,
    CallUpdateParams,
    CallUpsertBatchParams,
    CallUpsertBatchResponse,
    CallUsageParams,
    CallUsageResponse,
    CompletionCreateParams,
    CompletionCreateResponse,
    CompletionCreateStreamParams,
    CostCreateParams,
    CostCreateResponse,
    CostPurgeParams,
    CostQueryParams,
    CostQueryResponse,
    DatasetSourceLinkParams,
    DatasetSourceLinkResponse,
    DatasetSourceQueryParams,
    DatasetSourceQueryResponse,
    DatasetSourceSourceDatasetsQueryParams,
    DatasetSourceSourceDatasetsQueryResponse,
    EvaluationEvaluateModelParams,
    EvaluationEvaluateModelResponse,
    EvaluationRescoreParams,
    EvaluationRescoreResponse,
    EvaluationStatusParams,
    EvaluationStatusResponse,
    FeedbackAggregateParams,
    FeedbackAggregateResponse,
    FeedbackBatchCreateParams,
    FeedbackBatchCreateResponse,
    FeedbackCreateParams,
    FeedbackCreateResponse,
    FeedbackPayloadSchemaParams,
    FeedbackPayloadSchemaResponse,
    FeedbackPurgeParams,
    FeedbackQueryParams,
    FeedbackQueryResponse,
    FeedbackReplaceParams,
    FeedbackReplaceResponse,
    FeedbackStatsParams,
    FeedbackStatsResponse,
    FileContentParams,
    FileCreateParams,
    FileCreateResponse,
    FileStatsParams,
    FileStatsResponse,
    ImageCreateParams,
    ImageCreateResponse,
    ObjectCreateParams,
    ObjectCreateResponse,
    ObjectDeleteParams,
    ObjectDeleteResponse,
    ObjectQueryParams,
    ObjectQueryResponse,
    ObjectReadParams,
    ObjectReadResponse,
    ProjectStatsParams,
    ProjectStatsResponse,
    RefReadBatchParams,
    RefReadBatchResponse,
    ServerInfoRes,
    ServiceProjectsInfoParams,
    ServiceProjectsInfoResponse,
    TableCreateFromDigestsParams,
    TableCreateFromDigestsResponse,
    TableCreateParams,
    TableCreateResponse,
    TableQueryParams,
    TableQueryResponse,
    TableQueryStatsBatchParams,
    TableQueryStatsBatchResponse,
    TableQueryStatsParams,
    TableQueryStatsResponse,
    TableUpdateParams,
    TableUpdateResponse,
    ThreadStreamQueryParams,
    ThreadStreamQueryResponse,
    TraceUsageParams,
    TraceUsageResponse,
    V2DatasetCreateResponse,
    V2DatasetDeleteResponse,
    V2DatasetListResponse,
    V2DatasetReadResponse,
    V2EvalResultQueryResponse,
    V2EvaluationCreateResponse,
    V2EvaluationDeleteResponse,
    V2EvaluationListResponse,
    V2EvaluationReadResponse,
    V2EvaluationRunCreateResponse,
    V2EvaluationRunDeleteResponse,
    V2EvaluationRunFinishResponse,
    V2EvaluationRunListResponse,
    V2EvaluationRunReadResponse,
    V2ModelCreateResponse,
    V2ModelDeleteResponse,
    V2ModelListResponse,
    V2ModelReadResponse,
    V2OpCreateResponse,
    V2OpDeleteResponse,
    V2OpListResponse,
    V2OpReadResponse,
    V2PredictionCreateResponse,
    V2PredictionDeleteResponse,
    V2PredictionFinishResponse,
    V2PredictionListResponse,
    V2PredictionReadResponse,
    V2RuntimeApplyResponse,
    V2ScoreCreateResponse,
    V2ScoreDeleteResponse,
    V2ScoreListResponse,
    V2ScorerCreateResponse,
    V2ScorerDeleteResponse,
    V2ScoreReadResponse,
    V2ScorerListResponse,
    V2ScorerReadResponse,
)
from weave.vendor.weave_server_sdk.types.agents import (
    AgentVersionQueryParams,
    AgentVersionQueryResponse,
    ConversationChatParams,
    ConversationChatResponse,
    ConversationSpansParams,
    ConversationSpansResponse,
    SpanCustomAttrsSchemaParams,
    SpanCustomAttrsSchemaResponse,
    SpanQueryParams,
    SpanQueryResponse,
    SpanStatsParams,
    SpanStatsResponse,
    TraceChatParams,
)
from weave.vendor.weave_server_sdk.types.annotation_queues import (
    ItemAddParams,
    ItemAddResponse,
    ItemQueryParams,
    ItemQueryResponse,
    ItemUpdateProgressParams,
    ItemUpdateProgressResponse,
)
from weave.vendor.weave_server_sdk.types.call_read_response import Call
from weave.vendor.weave_server_sdk.types.objects import (
    AliasListParams,
    AliasListResponse,
    AliasRemoveParams,
    AliasSetParams,
    TagAddParams,
    TagListParams,
    TagListResponse,
    TagRemoveParams,
)
from weave.vendor.weave_server_sdk.types.projects import (
    TtlSettingReadParams,
    TtlSettingReadResponse,
    TtlSettingUpdateParams,
    TtlSettingUpdateResponse,
)
from weave.vendor.weave_server_sdk.types.table_query_response import Row

if TYPE_CHECKING:
    from weave.shared import trace_server_interface as tsi
    from weave.shared.agents import types as agent_types
    from weave.shared.service_interface import ProjectsInfoReq


# The generated tag and alias methods take their last path parameter as a
# positional argument, so their params types leave it out.
class ObjAddTagsParams(TagAddParams):
    digest: str


class ObjRemoveTagsParams(TagRemoveParams):
    digest: str


class ObjSetAliasesParams(AliasSetParams):
    object_id: str


class ObjRemoveAliasesParams(AliasRemoveParams):
    object_id: str


# The generated annotation queue methods take the queue or item id as a
# positional path argument, so their params types leave it out.
class QueueReadParams(AnnotationQueueReadParams):
    queue_id: str


class QueueDeleteParams(AnnotationQueueDeleteParams):
    queue_id: str


class QueueUpdateParams(AnnotationQueueUpdateParams):
    queue_id: str


class QueueAddCallsParams(ItemAddParams):
    queue_id: str


class QueueItemsQueryParams(ItemQueryParams):
    queue_id: str


class QueueItemProgressUpdateParams(ItemUpdateProgressParams):
    item_id: str


class TraceServerClientInterface(Protocol):
    """Interface for trace server client implementations.

    The storage API (calls, objects, tables, files, feedback and the v2
    object routes) followed by the service API (server info and project
    management).
    """

    # OTEL API
    def otel_export(self, req: tsi.OTelExportReq) -> tsi.OTelExportRes: ...

    # GenAI / Agent Observability API
    def genai_otel_export(
        self,
        req: agent_types.GenAIOTelExportReq,
        *,
        enable_llm_powered_features: bool = True,
    ) -> agent_types.GenAIOTelExportRes: ...
    def agent_spans_query(
        self, req: SpanQueryParams | agent_types.AgentSpansQueryReq
    ) -> SpanQueryResponse: ...
    def agent_spans_stats(
        self, req: SpanStatsParams | agent_types.AgentSpanStatsReq
    ) -> SpanStatsResponse: ...
    def agent_custom_attrs_schema(
        self, req: SpanCustomAttrsSchemaParams | agent_types.AgentCustomAttrsSchemaReq
    ) -> SpanCustomAttrsSchemaResponse: ...
    def agent_agents_query(
        self, req: AgentQueryParams | agent_types.AgentsQueryReq
    ) -> AgentQueryResponse: ...
    def agent_versions_query(
        self, req: AgentVersionQueryParams | agent_types.AgentVersionsQueryReq
    ) -> AgentVersionQueryResponse: ...
    def agent_search(
        self, req: AgentSearchParams | agent_types.AgentSearchReq
    ) -> AgentSearchResponse: ...
    def agent_traces_chat(
        self, req: TraceChatParams | agent_types.AgentTraceChatReq
    ) -> AgentTraceChatRes: ...
    def agent_conversation_chat(
        self, req: ConversationChatParams | agent_types.AgentConversationChatReq
    ) -> ConversationChatResponse: ...
    def agent_conversation_spans(
        self, req: ConversationSpansParams | agent_types.AgentConversationSpansReq
    ) -> ConversationSpansResponse: ...

    # Call API
    def call_start(
        self, req: CallStartParams | tsi.CallStartReq
    ) -> CallStartResponse: ...
    def call_end(self, req: CallEndParams | tsi.CallEndReq) -> object: ...
    def call_read(self, req: CallReadParams | tsi.CallReadReq) -> CallReadResponse: ...
    def calls_query(
        self, req: CallStreamQueryParams | tsi.CallsQueryReq
    ) -> CallsQueryRes: ...
    def calls_query_stream(
        self, req: CallStreamQueryParams | tsi.CallsQueryReq
    ) -> Iterator[Call]: ...
    def calls_delete(
        self, req: CallDeleteParams | tsi.CallsDeleteReq
    ) -> CallDeleteResponse: ...
    def calls_query_stats(
        self, req: CallQueryStatsParams | tsi.CallsQueryStatsReq
    ) -> CallQueryStatsResponse: ...
    def call_stats(
        self, req: CallStatsParams | tsi.CallStatsReq
    ) -> CallStatsResponse: ...
    def trace_usage(
        self, req: TraceUsageParams | tsi.TraceUsageReq
    ) -> TraceUsageResponse: ...
    def calls_usage(
        self, req: CallUsageParams | tsi.CallsUsageReq
    ) -> CallUsageResponse: ...
    def call_update(self, req: CallUpdateParams | tsi.CallUpdateReq) -> object: ...
    def call_start_batch(
        self, req: CallUpsertBatchParams | tsi.CallCreateBatchReq
    ) -> CallUpsertBatchResponse: ...

    # Cost API
    def cost_create(
        self, req: CostCreateParams | tsi.CostCreateReq
    ) -> CostCreateResponse: ...
    def cost_query(
        self, req: CostQueryParams | tsi.CostQueryReq
    ) -> CostQueryResponse: ...
    def cost_purge(self, req: CostPurgeParams | tsi.CostPurgeReq) -> object: ...

    # Obj API
    def obj_create(
        self, req: ObjectCreateParams | tsi.ObjCreateReq
    ) -> ObjectCreateResponse: ...
    def obj_read(
        self, req: ObjectReadParams | tsi.ObjReadReq
    ) -> ObjectReadResponse: ...
    def objs_query(
        self, req: ObjectQueryParams | tsi.ObjQueryReq
    ) -> ObjectQueryResponse: ...
    def obj_delete(
        self, req: ObjectDeleteParams | tsi.ObjDeleteReq
    ) -> ObjectDeleteResponse: ...

    # Tag and Alias API
    def obj_add_tags(self, req: ObjAddTagsParams | tsi.ObjAddTagsReq) -> object: ...
    def obj_remove_tags(
        self, req: ObjRemoveTagsParams | tsi.ObjRemoveTagsReq
    ) -> object: ...
    def obj_set_aliases(
        self, req: ObjSetAliasesParams | tsi.ObjSetAliasesReq
    ) -> object: ...
    def obj_remove_aliases(
        self, req: ObjRemoveAliasesParams | tsi.ObjRemoveAliasesReq
    ) -> object: ...
    def tags_list(self, req: TagListParams | tsi.TagsListReq) -> TagListResponse: ...
    def aliases_list(
        self, req: AliasListParams | tsi.AliasesListReq
    ) -> AliasListResponse: ...

    # Table API
    def table_create(
        self, req: TableCreateParams | tsi.TableCreateReq
    ) -> TableCreateResponse: ...
    def table_create_from_digests(
        self, req: TableCreateFromDigestsParams | tsi.TableCreateFromDigestsReq
    ) -> TableCreateFromDigestsResponse: ...

    def table_update(
        self, req: TableUpdateParams | tsi.TableUpdateReq
    ) -> TableUpdateResponse: ...
    def table_query(
        self, req: TableQueryParams | tsi.TableQueryReq
    ) -> TableQueryResponse: ...
    def table_query_stream(
        self, req: TableQueryParams | tsi.TableQueryReq
    ) -> Iterator[Row]: ...
    def table_query_stats(
        self, req: TableQueryStatsParams | tsi.TableQueryStatsReq
    ) -> TableQueryStatsResponse: ...
    def table_query_stats_batch(
        self, req: TableQueryStatsBatchParams | tsi.TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchResponse: ...

    # Ref API
    def refs_read_batch(
        self, req: RefReadBatchParams | tsi.RefsReadBatchReq
    ) -> RefReadBatchResponse: ...

    # File API
    def file_create(
        self, req: FileCreateParams | tsi.FileCreateReq
    ) -> FileCreateResponse: ...
    def file_content_read(
        self, req: FileContentParams | tsi.FileContentReadReq
    ) -> FileContentReadRes: ...
    def files_stats(
        self, req: FileStatsParams | tsi.FilesStatsReq
    ) -> FileStatsResponse: ...

    # Export API
    def export_start(self, req: tsi.ExportStartReq) -> tsi.ExportStartRes: ...
    def export_status(self, req: tsi.ExportStatusReq) -> tsi.ExportStatusRes: ...

    # Feedback API
    def feedback_create(
        self, req: FeedbackCreateParams | tsi.FeedbackCreateReq
    ) -> FeedbackCreateResponse: ...
    def feedback_create_batch(
        self, req: FeedbackBatchCreateParams | tsi.FeedbackCreateBatchReq
    ) -> FeedbackBatchCreateResponse: ...

    def feedback_query(
        self, req: FeedbackQueryParams | tsi.FeedbackQueryReq
    ) -> FeedbackQueryResponse: ...
    def feedback_purge(
        self, req: FeedbackPurgeParams | tsi.FeedbackPurgeReq
    ) -> object: ...
    def feedback_replace(
        self, req: FeedbackReplaceParams | tsi.FeedbackReplaceReq
    ) -> FeedbackReplaceResponse: ...
    def feedback_stats(
        self, req: FeedbackStatsParams | tsi.FeedbackStatsReq
    ) -> FeedbackStatsResponse: ...
    def feedback_aggregate(
        self, req: FeedbackAggregateParams | tsi.FeedbackAggregateReq
    ) -> FeedbackAggregateResponse: ...
    def feedback_payload_schema(
        self, req: FeedbackPayloadSchemaParams | tsi.FeedbackPayloadSchemaReq
    ) -> FeedbackPayloadSchemaResponse: ...

    # Execute LLM API
    def completions_create(
        self, req: CompletionCreateParams | tsi.CompletionsCreateReq
    ) -> CompletionCreateResponse: ...

    # Execute LLM API (Streaming)
    # Returns an iterator of JSON-serializable chunks that together form the streamed
    # response from the model provider. Each element must be a dictionary that can
    # be serialized with ``json.dumps``.
    def completions_create_stream(
        self, req: CompletionCreateStreamParams | tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]: ...

    # Execute Image Generation API
    def image_create(
        self, req: ImageCreateParams | tsi.ImageGenerationCreateReq
    ) -> ImageCreateResponse: ...

    # Project statistics API
    def project_stats(
        self, req: ProjectStatsParams | tsi.ProjectStatsReq
    ) -> ProjectStatsResponse: ...

    # TTL settings API
    def project_ttl_settings_read(
        self, req: TtlSettingReadParams | tsi.ProjectTTLSettingsReadReq
    ) -> TtlSettingReadResponse: ...

    def project_ttl_settings_update(
        self, req: TtlSettingUpdateParams | tsi.ProjectTTLSettingsUpdateReq
    ) -> TtlSettingUpdateResponse: ...

    # Thread API
    def threads_query_stream(
        self, req: ThreadStreamQueryParams | tsi.ThreadsQueryReq
    ) -> Iterator[ThreadStreamQueryResponse]: ...

    # Annotation Queue API
    def annotation_queue_create(
        self, req: AnnotationQueueCreateParams | tsi.AnnotationQueueCreateReq
    ) -> AnnotationQueueCreateResponse: ...

    def annotation_queues_query_stream(
        self, req: AnnotationQueueQueryParams | tsi.AnnotationQueuesQueryReq
    ) -> Iterator[AnnotationQueueSchema]: ...

    def annotation_queue_read(
        self, req: QueueReadParams | tsi.AnnotationQueueReadReq
    ) -> AnnotationQueueReadResponse: ...

    def annotation_queue_delete(
        self, req: QueueDeleteParams | tsi.AnnotationQueueDeleteReq
    ) -> AnnotationQueueDeleteResponse: ...

    def annotation_queue_update(
        self, req: QueueUpdateParams | tsi.AnnotationQueueUpdateReq
    ) -> AnnotationQueueUpdateResponse: ...

    def annotation_queue_add_calls(
        self, req: QueueAddCallsParams | tsi.AnnotationQueueAddCallsReq
    ) -> ItemAddResponse: ...

    def annotation_queues_stats(
        self, req: AnnotationQueueStatsParams | tsi.AnnotationQueuesStatsReq
    ) -> AnnotationQueueStatsResponse: ...

    def annotation_queue_items_query(
        self, req: QueueItemsQueryParams | tsi.AnnotationQueueItemsQueryReq
    ) -> ItemQueryResponse: ...

    def annotator_queue_items_progress_update(
        self,
        req: QueueItemProgressUpdateParams | tsi.AnnotatorQueueItemsProgressUpdateReq,
    ) -> ItemUpdateProgressResponse: ...

    # Dataset Sources API
    def dataset_sources_link(
        self, req: DatasetSourceLinkParams | tsi.DatasetSourcesLinkReq
    ) -> DatasetSourceLinkResponse: ...

    def dataset_sources_link_delete(
        self, req: Mapping[str, Any] | tsi.DatasetSourcesLinkDeleteReq
    ) -> DatasetSourcesLinkDeleteRes: ...

    def dataset_sources_query(
        self, req: DatasetSourceQueryParams | tsi.DatasetSourcesQueryReq
    ) -> DatasetSourceQueryResponse: ...

    def source_datasets_query(
        self, req: DatasetSourceSourceDatasetsQueryParams | tsi.SourceDatasetsQueryReq
    ) -> DatasetSourceSourceDatasetsQueryResponse: ...

    # Evaluation API
    def evaluate_model(
        self, req: EvaluationEvaluateModelParams | tsi.EvaluateModelReq
    ) -> EvaluationEvaluateModelResponse: ...
    def evaluation_status(
        self, req: EvaluationStatusParams | tsi.EvaluationStatusReq
    ) -> EvaluationStatusResponse: ...
    def rescore(
        self, req: EvaluationRescoreParams | tsi.RescoreReq
    ) -> EvaluationRescoreResponse: ...

    # Scoring API
    def calls_score(self, req: CallScoreParams | tsi.CallsScoreReq) -> object: ...

    # Calls V2 API
    def calls_complete(
        self, req: Mapping[str, Any] | tsi.CallsUpsertCompleteReq
    ) -> object: ...
    def call_start_v2(self, req: tsi.CallStartV2Req) -> tsi.CallStartV2Res: ...
    def call_end_v2(self, req: tsi.CallEndV2Req) -> tsi.CallEndV2Res: ...

    # Ops
    def op_create(
        self, req: Mapping[str, Any] | tsi.OpCreateReq
    ) -> V2OpCreateResponse: ...
    def op_read(self, req: Mapping[str, Any] | tsi.OpReadReq) -> V2OpReadResponse: ...
    def op_list(
        self, req: Mapping[str, Any] | tsi.OpListReq
    ) -> Iterator[V2OpListResponse]: ...
    def op_delete(
        self, req: Mapping[str, Any] | tsi.OpDeleteReq
    ) -> V2OpDeleteResponse: ...

    # Datasets
    def dataset_create(
        self, req: Mapping[str, Any] | tsi.DatasetCreateReq
    ) -> V2DatasetCreateResponse: ...
    def dataset_read(
        self, req: Mapping[str, Any] | tsi.DatasetReadReq
    ) -> V2DatasetReadResponse: ...
    def dataset_list(
        self, req: Mapping[str, Any] | tsi.DatasetListReq
    ) -> Iterator[V2DatasetListResponse]: ...
    def dataset_delete(
        self, req: Mapping[str, Any] | tsi.DatasetDeleteReq
    ) -> V2DatasetDeleteResponse: ...

    # Custom Runtimes
    # The request names its project as project_id, which fills the route's
    # entity and project path parameters that the generated params require.
    def custom_runtime_apply(
        self, req: Mapping[str, Any] | tsi.CustomRuntimeApplyReq
    ) -> V2RuntimeApplyResponse: ...

    # Scorers
    def scorer_create(
        self, req: Mapping[str, Any] | tsi.ScorerCreateReq
    ) -> V2ScorerCreateResponse: ...
    def scorer_read(
        self, req: Mapping[str, Any] | tsi.ScorerReadReq
    ) -> V2ScorerReadResponse: ...
    def scorer_list(
        self, req: Mapping[str, Any] | tsi.ScorerListReq
    ) -> Iterator[V2ScorerListResponse]: ...
    def scorer_delete(
        self, req: Mapping[str, Any] | tsi.ScorerDeleteReq
    ) -> V2ScorerDeleteResponse: ...

    # Evaluations
    def evaluation_create(
        self, req: Mapping[str, Any] | tsi.EvaluationCreateReq
    ) -> V2EvaluationCreateResponse: ...
    def evaluation_read(
        self, req: Mapping[str, Any] | tsi.EvaluationReadReq
    ) -> V2EvaluationReadResponse: ...
    def evaluation_list(
        self, req: Mapping[str, Any] | tsi.EvaluationListReq
    ) -> Iterator[V2EvaluationListResponse]: ...
    def evaluation_delete(
        self, req: Mapping[str, Any] | tsi.EvaluationDeleteReq
    ) -> V2EvaluationDeleteResponse: ...

    # Models
    def model_create(
        self, req: Mapping[str, Any] | tsi.ModelCreateReq
    ) -> V2ModelCreateResponse: ...
    def model_read(
        self, req: Mapping[str, Any] | tsi.ModelReadReq
    ) -> V2ModelReadResponse: ...
    def model_list(
        self, req: Mapping[str, Any] | tsi.ModelListReq
    ) -> Iterator[V2ModelListResponse]: ...
    def model_delete(
        self, req: Mapping[str, Any] | tsi.ModelDeleteReq
    ) -> V2ModelDeleteResponse: ...

    # Evaluation Runs
    def evaluation_run_create(
        self, req: Mapping[str, Any] | tsi.EvaluationRunCreateReq
    ) -> V2EvaluationRunCreateResponse: ...
    def evaluation_run_read(
        self, req: Mapping[str, Any] | tsi.EvaluationRunReadReq
    ) -> V2EvaluationRunReadResponse: ...
    def evaluation_run_list(
        self, req: Mapping[str, Any] | tsi.EvaluationRunListReq
    ) -> Iterator[V2EvaluationRunListResponse]: ...
    def evaluation_run_delete(
        self, req: Mapping[str, Any] | tsi.EvaluationRunDeleteReq
    ) -> V2EvaluationRunDeleteResponse: ...
    def evaluation_run_finish(
        self, req: Mapping[str, Any] | tsi.EvaluationRunFinishReq
    ) -> V2EvaluationRunFinishResponse: ...

    # Predictions
    def prediction_create(
        self, req: Mapping[str, Any] | tsi.PredictionCreateReq
    ) -> V2PredictionCreateResponse: ...
    def prediction_read(
        self, req: Mapping[str, Any] | tsi.PredictionReadReq
    ) -> V2PredictionReadResponse: ...
    def prediction_list(
        self, req: Mapping[str, Any] | tsi.PredictionListReq
    ) -> Iterator[V2PredictionListResponse]: ...
    def prediction_delete(
        self, req: Mapping[str, Any] | tsi.PredictionDeleteReq
    ) -> V2PredictionDeleteResponse: ...
    def prediction_finish(
        self, req: Mapping[str, Any] | tsi.PredictionFinishReq
    ) -> V2PredictionFinishResponse: ...

    # Scores
    def score_create(
        self, req: Mapping[str, Any] | tsi.ScoreCreateReq
    ) -> V2ScoreCreateResponse: ...
    def score_read(
        self, req: Mapping[str, Any] | tsi.ScoreReadReq
    ) -> V2ScoreReadResponse: ...
    def score_list(
        self, req: Mapping[str, Any] | tsi.ScoreListReq
    ) -> Iterator[V2ScoreListResponse]: ...
    def score_delete(
        self, req: Mapping[str, Any] | tsi.ScoreDeleteReq
    ) -> V2ScoreDeleteResponse: ...
    def eval_results_query(
        self, req: Mapping[str, Any] | tsi.EvalResultsQueryReq
    ) -> V2EvalResultQueryResponse: ...

    # Service API
    def server_info(self) -> ServerInfoRes: ...
    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes: ...
    def projects_info(
        self, req: ServiceProjectsInfoParams | ProjectsInfoReq
    ) -> ServiceProjectsInfoResponse: ...
