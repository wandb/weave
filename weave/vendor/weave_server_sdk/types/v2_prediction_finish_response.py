# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["V2PredictionFinishResponse"]


class V2PredictionFinishResponse(BaseModel):
    success: bool
    """Whether the prediction was finished successfully"""
