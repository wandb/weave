# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional
from typing_extensions import Literal, Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["TableQueryParams", "Filter", "SortBy"]


class TableQueryParams(TypedDict, total=False):
    digest: Required[str]
    """The digest of the table to query"""

    project_id: Required[str]
    """The ID of the project"""

    filter: Optional[Filter]
    """Optional filter to apply to the query. See `TableRowFilter` for more details."""

    limit: Optional[int]
    """Maximum number of rows to return"""

    offset: Optional[int]
    """Number of rows to skip before starting to return rows"""

    sort_by: Optional[Iterable[SortBy]]
    """List of fields to sort by.

    Fields can be dot-separated to access dictionary values. No sorting uses the
    default table order (insertion order).
    """


class Filter(TypedDict, total=False):
    """Optional filter to apply to the query. See `TableRowFilter` for more details."""

    row_digests: Optional[SequenceNotStr[str]]
    """List of row digests to filter by"""


class SortBy(TypedDict, total=False):
    direction: Required[Literal["asc", "desc"]]

    field: Required[str]
