# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["V2OpDeleteParams"]


class V2OpDeleteParams(TypedDict, total=False):
    entity: Required[str]

    project: Required[str]

    digests: Optional[SequenceNotStr[str]]
    """List of digests to delete.

    If not provided, all digests for the op will be deleted.
    """
