# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["ObjectCreateParams", "Obj"]


class ObjectCreateParams(TypedDict, total=False):
    obj: Required[Obj]


class Obj(TypedDict, total=False):
    object_id: Required[str]

    project_id: Required[str]

    val: Required[object]

    builtin_object_class: Optional[str]

    expected_digest: Optional[str]
    """Client-computed digest for server-side validation.

    If provided, the server will verify it matches the server-computed digest.
    """

    set_base_object_class: Optional[str]

    wb_user_id: Optional[str]
    """Do not set directly. Server will automatically populate this field."""
