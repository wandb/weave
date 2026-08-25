# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["V2ModelReadResponse"]


class V2ModelReadResponse(BaseModel):
    created_at: datetime
    """When the model was created"""

    digest: str
    """The digest of the model"""

    name: str
    """The name of the model"""

    object_id: str
    """The model ID"""

    source_code: str
    """The source code of the model"""

    version_index: int
    """The version index of the object"""

    attributes: Optional[Dict[str, object]] = None
    """Additional attributes stored with the model"""

    description: Optional[str] = None
    """Description of the model"""
