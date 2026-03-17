"""V2 Service Interface — Tier 2: Business Logic

ServiceInterface protocol for server-side business operations.

Implementations: TraceService (initially delegation to v1, later real impl).

This is the middle tier. It provides all StorageInterface methods (by
delegating to a storage backend) plus additional operations that involve
business logic, orchestration, or external service calls:

- OTEL span transformation
- Call batch coordination
- LLM proxy (completions, image generation)
- Action execution
- Evaluation orchestration and scoring
- High-level object APIs (ops, datasets, scorers, evaluations, models,
  evaluation runs, predictions, scores)
- Service metadata (server info, project management)
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
    # ── Call batch / v2 types ─────────────────────────────────────────
    CallCreateBatchReq,
    CallCreateBatchRes,
    CallEndV2Req,
    CallEndV2Res,
    CallsScoreReq,
    CallsScoreRes,
    CallStartV2Req,
    CallStartV2Res,
    CallsUpsertCompleteReq,
    CallsUpsertCompleteRes,
    # ── LLM proxy types ───────────────────────────────────────────────
    CompletionsCreateReq,
    CompletionsCreateRes,
    # ── High-level object API types: Datasets ─────────────────────────
    DatasetCreateReq,
    DatasetCreateRes,
    DatasetDeleteReq,
    DatasetDeleteRes,
    DatasetListReq,
    DatasetReadReq,
    DatasetReadRes,
    # ── Eval Results ──────────────────────────────────────────────────
    EvalResultsQueryReq,
    EvalResultsQueryRes,
    # ── Evaluation orchestration types ────────────────────────────────
    EvaluateModelReq,
    EvaluateModelRes,
    # ── High-level object API types: Evaluations ─────────────────────
    EvaluationCreateReq,
    EvaluationCreateRes,
    EvaluationDeleteReq,
    EvaluationDeleteRes,
    EvaluationListReq,
    EvaluationReadReq,
    EvaluationReadRes,
    # ── High-level object API types: Evaluation Runs ──────────────────
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
    ImageGenerationCreateReq,
    ImageGenerationCreateRes,
    # ── High-level object API types: Models ───────────────────────────
    ModelCreateReq,
    ModelCreateRes,
    ModelDeleteReq,
    ModelDeleteRes,
    ModelListReq,
    ModelReadReq,
    ModelReadRes,
    # ── High-level object API types: Ops ──────────────────────────────
    OpCreateReq,
    OpCreateRes,
    OpDeleteReq,
    OpDeleteRes,
    OpListReq,
    OpReadReq,
    OpReadRes,
    # ── OTEL types ────────────────────────────────────────────────────
    OTelExportReq,
    OTelExportRes,
    # ── High-level object API types: Predictions ─────────────────────
    PredictionCreateReq,
    PredictionCreateRes,
    PredictionDeleteReq,
    PredictionDeleteRes,
    PredictionFinishReq,
    PredictionFinishRes,
    PredictionListReq,
    PredictionReadReq,
    PredictionReadRes,
    # ── High-level object API types: Scores ───────────────────────────
    ScoreCreateReq,
    ScoreCreateRes,
    ScoreDeleteReq,
    ScoreDeleteRes,
    ScoreListReq,
    # ── High-level object API types: Scorers ──────────────────────────
    ScorerCreateReq,
    ScorerCreateRes,
    ScorerDeleteReq,
    ScorerDeleteRes,
    ScoreReadReq,
    ScoreReadRes,
    ScorerListReq,
    ScorerReadReq,
    ScorerReadRes,
)
from weave.trace_server.v2.storage_interface import StorageInterface


class ServiceInterface(StorageInterface, Protocol):
    """Business-logic protocol (Tier 2).

    Implementations: TraceService.

    Inherits all StorageInterface methods (the service layer provides them by
    delegating to a storage backend) and adds operations that involve business
    logic, orchestration, or external service calls.

    The service layer is where:
    - OTEL spans are transformed into call data
    - Batch operations are coordinated
    - LLM completions/image generation are proxied
    - Actions are executed
    - Evaluations are orchestrated
    - High-level object APIs are implemented on top of core obj_create/obj_read
    """

    # ── Service Metadata ──────────────────────────────────────────────

    def server_info(self) -> ServerInfoRes: ...

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes: ...

    def projects_info(self, req: ProjectsInfoReq) -> list[ProjectsInfoRes]: ...

    # ── OTEL ──────────────────────────────────────────────────────────

    def otel_export(self, req: OTelExportReq) -> OTelExportRes: ...

    # ── Call Batch / V2 ───────────────────────────────────────────────
    # These are server-side batch endpoints. The SDK does not call them
    # directly — RemoteHTTPClient uses them internally for batching.

    def call_start_batch(
        self, req: CallCreateBatchReq
    ) -> CallCreateBatchRes: ...

    def calls_complete(
        self, req: CallsUpsertCompleteReq
    ) -> CallsUpsertCompleteRes: ...

    def call_start_v2(self, req: CallStartV2Req) -> CallStartV2Res: ...

    def call_end_v2(self, req: CallEndV2Req) -> CallEndV2Res: ...

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

    # ── Evaluation Orchestration ──────────────────────────────────────

    def evaluate_model(self, req: EvaluateModelReq) -> EvaluateModelRes: ...

    def evaluation_status(
        self, req: EvaluationStatusReq
    ) -> EvaluationStatusRes: ...

    def calls_score(self, req: CallsScoreReq) -> CallsScoreRes: ...

    # ── High-Level Object APIs ────────────────────────────────────────
    # These provide domain-specific interfaces on top of the generic
    # obj_create/obj_read/objs_query storage methods.

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
