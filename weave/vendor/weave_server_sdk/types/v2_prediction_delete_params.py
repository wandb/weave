# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["V2PredictionDeleteParams"]


class V2PredictionDeleteParams(TypedDict, total=False):
    entity: Required[str]

    prediction_ids: Required[SequenceNotStr[str]]
    """List of prediction IDs to delete"""
