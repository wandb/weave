# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["V2DatasetCreateResponse"]


class V2DatasetCreateResponse(BaseModel):
    digest: str
    """The digest of the created dataset"""

    object_id: str
    """The ID of the created dataset"""

    version_index: int
    """The version index of the created dataset"""
