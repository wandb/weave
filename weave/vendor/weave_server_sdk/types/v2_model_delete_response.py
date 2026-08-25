# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["V2ModelDeleteResponse"]


class V2ModelDeleteResponse(BaseModel):
    num_deleted: int
    """Number of model versions deleted"""
