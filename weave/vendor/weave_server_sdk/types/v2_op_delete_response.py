# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["V2OpDeleteResponse"]


class V2OpDeleteResponse(BaseModel):
    num_deleted: int
    """Number of op versions deleted from this op"""
