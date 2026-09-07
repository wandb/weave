# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Optional
from typing_extensions import Literal, Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["DatasetSourceQueryParams"]


class DatasetSourceQueryParams(TypedDict, total=False):
    dataset_object_id: Required[str]

    project_id: Required[str]

    include_deleted: bool

    limit: Optional[int]

    offset: Optional[int]

    row_digests: Optional[SequenceNotStr[str]]

    source_kinds: Optional[List[Literal["call", "span", "conversation"]]]

    wb_user_id: Optional[str]
    """Do not set directly. Server will automatically populate this field."""
