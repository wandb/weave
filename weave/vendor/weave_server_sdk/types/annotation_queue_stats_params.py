# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["AnnotationQueueStatsParams"]


class AnnotationQueueStatsParams(TypedDict, total=False):
    project_id: Required[str]

    queue_ids: Required[SequenceNotStr[str]]
    """List of queue IDs to get stats for"""
