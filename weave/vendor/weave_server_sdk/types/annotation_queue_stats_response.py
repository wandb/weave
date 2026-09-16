# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List

from .._models import BaseModel

__all__ = ["AnnotationQueueStatsResponse", "Stat"]


class Stat(BaseModel):
    """Statistics for a single annotation queue."""

    completed_items: int
    """Number of items completed or skipped by at least one annotator"""

    queue_id: str
    """The queue ID"""

    total_items: int
    """Total number of items in the queue"""


class AnnotationQueueStatsResponse(BaseModel):
    """Response with stats for multiple annotation queues."""

    stats: List[Stat]
