# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional

from ..._models import BaseModel
from ..agent_trace_chat_res import AgentTraceChatRes

__all__ = ["ConversationChatResponse"]


class ConversationChatResponse(BaseModel):
    """Multi-turn chat view: an ordered list of per-turn chat responses.

    Each entry in `turns` corresponds to one trace_id, which Weave treats as
    one conversation turn. This is not necessarily one `invoke_agent` span:
    a turn can contain zero, one, or many agent invocations. The frontend can
    render turn-number dividers between entries and still reuse
    `AgentTraceChatRes` rendering for each individual turn.
    """

    conversation_id: str

    feedback: Optional[List[Dict[str, object]]] = None

    has_more: bool

    limit: int

    offset: int

    total_cost_usd: Optional[float] = None

    total_turns: int

    turns: List[AgentTraceChatRes]
