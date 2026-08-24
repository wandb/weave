# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["CallDeleteResponse"]


class CallDeleteResponse(BaseModel):
    num_deleted: int
    """The number of calls deleted"""
