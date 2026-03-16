"""Service interface (Tier 2) — business logic layer.

Operates on API request/response types (CallStartReq, ObjCreateReq, etc.).
Consumes StorageInterface internally. Handles:
  - Request validation and processing
  - ID translation (external ↔ internal)
  - Ref conversion
  - Orchestration (op_create = file_create + obj_create + read-back)
  - Write-target routing
  - Project management, server metadata

Implementor: TraceService (composes StorageInterface + IdConverter)
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
    # Calls
    CallEndReq,
    CallEndRes,
    CallReadReq,
    CallReadRes,
    CallSchema,
    CallsDeleteReq,
    CallsDeleteRes,
    CallsQueryReq,
    CallsQueryStatsReq,
    CallsQueryStatsRes,
    CallStartReq,
    CallStartRes,
    CallStartV2Req,
    CallStartV2Res,
    CallsUpsertCompleteReq,
    CallsUpsertCompleteRes,
    CallUpdateReq,
    CallUpdateRes,
    # Objects
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
    # Tables
    RefsReadBatchReq,
    RefsReadBatchRes,
    TableCreateFromDigestsReq,
    TableCreateFromDigestsRes,
    TableCreateReq,
    TableCreateRes,
    TableQueryReq,
    TableQueryRes,
    TableQueryStatsReq,
    TableQueryStatsRes,
    TableUpdateReq,
    TableUpdateRes,
    # Metadata
    AliasesListReq,
    AliasesListRes,
    TagsListReq,
    TagsListRes,
    # Files
    FileContentReadReq,
    FileContentReadRes,
    FileCreateReq,
    FileCreateRes,
    # Feedback
    FeedbackCreateReq,
    FeedbackCreateRes,
    # Costs
    CostCreateReq,
    CostCreateRes,
    CostPurgeReq,
    CostPurgeRes,
    CostQueryReq,
    CostQueryRes,
    # Object API (op, dataset, scorer, evaluation, model, etc.)
    OpCreateReq,
    OpCreateRes,
    OpReadReq,
    OpReadRes,
    OpListReq,
    OpDeleteReq,
    OpDeleteRes,
    DatasetCreateReq,
    DatasetCreateRes,
    DatasetReadReq,
    DatasetReadRes,
    DatasetListReq,
    DatasetDeleteReq,
    DatasetDeleteRes,
    ScorerCreateReq,
    ScorerCreateRes,
    ScorerReadReq,
    ScorerReadRes,
    ScorerListReq,
    ScorerDeleteReq,
    ScorerDeleteRes,
    EvaluationCreateReq,
    EvaluationCreateRes,
    EvaluationReadReq,
    EvaluationReadRes,
    EvaluationListReq,
    EvaluationDeleteReq,
    EvaluationDeleteRes,
    ModelCreateReq,
    ModelCreateRes,
    ModelReadReq,
    ModelReadRes,
    ModelListReq,
    ModelDeleteReq,
    ModelDeleteRes,
    EvaluationRunCreateReq,
    EvaluationRunCreateRes,
    EvaluationRunReadReq,
    EvaluationRunReadRes,
    EvaluationRunListReq,
    EvaluationRunDeleteReq,
    EvaluationRunDeleteRes,
    EvaluationRunFinishReq,
    EvaluationRunFinishRes,
    PredictionCreateReq,
    PredictionCreateRes,
    PredictionReadReq,
    PredictionReadRes,
    PredictionListReq,
    PredictionDeleteReq,
    PredictionDeleteRes,
    PredictionFinishReq,
    PredictionFinishRes,
    ScoreCreateReq,
    ScoreCreateRes,
    ScoreReadReq,
    ScoreReadRes,
    ScoreListReq,
    ScoreDeleteReq,
    ScoreDeleteRes,
    EvalResultsQueryReq,
    EvalResultsQueryRes,
)


class ServiceInterface(Protocol):
    """Business logic for the trace service.

    Takes API request types, validates, processes, orchestrates,
    and delegates to StorageInterface for data access.

    This is what the HTTP handler layer calls. It is also what
    DirectClient wraps for tests (skipping HTTP).
    """

    # ── Service ──────────────────────────────────────────────────────

    def server_info(self) -> ServerInfoRes: ...
    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes: ...
    def projects_info(self, req: ProjectsInfoReq) -> list[ProjectsInfoRes]: ...

    # ── Calls ────────────────────────────────────────────────────────

    def call_start(self, req: CallStartReq) -> CallStartRes: ...
    def call_end(self, req: CallEndReq) -> CallEndRes: ...
    def call_start_v2(self, req: CallStartV2Req) -> CallStartV2Res: ...
    def calls_complete(
        self, req: CallsUpsertCompleteReq
    ) -> CallsUpsertCompleteRes: ...
    def call_read(self, req: CallReadReq) -> CallReadRes: ...
    def call_update(self, req: CallUpdateReq) -> CallUpdateRes: ...
    def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]: ...
    def calls_query_stats(
        self, req: CallsQueryStatsReq
    ) -> CallsQueryStatsRes: ...
    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes: ...

    # ── Objects ──────────────────────────────────────────────────────

    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes: ...
    def obj_read(self, req: ObjReadReq) -> ObjReadRes: ...
    def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes: ...
    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes: ...
    def obj_add_tags(self, req: ObjAddTagsReq) -> ObjAddTagsRes: ...
    def obj_remove_tags(self, req: ObjRemoveTagsReq) -> ObjRemoveTagsRes: ...
    def obj_set_aliases(self, req: ObjSetAliasesReq) -> ObjSetAliasesRes: ...
    def obj_remove_aliases(
        self, req: ObjRemoveAliasesReq
    ) -> ObjRemoveAliasesRes: ...
    def tags_list(self, req: TagsListReq) -> TagsListRes: ...
    def aliases_list(self, req: AliasesListReq) -> AliasesListRes: ...

    # ── Tables ───────────────────────────────────────────────────────

    def table_create(self, req: TableCreateReq) -> TableCreateRes: ...
    def table_create_from_digests(
        self, req: TableCreateFromDigestsReq
    ) -> TableCreateFromDigestsRes: ...
    def table_update(self, req: TableUpdateReq) -> TableUpdateRes: ...
    def table_query(self, req: TableQueryReq) -> TableQueryRes: ...
    def table_query_stats(
        self, req: TableQueryStatsReq
    ) -> TableQueryStatsRes: ...
    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes: ...

    # ── Files ────────────────────────────────────────────────────────

    def file_create(self, req: FileCreateReq) -> FileCreateRes: ...
    def file_content_read(
        self, req: FileContentReadReq
    ) -> FileContentReadRes: ...

    # ── Feedback ─────────────────────────────────────────────────────

    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes: ...

    # ── Costs ────────────────────────────────────────────────────────

    def cost_create(self, req: CostCreateReq) -> CostCreateRes: ...
    def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes: ...
    def cost_query(self, req: CostQueryReq) -> CostQueryRes: ...

    # ── Object API (orchestrated operations) ─────────────────────────
    # These are NOT thin CRUD. op_create creates a file, builds a
    # payload, creates an object, and reads it back. dataset_create
    # creates a table and an object. etc.

    def op_create(self, req: OpCreateReq) -> OpCreateRes: ...
    def op_read(self, req: OpReadReq) -> OpReadRes: ...
    def op_list(self, req: OpListReq) -> Iterator[OpReadRes]: ...
    def op_delete(self, req: OpDeleteReq) -> OpDeleteRes: ...

    def dataset_create(self, req: DatasetCreateReq) -> DatasetCreateRes: ...
    def dataset_read(self, req: DatasetReadReq) -> DatasetReadRes: ...
    def dataset_list(self, req: DatasetListReq) -> Iterator[DatasetReadRes]: ...
    def dataset_delete(self, req: DatasetDeleteReq) -> DatasetDeleteRes: ...

    def scorer_create(self, req: ScorerCreateReq) -> ScorerCreateRes: ...
    def scorer_read(self, req: ScorerReadReq) -> ScorerReadRes: ...
    def scorer_list(self, req: ScorerListReq) -> Iterator[ScorerReadRes]: ...
    def scorer_delete(self, req: ScorerDeleteReq) -> ScorerDeleteRes: ...

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

    def model_create(self, req: ModelCreateReq) -> ModelCreateRes: ...
    def model_read(self, req: ModelReadReq) -> ModelReadRes: ...
    def model_list(self, req: ModelListReq) -> Iterator[ModelReadRes]: ...
    def model_delete(self, req: ModelDeleteReq) -> ModelDeleteRes: ...

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

    def score_create(self, req: ScoreCreateReq) -> ScoreCreateRes: ...
    def score_read(self, req: ScoreReadReq) -> ScoreReadRes: ...
    def score_list(self, req: ScoreListReq) -> Iterator[ScoreReadRes]: ...
    def score_delete(self, req: ScoreDeleteReq) -> ScoreDeleteRes: ...

    def eval_results_query(
        self, req: EvalResultsQueryReq
    ) -> EvalResultsQueryRes: ...
