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
    code: Literal["not_found"]


class StatusEvaluationStatusRunning(BaseModel):
    code: Literal["running"]

    completed_rows: int

    total_rows: int


class StatusEvaluationStatusFailed(BaseModel):
    code: Literal["failed"]

    error: Optional[str] = None


class StatusEvaluationStatusComplete(BaseModel):
    code: Literal["complete"]

    output: Dict[str, object]


Status: TypeAlias = Union[
    StatusEvaluationStatusNotFound,
    StatusEvaluationStatusRunning,
    StatusEvaluationStatusFailed,
    StatusEvaluationStatusComplete,
]


class EvaluationStatusResponse(BaseModel):
    status: Status
