# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime

from ..._models import BaseModel
from ..agent_trace_chat_res import AgentTraceChatRes

__all__ = ["ConversationChatResponse", "Feedback"]


class Feedback(BaseModel):
    """Feedback row from the agent chat `include_feedback` projection.

    Field names match FEEDBACK_QUERY_FIELDS. This is not the feedback
    table row and not FeedbackCreateReq: project_id and span_* are not
    selected.
    """

    id: str

    annotation_ref: Optional[str] = None

    call_ref: Optional[str] = None

    created_at: Optional[datetime] = None

    creator: Optional[str] = None

    feedback_type: str

    payload: Dict[str, object]

    runnable_ref: Optional[str] = None

    scorer_rating_confidences: Dict[str, float]

    scorer_rating_reasons: Dict[str, str]

    scorer_ratings: Dict[str, float]

    scorer_tag_confidences: Dict[str, float]

    scorer_tag_reasons: Dict[str, str]

    scorer_tags: List[str]

    trigger_ref: Optional[str] = None

    wb_user_id: Optional[str] = None

    weave_ref: str


class ConversationChatResponse(BaseModel):
    """Multi-turn chat view: an ordered list of per-turn chat responses.

    Each entry in `turns` corresponds to one trace_id, which Weave treats as
    one conversation turn. This is not necessarily one `invoke_agent` span:
    a turn can contain zero, one, or many agent invocations. The frontend can
    render turn-number dividers between entries and still reuse
    `AgentTraceChatRes` rendering for each individual turn.
    """

    conversation_id: str

    feedback: Optional[List[Feedback]] = None

    has_more: bool

    limit: int

    offset: int

    total_cost_usd: Optional[float] = None

    total_turns: int

    turns: List[AgentTraceChatRes]
