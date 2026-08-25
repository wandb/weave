# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from typing_extensions import TypeAlias

from .._models import BaseModel

__all__ = ["V2ScoreListResponse", "V2ScoreListResponseItem"]


class V2ScoreListResponseItem(BaseModel):
    score_id: str
    """The score ID"""

    scorer: str
    """The scorer reference (weave:// URI)"""

    value: object
    """The raw output of the scorer"""

    evaluation_run_id: Optional[str] = None
    """Evaluation run ID if this score is linked to one"""

    wb_user_id: Optional[str] = None
    """Do not set directly. Server will automatically populate this field."""


V2ScoreListResponse: TypeAlias = List[V2ScoreListResponseItem]
