# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["V2ScoreCreateParams"]


class V2ScoreCreateParams(TypedDict, total=False):
    entity: Required[str]

    prediction_id: Required[str]
    """The prediction ID"""

    scorer: Required[str]
    """The scorer reference (weave:// URI)"""

    value: Required[object]
    """The raw output of the scorer"""

    evaluation_run_id: Optional[str]
    """Optional evaluation run ID to link this score as a child call"""
