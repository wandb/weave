# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from datetime import datetime

from .._models import BaseModel

__all__ = ["V2OpReadResponse"]


class V2OpReadResponse(BaseModel):
    """Response model for reading an Op object.

    The code field contains the actual source code of the op.
    """

    code: str
    """The actual op source code"""

    created_at: datetime
    """When this op was created"""

    digest: str
    """The digest of the op"""

    object_id: str
    """The op ID"""

    version_index: int
    """The version index of this op"""
