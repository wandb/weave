# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["CallStartResponse"]


class CallStartResponse(BaseModel):
    id: str

    trace_id: str
