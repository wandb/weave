# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["CallDeleteParams"]


class CallDeleteParams(TypedDict, total=False):
    call_ids: Required[SequenceNotStr[str]]

    project_id: Required[str]

    wb_user_id: Optional[str]
    """Do not set directly. Server will automatically populate this field."""
