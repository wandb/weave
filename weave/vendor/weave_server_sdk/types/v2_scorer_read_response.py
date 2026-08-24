# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["V2ScorerReadResponse"]


class V2ScorerReadResponse(BaseModel):
    created_at: datetime
    """When the scorer was created"""

    digest: str
    """The digest of the scorer"""

    name: str
    """The name of the scorer"""

    object_id: str
    """The scorer ID"""

    score_op: str
    """The Scorer.score op reference"""

    version_index: int
    """The version index of the object"""

    description: Optional[str] = None
    """Description of the scorer"""
