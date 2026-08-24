# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Required, TypedDict

__all__ = ["V2EvaluationRunFinishParams"]


class V2EvaluationRunFinishParams(TypedDict, total=False):
    entity: Required[str]

    project: Required[str]

    summary: Optional[Dict[str, object]]
    """Optional summary dictionary for the evaluation run"""
