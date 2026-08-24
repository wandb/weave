# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["V2EvaluationReadResponse"]


class V2EvaluationReadResponse(BaseModel):
    created_at: datetime
    """When the evaluation was created"""

    dataset: str
    """Dataset reference (weave:// URI)"""

    digest: str
    """The digest of the evaluation"""

    name: str
    """The name of the evaluation"""

    object_id: str
    """The evaluation ID"""

    scorers: List[str]
    """List of scorer references (weave:// URIs)"""

    trials: int
    """Number of trials"""

    version_index: int
    """The version index of the evaluation"""

    description: Optional[str] = None
    """A description of the evaluation"""

    evaluate_op: Optional[str] = None
    """Evaluate op reference (weave:// URI)"""

    evaluation_name: Optional[str] = None
    """Name for the evaluation run"""

    predict_and_score_op: Optional[str] = None
    """Predict and score op reference (weave:// URI)"""

    summarize_op: Optional[str] = None
    """Summarize op reference (weave:// URI)"""
