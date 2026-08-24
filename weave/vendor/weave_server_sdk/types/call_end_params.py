# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["CallEndParams", "End", "EndSummary", "EndSummaryUsage"]


class CallEndParams(TypedDict, total=False):
    end: Required[End]


class EndSummaryUsage(TypedDict, total=False, extra_items=object):  # type: ignore[call-arg]
    cache_creation_input_tokens: Optional[int]

    cache_read_input_tokens: Optional[int]

    completion_tokens: Optional[int]

    input_tokens: Optional[int]

    output_tokens: Optional[int]

    prompt_tokens: Optional[int]

    requests: Optional[int]

    total_tokens: Optional[int]


class EndSummary(TypedDict, total=False, extra_items=object):  # type: ignore[call-arg]
    status_counts: Dict[str, int]

    usage: Dict[str, EndSummaryUsage]


class End(TypedDict, total=False):
    id: Required[str]

    ended_at: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]

    project_id: Required[str]

    summary: Required[EndSummary]

    exception: Optional[str]

    is_eval: Optional[bool]

    output: object

    started_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    trace_id: Optional[str]

    wb_run_step_end: Optional[int]
