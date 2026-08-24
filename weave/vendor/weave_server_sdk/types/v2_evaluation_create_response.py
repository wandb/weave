# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["V2EvaluationCreateResponse"]


class V2EvaluationCreateResponse(BaseModel):
    digest: str
    """The digest of the created evaluation"""

    evaluation_ref: str
    """Full reference to the created evaluation"""

    object_id: str
    """The ID of the created evaluation"""

    version_index: int
    """The version index of the created evaluation"""
