# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["V2CallStartResponse"]


class V2CallStartResponse(BaseModel):
    """Response for starting a single call via v2 API."""

    id: str

    trace_id: str
