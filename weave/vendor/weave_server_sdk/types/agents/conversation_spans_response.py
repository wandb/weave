# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from typing_extensions import Literal

from ..._models import BaseModel

__all__ = [
    "ConversationSpansResponse",
    "Conversation",
    "ConversationSpan",
    "ConversationSpansFeedback",
    "ConversationSpansFeedbackRating",
]


class ConversationSpan(BaseModel):
    """One span in a conversation's trace.

    Returned by `agent_conversation_spans`, which reads span scalar columns
    only (no message bodies). Spans are ordered by `started_at`, which
    approximates — but does not exactly match — the detail chat view's
    parent/child tree-walk order. `operation_name` is the raw OTel value; the
    client maps it to a display category.
    """

    duration_ms: int

    operation_name: str

    span_id: str

    status: Literal["UNSET", "OK", "ERROR"]

    trace_id: str


class ConversationSpansFeedbackRating(BaseModel):
    """One numeric rating (a scorer score) applied to a turn or conversation."""

    confidence: Optional[float] = None

    name: str

    reason: Optional[str] = None

    value: float


class ConversationSpansFeedback(BaseModel):
    """Tags and ratings applied to a conversation's turn (or the conversation).

    Positioned client-side by matching `trace_id` (turn) against the spans;
    `trace_id` is None for conversation-level feedback.
    """

    feedback_type: Literal["wandb.agent_user_feedback", "wandb.agent_monitor"]

    ratings: List[ConversationSpansFeedbackRating]
    """Numeric scorer ratings applied to this feedback."""

    tags: List[str]
    """Arbitrary descriptive tags applied to this feedback."""

    trace_id: Optional[str] = None
    """The turn this feedback is anchored to; None for conversation-level."""


class Conversation(BaseModel):
    """One conversation's span sequence and its feedback markers."""

    conversation_id: str

    spans: List[ConversationSpan]

    spans_feedback: List[ConversationSpansFeedback]


class ConversationSpansResponse(BaseModel):
    """Span sequences + feedback markers, one entry per requested conversation."""

    conversations: List[Conversation]
