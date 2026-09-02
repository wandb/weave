# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Iterable, Optional
from typing_extensions import Literal, Required, TypedDict

__all__ = ["ItemQueryParams", "Filter", "SortBy"]


class ItemQueryParams(TypedDict, total=False):
    project_id: Required[str]

    filter: Optional[Filter]
    """Simple filter for annotation queue items.

    Supports equality filtering on call metadata fields and IN filtering on
    annotation state.
    """

    include_position: bool
    """Include position_in_queue field (1-based index in full queue)"""

    limit: Optional[int]

    offset: Optional[int]

    sort_by: Optional[Iterable[SortBy]]
    """Sort by multiple fields (e.g., created_at, updated_at)"""


class Filter(TypedDict, total=False):
    """Simple filter for annotation queue items.

    Supports equality filtering on call metadata fields and IN filtering on annotation state.
    """

    id: Optional[str]
    """Filter by exact queue item ID"""

    added_by: Optional[str]
    """Filter by W&B user ID who added the call"""

    annotation_states: Optional[List[Literal["unstarted", "in_progress", "completed", "skipped"]]]
    """Filter by annotation states (unstarted, in_progress, completed, skipped)"""

    call_id: Optional[str]
    """Filter by exact call ID"""

    call_op_name: Optional[str]
    """Filter by exact operation name"""

    call_trace_id: Optional[str]
    """Filter by exact trace ID"""


class SortBy(TypedDict, total=False):
    direction: Required[Literal["asc", "desc"]]

    field: Required[str]
