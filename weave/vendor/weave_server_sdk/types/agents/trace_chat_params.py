# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["TraceChatParams"]


class TraceChatParams(TypedDict, total=False):
    project_id: Required[str]

    trace_id: Required[str]

    include_feedback: bool
