# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from ..._models import BaseModel

__all__ = ["ItemAddResponse"]


class ItemAddResponse(BaseModel):
    """Response from adding calls to a queue."""

    added_count: int

    duplicates: int
