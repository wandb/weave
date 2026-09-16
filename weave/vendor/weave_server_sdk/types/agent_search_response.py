# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Union
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["AgentSearchResponse", "Result", "ResultMatchedMessage"]


class ResultMatchedMessage(BaseModel):
    """A single message that matched the search query."""

    content_digest: str

    content_preview: str

    role: Union[Literal["", "user", "assistant", "system", "tool", "tool_call", "tool_result"], str]

    span_id: str

    started_at: datetime

    trace_id: str


class Result(BaseModel):
    """A conversation containing messages that matched the search query."""

    agent_name: str

    conversation_id: str

    conversation_name: str

    last_activity: datetime

    matched_messages: List[ResultMatchedMessage]


class AgentSearchResponse(BaseModel):
    """Response from a full-text search across agent messages."""

    results: List[Result]

    total_conversations: int
