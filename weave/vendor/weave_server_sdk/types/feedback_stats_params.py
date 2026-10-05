# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["FeedbackStatsParams", "Metric"]


class FeedbackStatsParams(TypedDict, total=False):
    project_id: Required[str]

    start: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]
    """Inclusive start time (UTC, ISO 8601)."""

    end: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """Exclusive end time (UTC, ISO 8601). Defaults to now if omitted."""

    feedback_type: Optional[str]
    """Filter by feedback_type."""

    granularity: Optional[int]
    """Bucket size in seconds. If omitted, auto-selected based on time range."""

    metrics: Iterable[Metric]
    """Metrics to aggregate from payload_dump."""

    timezone: str
    """IANA timezone for bucket alignment."""

    trigger_ref: Optional[str]
    """Filter by trigger_ref (exact or prefix match for all-versions)."""


class Metric(TypedDict, total=False):
    """Specification for a feedback payload metric to aggregate."""

    json_path: Required[str]
    """Dot path into payload_dump (e.g. 'output', 'output.score')."""

    aggregations: List[Literal["sum", "avg", "min", "max", "count", "count_true", "count_false"]]
    """Aggregation functions to compute.

    If empty, defaults are chosen based on value_type: numeric->avg/min/max,
    boolean->count_true/count_false.
    """

    percentiles: Iterable[float]
    """Percentile values to compute (0–100), e.g.

    [5, 50, 95]. Only applicable for numeric value_type fields; ignored for
    boolean/categorical.
    """

    value_type: Literal["numeric", "boolean", "categorical"]
    """Type of value at path. numeric: avg/min/max; boolean: count_true/count_false."""
