# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from typing_extensions import TypeAlias

from .._models import BaseModel

__all__ = ["V2PredictionListResponse", "V2PredictionListResponseItem"]


class V2PredictionListResponseItem(BaseModel):
    inputs: Dict[str, object]
    """The inputs to the prediction"""

    model: str
    """The model reference (weave:// URI)"""

    output: object
    """The output of the prediction"""

    prediction_id: str
    """The prediction ID"""

    evaluation_run_id: Optional[str] = None
    """Evaluation run ID if this prediction is linked to one"""

    wb_user_id: Optional[str] = None
    """Do not set directly. Server will automatically populate this field."""


V2PredictionListResponse: TypeAlias = List[V2PredictionListResponseItem]
