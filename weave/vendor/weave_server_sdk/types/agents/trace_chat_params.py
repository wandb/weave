# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["TraceChatParams"]


class TraceChatParams(TypedDict, total=False):
    project_id: Required[str]

    trace_id: Required[str]

    include_feedback: bool

    include_model_tool_calls: bool
    """
    Include tool calls requested in model outputs, even when no execution span was
    recorded, and place each execution span after the model span that requested it.
    Requests without execution evidence have no status, duration, or result.
    Defaults to false.
    """
