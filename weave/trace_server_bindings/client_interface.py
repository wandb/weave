from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Protocol

from weave.shared import trace_server_interface as tsi
from weave.shared.agents import types as agent_types
from weave.shared.service_interface import ProjectsInfoReq
from weave.trace_server_bindings.models import (
    CallsQueryRes,
    DatasetSourcesLinkDeleteRes,
    EnsureProjectExistsRes,
)
from weave.vendor.weave_server_sdk.types import (
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
    ImageCreateParams,
    ImageCreateResponse,
    ProjectStatsParams,
    ProjectStatsResponse,
    ServerInfoRes,
    ServiceProjectsInfoParams,
    ServiceProjectsInfoResponse,
    ThreadStreamQueryParams,
    ThreadStreamQueryResponse,
    TraceUsageParams,
    TraceUsageResponse,
    V2RuntimeApplyResponse,
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
from weave.vendor.weave_server_sdk.types.projects import (
    TtlSettingReadParams,
    TtlSettingReadResponse,
    TtlSettingUpdateParams,
    TtlSettingUpdateResponse,
)


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
        self, req: agent_types.AgentSpansQueryReq
    ) -> agent_types.AgentSpansQueryRes: ...
    def agent_spans_stats(
        self, req: agent_types.AgentSpanStatsReq
    ) -> agent_types.AgentSpanStatsRes: ...
    def agent_custom_attrs_schema(
        self, req: agent_types.AgentCustomAttrsSchemaReq
    ) -> agent_types.AgentCustomAttrsSchemaRes: ...
    def agent_agents_query(
        self, req: agent_types.AgentsQueryReq
    ) -> agent_types.AgentsQueryRes: ...
    def agent_versions_query(
        self, req: agent_types.AgentVersionsQueryReq
    ) -> agent_types.AgentVersionsQueryRes: ...
    def agent_search(
        self, req: agent_types.AgentSearchReq
    ) -> agent_types.AgentSearchRes: ...
    def agent_traces_chat(
        self, req: agent_types.AgentTraceChatReq
    ) -> agent_types.AgentTraceChatRes: ...
    def agent_conversation_chat(
        self, req: agent_types.AgentConversationChatReq
    ) -> agent_types.AgentConversationChatRes: ...
    def agent_conversation_spans(
        self, req: agent_types.AgentConversationSpansReq
    ) -> agent_types.AgentConversationSpansRes: ...

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
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes: ...
    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes: ...
    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes: ...
    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes: ...

    # Tag and Alias API
    def obj_add_tags(self, req: tsi.ObjAddTagsReq) -> tsi.ObjAddTagsRes: ...
    def obj_remove_tags(self, req: tsi.ObjRemoveTagsReq) -> tsi.ObjRemoveTagsRes: ...
    def obj_set_aliases(self, req: tsi.ObjSetAliasesReq) -> tsi.ObjSetAliasesRes: ...
    def obj_remove_aliases(
        self, req: tsi.ObjRemoveAliasesReq
    ) -> tsi.ObjRemoveAliasesRes: ...
    def tags_list(self, req: tsi.TagsListReq) -> tsi.TagsListRes: ...
    def aliases_list(self, req: tsi.AliasesListReq) -> tsi.AliasesListRes: ...

    # Table API
    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes: ...
    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes: ...

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes: ...
    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes: ...
    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]: ...
    def table_query_stats(
        self, req: tsi.TableQueryStatsReq
    ) -> tsi.TableQueryStatsRes: ...
    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes: ...

    # Ref API
    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes: ...

    # File API
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes: ...
    def file_content_read(
        self, req: tsi.FileContentReadReq
    ) -> tsi.FileContentReadRes: ...
    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes: ...

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
    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes: ...
    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes: ...
    def op_list(self, req: tsi.OpListReq) -> Iterator[tsi.OpReadRes]: ...
    def op_delete(self, req: tsi.OpDeleteReq) -> tsi.OpDeleteRes: ...

    # Datasets
    def dataset_create(self, req: tsi.DatasetCreateReq) -> tsi.DatasetCreateRes: ...
    def dataset_read(self, req: tsi.DatasetReadReq) -> tsi.DatasetReadRes: ...
    def dataset_list(self, req: tsi.DatasetListReq) -> Iterator[tsi.DatasetReadRes]: ...
    def dataset_delete(self, req: tsi.DatasetDeleteReq) -> tsi.DatasetDeleteRes: ...

    # Custom Runtimes
    # The request names its project as project_id, which fills the route's
    # entity and project path parameters that the generated params require.
    def custom_runtime_apply(
        self, req: Mapping[str, Any] | tsi.CustomRuntimeApplyReq
    ) -> V2RuntimeApplyResponse: ...

    # Scorers
    def scorer_create(self, req: tsi.ScorerCreateReq) -> tsi.ScorerCreateRes: ...
    def scorer_read(self, req: tsi.ScorerReadReq) -> tsi.ScorerReadRes: ...
    def scorer_list(self, req: tsi.ScorerListReq) -> Iterator[tsi.ScorerReadRes]: ...
    def scorer_delete(self, req: tsi.ScorerDeleteReq) -> tsi.ScorerDeleteRes: ...

    # Evaluations
    def evaluation_create(
        self, req: tsi.EvaluationCreateReq
    ) -> tsi.EvaluationCreateRes: ...
    def evaluation_read(self, req: tsi.EvaluationReadReq) -> tsi.EvaluationReadRes: ...
    def evaluation_list(
        self, req: tsi.EvaluationListReq
    ) -> Iterator[tsi.EvaluationReadRes]: ...
    def evaluation_delete(
        self, req: tsi.EvaluationDeleteReq
    ) -> tsi.EvaluationDeleteRes: ...

    # Models
    def model_create(self, req: tsi.ModelCreateReq) -> tsi.ModelCreateRes: ...
    def model_read(self, req: tsi.ModelReadReq) -> tsi.ModelReadRes: ...
    def model_list(self, req: tsi.ModelListReq) -> Iterator[tsi.ModelReadRes]: ...
    def model_delete(self, req: tsi.ModelDeleteReq) -> tsi.ModelDeleteRes: ...

    # Evaluation Runs
    def evaluation_run_create(
        self, req: tsi.EvaluationRunCreateReq
    ) -> tsi.EvaluationRunCreateRes: ...
    def evaluation_run_read(
        self, req: tsi.EvaluationRunReadReq
    ) -> tsi.EvaluationRunReadRes: ...
    def evaluation_run_list(
        self, req: tsi.EvaluationRunListReq
    ) -> Iterator[tsi.EvaluationRunReadRes]: ...
    def evaluation_run_delete(
        self, req: tsi.EvaluationRunDeleteReq
    ) -> tsi.EvaluationRunDeleteRes: ...
    def evaluation_run_finish(
        self, req: tsi.EvaluationRunFinishReq
    ) -> tsi.EvaluationRunFinishRes: ...

    # Predictions
    def prediction_create(
        self, req: tsi.PredictionCreateReq
    ) -> tsi.PredictionCreateRes: ...
    def prediction_read(self, req: tsi.PredictionReadReq) -> tsi.PredictionReadRes: ...
    def prediction_list(
        self, req: tsi.PredictionListReq
    ) -> Iterator[tsi.PredictionReadRes]: ...
    def prediction_delete(
        self, req: tsi.PredictionDeleteReq
    ) -> tsi.PredictionDeleteRes: ...
    def prediction_finish(
        self, req: tsi.PredictionFinishReq
    ) -> tsi.PredictionFinishRes: ...

    # Scores
    def score_create(self, req: tsi.ScoreCreateReq) -> tsi.ScoreCreateRes: ...
    def score_read(self, req: tsi.ScoreReadReq) -> tsi.ScoreReadRes: ...
    def score_list(self, req: tsi.ScoreListReq) -> Iterator[tsi.ScoreReadRes]: ...
    def score_delete(self, req: tsi.ScoreDeleteReq) -> tsi.ScoreDeleteRes: ...
    def eval_results_query(
        self, req: tsi.EvalResultsQueryReq
    ) -> tsi.EvalResultsQueryRes: ...

    # Service API
    def server_info(self) -> ServerInfoRes: ...
    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes: ...
    def projects_info(
        self, req: ServiceProjectsInfoParams | ProjectsInfoReq
    ) -> ServiceProjectsInfoResponse: ...
