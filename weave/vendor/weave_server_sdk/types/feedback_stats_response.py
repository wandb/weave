# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["FeedbackStatsResponse"]


class FeedbackStatsResponse(BaseModel):
    """Response with time-series feedback statistics."""

    end: datetime
    """Resolved end time (always UTC, regardless of the requested timezone)."""

    granularity: int
    """Bucket size used (in seconds)"""

    start: datetime
    """Resolved start time (always UTC, regardless of the requested timezone)."""

    timezone: str
    """Timezone used for bucket alignment"""

    buckets: Optional[List[Dict[str, object]]] = None
    """Time-bucketed aggregations.

    Each dict has 'timestamp' (ISO string), 'count' (int), and '{agg}\\__{slug}' keys
    for each requested metric+aggregation.
    """

    window_stats: Optional[Dict[str, Dict[str, Optional[float]]]] = None
    """Aggregations over the full query window, keyed by metric slug (e.g.

    'output_score'). Each value maps agg name to result.
    """
