# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["V2OpReadParams"]


class V2OpReadParams(TypedDict, total=False):
    entity: Required[str]

    project: Required[str]

    object_id: Required[str]

    eager: bool
    """Whether to eagerly load the op code"""
