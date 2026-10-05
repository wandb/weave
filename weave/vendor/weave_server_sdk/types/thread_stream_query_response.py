# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["ThreadStreamQueryResponse"]


class ThreadStreamQueryResponse(BaseModel):
    first_turn_id: Optional[str] = None
    """Turn ID of the first turn in this thread (earliest start_time)"""

    last_turn_id: Optional[str] = None
    """Turn ID of the latest turn in this thread (latest end_time)"""

    last_updated: datetime
    """Latest end time of turn calls in this thread"""

    p50_turn_duration_ms: Optional[float] = None
    """50th percentile (median) of turn durations in milliseconds within this thread"""

    p99_turn_duration_ms: Optional[float] = None
    """99th percentile of turn durations in milliseconds within this thread"""

    start_time: datetime
    """Earliest start time of turn calls in this thread"""

    thread_id: str

    turn_count: int
    """Number of turn calls in this thread"""
