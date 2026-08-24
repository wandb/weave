# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["TableQueryStatsBatchParams"]


class TableQueryStatsBatchParams(TypedDict, total=False):
    project_id: Required[str]
    """The ID of the project"""

    digests: Optional[SequenceNotStr[str]]
    """The digests of the tables to query"""

    include_storage_size: Optional[bool]
    """If true, the `storage_size_bytes` column is returned."""
