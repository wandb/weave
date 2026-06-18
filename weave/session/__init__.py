"""Public namespace for the Weave Session SDK.

Imports everything user code needs to construct sessions, turns, llm
spans, tool spans, and structured messages. Concrete message parts
(``TextPart``, ``ToolCallPart``, etc.) and the ``MessagePart`` union
live here rather than at the top-level ``weave`` namespace, mirroring
the ``langchain_core.messages`` pattern: callers building structured
messages do ``from weave.session import TextPart, ToolCallPart``.
"""

from weave.session.agent_context import agent_name_override
from weave.session.session import (
    LLM,
    BlobPart,
    FilePart,
    LogResult,
    MediaAttachment,
    Message,
    MessagePart,
    Reasoning,
    ReasoningPart,
    Session,
    SubAgent,
    TextPart,
    Tool,
    ToolCallPart,
    ToolCallResponsePart,
    Turn,
    UriPart,
    Usage,
    end_llm,
    end_session,
    end_turn,
    get_current_llm,
    get_current_session,
    get_current_turn,
    log_session,
    log_turn,
    start_llm,
    start_session,
    start_subagent,
    start_tool,
    start_turn,
)

__all__ = [
    "LLM",
    "BlobPart",
    "FilePart",
    "LogResult",
    "MediaAttachment",
    "Message",
    "MessagePart",
    "Reasoning",
    "ReasoningPart",
    "Session",
    "SubAgent",
    "TextPart",
    "Tool",
    "ToolCallPart",
    "ToolCallResponsePart",
    "Turn",
    "UriPart",
    "Usage",
    "agent_name_override",
    "end_llm",
    "end_session",
    "end_turn",
    "get_current_llm",
    "get_current_session",
    "get_current_turn",
    "log_session",
    "log_turn",
    "start_llm",
    "start_session",
    "start_subagent",
    "start_tool",
    "start_turn",
]
