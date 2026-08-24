# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["V2DatasetDeleteResponse"]


class V2DatasetDeleteResponse(BaseModel):
    num_deleted: int
    """Number of dataset versions deleted"""
