"""Normalize raw hook payloads from different IDE/agent sources.

Each IDE (Cursor, Claude Code, Codex) has its own hook event schema.
Functions in this module translate those into ``AgentHookEvent`` objects so
the span builder can be source-agnostic.

Adding a new integration:
    1. Write a ``normalize_<source>(payload: dict) -> AgentHookEvent | None``
       function following the same pattern.
    2. Register it in ``normalize()``.
"""

from __future__ import annotations

import json
import time
from typing import Any

from weave.agent_hooks.events import AgentHookEvent

# ---------------------------------------------------------------------------
# Cursor
# ---------------------------------------------------------------------------

# Maps Cursor hook_event_name to EventKind
_CURSOR_EVENT_MAP: dict[str, str] = {
    "sessionStart": "session_start",
    "sessionEnd": "session_end",
    "beforeSubmitPrompt": "user_prompt",
    "afterAgentResponse": "agent_response",
    "afterAgentThought": "agent_thought",
    "preToolUse": "tool_use_start",
    "postToolUse": "tool_use_end",
    "postToolUseFailure": "tool_use_failed",
    "afterShellExecution": "shell_exec",
    "afterFileEdit": "file_edit",
    "beforeReadFile": "file_read",
    "afterMCPExecution": "mcp_call",
    "subagentStart": "subagent_start",
    "subagentStop": "subagent_stop",
    "preCompact": "context_compacted",
    "stop": "stop",
}


def _coerce_str(v: Any) -> str:
    """Convert a value to a JSON string if it's not already a str."""
    if isinstance(v, str):
        return v
    return json.dumps(v)


def normalize_cursor(payload: dict) -> AgentHookEvent | None:
    """Convert a Cursor hook payload to a normalized ``AgentHookEvent``.

    Returns ``None`` for hooks we don't need to trace (e.g.
    ``beforeShellExecution`` — we only act on the *after* variant).

    Args:
        payload: Raw JSON object received on stdin by the Cursor hook.

    Returns:
        Normalized event, or ``None`` if this hook should be ignored.

    Examples:
        >>> ev = normalize_cursor({
        ...     "hook_event_name": "sessionStart",
        ...     "conversation_id": "abc",
        ...     "model": "claude-sonnet-4",
        ... })
        >>> ev.event_kind
        'session_start'
    """
    hook = payload.get("hook_event_name", "")
    event_kind = _CURSOR_EVENT_MAP.get(hook)
    if event_kind is None:
        return None

    conv_id = payload.get("conversation_id", "")
    gen_id = payload.get("generation_id", "")
    model = payload.get("model", "")
    ts = int(time.time() * 1000)
    roots = payload.get("workspace_roots", [])

    base: dict[str, Any] = {
        "source": "cursor",
        "event_kind": event_kind,
        "conversation_id": conv_id,
        "generation_id": gen_id,
        "model": model,
        "timestamp_ms": ts,
        "workspace_roots": roots,
        "raw": payload,
    }

    if hook == "beforeSubmitPrompt":
        return AgentHookEvent(prompt_text=payload.get("prompt", ""), **base)

    if hook == "afterAgentResponse":
        return AgentHookEvent(response_text=payload.get("text", ""), **base)

    if hook == "afterAgentThought":
        return AgentHookEvent(
            thought_text=payload.get("text", ""),
            thought_duration_ms=payload.get("duration_ms", 0),
            **base,
        )

    if hook == "preToolUse":
        return AgentHookEvent(
            tool_use_id=payload.get("tool_use_id", ""),
            tool_name=payload.get("tool_name", ""),
            tool_input=payload.get("tool_input", {}),
            **base,
        )

    if hook == "postToolUse":
        return AgentHookEvent(
            tool_use_id=payload.get("tool_use_id", ""),
            tool_name=payload.get("tool_name", ""),
            tool_input=payload.get("tool_input", {}),
            tool_output=_coerce_str(payload.get("tool_output", "")),
            tool_duration_ms=int(payload.get("duration", 0) * 1000),
            **base,
        )

    if hook == "postToolUseFailure":
        return AgentHookEvent(
            tool_use_id=payload.get("tool_use_id", ""),
            tool_name=payload.get("tool_name", ""),
            tool_error=payload.get("error_message", ""),
            **base,
        )

    if hook == "afterShellExecution":
        return AgentHookEvent(
            shell_command=payload.get("command", ""),
            shell_output=payload.get("output", ""),
            shell_exit_code=int(payload.get("exit_code", 0)),
            shell_duration_ms=int(payload.get("duration", 0) * 1000),
            **base,
        )

    if hook == "afterMCPExecution":
        return AgentHookEvent(
            tool_name=payload.get("tool_name", ""),
            tool_input=payload.get("tool_input", {}),
            tool_output=_coerce_str(payload.get("result_json", "")),
            mcp_server=payload.get("server_url", payload.get("server_command", "")),
            **base,
        )

    if hook == "afterFileEdit":
        return AgentHookEvent(
            file_path=payload.get("file_path", ""),
            file_edits=payload.get("edits", []),
            **base,
        )

    if hook == "beforeReadFile":
        return AgentHookEvent(
            file_path=payload.get("file_path", ""),
            file_content=payload.get("content", "")[:500],  # truncate
            **base,
        )

    if hook == "subagentStart":
        return AgentHookEvent(
            subagent_id=payload.get("subagent_id", ""),
            subagent_type=payload.get("subagent_type", ""),
            subagent_task=payload.get("task", ""),
            subagent_model=payload.get("subagent_model", ""),
            parent_conversation_id=payload.get("parent_conversation_id", ""),
            **base,
        )

    if hook == "subagentStop":
        return AgentHookEvent(
            subagent_id=payload.get("subagent_id", ""),
            subagent_status=payload.get("status", ""),
            subagent_duration_ms=payload.get("duration_ms", 0),
            subagent_tool_call_count=payload.get("tool_call_count", 0),
            subagent_modified_files=payload.get("modified_files", []),
            subagent_summary=payload.get("summary", ""),
            **base,
        )

    if hook == "preCompact":
        return AgentHookEvent(
            context_tokens=payload.get("context_tokens", 0),
            context_window=payload.get("context_window_size", 0),
            **base,
        )

    # sessionStart, sessionEnd, stop — no extra fields needed
    return AgentHookEvent(**base)


# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------
# Claude Code hooks use PascalCase event names and a slightly different schema.
# Ref: https://docs.anthropic.com/en/docs/claude-code/hooks

_CLAUDE_EVENT_MAP: dict[str, str] = {
    "PreToolUse": "tool_use_start",
    "PostToolUse": "tool_use_end",
    "Notification": "agent_response",
    "Stop": "stop",
    "SubagentStop": "subagent_stop",
}


def normalize_claude_code(payload: dict) -> AgentHookEvent | None:
    """Convert a Claude Code hook payload to a normalized ``AgentHookEvent``.

    Claude Code hooks are invoked with the event type in a ``hook_type`` field
    (or passed as an environment variable ``CLAUDE_HOOK_TYPE``).

    Args:
        payload: Raw JSON object received on stdin by the Claude Code hook.

    Returns:
        Normalized event, or ``None`` if this hook should be ignored.

    Examples:
        >>> ev = normalize_claude_code({
        ...     "hook_type": "PreToolUse",
        ...     "session_id": "sess-123",
        ...     "tool_name": "Read",
        ...     "tool_input": {"path": "/foo/bar.py"},
        ... })
        >>> ev.event_kind
        'tool_use_start'
    """
    hook = payload.get("hook_type", "")
    event_kind = _CLAUDE_EVENT_MAP.get(hook)
    if event_kind is None:
        return None

    session_id = payload.get("session_id", "")
    # Claude Code doesn't have conversation_id — use session_id as the key
    conv_id = session_id
    ts = int(time.time() * 1000)

    base: dict[str, Any] = {
        "source": "claude-code",
        "event_kind": event_kind,
        "conversation_id": conv_id,
        "session_id": session_id,
        "model": payload.get("model", ""),
        "timestamp_ms": ts,
        "raw": payload,
    }

    if hook in {"PreToolUse", "PostToolUse"}:
        tool_result = payload.get("tool_response", {})
        return AgentHookEvent(
            tool_name=payload.get("tool_name", ""),
            tool_input=payload.get("tool_input", {}),
            tool_output=_coerce_str(tool_result) if hook == "PostToolUse" else "",
            **base,
        )

    if hook == "Notification":
        return AgentHookEvent(response_text=payload.get("message", ""), **base)

    return AgentHookEvent(**base)


# ---------------------------------------------------------------------------
# Codex (OpenAI)
# ---------------------------------------------------------------------------
# OpenAI Codex exposes hooks in a similar pattern to Cursor.
# Ref: https://platform.openai.com/docs/codex/hooks (TBD — extend as needed)

def normalize_codex(payload: dict) -> AgentHookEvent | None:
    """Convert an OpenAI Codex hook payload to a normalized ``AgentHookEvent``.

    Args:
        payload: Raw JSON object received on stdin by the Codex hook.

    Returns:
        Normalized event, or ``None`` if this hook should be ignored.
    """
    # Codex uses the same schema as Cursor for tool-use hooks
    # (both are VS Code extensions under the hood).  Delegate to the Cursor
    # normalizer but override ``source``.
    event = normalize_cursor(payload)
    if event is not None:
        event.source = "codex"
    return event


# ---------------------------------------------------------------------------
# Top-level dispatcher
# ---------------------------------------------------------------------------

def normalize(payload: dict) -> AgentHookEvent | None:
    """Detect the source and normalize a raw hook payload.

    Source is detected by the presence of a ``hook_event_name`` key (Cursor /
    Codex) or ``hook_type`` key (Claude Code).  Falls back to Cursor.

    Args:
        payload: Raw JSON object received from any supported IDE hook.

    Returns:
        Normalized ``AgentHookEvent``, or ``None`` to skip this event.

    Examples:
        >>> ev = normalize({"hook_event_name": "sessionStart",
        ...                 "conversation_id": "xyz"})
        >>> ev.source
        'cursor'
    """
    if "hook_type" in payload:
        return normalize_claude_code(payload)
    # Check for Codex-specific marker (set by Codex hooks.json)
    if payload.get("_source") == "codex":
        return normalize_codex(payload)
    return normalize_cursor(payload)
