# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel

__all__ = ["FileResolveURLResponse"]


class FileResolveURLResponse(BaseModel):
    download_urls: List[str]

    expires_at: Optional[str] = None
