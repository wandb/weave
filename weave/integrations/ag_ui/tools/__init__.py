"""Agent-Specific Tool Registries

Each agentic tool (Claude, Gemini, Codex) has its own set of tools
with specific behaviors. This module provides registries that map
tool names to their configuration.
"""

from typing import Any

from weave.integrations.ag_ui.tools.claude import CLAUDE_TOOL_REGISTRY

# Map agent names to their tool registries
_REGISTRIES: dict[str, dict[str, dict[str, Any]]] = {
    "Claude Code": CLAUDE_TOOL_REGISTRY,
    # Future:
    # "Gemini CLI": GEMINI_TOOL_REGISTRY,
    # "Codex CLI": CODEX_TOOL_REGISTRY,
}


def get_tool_registry(agent_name: str) -> dict[str, dict[str, Any]]:
    """Get the tool registry for a specific agent.

    Args:
        agent_name: The agent name (e.g., "Claude Code")

    Returns:
        Dict mapping tool names to their configuration.
        Returns empty dict for unknown agents.
    """
    return _REGISTRIES.get(agent_name, {})
