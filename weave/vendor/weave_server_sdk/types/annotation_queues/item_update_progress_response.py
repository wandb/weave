# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from datetime import datetime
from typing_extensions import Literal

from ..._models import BaseModel

__all__ = ["ItemUpdateProgressResponse", "Item"]


class Item(BaseModel):
    """Schema for annotation queue item responses."""

    id: str

    annotation_state: Literal["unstarted", "in_progress", "completed", "skipped"]

    call_id: str

    call_op_name: str

    call_started_at: datetime

    call_trace_id: str

    created_at: datetime

    created_by: str

    display_fields: List[str]

    project_id: str

    queue_id: str

    updated_at: datetime

    added_by: Optional[str] = None

    annotator_user_id: Optional[str] = None

    call_ended_at: Optional[datetime] = None

    deleted_at: Optional[datetime] = None

    position_in_queue: Optional[int] = None


class ItemUpdateProgressResponse(BaseModel):
    """Response from updating annotation state."""

    item: Item
    """Schema for annotation queue item responses."""
