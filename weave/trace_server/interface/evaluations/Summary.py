from abc import ABC, abstractmethod
from typing import Any, Optional, List

from pydantic import BaseModel

"""
Summary

A Summary captures the aggregated evaluation results for a ModelInstance on a TaskDefinition,
freezing the specific set of examples and labels used to ensure reproducibility.

"""


class SummaryMutableProperties(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class SummaryImmutableProperties(BaseModel):
    model_instance_id: str
    task_definition_id: str
    scorer_instance_id: str
    # Freeze the specific examples and labels used
    task_example_ids: List[str]  # The examples from the task
    example_label_ids: List[str]  # The corresponding labels
    score_result_ids: List[str]  # The individual scores
    # Aggregated results
    aggregate_metrics: dict[str, Any]  # e.g., {"mean": 0.85, "std": 0.1, "min": 0.7, "max": 0.95}
    metadata: Optional[dict[str, Any]] = None  # Additional context (e.g., evaluation date, config)


class SummaryUserDefinedProperties(
    BaseModel, SummaryMutableProperties, SummaryImmutableProperties
): ...


class Summary(BaseModel, SummaryUserDefinedProperties):
    id: str


class CreateSummaryReq(BaseModel):
    properties: SummaryUserDefinedProperties


class CreateSummaryRes(BaseModel):
    id: str


class GetSummaryReq(BaseModel):
    id: str


class GetSummaryRes(BaseModel):
    Summary: Summary


class UpdateSummaryReq(BaseModel):
    id: str
    updates: SummaryMutableProperties


class UpdateSummaryRes(BaseModel):
    pass


class DeleteSummaryReq(BaseModel):
    id: str


class DeleteSummaryRes(BaseModel):
    pass


class TSEIMSummaryMixin(ABC):
    @abstractmethod
    async def async_create_summary(
        self, req: CreateSummaryReq
    ) -> CreateSummaryRes: ...

    @abstractmethod
    async def async_get_summary(
        self, req: GetSummaryReq
    ) -> GetSummaryRes: ...

    @abstractmethod
    async def async_update_summary(
        self, req: UpdateSummaryReq
    ) -> UpdateSummaryRes: ...

    @abstractmethod
    async def async_delete_summary(
        self, req: DeleteSummaryReq
    ) -> DeleteSummaryRes: ... 