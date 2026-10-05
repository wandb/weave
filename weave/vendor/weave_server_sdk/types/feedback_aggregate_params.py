# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Optional
from typing_extensions import Literal, Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["FeedbackAggregateParams"]


class FeedbackAggregateParams(TypedDict, total=False):
    after_ms: Required[int]
    """Inclusive lower bound on created_at (milliseconds since epoch)."""

    before_ms: Required[int]
    """Exclusive upper bound on created_at (milliseconds since epoch)."""

    project_id: Required[str]

    feedback_types: SequenceNotStr[str]
    """Filter on feedback_type by prefix"""

    group_by: List[Literal["scorer_id", "span_agent_name", "span_agent_version", "span_status_code"]]
    """
    Allowed: ['scorer_id', 'span_agent_name', 'span_agent_version',
    'span_status_code'].
    """

    monitor_ids: SequenceNotStr[str]
    """Filter to these monitor ids (exact match; suffix with '\\**' for prefix match)."""

    rating_max: Optional[float]
    """Include only rows with a rating <= this value"""

    rating_min: Optional[float]
    """Include only rows with a rating >= this value"""

    scorer_ids: SequenceNotStr[str]
    """Filter to these scorer ids (exact match; suffix with '\\**' for prefix match)."""

    span_agent_names: SequenceNotStr[str]
    """Filter to feedback whose span_agent_name matches any of these (exact)."""

    span_types: List[Literal["agent_turn", "agent_conversation"]]
    """Filter by span type (turn vs conversation)."""

    tags: SequenceNotStr[str]
    """Filter to feedback that includes any of the given tags"""

    time_bucket_seconds: Optional[int]
    """Time bucket size in seconds, e.g. 3600 for 1h buckets"""
