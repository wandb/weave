"""Claude Code Tool Registry

Defines special behaviors for Claude Code tools.
Used by the trace builder to create appropriate traces and views.
"""

from typing import Any

# Tool name → configuration
CLAUDE_TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    # Subagent tools
    "Task": {
        "spawns_subagent": True,
        "subagent_id_field": "metadata.agentId",
        "metadata_fields": ["subagent_type", "description"],
    },
    # File modification tools
    "Edit": {
        "has_diff_view": True,
    },
    "Write": {
        "has_diff_view": True,
    },
    "NotebookEdit": {
        "has_diff_view": True,
    },
    # File reading tools
    "Read": {},
    "Glob": {},
    "Grep": {},
    # Execution tools
    "Bash": {},
    # Planning/tracking tools
    "TodoWrite": {
        "has_custom_view": True,
    },
    "EnterPlanMode": {
        "metadata_fields": ["plan_type"],
    },
    "ExitPlanMode": {},
    # User interaction tools
    "AskUserQuestion": {
        "is_qa_flow": True,
        "metadata_fields": ["questions"],
    },
    # Skill tools
    "Skill": {
        "metadata_fields": ["skill_name", "args"],
    },
    # Web tools
    "WebFetch": {},
    "WebSearch": {},
    # LSP tools
    "LSP": {
        "metadata_fields": ["operation"],
    },
    # Background task tools
    "TaskOutput": {},
    "KillShell": {},
}
