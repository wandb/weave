# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo

__all__ = ["CallStatsParams", "CallMetric", "Filter", "UsageMetric"]


class CallStatsParams(TypedDict, total=False):
    project_id: Required[str]

    start: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]
    """Inclusive start time (UTC, ISO 8601)."""

    call_metrics: Optional[Iterable[CallMetric]]
    """Call-level metrics (latency, counts) to compute. Grouped by timestamp only."""

    end: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """Exclusive end time (UTC, ISO 8601). Defaults to now if omitted."""

    filter: Optional[Filter]

    granularity: Optional[int]
    """Bucket size in seconds (e.g., 3600 for 1 hour).

    If omitted, auto-selected based on time range. Will be adjusted if it would
    produce more than 10,000 buckets.
    """

    timezone: str
    """IANA timezone for bucket alignment (e.g., 'America/New_York')"""

    usage_metrics: Optional[Iterable[UsageMetric]]
    """Usage metrics (tokens, cost) to compute. Grouped by timestamp and model."""


class CallMetric(TypedDict, total=False):
    """Specification for a call-level metric to aggregate (not grouped by model)."""

    metric: Required[Literal["latency_ms", "call_count", "error_count"]]
    """Metric to aggregate."""

    aggregations: List[Literal["sum", "avg", "min", "max", "count", "count_true", "count_false"]]
    """Basic aggregation functions to apply"""

    percentiles: Iterable[float]
    """Percentile values to compute (0-100). E.g., [50, 95, 99] for p50, p95, p99"""


class Filter(TypedDict, total=False):
    call_ids: Optional[SequenceNotStr[str]]

    input_refs: Optional[SequenceNotStr[str]]

    op_names: Optional[SequenceNotStr[str]]

    output_refs: Optional[SequenceNotStr[str]]

    parent_ids: Optional[SequenceNotStr[str]]

    thread_ids: Optional[SequenceNotStr[str]]

    trace_ids: Optional[SequenceNotStr[str]]

    trace_roots_only: Optional[bool]

    turn_ids: Optional[SequenceNotStr[str]]

    wb_run_ids: Optional[SequenceNotStr[str]]

    wb_user_ids: Optional[SequenceNotStr[str]]


class UsageMetric(TypedDict, total=False):
    """Specification for a usage metric to aggregate (grouped by model)."""

    metric: Required[
        Literal[
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
            "input_cost",
            "output_cost",
            "total_cost",
        ]
    ]
    """Metric to aggregate. Token metrics are normalized across providers."""

    aggregations: List[Literal["sum", "avg", "min", "max", "count", "count_true", "count_false"]]
    """Basic aggregation functions to apply"""

    percentiles: Iterable[float]
    """Percentile values to compute (0-100). E.g., [50, 95, 99] for p50, p95, p99"""
