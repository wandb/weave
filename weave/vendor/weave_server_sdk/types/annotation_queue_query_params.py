# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional
from typing_extensions import Literal, Required, TypedDict

__all__ = ["AnnotationQueueQueryParams", "SortBy"]


class AnnotationQueueQueryParams(TypedDict, total=False):
    project_id: Required[str]

    limit: Optional[int]

    name: Optional[str]
    """Filter by queue name (case-insensitive partial match)"""

    offset: Optional[int]

    sort_by: Optional[Iterable[SortBy]]
    """Sort by multiple fields (e.g., created_at, updated_at, name)"""


class SortBy(TypedDict, total=False):
    direction: Required[Literal["asc", "desc"]]

    field: Required[str]
