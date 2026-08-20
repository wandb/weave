# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["V2EvaluationRunReadResponse"]


class V2EvaluationRunReadResponse(BaseModel):
    evaluation: str
    """Reference to the evaluation (weave:// URI)"""

    evaluation_run_id: str
    """The evaluation run ID"""

    model: str
    """Reference to the model (weave:// URI)"""

    finished_at: Optional[datetime] = None
    """When the evaluation run finished"""

    source_evaluation_run_id: Optional[str] = None
    """Source evaluation run ID if this run was created by rescoring"""

    started_at: Optional[datetime] = None
    """When the evaluation run started"""

    status: Optional[str] = None
    """Status of the evaluation run"""

    summary: Optional[Dict[str, object]] = None
    """Summary data for the evaluation run"""
