# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional

from .._models import BaseModel

__all__ = ["TraceUsageResponse", "CallUsageCallUsageItem"]


class CallUsageCallUsageItem(BaseModel):
    """Aggregated usage metrics for a specific LLM."""

    cache_creation_input_tokens: Optional[int] = None

    cache_creation_input_tokens_total_cost: Optional[float] = None

    cache_read_input_tokens: Optional[int] = None

    cache_read_input_tokens_total_cost: Optional[float] = None

    completion_tokens: Optional[int] = None

    completion_tokens_total_cost: Optional[float] = None

    prompt_tokens: Optional[int] = None

    prompt_tokens_total_cost: Optional[float] = None

    requests: Optional[int] = None

    total_tokens: Optional[int] = None


class TraceUsageResponse(BaseModel):
    """Response with per-call usage metrics (each includes descendant contributions)."""

    call_usage: Optional[Dict[str, Dict[str, CallUsageCallUsageItem]]] = None

    unfinished_call_ids: Optional[List[str]] = None
