"""Shared visualization components for agent tracing.

Provides HTML generation for:
- File diffs (Edit tool)
- Todo lists (TodoWrite tool)
- Other tool-specific views
"""

from weave.integrations.ag_ui.views.diff_utils import (
    apply_structured_patch,
    build_file_diffs_from_file_changes,
    collect_all_file_changes_from_session,
    extract_edit_data_from_raw_messages,
    extract_write_data_from_raw_messages,
)
from weave.integrations.ag_ui.views.diff_view import (
    generate_edit_diff_html,
    generate_todo_html,
    generate_turn_diff_html,
)

__all__ = [
    "apply_structured_patch",
    "build_file_diffs_from_file_changes",
    "collect_all_file_changes_from_session",
    "extract_edit_data_from_raw_messages",
    "extract_write_data_from_raw_messages",
    "generate_edit_diff_html",
    "generate_todo_html",
    "generate_turn_diff_html",
]
