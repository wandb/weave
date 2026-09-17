# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from .._models import BaseModel

__all__ = ["RegistryLinkResponse"]


class RegistryLinkResponse(BaseModel):
    version_index: Optional[int] = None
