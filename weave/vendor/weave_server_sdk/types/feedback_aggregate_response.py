# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional

from .._models import BaseModel

__all__ = ["FeedbackAggregateResponse", "Bucket"]


class Bucket(BaseModel):
    """One (time bucket, group) row of aggregated scorer feedback."""

    group: Dict[str, str]
    """Group-by dimension values for this row (e.g. {'scorer_id': '...'})."""

    rating_counts: Dict[str, int]
    """Number of rows carrying each rating key (e.g. '_rating_')."""

    rating_sums: Dict[str, float]
    """Sum of each rating key's values; client derives avg = sum/count."""

    scored_count: int
    """Rows that emitted a score (at least one tag or rating).

    Excludes agent-monitor rows that scored nothing — use this for score volume.
    """

    tag_counts: Dict[str, int]
    """Count of each scorer tag."""

    time_bucket_start_ms: Optional[int] = None
    """Time bucket start, unix epoch ms (UTC). None when unbucketed."""

    total_count: int
    """Number of feedback rows in this bucket/group."""


class FeedbackAggregateResponse(BaseModel):
    """Sparse time-series of aggregated scorer feedback (empty buckets omitted)."""

    after_ms: int
    """Resolved inclusive lower bound, unix epoch ms (UTC)."""

    before_ms: int
    """Resolved exclusive upper bound, unix epoch ms (UTC)."""

    buckets: List[Bucket]

    time_bucket_seconds: Optional[int] = None
    """Time bucket size used (seconds). None when unbucketed."""
