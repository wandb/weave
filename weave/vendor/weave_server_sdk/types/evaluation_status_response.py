# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Union, Optional
from typing_extensions import Literal, TypeAlias

from .._models import BaseModel

__all__ = [
    "EvaluationStatusResponse",
    "Status",
    "StatusEvaluationStatusNotFound",
    "StatusEvaluationStatusRunning",
    "StatusEvaluationStatusFailed",
    "StatusEvaluationStatusComplete",
]


class StatusEvaluationStatusNotFound(BaseModel):
    code: Optional[Literal["not_found"]] = None


class StatusEvaluationStatusRunning(BaseModel):
    completed_rows: int

    total_rows: int

    code: Optional[Literal["running"]] = None


class StatusEvaluationStatusFailed(BaseModel):
    code: Optional[Literal["failed"]] = None

    error: Optional[str] = None


class StatusEvaluationStatusComplete(BaseModel):
    output: Dict[str, object]

    code: Optional[Literal["complete"]] = None


Status: TypeAlias = Union[
    StatusEvaluationStatusNotFound,
    StatusEvaluationStatusRunning,
    StatusEvaluationStatusFailed,
    StatusEvaluationStatusComplete,
]


class EvaluationStatusResponse(BaseModel):
    status: Status
