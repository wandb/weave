# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["V2ScorerCreateResponse"]


class V2ScorerCreateResponse(BaseModel):
    digest: str
    """The digest of the created scorer"""

    object_id: str
    """The ID of the created scorer"""

    scorer: str
    """Full reference to the created scorer"""

    version_index: int
    """The version index of the created scorer"""
