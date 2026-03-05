"""Display name utilities for Claude Agent SDK Weave integration."""

from __future__ import annotations

from typing import Any


def format_model_name(model_id: str) -> str:
    """Format a model ID into a nice display name.

    e.g. 'claude-sonnet-4-6' -> 'Claude Sonnet 4.6'
    """
    parts = model_id.split("-")
    result = []
    i = 0
    while i < len(parts):
        if parts[i].isdigit():
            nums = [parts[i]]
            while i + 1 < len(parts) and parts[i + 1].isdigit():
                i += 1
                nums.append(parts[i])
            result.append(".".join(nums))
        else:
            result.append(parts[i].title())
        i += 1
    return " ".join(result)


def _format_params(params: dict[str, Any]) -> str:
    """Format tool input params as k=v, k=v."""
    parts = []
    for k, v in params.items():
        if isinstance(v, str):
            parts.append(f'{k}="{v}"')
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


def tool_use_display_name(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Generate display name for a tool use call.

    MCP tools:  'mcp__math__add' + {a: 3, b: 7} -> 'Math MCP: Add(a=3, b=7)'
    Built-ins:  'Bash' + {command: 'ls'} -> 'Bash(command="ls")'
    """
    if tool_name.startswith("mcp__"):
        parts = tool_name.split("__")
        if len(parts) == 3:
            _, server, tool = parts
            params = _format_params(tool_input)
            return f"{server.title()} MCP: {tool.title()}({params})"

    params = _format_params(tool_input)
    return f"{tool_name}({params})"


def response_display_name(model: str | None) -> str:
    """Generate display name for a response call."""
    if model:
        return format_model_name(model)
    return "Response"


def turn_display_name(prompt: str | None, max_words: int = 8) -> str:
    """Generate display name for a turn call from the first few words of the prompt."""
    if not prompt:
        return "Turn"
    words = prompt.split()[:max_words]
    name = " ".join(words)
    if len(prompt.split()) > max_words:
        name += "..."
    return name


def session_display_name(prompt: str | None) -> str:
    """Generate display name for the root session call."""
    if prompt:
        truncated = prompt[:80] + ("..." if len(prompt) > 80 else "")
        return f"Session: {truncated}"
    return "Session"
