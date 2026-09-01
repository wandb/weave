# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional

from .._models import BaseModel

__all__ = ["FeedbackAggregateResponse", "Bucket"]


class Bucket(BaseModel):
    """One (time bucket, group) row of aggregated scorer feedback."""

    scored_count: int
    """Rows that emitted a score (at least one tag or rating).

    Excludes agent-monitor rows that scored nothing — use this for score volume.
    """

    total_count: int
    """Number of feedback rows in this bucket/group."""

    group: Optional[Dict[str, str]] = None
    """Group-by dimension values for this row (e.g. {'scorer_id': '...'})."""

    rating_counts: Optional[Dict[str, int]] = None
    """Number of rows carrying each rating key (e.g. '_rating_')."""

    rating_sums: Optional[Dict[str, float]] = None
    """Sum of each rating key's values; client derives avg = sum/count."""

    tag_counts: Optional[Dict[str, int]] = None
    """Count of each scorer tag."""

    time_bucket_start_ms: Optional[int] = None
    """Time bucket start, unix epoch ms (UTC). None when unbucketed."""


class FeedbackAggregateResponse(BaseModel):
    """Sparse time-series of aggregated scorer feedback (empty buckets omitted)."""

    after_ms: int
    """Resolved inclusive lower bound, unix epoch ms (UTC)."""

    before_ms: int
    """Resolved exclusive upper bound, unix epoch ms (UTC)."""

    buckets: Optional[List[Bucket]] = None

    time_bucket_seconds: Optional[int] = None
    """Time bucket size used (seconds). None when unbucketed."""
