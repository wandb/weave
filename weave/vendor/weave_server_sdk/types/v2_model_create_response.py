# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from pydantic import Field as FieldInfo

from .._models import BaseModel

__all__ = ["V2ModelCreateResponse"]


class V2ModelCreateResponse(BaseModel):
    digest: str
    """The digest of the created model"""

    api_model_ref: str = FieldInfo(alias="model_ref")
    """Full reference to the created model"""

    object_id: str
    """The ID of the created model"""

    version_index: int
    """The version index of the created model"""
