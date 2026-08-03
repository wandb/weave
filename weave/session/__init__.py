"""Deprecated import path for the Weave Conversation SDK.

The Weave **Session SDK** was renamed to the **Conversation SDK**. Importing
from ``weave.session`` still works but emits a ``DeprecationWarning`` and will
be removed in a future release — import from ``weave.conversation`` instead::

    from weave.conversation import TextPart, ToolCallPart, start_conversation

The ``session``-named callables re-exported here (``start_session``,
``Session``, ``end_session``, ``log_session``, ``get_current_session``) are
deprecated aliases that forward to their ``conversation`` equivalents and
translate the old ``session_id`` / ``session_name`` arguments.
"""

from __future__ import annotations

import warnings

from weave.conversation import (
    LLM,
    BlobPart,
    FilePart,
    LogResult,
    MediaAttachment,
    Message,
    MessagePart,
    Reasoning,
    ReasoningPart,
    SubAgent,
    TextPart,
    Tool,
    ToolCallPart,
    ToolCallResponsePart,
    Turn,
    UriPart,
    Usage,
    agent_name_override,
    end_llm,
    end_subagent,
    end_tool,
    end_turn,
    get_current_llm,
    get_current_span,
    get_current_subagent,
    get_current_tool,
    get_current_turn,
    log_turn,
    start_llm,
    start_subagent,
    start_tool,
    start_turn,
)
from weave.conversation._deprecated import (
    Session,
    end_session,
    get_current_session,
    log_session,
    start_session,
)

warnings.warn(
    "weave.session has been renamed to weave.conversation; importing from "
    "weave.session is deprecated and will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
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
    "end_subagent",
    "end_tool",
    "end_turn",
    "get_current_llm",
    "get_current_session",
    "get_current_span",
    "get_current_subagent",
    "get_current_tool",
    "get_current_turn",
    "log_session",
    "log_turn",
    "start_llm",
    "start_session",
    "start_subagent",
    "start_tool",
    "start_turn",
]
