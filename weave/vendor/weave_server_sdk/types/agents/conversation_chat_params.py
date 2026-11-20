# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional
from typing_extensions import Literal, Required, TypedDict

__all__ = ["ConversationChatParams", "SortBy"]


class ConversationChatParams(TypedDict, total=False):
    conversation_id: Required[str]

    project_id: Required[str]

    include_feedback: bool

    include_model_tool_calls: bool
    """
    Include tool calls requested in model outputs, even when no execution span was
    recorded, and place each execution span after the model span that requested it.
    Requests without execution evidence have no status, duration, or result.
    Defaults to false.
    """

    limit: int
    """Maximum number of conversation turns to return."""

    offset: int
    """Number of turns to skip in the requested sort order.

    When `sort_by` is omitted, results are returned in chronological order within
    the selected page.
    """

    sort_by: Optional[Iterable[SortBy]]
    """Controls how turns are sorted and paginated.

    Only `started_at` is supported. When omitted, the endpoint selects the most
    recent `limit` turns and returns them in ascending `started_at` order.
    """


class SortBy(TypedDict, total=False):
    """Sort specification for agent query endpoints."""

    field: Required[str]

    direction: Literal["asc", "desc"]
