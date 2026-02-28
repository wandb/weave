"""Shared visualization components for agent tracing.

Provides HTML generation for:
- File diffs (Edit tool)
- Todo lists (TodoWrite tool)
- Other tool-specific views
"""

from weave.integrations.ag_ui.views.diff_view import (
    generate_edit_diff_html,
    generate_todo_html,
    generate_turn_diff_html,
)

__all__ = [
    "generate_edit_diff_html",
    "generate_todo_html",
    "generate_turn_diff_html",
]
