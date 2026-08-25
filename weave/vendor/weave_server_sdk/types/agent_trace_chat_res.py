# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = [
    "AgentTraceChatRes",
    "Message",
    "MessageAgentStart",
    "MessageAssistantMessage",
    "MessageContextCompacted",
    "MessageToolCall",
    "MessageUserMessage",
]


class MessageAgentStart(BaseModel):
    """Payload for an agent lifecycle boundary."""

    model: Optional[str] = None

    status: Optional[Literal["UNSET", "OK", "ERROR"]] = None

    system_instructions: Optional[str] = None

    tool_definitions: Optional[str] = None


class MessageAssistantMessage(BaseModel):
    """Payload for assistant text emitted by an agent or LLM span."""

    text: str

    content_refs: Optional[List[str]] = None

    duration_ms: Optional[int] = None

    input_cost_usd: Optional[float] = None

    input_tokens: Optional[int] = None

    model: Optional[str] = None

    output_cost_usd: Optional[float] = None

    output_tokens: Optional[int] = None

    reasoning_content: Optional[str] = None

    reasoning_tokens: Optional[int] = None

    status: Optional[Literal["UNSET", "OK", "ERROR"]] = None

    total_cost_usd: Optional[float] = None


class MessageContextCompacted(BaseModel):
    """Payload for a context-window compaction event."""

    compaction_items_after: Optional[int] = None

    compaction_items_before: Optional[int] = None

    compaction_summary: Optional[str] = None


class MessageToolCall(BaseModel):
    """Payload for a tool call timeline event."""

    content_refs: Optional[List[str]] = None

    duration_ms: Optional[int] = None

    status: Optional[Literal["UNSET", "OK", "ERROR"]] = None

    tool_arguments: Optional[str] = None

    tool_name: Optional[str] = None

    tool_result: Optional[str] = None


class MessageUserMessage(BaseModel):
    """Payload for a user prompt in the chat timeline."""

    text: str

    content_refs: Optional[List[str]] = None


class Message(BaseModel):
    """A single element in the structured agent trajectory / chat view.

    Common event fields live at the top level. Type-specific fields are
    grouped under the payload matching `type`, and exactly one payload must be
    set. This keeps subtype nullability explicit while preserving a single
    ordered timeline model for callers.
    """

    type: Literal["user_message", "assistant_message", "tool_call", "agent_handoff", "agent_start", "context_compacted"]

    agent_handoff: Optional[object] = None
    """Payload for a future agent-to-agent handoff event."""

    agent_name: Optional[str] = None

    agent_start: Optional[MessageAgentStart] = None
    """Payload for an agent lifecycle boundary."""

    agent_version: Optional[str] = None

    assistant_message: Optional[MessageAssistantMessage] = None
    """Payload for assistant text emitted by an agent or LLM span."""

    context_compacted: Optional[MessageContextCompacted] = None
    """Payload for a context-window compaction event."""

    feedback: Optional[List[Dict[str, object]]] = None

    span_id: Optional[str] = None

    started_at: Optional[datetime] = None

    status_code: Optional[Literal["UNSET", "OK", "ERROR"]] = None

    tool_call: Optional[MessageToolCall] = None
    """Payload for a tool call timeline event."""

    user_message: Optional[MessageUserMessage] = None
    """Payload for a user prompt in the chat timeline."""


class AgentTraceChatRes(BaseModel):
    """
    Structured chat view: a linear sequence of messages representing
    the agent trajectory for a single trace.
    """

    trace_id: str

    agent_name: Optional[str] = None

    agent_version: Optional[str] = None

    ended_at: Optional[datetime] = None

    feedback: Optional[List[Dict[str, object]]] = None

    messages: Optional[List[Message]] = None

    provider: Optional[str] = None

    root_span_name: Optional[str] = None

    started_at: Optional[datetime] = None

    status_code: Optional[Literal["UNSET", "OK", "ERROR"]] = None

    total_cache_creation_input_tokens: Optional[int] = None

    total_cache_read_input_tokens: Optional[int] = None

    total_cost_usd: Optional[float] = None

    total_duration_ms: Optional[int] = None
    """Wall-clock duration of the trace root span in milliseconds.

    This is not a sum of child span durations.
    """

    total_input_tokens: Optional[int] = None

    total_output_tokens: Optional[int] = None

    total_reasoning_tokens: Optional[int] = None

    wb_user_id: Optional[str] = None
