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
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

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
        "transcript_path": payload.get("transcript_path") or "",
        "user_email": payload.get("user_email") or "",
        "raw": payload,
    }

    if hook == "beforeSubmitPrompt":
        raw_attachments = payload.get("attachments", [])
        logger.info(
            "beforeSubmitPrompt: %d rule-attachments (screenshots scanned at turn-close)",
            len(raw_attachments),
        )
        return AgentHookEvent(
            prompt_text=payload.get("prompt", ""),
            attachments=list(raw_attachments),
            **base,
        )

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
            agent_message=payload.get("agent_message", ""),
            cwd=payload.get("cwd", ""),
            **base,
        )

    if hook == "postToolUse":
        return AgentHookEvent(
            tool_use_id=payload.get("tool_use_id", ""),
            tool_name=payload.get("tool_name", ""),
            tool_input=payload.get("tool_input", {}),
            tool_output=_coerce_str(payload.get("tool_output", "")),
            tool_duration_ms=int(payload.get("duration", 0) * 1000),
            cwd=payload.get("cwd", ""),
            **base,
        )

    if hook == "postToolUseFailure":
        return AgentHookEvent(
            tool_use_id=payload.get("tool_use_id", ""),
            tool_name=payload.get("tool_name", ""),
            tool_error=payload.get("error_message", ""),
            failure_type=payload.get("failure_type", ""),
            is_interrupt=bool(payload.get("is_interrupt", False)),
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
            tool_call_id=payload.get("tool_call_id", ""),
            is_parallel_worker=bool(payload.get("is_parallel_worker", False)),
            git_branch=payload.get("git_branch", ""),
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
            agent_transcript_path=payload.get("agent_transcript_path") or "",
            subagent_message_count=payload.get("message_count", 0),
            subagent_loop_count=payload.get("loop_count", 0),
            **base,
        )

    if hook == "preCompact":
        return AgentHookEvent(
            context_tokens=payload.get("context_tokens", 0),
            context_window=payload.get("context_window_size", 0),
            compact_trigger=payload.get("trigger", ""),
            context_usage_percent=int(payload.get("context_usage_percent", 0)),
            message_count=payload.get("message_count", 0),
            messages_to_compact=payload.get("messages_to_compact", 0),
            is_first_compaction=bool(payload.get("is_first_compaction", False)),
            **base,
        )

    if hook == "sessionStart":
        return AgentHookEvent(
            session_id=payload.get("session_id", ""),
            is_background_agent=bool(payload.get("is_background_agent", False)),
            composer_mode=payload.get("composer_mode", ""),
            **base,
        )

    if hook == "sessionEnd":
        return AgentHookEvent(
            session_id=payload.get("session_id", ""),
            end_reason=payload.get("reason", ""),
            end_duration_ms=payload.get("duration_ms", 0),
            final_status=payload.get("final_status", ""),
            is_background_agent=bool(payload.get("is_background_agent", False)),
            **base,
        )

    if hook == "stop":
        return AgentHookEvent(
            stop_status=payload.get("status", ""),
            loop_count=payload.get("loop_count", 0),
            **base,
        )

    return AgentHookEvent(**base)


# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------
# Claude Code hooks use PascalCase event names in ``hook_event_name`` and a
# slightly different payload schema from Cursor.
# Ref: https://docs.anthropic.com/en/docs/claude-code/hooks

_CLAUDE_EVENT_MAP: dict[str, str] = {
    "SessionStart": "session_start",
    "SessionEnd": "session_end",
    "UserPromptSubmit": "user_prompt",
    "PreToolUse": "tool_use_start",
    "PostToolUse": "tool_use_end",
    "PostToolUseFailure": "tool_use_failed",
    "Notification": "agent_response",
    "SubagentStart": "subagent_start",
    "SubagentStop": "subagent_stop",
    "Stop": "stop",
    "StopFailure": "stop_failure",
    "PreCompact": "context_compacted",
    "PostCompact": "post_compact",
}


def normalize_claude_code(payload: dict) -> AgentHookEvent | None:
    """Convert a Claude Code hook payload to a normalized ``AgentHookEvent``.

    Claude Code hooks send the event type in ``hook_event_name`` using
    PascalCase names (e.g. ``"PreToolUse"``).  Common fields include
    ``session_id``, ``transcript_path``, and ``cwd``.

    Args:
        payload: Raw JSON object received from a Claude Code hook.

    Returns:
        Normalized event, or ``None`` if this hook should be ignored.

    Examples:
        >>> ev = normalize_claude_code({
        ...     "hook_event_name": "PreToolUse",
        ...     "session_id": "sess-123",
        ...     "tool_name": "Read",
        ...     "tool_input": {"path": "/foo/bar.py"},
        ... })
        >>> ev.event_kind
        'tool_use_start'
    """
    hook = payload.get("hook_event_name", "")
    event_kind = _CLAUDE_EVENT_MAP.get(hook)
    if event_kind is None:
        return None

    session_id = payload.get("session_id", "")
    conv_id = session_id
    ts = int(time.time() * 1000)

    base: dict[str, Any] = {
        "source": "claude-code",
        "event_kind": event_kind,
        "conversation_id": conv_id,
        "session_id": session_id,
        "model": payload.get("model", ""),
        "timestamp_ms": ts,
        "transcript_path": payload.get("transcript_path", ""),
        "cwd": payload.get("cwd", ""),
        "raw": payload,
    }

    if hook == "SessionStart":
        return AgentHookEvent(
            composer_mode=payload.get("source", ""),
            **base,
        )

    if hook == "SessionEnd":
        return AgentHookEvent(
            end_reason=payload.get("reason", ""),
            **base,
        )

    if hook == "UserPromptSubmit":
        return AgentHookEvent(
            prompt_text=payload.get("prompt", ""),
            **base,
        )

    if hook == "PreToolUse":
        return AgentHookEvent(
            tool_use_id=payload.get("tool_use_id", ""),
            tool_name=payload.get("tool_name", ""),
            tool_input=payload.get("tool_input", {}),
            **base,
        )

    if hook == "PostToolUse":
        tool_result = payload.get("tool_response", {})
        return AgentHookEvent(
            tool_use_id=payload.get("tool_use_id", ""),
            tool_name=payload.get("tool_name", ""),
            tool_input=payload.get("tool_input", {}),
            tool_output=_coerce_str(tool_result),
            **base,
        )

    if hook == "PostToolUseFailure":
        return AgentHookEvent(
            tool_use_id=payload.get("tool_use_id", ""),
            tool_name=payload.get("tool_name", ""),
            tool_input=payload.get("tool_input", {}),
            tool_error=payload.get("error", ""),
            is_interrupt=bool(payload.get("is_interrupt", False)),
            **base,
        )

    if hook == "Notification":
        return AgentHookEvent(
            response_text=payload.get("message", ""),
            **base,
        )

    if hook == "SubagentStart":
        return AgentHookEvent(
            subagent_id=payload.get("agent_id", ""),
            subagent_type=payload.get("agent_type", ""),
            **base,
        )

    if hook == "SubagentStop":
        return AgentHookEvent(
            subagent_id=payload.get("agent_id", ""),
            subagent_type=payload.get("agent_type", ""),
            agent_transcript_path=payload.get("agent_transcript_path", ""),
            subagent_summary=payload.get("last_assistant_message", ""),
            **base,
        )

    if hook == "Stop":
        return AgentHookEvent(
            response_text=payload.get("last_assistant_message", ""),
            **base,
        )

    if hook == "StopFailure":
        return AgentHookEvent(
            stop_error=payload.get("error", ""),
            stop_error_details=payload.get("error_details", ""),
            response_text=payload.get("last_assistant_message", ""),
            **base,
        )

    if hook == "PreCompact":
        return AgentHookEvent(
            compact_trigger=payload.get("trigger", ""),
            **base,
        )

    if hook == "PostCompact":
        return AgentHookEvent(
            compact_trigger=payload.get("trigger", ""),
            compact_summary=payload.get("compact_summary", ""),
            **base,
        )

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

    Claude Code uses PascalCase event names in ``hook_event_name`` (e.g.
    ``"PreToolUse"``); Cursor uses camelCase (e.g. ``"preToolUse"``).
    Detection checks whether the event name appears in the Claude Code
    event map first, then falls back to Codex/Cursor.

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
    hook_name = payload.get("hook_event_name", "")
    if hook_name in _CLAUDE_EVENT_MAP:
        return normalize_claude_code(payload)
    # Check for Codex-specific marker (set by Codex hooks.json)
    if payload.get("_source") == "codex":
        return normalize_codex(payload)
    return normalize_cursor(payload)
