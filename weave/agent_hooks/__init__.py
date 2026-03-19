"""Agent session tracing via IDE hooks.

Provides a daemon + relay CLI pair that instruments Cursor, Claude Code, and
Codex agent sessions as OTel spans, emitting them to the Weave GenAI trace
server so they appear in the Traces and Conversations views alongside
OpenAI/Google traces.

Usage (after ``weave agent-hooks daemon`` is running)::

    # In ~/.cursor/hooks.json or ~/.claude/hooks.json:
    # { "hooks": { "preToolUse": [{"command": "weave agent-hooks relay"}] } }

    # Start the daemon:
    weave agent-hooks daemon --project my-project

    # Check status:
    weave agent-hooks status
"""

from weave.agent_hooks.events import AgentHookEvent, EventKind, SourceKind

__all__ = ["AgentHookEvent", "EventKind", "SourceKind"]
