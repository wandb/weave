# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["V2EvaluationRunFinishResponse"]


class V2EvaluationRunFinishResponse(BaseModel):
    success: bool
    """Whether the evaluation run was finished successfully"""
