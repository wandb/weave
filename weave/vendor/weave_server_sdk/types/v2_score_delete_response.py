# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["V2ScoreDeleteResponse"]


class V2ScoreDeleteResponse(BaseModel):
    num_deleted: int
    """Number of scores deleted"""
