"""Object Interface protocol and models for Trace Server.

This module contains the ObjectInterface protocol and all related request/response
models for the object-oriented APIs (Ops, Datasets, Scorers, Evaluations, Models,
Evaluation Runs, Predictions, and Scores).
"""

import datetime
from collections.abc import Iterator
from typing import Any, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field

WB_USER_ID_DESCRIPTION = (
    "Do not set directly. Server will automatically populate this field."
)


class BaseModelStrict(BaseModel):
    """Base model with strict validation that forbids extra fields."""

    model_config = ConfigDict(extra="forbid")


# ============================================================================
# Op API Models
# ============================================================================


class OpCreateBody(BaseModel):
    """Request body for creating an Op object via REST API.

    This model excludes project_id since it comes from the URL path in RESTful endpoints.
    """

    name: Optional[str] = Field(
        None,
        description="The name of this op. Ops with the same name will be versioned together.",
    )
    source_code: Optional[str] = Field(
        None, description="Complete source code for this op, including imports"
    )


class OpCreateReq(OpCreateBody):
    """Request model for creating an Op object.

    Extends OpCreateBody by adding project_id for internal API usage.
    """

    project_id: str = Field(
        ..., description="The project where this object will be saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class OpCreateRes(BaseModel):
    """Response model for creating an Op object."""

    digest: str = Field(..., description="The digest of the created op")
    object_id: str = Field(..., description="The ID of the created op")
    version_index: int = Field(..., description="The version index of the created op")


class OpReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this op is saved"
    )
    object_id: str = Field(..., description="The op ID")
    digest: str = Field(..., description="The digest of the op object")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class OpReadRes(BaseModel):
    """Response model for reading an Op object.

    The code field contains the actual source code of the op.
    """

    object_id: str = Field(..., description="The op ID")
    digest: str = Field(..., description="The digest of the op")
    version_index: int = Field(..., description="The version index of this op")
    created_at: datetime.datetime = Field(..., description="When this op was created")
    code: str = Field(..., description="The actual op source code")


class OpListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these ops are saved"
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of ops to return"
    )
    offset: Optional[int] = Field(default=None, description="Number of ops to skip")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class OpDeleteReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this op is saved"
    )
    object_id: str = Field(..., description="The op ID")
    digests: Optional[list[str]] = Field(
        default=None,
        description="List of digests to delete. If not provided, all digests for the op will be deleted.",
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class OpDeleteRes(BaseModel):
    num_deleted: int = Field(
        ..., description="Number of op versions deleted from this op"
    )


# ============================================================================
# Dataset API Models
# ============================================================================


class DatasetCreateBody(BaseModel):
    name: Optional[str] = Field(
        None,
        description="The name of this dataset.  Datasets with the same name will be versioned together.",
    )
    description: Optional[str] = Field(
        None,
        description="A description of this dataset",
    )
    rows: list[dict[str, Any]] = Field(..., description="Dataset rows")


class DatasetCreateReq(DatasetCreateBody):
    project_id: str = Field(
        ..., description="The `entity/project` where this dataset will be saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class DatasetCreateRes(BaseModel):
    digest: str = Field(..., description="The digest of the created dataset")
    object_id: str = Field(..., description="The ID of the created dataset")
    version_index: int = Field(
        ..., description="The version index of the created dataset"
    )


class DatasetReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this dataset is saved"
    )
    object_id: str = Field(..., description="The dataset ID")
    digest: str = Field(..., description="The digest of the dataset object")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class DatasetReadRes(BaseModel):
    object_id: str = Field(..., description="The dataset ID")
    digest: str = Field(..., description="The digest of the dataset object")
    version_index: int = Field(..., description="The version index of the object")
    created_at: datetime.datetime = Field(
        ..., description="When the object was created"
    )
    name: str = Field(..., description="The name of the dataset")
    description: Optional[str] = Field(None, description="Description of the dataset")
    rows: str = Field(
        ...,
        description="Reference to the dataset rows data",
    )


class DatasetListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these datasets are saved"
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of datasets to return"
    )
    offset: Optional[int] = Field(
        default=None, description="Number of datasets to skip"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class DatasetDeleteReq(BaseModelStrict):
    project_id: str = Field(
        ..., description="The `entity/project` where this dataset is saved"
    )
    object_id: str = Field(..., description="The dataset ID")
    digests: Optional[list[str]] = Field(
        default=None,
        description="List of digests to delete. If not provided, all digests for the dataset will be deleted.",
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class DatasetDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="Number of dataset versions deleted")


# ============================================================================
# Scorer API Models
# ============================================================================


class ScorerCreateBody(BaseModel):
    name: str = Field(
        ...,
        description="The name of this scorer.  Scorers with the same name will be versioned together.",
    )
    description: Optional[str] = Field(
        None,
        description="A description of this scorer",
    )
    op_source_code: str = Field(
        ...,
        description="Complete source code for the Scorer.score op including imports",
    )


class ScorerCreateReq(ScorerCreateBody):
    project_id: str = Field(
        ..., description="The `entity/project` where this scorer will be saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScorerCreateRes(BaseModel):
    digest: str = Field(..., description="The digest of the created scorer")
    object_id: str = Field(..., description="The ID of the created scorer")
    version_index: int = Field(
        ..., description="The version index of the created scorer"
    )
    scorer: str = Field(
        ...,
        description="Full reference to the created scorer",
    )


class ScorerReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this scorer is saved"
    )
    object_id: str = Field(..., description="The scorer ID")
    digest: str = Field(..., description="The digest of the scorer")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScorerReadRes(BaseModel):
    object_id: str = Field(..., description="The scorer ID")
    digest: str = Field(..., description="The digest of the scorer")
    version_index: int = Field(..., description="The version index of the object")
    created_at: datetime.datetime = Field(
        ..., description="When the scorer was created"
    )
    name: str = Field(..., description="The name of the scorer")
    description: Optional[str] = Field(None, description="Description of the scorer")
    score_op: str = Field(
        ...,
        description="The Scorer.score op reference",
    )


class ScorerListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these scorers are saved"
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of scorers to return"
    )
    offset: Optional[int] = Field(default=None, description="Number of scorers to skip")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScorerDeleteReq(BaseModelStrict):
    project_id: str = Field(
        ..., description="The `entity/project` where this scorer is saved"
    )
    object_id: str = Field(..., description="The scorer ID")
    digests: Optional[list[str]] = Field(
        default=None,
        description="List of digests to delete. If not provided, all digests for the scorer will be deleted",
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScorerDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="Number of scorer versions deleted")


# ============================================================================
# Evaluation API Models
# ============================================================================


class EvaluationCreateBody(BaseModel):
    name: str = Field(
        ...,
        description="The name of this evaluation.  Evaluations with the same name will be versioned together.",
    )
    description: Optional[str] = Field(
        None,
        description="A description of this evaluation",
    )

    dataset: str = Field(..., description="Reference to the dataset (weave:// URI)")
    scorers: Optional[list[str]] = Field(
        None, description="List of scorer references (weave:// URIs)"
    )

    trials: int = Field(default=1, description="Number of trials to run")
    evaluation_name: Optional[str] = Field(
        None, description="Name for the evaluation run"
    )
    eval_attributes: Optional[dict[str, Any]] = Field(
        None, description="Optional attributes for the evaluation"
    )


class EvaluationCreateReq(EvaluationCreateBody):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation will be saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationCreateRes(BaseModel):
    digest: str = Field(..., description="The digest of the created evaluation")
    object_id: str = Field(..., description="The ID of the created evaluation")
    version_index: int = Field(
        ..., description="The version index of the created evaluation"
    )
    evaluation_ref: str = Field(
        ..., description="Full reference to the created evaluation"
    )


class EvaluationReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation is saved"
    )
    object_id: str = Field(..., description="The evaluation ID")
    digest: str = Field(..., description="The digest of the evaluation")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationReadRes(BaseModel):
    object_id: str = Field(..., description="The evaluation ID")
    digest: str = Field(..., description="The digest of the evaluation")
    version_index: int = Field(..., description="The version index of the evaluation")
    created_at: datetime.datetime = Field(
        ..., description="When the evaluation was created"
    )
    name: str = Field(..., description="The name of the evaluation")
    description: Optional[str] = Field(
        None, description="A description of the evaluation"
    )
    dataset: str = Field(..., description="Dataset reference (weave:// URI)")
    scorers: list[str] = Field(
        ..., description="List of scorer references (weave:// URIs)"
    )
    trials: int = Field(..., description="Number of trials")
    evaluation_name: Optional[str] = Field(
        None, description="Name for the evaluation run"
    )
    evaluate_op: Optional[str] = Field(
        None, description="Evaluate op reference (weave:// URI)"
    )
    predict_and_score_op: Optional[str] = Field(
        None, description="Predict and score op reference (weave:// URI)"
    )
    summarize_op: Optional[str] = Field(
        None, description="Summarize op reference (weave:// URI)"
    )


class EvaluationListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these evaluations are saved"
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of evaluations to return"
    )
    offset: Optional[int] = Field(
        default=None, description="Number of evaluations to skip"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationDeleteReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation is saved"
    )
    object_id: str = Field(..., description="The evaluation ID")
    digests: Optional[list[str]] = Field(
        default=None,
        description="List of digests to delete. If not provided, all digests for the evaluation will be deleted.",
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="Number of evaluation versions deleted")


# ============================================================================
# Model API Models
# ============================================================================


class ModelCreateBody(BaseModel):
    name: str = Field(
        ...,
        description="The name of this model. Models with the same name will be versioned together.",
    )
    description: Optional[str] = Field(
        None,
        description="A description of this model",
    )
    source_code: str = Field(
        ...,
        description="Complete source code for the Model class including imports",
    )
    attributes: Optional[dict[str, Any]] = Field(
        None,
        description="Additional attributes to be stored with the model",
    )


class ModelCreateReq(ModelCreateBody):
    project_id: str = Field(
        ..., description="The `entity/project` where this model will be saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ModelCreateRes(BaseModel):
    digest: str = Field(..., description="The digest of the created model")
    object_id: str = Field(..., description="The ID of the created model")
    version_index: int = Field(
        ..., description="The version index of the created model"
    )
    model_ref: str = Field(
        ...,
        description="Full reference to the created model",
    )


class ModelReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this model is saved"
    )
    object_id: str = Field(..., description="The model ID")
    digest: str = Field(..., description="The digest of the model object")


class ModelReadRes(BaseModel):
    object_id: str = Field(..., description="The model ID")
    digest: str = Field(..., description="The digest of the model")
    version_index: int = Field(..., description="The version index of the object")
    created_at: datetime.datetime = Field(..., description="When the model was created")
    name: str = Field(..., description="The name of the model")
    description: Optional[str] = Field(None, description="Description of the model")
    source_code: str = Field(
        ...,
        description="The source code of the model",
    )
    attributes: Optional[dict[str, Any]] = Field(
        None, description="Additional attributes stored with the model"
    )


class ModelListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these models are saved"
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of models to return"
    )
    offset: Optional[int] = Field(default=None, description="Number of models to skip")


class ModelDeleteReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this model is saved"
    )
    object_id: str = Field(..., description="The model ID")
    digests: Optional[list[str]] = Field(
        None,
        description="List of model digests to delete. If None, deletes all versions.",
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ModelDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="Number of model versions deleted")


# ============================================================================
# Evaluation Run API Models
# ============================================================================


class EvaluationRunCreateBody(BaseModel):
    evaluation: str = Field(
        ..., description="Reference to the evaluation (weave:// URI)"
    )
    model: str = Field(..., description="Reference to the model (weave:// URI)")


class EvaluationRunCreateReq(EvaluationRunCreateBody):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation run will be saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationRunCreateRes(BaseModel):
    evaluation_run_id: str = Field(
        ..., description="The ID of the created evaluation run"
    )


class EvaluationRunReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation run is saved"
    )
    evaluation_run_id: str = Field(..., description="The evaluation run ID")


class EvaluationRunReadRes(BaseModel):
    evaluation_run_id: str = Field(..., description="The evaluation run ID")
    evaluation: str = Field(
        ..., description="Reference to the evaluation (weave:// URI)"
    )
    model: str = Field(..., description="Reference to the model (weave:// URI)")
    status: Optional[str] = Field(None, description="Status of the evaluation run")
    started_at: Optional[datetime.datetime] = Field(
        None, description="When the evaluation run started"
    )
    finished_at: Optional[datetime.datetime] = Field(
        None, description="When the evaluation run finished"
    )
    summary: Optional[dict[str, Any]] = Field(
        None, description="Summary data for the evaluation run"
    )


class EvaluationRunFilter(BaseModel):
    evaluations: Optional[list[str]] = Field(
        None, description="Filter by evaluation references"
    )
    models: Optional[list[str]] = Field(None, description="Filter by model references")
    evaluation_run_ids: Optional[list[str]] = Field(
        None, description="Filter by evaluation run IDs"
    )


class EvaluationRunListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these evaluation runs are saved"
    )
    filter: Optional[EvaluationRunFilter] = Field(
        None, description="Filter criteria for evaluation runs"
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of evaluation runs to return"
    )
    offset: Optional[int] = Field(
        default=None, description="Number of evaluation runs to skip"
    )


class EvaluationRunDeleteReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these evaluation runs exist"
    )
    evaluation_run_ids: list[str] = Field(
        ..., description="List of evaluation run IDs to delete"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationRunDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="Number of evaluation runs deleted")


class EvaluationRunFinishBody(BaseModel):
    """Request body for finishing an evaluation run via REST API.

    This model excludes project_id and evaluation_run_id since they come from the URL path in RESTful endpoints.
    """

    summary: Optional[dict[str, Any]] = Field(
        None, description="Optional summary dictionary for the evaluation run"
    )


class EvaluationRunFinishReq(EvaluationRunFinishBody):
    project_id: str = Field(
        ..., description="The `entity/project` where these evaluation runs exist"
    )
    evaluation_run_id: str = Field(..., description="The evaluation run ID to finish")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationRunFinishRes(BaseModel):
    success: bool = Field(
        ..., description="Whether the evaluation run was finished successfully"
    )


# ============================================================================
# Prediction API Models
# ============================================================================


class PredictionCreateBody(BaseModel):
    """Request body for creating a Prediction via REST API.

    This model excludes project_id since it comes from the URL path in RESTful endpoints.
    """

    model: str = Field(..., description="The model reference (weave:// URI)")
    inputs: dict[str, Any] = Field(..., description="The inputs to the prediction")
    output: Any = Field(..., description="The output of the prediction")
    evaluation_run_id: Optional[str] = Field(
        None,
        description="Optional evaluation run ID to link this prediction as a child call",
    )


class PredictionCreateReq(PredictionCreateBody):
    """Request model for creating a Prediction.

    Extends PredictionCreateBody by adding project_id for internal API usage.
    """

    project_id: str = Field(
        ..., description="The `entity/project` where this prediction is saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionCreateRes(BaseModel):
    prediction_id: str = Field(..., description="The prediction ID")


class PredictionReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this prediction is saved"
    )
    prediction_id: str = Field(..., description="The prediction ID")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionReadRes(BaseModel):
    prediction_id: str = Field(..., description="The prediction ID")
    model: str = Field(..., description="The model reference (weave:// URI)")
    inputs: dict[str, Any] = Field(..., description="The inputs to the prediction")
    output: Any = Field(..., description="The output of the prediction")
    evaluation_run_id: Optional[str] = Field(
        None, description="Evaluation run ID if this prediction is linked to one"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these predictions are saved"
    )
    evaluation_run_id: Optional[str] = Field(
        None,
        description="Optional evaluation run ID to filter predictions linked to this run",
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of predictions to return"
    )
    offset: Optional[int] = Field(
        default=None, description="Number of predictions to skip"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionListRes(BaseModel):
    predictions: list[PredictionReadRes] = Field(..., description="The predictions")


class PredictionDeleteReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these predictions are saved"
    )
    prediction_ids: list[str] = Field(..., description="The prediction IDs to delete")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="Number of predictions deleted")


class PredictionFinishReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this prediction is saved"
    )
    prediction_id: str = Field(..., description="The prediction ID to finish")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionFinishRes(BaseModel):
    success: bool = Field(
        ..., description="Whether the prediction was finished successfully"
    )


# ============================================================================
# Score API Models
# ============================================================================


class ScoreCreateBody(BaseModel):
    """Request body for creating a Score via REST API.

    This model excludes project_id since it comes from the URL path in RESTful endpoints.
    """

    prediction_id: str = Field(..., description="The prediction ID")
    scorer: str = Field(..., description="The scorer reference (weave:// URI)")
    value: float = Field(..., description="The value of the score")
    evaluation_run_id: Optional[str] = Field(
        None,
        description="Optional evaluation run ID to link this score as a child call",
    )


class ScoreCreateReq(ScoreCreateBody):
    """Request model for creating a Score.

    Extends ScoreCreateBody by adding project_id for internal API usage.
    """

    project_id: str = Field(
        ..., description="The `entity/project` where this score is saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreCreateRes(BaseModel):
    score_id: str = Field(..., description="The score ID")


class ScoreReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this score is saved"
    )
    score_id: str = Field(..., description="The score ID")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreReadRes(BaseModel):
    score_id: str = Field(..., description="The score ID")
    scorer: str = Field(..., description="The scorer reference (weave:// URI)")
    value: float = Field(..., description="The value of the score")
    evaluation_run_id: Optional[str] = Field(
        None, description="Evaluation run ID if this score is linked to one"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these scores are saved"
    )
    evaluation_run_id: Optional[str] = Field(
        None,
        description="Optional evaluation run ID to filter scores linked to this run",
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of scores to return"
    )
    offset: Optional[int] = Field(default=None, description="Number of scores to skip")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreDeleteReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these scores are saved"
    )
    score_ids: list[str] = Field(..., description="The score IDs to delete")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="Number of scores deleted")


# ============================================================================
# ObjectInterface Protocol
# ============================================================================


class ObjectInterface(Protocol):
    """Object API endpoints for Trace Server.

    This protocol contains the object-oriented APIs that provide cleaner,
    more RESTful interfaces. Implementations should support both this protocol
    and TraceServerInterface to maintain backward compatibility.
    """

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
    def evaluation_create(self, req: EvaluationCreateReq) -> EvaluationCreateRes: ...
    def evaluation_read(self, req: EvaluationReadReq) -> EvaluationReadRes: ...
    def evaluation_list(
        self, req: EvaluationListReq
    ) -> Iterator[EvaluationReadRes]: ...
    def evaluation_delete(self, req: EvaluationDeleteReq) -> EvaluationDeleteRes: ...

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
    def prediction_create(self, req: PredictionCreateReq) -> PredictionCreateRes: ...
    def prediction_read(self, req: PredictionReadReq) -> PredictionReadRes: ...
    def prediction_list(
        self, req: PredictionListReq
    ) -> Iterator[PredictionReadRes]: ...
    def prediction_delete(self, req: PredictionDeleteReq) -> PredictionDeleteRes: ...
    def prediction_finish(self, req: PredictionFinishReq) -> PredictionFinishRes: ...

    # Scores
    def score_create(self, req: ScoreCreateReq) -> ScoreCreateRes: ...
    def score_read(self, req: ScoreReadReq) -> ScoreReadRes: ...
    def score_list(self, req: ScoreListReq) -> Iterator[ScoreReadRes]: ...
    def score_delete(self, req: ScoreDeleteReq) -> ScoreDeleteRes: ...
