# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional

from .._models import BaseModel

__all__ = ["V2RuntimeApplyResponse", "RuntimeID"]


class RuntimeID(BaseModel):
    id: str
    """Value sent in the OpenAI-compatible request model field"""

    playground_id: str

    max_tokens: Optional[int] = None
    """Maximum tokens supported by this runtime ID"""


class V2RuntimeApplyResponse(BaseModel):
    api_key_secret: Optional[str] = None

    base_url: str

    headers: Dict[str, str]

    name: str
    """Stable custom runtime name"""

    runtime_ids: List[RuntimeID]
