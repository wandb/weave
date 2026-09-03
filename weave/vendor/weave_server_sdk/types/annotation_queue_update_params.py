# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["AnnotationQueueUpdateParams"]


class AnnotationQueueUpdateParams(TypedDict, total=False):
    project_id: Required[str]

    description: Optional[str]

    name: Optional[str]

    scorer_refs: Optional[SequenceNotStr[str]]
