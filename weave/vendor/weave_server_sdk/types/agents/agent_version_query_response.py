# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from datetime import datetime

from ..._models import BaseModel

__all__ = ["AgentVersionQueryResponse", "Version"]


class Version(BaseModel):
    """Aggregated per-version stats from the agent_versions AMT."""

    agent_name: str

    agent_version: str

    error_count: int

    first_seen: Optional[datetime] = None

    invocation_count: int

    last_seen: Optional[datetime] = None

    project_id: str

    span_count: int

    total_duration_ms: int

    total_input_tokens: int

    total_output_tokens: int

    total_cost_usd: Optional[float] = None


class AgentVersionQueryResponse(BaseModel):
    """Response containing agent version stats."""

    versions: List[Version]

    total_count: Optional[int] = None
