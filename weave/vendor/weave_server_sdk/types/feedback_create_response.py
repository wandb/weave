# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict
from datetime import datetime

from .._models import BaseModel

__all__ = ["FeedbackCreateResponse"]


class FeedbackCreateResponse(BaseModel):
    id: str

    created_at: datetime

    payload: Dict[str, object]

    wb_user_id: str
