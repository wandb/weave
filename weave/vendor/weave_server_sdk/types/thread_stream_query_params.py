# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo

__all__ = ["ThreadStreamQueryParams", "Filter", "SortBy"]


class ThreadStreamQueryParams(TypedDict, total=False):
    project_id: Required[str]
    """The ID of the project"""

    filter: Optional[Filter]
    """Filter criteria for the threads query"""

    limit: Optional[int]
    """Maximum number of threads to return"""

    offset: Optional[int]
    """Number of threads to skip"""

    sort_by: Optional[Iterable[SortBy]]
    """Sorting criteria for the threads.

    Supported fields: 'thread_id', 'turn_count', 'start_time', 'last_updated',
    'p50_turn_duration_ms', 'p99_turn_duration_ms'.
    """


class Filter(TypedDict, total=False):
    """Filter criteria for the threads query"""

    after_datetime: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """Only include threads with start_time after this timestamp"""

    before_datetime: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """Only include threads with last_updated before this timestamp"""

    thread_ids: Optional[SequenceNotStr[str]]
    """Only include threads with thread_ids in this list"""


class SortBy(TypedDict, total=False):
    direction: Required[Literal["asc", "desc"]]

    field: Required[str]
