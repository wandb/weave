# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List

from .._models import BaseModel

__all__ = ["FeedbackQueryResponse"]


class FeedbackQueryResponse(BaseModel):
    result: List[Dict[str, object]]

    total_count: int
