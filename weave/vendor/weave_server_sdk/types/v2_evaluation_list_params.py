# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["V2EvaluationListParams"]


class V2EvaluationListParams(TypedDict, total=False):
    entity: Required[str]

    limit: Optional[int]
    """Maximum number of evaluations to return"""

    offset: Optional[int]
    """Number of evaluations to skip"""
