# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["DatasetSourceQueryResponse", "Link"]


class Link(BaseModel):
    """Schema for a single dataset source link row."""

    id: str

    created_at: datetime

    row_digest: str

    source_display_name: str

    source_id: str

    source_kind: Literal["call", "span", "conversation"]

    source_started_at: datetime

    source_trace_id: str

    updated_at: datetime

    added_by: Optional[str] = None

    deleted_at: Optional[datetime] = None

    link_metadata: Optional[Dict[str, object]] = None


class DatasetSourceQueryResponse(BaseModel):
    """Response from the forward dataset -> sources query."""

    links: List[Link]
