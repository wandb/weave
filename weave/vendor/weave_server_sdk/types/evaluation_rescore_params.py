# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["EvaluationRescoreParams"]


class EvaluationRescoreParams(TypedDict, total=False):
    project_id: Required[str]

    scorer_refs: Required[SequenceNotStr[str]]
    """Scorer references (weave:// URIs) to apply; must be non-empty"""

    source_evaluation_run_id: Required[str]
    """The evaluation run whose predictions will be rescored"""

    wb_user_id: Optional[str]
    """Do not set directly. Server will automatically populate this field."""
