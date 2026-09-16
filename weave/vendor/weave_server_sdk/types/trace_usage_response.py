# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional

from .._models import BaseModel

__all__ = ["TraceUsageResponse", "CallUsageCallUsageItem"]


class CallUsageCallUsageItem(BaseModel):
    """Aggregated usage metrics for a specific LLM.

    Constructor defaults stay for Python callers. Serialization JSON Schema
    marks those fields required so OpenAPI matches the JSON FastAPI sends.
    """

    cache_creation_input_tokens: int

    cache_creation_input_tokens_total_cost: Optional[float] = None

    cache_read_input_tokens: int

    cache_read_input_tokens_total_cost: Optional[float] = None

    completion_tokens: int

    completion_tokens_total_cost: Optional[float] = None

    prompt_tokens: int

    prompt_tokens_total_cost: Optional[float] = None

    requests: int

    total_tokens: int


class TraceUsageResponse(BaseModel):
    """Response with per-call usage metrics (each includes descendant contributions)."""

    call_usage: Dict[str, Dict[str, CallUsageCallUsageItem]]

    unfinished_call_ids: List[str]
