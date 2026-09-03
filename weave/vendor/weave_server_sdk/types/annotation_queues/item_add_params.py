# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

from ..._types import SequenceNotStr

__all__ = ["ItemAddParams"]


class ItemAddParams(TypedDict, total=False):
    call_ids: Required[SequenceNotStr[str]]

    display_fields: Required[SequenceNotStr[str]]
    """JSON paths to display to annotators"""

    project_id: Required[str]
