# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["CallScoreParams"]


class CallScoreParams(TypedDict, total=False):
    call_ids: Required[SequenceNotStr[str]]
    """List of call IDs to score"""

    project_id: Required[str]

    scorer_refs: Required[SequenceNotStr[str]]
    """List of scorer refs to apply"""

    wb_user_id: Optional[str]
    """Do not set directly. Server will automatically populate this field."""
