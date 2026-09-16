# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional

from .._models import BaseModel

__all__ = ["ImageCreateResponse"]


class ImageCreateResponse(BaseModel):
    response: Dict[str, object]

    weave_call_id: Optional[str] = None
