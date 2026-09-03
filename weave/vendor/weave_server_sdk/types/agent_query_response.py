# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["AgentQueryResponse", "Agent"]


class Agent(BaseModel):
    """Aggregated per-agent stats from the agents table."""

    agent_name: str

    error_count: int

    first_seen: Optional[datetime] = None

    invocation_count: int

    last_seen: Optional[datetime] = None

    project_id: str

    span_count: int

    total_cost_usd: Optional[float] = None

    total_duration_ms: int

    total_input_tokens: int

    total_output_tokens: int


class AgentQueryResponse(BaseModel):
    """Response containing aggregated agent stats."""

    agents: List[Agent]

    total_count: int
