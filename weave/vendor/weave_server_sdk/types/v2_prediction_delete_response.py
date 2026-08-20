# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["V2PredictionDeleteResponse"]


class V2PredictionDeleteResponse(BaseModel):
    num_deleted: int
    """Number of predictions deleted"""
