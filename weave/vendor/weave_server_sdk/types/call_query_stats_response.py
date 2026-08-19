# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from .._models import BaseModel

__all__ = ["CallQueryStatsResponse"]


class CallQueryStatsResponse(BaseModel):
    count: int

    has_more: Optional[bool] = None

    total_storage_size_bytes: Optional[int] = None
