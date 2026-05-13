"""V2 Client Interface — Tier 3: SDK Transport

ClientInterface protocol for SDK-facing operations.

Implementations: DirectClient, RemoteHTTPClient, CachingClient.

This is the top tier — the contract that WeaveClient types against. It defines
what the SDK can call, independent of how the call reaches the server.

Key differences from ServiceInterface:
- No batch/v2 call methods (call_start_batch, calls_complete, call_start_v2,
  call_end_v2). Batching is an implementation detail of RemoteHTTPClient,
  hidden behind AsyncBatchProcessor.
- No otel_export. OTEL ingestion is a server-to-server concern.
- Includes service metadata (server_info, ensure_project_exists, projects_info)
  because the SDK needs these for initialization and project management.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol

from weave.trace_server.service_interface import (
    EnsureProjectExistsRes,
    ProjectsInfoReq,
    ProjectsInfoRes,
    ServerInfoRes,
)
from weave.trace_server.trace_server_interface import (
    # ── Action types ──────────────────────────────────────────────────
    ActionsExecuteBatchReq,
    ActionsExecuteBatchRes,
    # ── Tag & Alias types ─────────────────────────────────────────────
    AliasesListReq,
    AliasesListRes,
    # ── Annotation Queue types ────────────────────────────────────────
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
    # ── Call types ────────────────────────────────────────────────────
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
    CallsScoreReq,
    CallsScoreRes,
    CallStartReq,
    CallStartRes,
    CallStatsReq,
    CallStatsRes,
    CallsUsageReq,
    CallsUsageRes,
    CallUpdateReq,
    CallUpdateRes,
    # ── LLM proxy types ───────────────────────────────────────────────
    CompletionsCreateReq,
    CompletionsCreateRes,
    # ── Cost types ────────────────────────────────────────────────────
    CostCreateReq,
    CostCreateRes,
    CostPurgeReq,
    CostPurgeRes,
    CostQueryReq,
    CostQueryRes,
    DatasetCreateReq,
    DatasetCreateRes,
    DatasetDeleteReq,
    DatasetDeleteRes,
    DatasetListReq,
    DatasetReadReq,
    DatasetReadRes,
    EvalResultsQueryReq,
    EvalResultsQueryRes,
    # ── Evaluation orchestration types ────────────────────────────────
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
    # ── Feedback types ────────────────────────────────────────────────
    FeedbackCreateBatchReq,
    FeedbackCreateBatchRes,
    FeedbackCreateReq,
    FeedbackCreateRes,
    FeedbackPurgeReq,
    FeedbackPurgeRes,
    FeedbackQueryReq,
    FeedbackQueryRes,
    FeedbackReplaceReq,
    FeedbackReplaceRes,
    # ── File types ────────────────────────────────────────────────────
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
    # ── Object types ──────────────────────────────────────────────────
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
    # ── High-level object API types ───────────────────────────────────
    OpCreateReq,
    OpCreateRes,
    OpDeleteReq,
    OpDeleteRes,
    OpListReq,
    OpReadReq,
    OpReadRes,
    PredictionCreateReq,
    PredictionCreateRes,
    PredictionDeleteReq,
    PredictionDeleteRes,
    PredictionFinishReq,
    PredictionFinishRes,
    PredictionListReq,
    PredictionReadReq,
    PredictionReadRes,
    # ── Project Stats types ───────────────────────────────────────────
    ProjectStatsReq,
    ProjectStatsRes,
    # ── Ref types ─────────────────────────────────────────────────────
    RefsReadBatchReq,
    RefsReadBatchRes,
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
    # ── Table types ───────────────────────────────────────────────────
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
    # ── Thread types ──────────────────────────────────────────────────
    ThreadSchema,
    ThreadsQueryReq,
    TraceUsageReq,
    TraceUsageRes,
)


class ClientInterface(Protocol):
    """SDK transport protocol (Tier 3).

    Implementations: DirectClient, RemoteHTTPClient, CachingClient.

    This is what WeaveClient types against. It provides the full set of
    operations the SDK needs, hiding transport concerns like batching.

    NOT included (these are transport/server internals):
    - otel_export (server-to-server OTEL ingestion)
    - call_start_batch (server batch endpoint, used internally by transport)
    - calls_complete (server batch endpoint, used internally by transport)
    - call_start_v2 / call_end_v2 (server v2 endpoints, used internally)
    """

    # ── Service Metadata ──────────────────────────────────────────────

    def server_info(self) -> ServerInfoRes: ...

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes: ...

    def projects_info(self, req: ProjectsInfoReq) -> list[ProjectsInfoRes]: ...

    # ── Calls ─────────────────────────────────────────────────────────
    # SDK calls call_start/call_end. RemoteHTTPClient may internally
    # batch these into call_start_batch or calls_complete requests, but
    # that is invisible to the caller.

    def call_start(self, req: CallStartReq) -> CallStartRes: ...

    def call_end(self, req: CallEndReq) -> CallEndRes: ...

    def call_read(self, req: CallReadReq) -> CallReadRes: ...

    def calls_query(self, req: CallsQueryReq) -> CallsQueryRes: ...

    def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]: ...

    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes: ...

    def calls_query_stats(
        self, req: CallsQueryStatsReq
    ) -> CallsQueryStatsRes: ...

    def call_update(self, req: CallUpdateReq) -> CallUpdateRes: ...

    def call_stats(self, req: CallStatsReq) -> CallStatsRes: ...

    def trace_usage(self, req: TraceUsageReq) -> TraceUsageRes: ...

    def calls_usage(self, req: CallsUsageReq) -> CallsUsageRes: ...

    # ── Costs ─────────────────────────────────────────────────────────

    def cost_create(self, req: CostCreateReq) -> CostCreateRes: ...

    def cost_query(self, req: CostQueryReq) -> CostQueryRes: ...

    def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes: ...

    # ── Objects ───────────────────────────────────────────────────────

    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes: ...

    def obj_read(self, req: ObjReadReq) -> ObjReadRes: ...

    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes: ...

    def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes: ...

    # ── Tags & Aliases ────────────────────────────────────────────────

    def obj_add_tags(self, req: ObjAddTagsReq) -> ObjAddTagsRes: ...

    def obj_remove_tags(self, req: ObjRemoveTagsReq) -> ObjRemoveTagsRes: ...

    def obj_set_aliases(self, req: ObjSetAliasesReq) -> ObjSetAliasesRes: ...

    def obj_remove_aliases(
        self, req: ObjRemoveAliasesReq
    ) -> ObjRemoveAliasesRes: ...

    def tags_list(self, req: TagsListReq) -> TagsListRes: ...

    def aliases_list(self, req: AliasesListReq) -> AliasesListRes: ...

    # ── Tables ────────────────────────────────────────────────────────

    def table_create(self, req: TableCreateReq) -> TableCreateRes: ...

    def table_create_from_digests(
        self, req: TableCreateFromDigestsReq
    ) -> TableCreateFromDigestsRes: ...

    def table_update(self, req: TableUpdateReq) -> TableUpdateRes: ...

    def table_query(self, req: TableQueryReq) -> TableQueryRes: ...

    def table_query_stream(
        self, req: TableQueryReq
    ) -> Iterator[TableRowSchema]: ...

    def table_query_stats(
        self, req: TableQueryStatsReq
    ) -> TableQueryStatsRes: ...

    def table_query_stats_batch(
        self, req: TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchRes: ...

    # ── Refs ──────────────────────────────────────────────────────────

    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes: ...

    # ── Files ─────────────────────────────────────────────────────────

    def file_create(self, req: FileCreateReq) -> FileCreateRes: ...

    def file_content_read(
        self, req: FileContentReadReq
    ) -> FileContentReadRes: ...

    def files_stats(self, req: FilesStatsReq) -> FilesStatsRes: ...

    # ── Feedback ──────────────────────────────────────────────────────

    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes: ...

    def feedback_create_batch(
        self, req: FeedbackCreateBatchReq
    ) -> FeedbackCreateBatchRes: ...

    def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes: ...

    def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes: ...

    def feedback_replace(
        self, req: FeedbackReplaceReq
    ) -> FeedbackReplaceRes: ...

    # ── LLM Proxy ─────────────────────────────────────────────────────

    def completions_create(
        self, req: CompletionsCreateReq
    ) -> CompletionsCreateRes: ...

    def completions_create_stream(
        self, req: CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]: ...

    def image_create(
        self, req: ImageGenerationCreateReq
    ) -> ImageGenerationCreateRes: ...

    # ── Actions ───────────────────────────────────────────────────────

    def actions_execute_batch(
        self, req: ActionsExecuteBatchReq
    ) -> ActionsExecuteBatchRes: ...

    # ── Project Stats ─────────────────────────────────────────────────

    def project_stats(self, req: ProjectStatsReq) -> ProjectStatsRes: ...

    # ── Threads ───────────────────────────────────────────────────────

    def threads_query_stream(
        self, req: ThreadsQueryReq
    ) -> Iterator[ThreadSchema]: ...

    # ── Annotation Queues ─────────────────────────────────────────────

    def annotation_queue_create(
        self, req: AnnotationQueueCreateReq
    ) -> AnnotationQueueCreateRes: ...

    def annotation_queues_query_stream(
        self, req: AnnotationQueuesQueryReq
    ) -> Iterator[AnnotationQueueSchema]: ...

    def annotation_queue_read(
        self, req: AnnotationQueueReadReq
    ) -> AnnotationQueueReadRes: ...

    def annotation_queue_delete(
        self, req: AnnotationQueueDeleteReq
    ) -> AnnotationQueueDeleteRes: ...

    def annotation_queue_update(
        self, req: AnnotationQueueUpdateReq
    ) -> AnnotationQueueUpdateRes: ...

    def annotation_queue_add_calls(
        self, req: AnnotationQueueAddCallsReq
    ) -> AnnotationQueueAddCallsRes: ...

    def annotation_queues_stats(
        self, req: AnnotationQueuesStatsReq
    ) -> AnnotationQueuesStatsRes: ...

    def annotation_queue_items_query(
        self, req: AnnotationQueueItemsQueryReq
    ) -> AnnotationQueueItemsQueryRes: ...

    def annotator_queue_items_progress_update(
        self, req: AnnotatorQueueItemsProgressUpdateReq
    ) -> AnnotatorQueueItemsProgressUpdateRes: ...

    # ── Evaluation Orchestration ──────────────────────────────────────

    def evaluate_model(self, req: EvaluateModelReq) -> EvaluateModelRes: ...

    def evaluation_status(
        self, req: EvaluationStatusReq
    ) -> EvaluationStatusRes: ...

    def calls_score(self, req: CallsScoreReq) -> CallsScoreRes: ...

    # ── High-Level Object APIs ────────────────────────────────────────

    # Ops
    def op_create(self, req: OpCreateReq) -> OpCreateRes: ...
    def op_read(self, req: OpReadReq) -> OpReadRes: ...
    def op_list(self, req: OpListReq) -> Iterator[OpReadRes]: ...
    def op_delete(self, req: OpDeleteReq) -> OpDeleteRes: ...

    # Datasets
    def dataset_create(self, req: DatasetCreateReq) -> DatasetCreateRes: ...
    def dataset_read(self, req: DatasetReadReq) -> DatasetReadRes: ...
    def dataset_list(self, req: DatasetListReq) -> Iterator[DatasetReadRes]: ...
    def dataset_delete(self, req: DatasetDeleteReq) -> DatasetDeleteRes: ...

    # Scorers
    def scorer_create(self, req: ScorerCreateReq) -> ScorerCreateRes: ...
    def scorer_read(self, req: ScorerReadReq) -> ScorerReadRes: ...
    def scorer_list(self, req: ScorerListReq) -> Iterator[ScorerReadRes]: ...
    def scorer_delete(self, req: ScorerDeleteReq) -> ScorerDeleteRes: ...

    # Evaluations
    def evaluation_create(
        self, req: EvaluationCreateReq
    ) -> EvaluationCreateRes: ...
    def evaluation_read(
        self, req: EvaluationReadReq
    ) -> EvaluationReadRes: ...
    def evaluation_list(
        self, req: EvaluationListReq
    ) -> Iterator[EvaluationReadRes]: ...
    def evaluation_delete(
        self, req: EvaluationDeleteReq
    ) -> EvaluationDeleteRes: ...

    # Models
    def model_create(self, req: ModelCreateReq) -> ModelCreateRes: ...
    def model_read(self, req: ModelReadReq) -> ModelReadRes: ...
    def model_list(self, req: ModelListReq) -> Iterator[ModelReadRes]: ...
    def model_delete(self, req: ModelDeleteReq) -> ModelDeleteRes: ...

    # Evaluation Runs
    def evaluation_run_create(
        self, req: EvaluationRunCreateReq
    ) -> EvaluationRunCreateRes: ...
    def evaluation_run_read(
        self, req: EvaluationRunReadReq
    ) -> EvaluationRunReadRes: ...
    def evaluation_run_list(
        self, req: EvaluationRunListReq
    ) -> Iterator[EvaluationRunReadRes]: ...
    def evaluation_run_delete(
        self, req: EvaluationRunDeleteReq
    ) -> EvaluationRunDeleteRes: ...
    def evaluation_run_finish(
        self, req: EvaluationRunFinishReq
    ) -> EvaluationRunFinishRes: ...

    # Predictions
    def prediction_create(
        self, req: PredictionCreateReq
    ) -> PredictionCreateRes: ...
    def prediction_read(
        self, req: PredictionReadReq
    ) -> PredictionReadRes: ...
    def prediction_list(
        self, req: PredictionListReq
    ) -> Iterator[PredictionReadRes]: ...
    def prediction_delete(
        self, req: PredictionDeleteReq
    ) -> PredictionDeleteRes: ...
    def prediction_finish(
        self, req: PredictionFinishReq
    ) -> PredictionFinishRes: ...

    # Scores
    def score_create(self, req: ScoreCreateReq) -> ScoreCreateRes: ...
    def score_read(self, req: ScoreReadReq) -> ScoreReadRes: ...
    def score_list(self, req: ScoreListReq) -> Iterator[ScoreReadRes]: ...
    def score_delete(self, req: ScoreDeleteReq) -> ScoreDeleteRes: ...

    # Eval Results
    def eval_results_query(
        self, req: EvalResultsQueryReq
    ) -> EvalResultsQueryRes: ...
