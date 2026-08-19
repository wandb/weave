# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["V2ScorerDeleteResponse"]


class V2ScorerDeleteResponse(BaseModel):
    num_deleted: int
    """Number of scorer versions deleted"""
