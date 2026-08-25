# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["V2PredictionListParams"]


class V2PredictionListParams(TypedDict, total=False):
    entity: Required[str]

    evaluation_run_id: Optional[str]
    """Filter by evaluation run ID"""

    limit: Optional[int]
    """Maximum number of predictions to return"""

    offset: Optional[int]
    """Number of predictions to skip"""
