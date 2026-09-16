# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["EvaluationRescoreResponse"]


class EvaluationRescoreResponse(BaseModel):
    """Response for a rescore request."""

    call_id: str
    """Call ID for /evaluations/status polling"""

    evaluation_run_id: str
    """The newly created EvaluationRun ID"""
