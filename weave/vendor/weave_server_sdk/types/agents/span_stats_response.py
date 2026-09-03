# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Union, Optional
from datetime import datetime
from typing_extensions import Literal

from ..._models import BaseModel

__all__ = ["SpanStatsResponse", "Column"]


class Column(BaseModel):
    """Metadata describing one column in an agent span stats result row."""

    aggregation: Optional[str] = None

    metric: Optional[str] = None

    name: str

    role: Literal["time", "bucket", "group", "metric"]

    value_type: Literal["datetime", "number", "boolean", "string"]


class SpanStatsResponse(BaseModel):
    """Response containing chart-ready agent span stats rows."""

    bucket_type: Literal["time", "number"]

    columns: List[Column]

    end: datetime

    granularity: Optional[int] = None

    rows: List[Dict[str, Union[datetime, str, float, bool, None]]]

    start: datetime

    timezone: str
