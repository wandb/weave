# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["V2EvaluationRunListParams"]


class V2EvaluationRunListParams(TypedDict, total=False):
    entity: Required[str]

    evaluation_run_ids: Optional[SequenceNotStr[str]]
    """Filter by evaluation run IDs"""

    evaluations: Optional[SequenceNotStr[str]]
    """Filter by evaluation references"""

    limit: Optional[int]
    """Maximum number of evaluation runs to return"""

    models: Optional[SequenceNotStr[str]]
    """Filter by model references"""

    offset: Optional[int]
    """Number of evaluation runs to skip"""
