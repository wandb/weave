from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel

"""
EvaluationSummary

A EvaluationSummary captures the aggregated evaluation results for a ModelInstance on a TaskDefinition,
freezing the specific set of examples and labels used to ensure reproducibility.

"""


class EvaluationSummaryMutableProperties(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class EvaluationSummaryImmutableProperties(BaseModel):
    model_instance_id: str
    task_definition_id: str
    scorer_instance_id: str
    # Freeze the specific examples and labels used
    task_example_ids: list[str]  # The examples from the task
    example_label_ids: list[str]  # The corresponding labels
    score_result_ids: list[str]  # The individual scores
    # Aggregated results
    aggregate_metrics: dict[
        str, Any
    ]  # e.g., {"mean": 0.85, "std": 0.1, "min": 0.7, "max": 0.95}
    metadata: Optional[dict[str, Any]] = (
        None  # Additional context (e.g., evaluation date, config)
    )


class EvaluationSummaryUserDefinedProperties(
    EvaluationSummaryMutableProperties, EvaluationSummaryImmutableProperties
): ...


class EvaluationSummary(EvaluationSummaryUserDefinedProperties):
    id: str


class CreateEvaluationSummaryReq(BaseModel):
    properties: EvaluationSummaryUserDefinedProperties


class CreateEvaluationSummaryRes(BaseModel):
    id: str


class GetEvaluationSummaryReq(BaseModel):
    id: str


class GetEvaluationSummaryRes(BaseModel):
    EvaluationSummary: EvaluationSummary


class UpdateEvaluationSummaryReq(BaseModel):
    id: str
    updates: EvaluationSummaryMutableProperties


class UpdateEvaluationSummaryRes(BaseModel):
    pass


class DeleteEvaluationSummaryReq(BaseModel):
    id: str


class DeleteEvaluationSummaryRes(BaseModel):
    pass


class TSEIMEvaluationSummaryMixin(ABC):
    @abstractmethod
    async def async_create_evaluation_summary(
        self, req: CreateEvaluationSummaryReq
    ) -> CreateEvaluationSummaryRes: ...

    @abstractmethod
    async def async_get_evaluation_summary(
        self, req: GetEvaluationSummaryReq
    ) -> GetEvaluationSummaryRes: ...

    @abstractmethod
    async def async_update_evaluation_summary(
        self, req: UpdateEvaluationSummaryReq
    ) -> UpdateEvaluationSummaryRes: ...

    @abstractmethod
    async def async_delete_evaluation_summary(
        self, req: DeleteEvaluationSummaryReq
    ) -> DeleteEvaluationSummaryRes: ...
