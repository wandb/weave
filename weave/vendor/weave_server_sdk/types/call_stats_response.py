# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["CallStatsResponse"]


class CallStatsResponse(BaseModel):
    """Response containing time-series call statistics."""

    end: datetime
    """Resolved end time (UTC)"""

    granularity: int
    """Bucket size used (in seconds)"""

    start: datetime
    """Resolved start time (UTC)"""

    timezone: str
    """Timezone used for bucket alignment"""

    call_buckets: Optional[List[Dict[str, object]]] = None
    """Call-level metrics.

    Each bucket contains 'timestamp' and aggregated metric values.
    """

    usage_buckets: Optional[List[Dict[str, object]]] = None
    """Usage metrics by model.

    Each bucket contains 'timestamp', 'model', and aggregated metric values.
    """
