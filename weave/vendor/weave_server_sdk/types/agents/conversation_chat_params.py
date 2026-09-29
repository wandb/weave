# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["ConversationChatParams"]


class ConversationChatParams(TypedDict, total=False):
    conversation_id: Required[str]

    project_id: Required[str]

    include_feedback: bool

    include_model_tool_calls: bool
    """
    Include tool calls requested in model outputs, even when no execution span was
    recorded. Requests without execution evidence have no status, duration, or
    result. Defaults to false.
    """

    limit: int
    """Maximum number of conversation turns to return."""

    offset: int
    """Number of most-recent turns to skip.

    Results are returned in chronological order within the selected page.
    """
