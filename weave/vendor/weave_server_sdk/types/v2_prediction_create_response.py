# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["V2PredictionCreateResponse"]


class V2PredictionCreateResponse(BaseModel):
    prediction_id: str
    """The prediction ID"""
