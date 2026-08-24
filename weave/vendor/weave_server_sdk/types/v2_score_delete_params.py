# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["V2ScoreDeleteParams"]


class V2ScoreDeleteParams(TypedDict, total=False):
    entity: Required[str]

    score_ids: Required[SequenceNotStr[str]]
    """List of score IDs to delete"""
