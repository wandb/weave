from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Protocol

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

    # OTEL API. The generated client has no route or types for it.
    def otel_export(self, req: Mapping[str, Any]) -> Any: ...

    # GenAI / Agent Observability API
    def agent_spans_query(self, req: SpanQueryParams) -> SpanQueryResponse: ...
    def agent_spans_stats(self, req: SpanStatsParams) -> SpanStatsResponse: ...
    def agent_custom_attrs_schema(
        self, req: SpanCustomAttrsSchemaParams
    ) -> SpanCustomAttrsSchemaResponse: ...
    def agent_agents_query(self, req: AgentQueryParams) -> AgentQueryResponse: ...
    def agent_versions_query(
        self, req: AgentVersionQueryParams
    ) -> AgentVersionQueryResponse: ...
    def agent_search(self, req: AgentSearchParams) -> AgentSearchResponse: ...
    def agent_traces_chat(self, req: TraceChatParams) -> AgentTraceChatRes: ...
    def agent_conversation_chat(
        self, req: ConversationChatParams
    ) -> ConversationChatResponse: ...
    def agent_conversation_spans(
        self, req: ConversationSpansParams
    ) -> ConversationSpansResponse: ...

    # Call API
    def call_start(self, req: CallStartParams) -> CallStartResponse: ...
    def call_end(self, req: CallEndParams) -> object: ...
    def call_read(self, req: CallReadParams) -> CallReadResponse: ...
    def calls_query(self, req: CallStreamQueryParams) -> CallsQueryRes: ...
    def calls_query_stream(self, req: CallStreamQueryParams) -> Iterator[Call]: ...
    def calls_delete(self, req: CallDeleteParams) -> CallDeleteResponse: ...
    def calls_query_stats(
        self, req: CallQueryStatsParams
    ) -> CallQueryStatsResponse: ...
    def call_stats(self, req: CallStatsParams) -> CallStatsResponse: ...
    def trace_usage(self, req: TraceUsageParams) -> TraceUsageResponse: ...
    def calls_usage(self, req: CallUsageParams) -> CallUsageResponse: ...
    def call_update(self, req: CallUpdateParams) -> object: ...
    def call_start_batch(
        self, req: CallUpsertBatchParams
    ) -> CallUpsertBatchResponse: ...

    # Cost API
    def cost_create(self, req: CostCreateParams) -> CostCreateResponse: ...
    def cost_query(self, req: CostQueryParams) -> CostQueryResponse: ...
    def cost_purge(self, req: CostPurgeParams) -> object: ...

    # Obj API
    def obj_create(self, req: ObjectCreateParams) -> ObjectCreateResponse: ...
    def obj_read(self, req: ObjectReadParams) -> ObjectReadResponse: ...
    def objs_query(self, req: ObjectQueryParams) -> ObjectQueryResponse: ...
    def obj_delete(self, req: ObjectDeleteParams) -> ObjectDeleteResponse: ...

    # Tag and Alias API
    def obj_add_tags(self, req: ObjAddTagsParams) -> object: ...
    def obj_remove_tags(self, req: ObjRemoveTagsParams) -> object: ...
    def obj_set_aliases(self, req: ObjSetAliasesParams) -> object: ...
    def obj_remove_aliases(self, req: ObjRemoveAliasesParams) -> object: ...
    def tags_list(self, req: TagListParams) -> TagListResponse: ...
    def aliases_list(self, req: AliasListParams) -> AliasListResponse: ...

    # Table API
    def table_create(self, req: TableCreateParams) -> TableCreateResponse: ...
    def table_create_from_digests(
        self, req: TableCreateFromDigestsParams
    ) -> TableCreateFromDigestsResponse: ...

    def table_update(self, req: TableUpdateParams) -> TableUpdateResponse: ...
    def table_query(self, req: TableQueryParams) -> TableQueryResponse: ...
    def table_query_stream(self, req: TableQueryParams) -> Iterator[Row]: ...
    def table_query_stats(
        self, req: TableQueryStatsParams
    ) -> TableQueryStatsResponse: ...
    def table_query_stats_batch(
        self, req: TableQueryStatsBatchParams
    ) -> TableQueryStatsBatchResponse: ...

    # Ref API
    def refs_read_batch(self, req: RefReadBatchParams) -> RefReadBatchResponse: ...

    # File API
    def file_create(self, req: FileCreateParams) -> FileCreateResponse: ...
    def file_content_read(self, req: FileContentParams) -> FileContentReadRes: ...
    def files_stats(self, req: FileStatsParams) -> FileStatsResponse: ...

    # Feedback API
    def feedback_create(self, req: FeedbackCreateParams) -> FeedbackCreateResponse: ...
    def feedback_create_batch(
        self, req: FeedbackBatchCreateParams
    ) -> FeedbackBatchCreateResponse: ...

    def feedback_query(self, req: FeedbackQueryParams) -> FeedbackQueryResponse: ...
    def feedback_purge(self, req: FeedbackPurgeParams) -> object: ...
    def feedback_replace(
        self, req: FeedbackReplaceParams
    ) -> FeedbackReplaceResponse: ...
    def feedback_stats(self, req: FeedbackStatsParams) -> FeedbackStatsResponse: ...
    def feedback_aggregate(
        self, req: FeedbackAggregateParams
    ) -> FeedbackAggregateResponse: ...
    def feedback_payload_schema(
        self, req: FeedbackPayloadSchemaParams
    ) -> FeedbackPayloadSchemaResponse: ...

    # Execute LLM API
    def completions_create(
        self, req: CompletionCreateParams
    ) -> CompletionCreateResponse: ...

    # Execute LLM API (Streaming)
    # Returns an iterator of JSON-serializable chunks that together form the streamed
    # response from the model provider. Each element must be a dictionary that can
    # be serialized with ``json.dumps``.
    def completions_create_stream(
        self, req: CompletionCreateStreamParams
    ) -> Iterator[dict[str, Any]]: ...

    # Execute Image Generation API
    def image_create(self, req: ImageCreateParams) -> ImageCreateResponse: ...

    # Project statistics API
    def project_stats(self, req: ProjectStatsParams) -> ProjectStatsResponse: ...

    # TTL settings API
    def project_ttl_settings_read(
        self, req: TtlSettingReadParams
    ) -> TtlSettingReadResponse: ...

    def project_ttl_settings_update(
        self, req: TtlSettingUpdateParams
    ) -> TtlSettingUpdateResponse: ...

    # Thread API
    def threads_query_stream(
        self, req: ThreadStreamQueryParams
    ) -> Iterator[ThreadStreamQueryResponse]: ...

    # Annotation Queue API
    def annotation_queue_create(
        self, req: AnnotationQueueCreateParams
    ) -> AnnotationQueueCreateResponse: ...

    def annotation_queues_query_stream(
        self, req: AnnotationQueueQueryParams
    ) -> Iterator[AnnotationQueueSchema]: ...

    def annotation_queue_read(
        self, req: QueueReadParams
    ) -> AnnotationQueueReadResponse: ...

    def annotation_queue_delete(
        self, req: QueueDeleteParams
    ) -> AnnotationQueueDeleteResponse: ...

    def annotation_queue_update(
        self, req: QueueUpdateParams
    ) -> AnnotationQueueUpdateResponse: ...

    def annotation_queue_add_calls(
        self, req: QueueAddCallsParams
    ) -> ItemAddResponse: ...

    def annotation_queues_stats(
        self, req: AnnotationQueueStatsParams
    ) -> AnnotationQueueStatsResponse: ...

    def annotation_queue_items_query(
        self, req: QueueItemsQueryParams
    ) -> ItemQueryResponse: ...

    def annotator_queue_items_progress_update(
        self,
        req: QueueItemProgressUpdateParams,
    ) -> ItemUpdateProgressResponse: ...

    # Dataset Sources API
    def dataset_sources_link(
        self, req: DatasetSourceLinkParams
    ) -> DatasetSourceLinkResponse: ...

    def dataset_sources_link_delete(
        self, req: Mapping[str, Any]
    ) -> DatasetSourcesLinkDeleteRes: ...

    def dataset_sources_query(
        self, req: DatasetSourceQueryParams
    ) -> DatasetSourceQueryResponse: ...

    def source_datasets_query(
        self, req: DatasetSourceSourceDatasetsQueryParams
    ) -> DatasetSourceSourceDatasetsQueryResponse: ...

    # Evaluation API
    def evaluate_model(
        self, req: EvaluationEvaluateModelParams
    ) -> EvaluationEvaluateModelResponse: ...
    def evaluation_status(
        self, req: EvaluationStatusParams
    ) -> EvaluationStatusResponse: ...
    def rescore(self, req: EvaluationRescoreParams) -> EvaluationRescoreResponse: ...

    # Scoring API
    def calls_score(self, req: CallScoreParams) -> object: ...
    def calls_complete(self, req: Mapping[str, Any]) -> object: ...

    # Ops
    def op_create(self, req: Mapping[str, Any]) -> V2OpCreateResponse: ...
    def op_read(self, req: Mapping[str, Any]) -> V2OpReadResponse: ...
    def op_list(self, req: Mapping[str, Any]) -> Iterator[V2OpListResponse]: ...
    def op_delete(self, req: Mapping[str, Any]) -> V2OpDeleteResponse: ...

    # Datasets
    def dataset_create(self, req: Mapping[str, Any]) -> V2DatasetCreateResponse: ...
    def dataset_read(self, req: Mapping[str, Any]) -> V2DatasetReadResponse: ...
    def dataset_list(
        self, req: Mapping[str, Any]
    ) -> Iterator[V2DatasetListResponse]: ...
    def dataset_delete(self, req: Mapping[str, Any]) -> V2DatasetDeleteResponse: ...

    # Custom Runtimes
    # The request names its project as project_id, which fills the route's
    # entity and project path parameters that the generated params require.
    def custom_runtime_apply(
        self, req: Mapping[str, Any]
    ) -> V2RuntimeApplyResponse: ...

    # Scorers
    def scorer_create(self, req: Mapping[str, Any]) -> V2ScorerCreateResponse: ...
    def scorer_read(self, req: Mapping[str, Any]) -> V2ScorerReadResponse: ...
    def scorer_list(self, req: Mapping[str, Any]) -> Iterator[V2ScorerListResponse]: ...
    def scorer_delete(self, req: Mapping[str, Any]) -> V2ScorerDeleteResponse: ...

    # Evaluations
    def evaluation_create(
        self, req: Mapping[str, Any]
    ) -> V2EvaluationCreateResponse: ...
    def evaluation_read(self, req: Mapping[str, Any]) -> V2EvaluationReadResponse: ...
    def evaluation_list(
        self, req: Mapping[str, Any]
    ) -> Iterator[V2EvaluationListResponse]: ...
    def evaluation_delete(
        self, req: Mapping[str, Any]
    ) -> V2EvaluationDeleteResponse: ...

    # Models
    def model_create(self, req: Mapping[str, Any]) -> V2ModelCreateResponse: ...
    def model_read(self, req: Mapping[str, Any]) -> V2ModelReadResponse: ...
    def model_list(self, req: Mapping[str, Any]) -> Iterator[V2ModelListResponse]: ...
    def model_delete(self, req: Mapping[str, Any]) -> V2ModelDeleteResponse: ...

    # Evaluation Runs
    def evaluation_run_create(
        self, req: Mapping[str, Any]
    ) -> V2EvaluationRunCreateResponse: ...
    def evaluation_run_read(
        self, req: Mapping[str, Any]
    ) -> V2EvaluationRunReadResponse: ...
    def evaluation_run_list(
        self, req: Mapping[str, Any]
    ) -> Iterator[V2EvaluationRunListResponse]: ...
    def evaluation_run_delete(
        self, req: Mapping[str, Any]
    ) -> V2EvaluationRunDeleteResponse: ...
    def evaluation_run_finish(
        self, req: Mapping[str, Any]
    ) -> V2EvaluationRunFinishResponse: ...

    # Predictions
    def prediction_create(
        self, req: Mapping[str, Any]
    ) -> V2PredictionCreateResponse: ...
    def prediction_read(self, req: Mapping[str, Any]) -> V2PredictionReadResponse: ...
    def prediction_list(
        self, req: Mapping[str, Any]
    ) -> Iterator[V2PredictionListResponse]: ...
    def prediction_delete(
        self, req: Mapping[str, Any]
    ) -> V2PredictionDeleteResponse: ...
    def prediction_finish(
        self, req: Mapping[str, Any]
    ) -> V2PredictionFinishResponse: ...

    # Scores
    def score_create(self, req: Mapping[str, Any]) -> V2ScoreCreateResponse: ...
    def score_read(self, req: Mapping[str, Any]) -> V2ScoreReadResponse: ...
    def score_list(self, req: Mapping[str, Any]) -> Iterator[V2ScoreListResponse]: ...
    def score_delete(self, req: Mapping[str, Any]) -> V2ScoreDeleteResponse: ...
    def eval_results_query(
        self, req: Mapping[str, Any]
    ) -> V2EvalResultQueryResponse: ...

    # Service API
    def server_info(self) -> ServerInfoRes: ...
    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes: ...
    def projects_info(
        self, req: ServiceProjectsInfoParams
    ) -> ServiceProjectsInfoResponse: ...
