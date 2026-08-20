# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["V2EvaluationRunCreateParams"]


class V2EvaluationRunCreateParams(TypedDict, total=False):
    entity: Required[str]

    evaluation: Required[str]
    """Reference to the evaluation (weave:// URI)"""

    model: Required[str]
    """Reference to the model (weave:// URI)"""

    source_evaluation_run_id: Optional[str]
    """Source evaluation run ID if this run was created by rescoring — provenance link"""
