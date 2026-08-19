# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["V2OpCreateParams"]


class V2OpCreateParams(TypedDict, total=False):
    entity: Required[str]

    name: Optional[str]
    """The name of this op. Ops with the same name will be versioned together."""

    source_code: Optional[str]
    """Complete source code for this op, including imports"""
