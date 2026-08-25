# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["CallStartParams", "Start"]


class CallStartParams(TypedDict, total=False):
    start: Required[Start]


class Start(TypedDict, total=False):
    attributes: Required[Dict[str, object]]

    inputs: Required[Dict[str, object]]

    op_name: Required[str]

    project_id: Required[str]

    started_at: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]

    id: Optional[str]

    display_name: Optional[str]

    otel_dump: Optional[Dict[str, object]]

    parent_id: Optional[str]

    thread_id: Optional[str]

    trace_id: Optional[str]

    turn_id: Optional[str]

    wb_run_id: Optional[str]

    wb_run_step: Optional[int]

    wb_user_id: Optional[str]
    """Do not set directly. Server will automatically populate this field."""
