"""Normalized event types for agent session tracing.

All IDE/agent hook sources (Cursor, Claude Code, Codex) are normalized into
``AgentHookEvent`` before being processed by the span builder, so the daemon
is source-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SourceKind = Literal["cursor", "claude-code", "codex"]

EventKind = Literal[
    "session_start",
    "session_end",
    "user_prompt",
    "agent_response",
    "agent_thought",
    "tool_use_start",
    "tool_use_end",
    "tool_use_failed",
    "shell_exec",
    "file_read",
    "file_edit",
    "mcp_call",
    "subagent_start",
    "subagent_stop",
    "context_compacted",
    "stop",  # agent loop ended for one turn
]


@dataclass
class AgentHookEvent:
    """Normalized representation of a single IDE hook event.

    Source-specific normalizers (in normalizer.py) parse raw hook payloads and
    return instances of this class.  The span builder only consumes these.

    Args:
        source: Which IDE/agent emitted this event.
        event_kind: Normalized event type.
        conversation_id: Stable identifier across the whole conversation
            (maps to ``gen_ai.conversation.id``).
        generation_id: Changes per user message (identifies one turn).
        session_id: Human-readable session name, if any.
        model: LLM model in use (``gen_ai.request.model``).
        timestamp_ms: Unix milliseconds when the event occurred.
        workspace_roots: Absolute paths of open workspace folders.
        raw: Original payload dict for debugging.

    Examples:
        >>> e = AgentHookEvent(source="cursor", event_kind="session_start",
        ...                    conversation_id="abc123", model="claude-4")
        >>> e.event_kind
        'session_start'
    """

    source: SourceKind
    event_kind: EventKind
    conversation_id: str
    generation_id: str = ""
    session_id: str = ""
    model: str = ""
    timestamp_ms: int = 0
    workspace_roots: list[str] = field(default_factory=list)

    # --- prompt / response ---
    prompt_text: str = ""
    response_text: str = ""

    # --- agent thought / reasoning ---
    thought_text: str = ""
    thought_duration_ms: int = 0

    # --- tool calls (preToolUse / postToolUse) ---
    tool_use_id: str = ""
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    tool_output: str = ""
    tool_error: str = ""
    tool_duration_ms: int = 0

    # --- shell execution ---
    shell_command: str = ""
    shell_output: str = ""
    shell_exit_code: int = 0
    shell_duration_ms: int = 0

    # --- file operations ---
    file_path: str = ""
    file_content: str = ""
    file_edits: list[dict] = field(default_factory=list)

    # --- MCP calls ---
    mcp_server: str = ""
    mcp_result: str = ""

    # --- subagent (Task tool) ---
    subagent_id: str = ""
    subagent_type: str = ""
    subagent_task: str = ""
    subagent_model: str = ""
    subagent_status: str = ""
    subagent_duration_ms: int = 0
    subagent_tool_call_count: int = 0
    subagent_modified_files: list[str] = field(default_factory=list)
    subagent_summary: str = ""
    parent_conversation_id: str = ""

    # --- context compaction ---
    context_tokens: int = 0
    context_window: int = 0

    # --- raw payload for debugging ---
    raw: dict = field(default_factory=dict)
