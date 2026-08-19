# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["ObjectDeleteParams"]


class ObjectDeleteParams(TypedDict, total=False):
    object_id: Required[str]

    project_id: Required[str]

    digests: Optional[SequenceNotStr[str]]
    """List of digests to delete.

    If not provided, all digests for the object will be deleted.
    """
