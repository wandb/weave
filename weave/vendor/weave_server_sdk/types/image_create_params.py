# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["ImageCreateParams", "Inputs"]


class ImageCreateParams(TypedDict, total=False):
    inputs: Required[Inputs]

    project_id: Required[str]

    track_llm_call: Optional[bool]
    """Whether to track this image generation call in the trace server"""

    wb_user_id: Optional[str]
    """Do not set directly. Server will automatically populate this field."""


class Inputs(TypedDict, total=False):
    model: Required[str]

    prompt: Required[str]

    n: Optional[int]
