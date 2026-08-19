# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List
from datetime import datetime

from .._models import BaseModel

__all__ = ["FeedbackBatchCreateResponse", "Re"]


class Re(BaseModel):
    id: str

    created_at: datetime

    payload: Dict[str, object]

    wb_user_id: str


class FeedbackBatchCreateResponse(BaseModel):
    res: List[Re]
