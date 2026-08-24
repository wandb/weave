# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Union
from typing_extensions import TypeAlias

from .._models import BaseModel

__all__ = ["CallUpsertBatchResponse", "Re", "ReCallStartRes"]


class ReCallStartRes(BaseModel):
    id: str

    trace_id: str


Re: TypeAlias = Union[ReCallStartRes, object]


class CallUpsertBatchResponse(BaseModel):
    res: List[Re]
