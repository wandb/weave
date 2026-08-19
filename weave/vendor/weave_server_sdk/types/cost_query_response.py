# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["CostQueryResponse", "Result"]


class Result(BaseModel):
    id: Optional[str] = None

    cache_creation_input_token_cost: Optional[float] = None

    cache_read_input_token_cost: Optional[float] = None

    completion_token_cost: Optional[float] = None

    completion_token_cost_unit: Optional[str] = None

    effective_date: Optional[datetime] = None

    llm_id: Optional[str] = None

    prompt_token_cost: Optional[float] = None

    prompt_token_cost_unit: Optional[str] = None

    provider_id: Optional[str] = None


class CostQueryResponse(BaseModel):
    results: List[Result]
