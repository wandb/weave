# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["V2CallCompleteParams", "Batch", "BatchSummary", "BatchSummaryUsage"]


class V2CallCompleteParams(TypedDict, total=False):
    entity: Required[str]

    batch: Required[Iterable[Batch]]


class BatchSummaryUsage(TypedDict, total=False, extra_items=object):  # type: ignore[call-arg]
    cache_creation_input_tokens: Optional[int]

    cache_read_input_tokens: Optional[int]

    completion_tokens: Optional[int]

    input_tokens: Optional[int]

    output_tokens: Optional[int]

    prompt_tokens: Optional[int]

    requests: Optional[int]

    total_tokens: Optional[int]


class BatchSummary(TypedDict, total=False, extra_items=object):  # type: ignore[call-arg]
    status_counts: Dict[str, int]

    usage: Dict[str, BatchSummaryUsage]


class Batch(TypedDict, total=False):
    """Schema for inserting a completed call directly.

    This represents a call that is already finished at insertion time, with both
    start and end information provided together. Used by the calls_complete endpoint.
    """

    id: Required[str]

    attributes: Required[Dict[str, object]]

    ended_at: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]

    inputs: Required[Dict[str, object]]

    op_name: Required[str]

    project_id: Required[str]

    started_at: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]

    summary: Required[BatchSummary]

    trace_id: Required[str]

    display_name: Optional[str]

    exception: Optional[str]

    otel_dump: Optional[Dict[str, object]]

    output: object

    parent_id: Optional[str]

    thread_id: Optional[str]

    turn_id: Optional[str]

    wb_run_id: Optional[str]

    wb_run_step: Optional[int]

    wb_run_step_end: Optional[int]

    wb_user_id: Optional[str]
    """Do not set directly. Server will automatically populate this field."""
