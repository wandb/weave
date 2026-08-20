# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["TableCreateFromDigestsParams"]


class TableCreateFromDigestsParams(TypedDict, total=False):
    project_id: Required[str]

    row_digests: Required[SequenceNotStr[str]]

    expected_digest: Optional[str]
    """Client-computed table digest for server-side validation."""
