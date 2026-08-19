# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["V2EvaluationRunDeleteResponse"]


class V2EvaluationRunDeleteResponse(BaseModel):
    num_deleted: int
    """Number of evaluation runs deleted"""
