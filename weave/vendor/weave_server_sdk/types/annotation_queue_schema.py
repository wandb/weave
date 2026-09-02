# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["AnnotationQueueSchema"]


class AnnotationQueueSchema(BaseModel):
    """Schema for annotation queue responses."""

    id: str

    created_at: datetime

    created_by: str

    description: str

    name: str

    project_id: str

    scorer_refs: List[str]

    updated_at: datetime

    deleted_at: Optional[datetime] = None
