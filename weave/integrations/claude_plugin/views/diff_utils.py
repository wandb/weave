"""Utilities for reconstructing file diffs from Edit tool call data.

Claude Code Edit tool results contain rich data that can be used to reconstruct
file diffs without relying on file-history-snapshot entries:

- originalFile: The complete original file content before the edit
- structuredPatch: Array of diff hunks with line information

This is particularly useful for subagent files, which do NOT record
file-history-snapshot entries even when they make Edit calls.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def apply_structured_patch(
    original_content: str,
    structured_patch: list[dict[str, Any]],
) -> str:
    """Apply a structuredPatch to original content to get new content.

    Args:
        original_content: The original file content
        structured_patch: Array of patch hunks from Claude Code's toolUseResult

    Returns:
        The new file content after applying the patch
    """
    # Split original into lines (keeping track of final newline)
    has_final_newline = original_content.endswith("\n")
    original_lines = original_content.splitlines()

    # Process patches in reverse order to avoid line number shifts
    sorted_hunks = sorted(
        structured_patch,
        key=lambda h: h.get("oldStart", 1),
        reverse=True,
    )

    for hunk in sorted_hunks:
        old_start = hunk.get("oldStart", 1) - 1  # Convert to 0-indexed
        old_lines_count = hunk.get("oldLines", 0)
        patch_lines = hunk.get("lines", [])

        # Extract new lines from the patch (lines starting with + or space)
        new_lines = []
        for line in patch_lines:
            if line.startswith("+"):
                new_lines.append(line[1:])  # Remove the + prefix
            elif line.startswith(" "):
                new_lines.append(line[1:])  # Remove the space prefix
            # Lines starting with - are removed, so we skip them

        # Replace the old lines with new lines
        original_lines[old_start:old_start + old_lines_count] = new_lines

    result = "\n".join(original_lines)
    if has_final_newline:
        result += "\n"

    return result


def extract_edit_data_from_raw_messages(
    raw_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract Edit tool data from raw messages.

    Finds messages with toolUseResult containing Edit tool data
    (originalFile, structuredPatch) and extracts them.

    Args:
        raw_messages: List of raw message dicts from a session

    Returns:
        List of edit data dicts
    """
    edits = []

    for msg in raw_messages:
        tool_use_result = msg.get("toolUseResult")
        if not tool_use_result:
            continue

        # toolUseResult can be a string (simple result) or dict (rich data)
        # Only process dict results with Edit tool data
        if not isinstance(tool_use_result, dict):
            continue

        # Only process Edit tool results with the rich data
        file_path = tool_use_result.get("filePath")
        original_file = tool_use_result.get("originalFile")
        structured_patch = tool_use_result.get("structuredPatch")

        if file_path and structured_patch:
            edits.append({
                "file_path": file_path,
                "original_file": original_file or "",
                "structured_patch": structured_patch,
                "old_string": tool_use_result.get("oldString", ""),
                "new_string": tool_use_result.get("newString", ""),
            })

    return edits


def extract_write_data_from_raw_messages(
    raw_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract Write tool data from raw messages.

    Finds messages with toolUseResult containing Write tool data
    (type="create", filePath, content) and extracts them.

    Args:
        raw_messages: List of raw message dicts from a session

    Returns:
        List of write data dicts with file_path and content
    """
    writes = []

    for msg in raw_messages:
        tool_use_result = msg.get("toolUseResult")
        if not tool_use_result:
            continue

        # toolUseResult can be a string (simple result) or dict (rich data)
        if not isinstance(tool_use_result, dict):
            continue

        # Write tool results have type="create" and content
        result_type = tool_use_result.get("type")
        file_path = tool_use_result.get("filePath")
        content = tool_use_result.get("content")

        if result_type == "create" and file_path and content is not None:
            writes.append({
                "file_path": file_path,
                "content": content,
                "is_new_file": True,
            })

    return writes


def collect_all_file_changes_from_session(
    session: Any,
    sessions_dir: Any,
) -> dict[str, dict[str, Any]]:
    """Collect all file changes from a session including subagents.

    Aggregates Edit and Write tool data from the main session and all
    linked subagent files to build a complete picture of file changes.

    Args:
        session: Parsed Session object
        sessions_dir: Path to the directory containing session files

    Returns:
        Dict mapping file_path to change info:
        {
            "file_path": {
                "before": str or None (None for new files),
                "after": str,
                "is_new_file": bool,
                "edits": list of edit operations,
            }
        }
    """
    from pathlib import Path

    from weave.integrations.claude_plugin.session.session_parser import parse_session_file

    # Regex to extract agentId from Task tool results
    import re
    AGENT_ID_PATTERN = re.compile(r"^agentId:\s*(\w+)", re.MULTILINE)

    def extract_agent_id(tool_result: str | None) -> str | None:
        if not tool_result:
            return None
        match = AGENT_ID_PATTERN.search(tool_result)
        return match.group(1) if match else None

    file_changes: dict[str, dict[str, Any]] = {}

    def process_turn(turn: Any) -> None:
        """Process a turn's raw messages for file changes."""
        if not turn.raw_messages:
            return

        # Extract Edit data first
        edit_data_list = extract_edit_data_from_raw_messages(turn.raw_messages)
        for edit_data in edit_data_list:
            file_path = edit_data["file_path"]
            if file_path not in file_changes:
                # First time seeing this file - use original_file as before state
                file_changes[file_path] = {
                    "before": edit_data["original_file"],
                    "after": None,
                    "is_new_file": False,
                    "edits": [],
                }
            file_changes[file_path]["edits"].append(edit_data)

            # Apply patch to get after state
            if edit_data["structured_patch"]:
                # Use current "after" state as base if it exists, otherwise use "before"
                base = file_changes[file_path]["after"] or file_changes[file_path]["before"] or ""
                try:
                    after = apply_structured_patch(base, edit_data["structured_patch"])
                    file_changes[file_path]["after"] = after
                except Exception as e:
                    logger.debug(f"Failed to apply patch to {file_path}: {e}")

        # Extract Write data - these create new files
        write_data_list = extract_write_data_from_raw_messages(turn.raw_messages)
        for write_data in write_data_list:
            file_path = write_data["file_path"]
            if file_path not in file_changes:
                # New file created with Write
                file_changes[file_path] = {
                    "before": None,  # New file has no before state
                    "after": write_data["content"],
                    "is_new_file": True,
                    "edits": [],
                }
            else:
                # File was previously edited, now being overwritten
                # Keep the original before state, update after
                file_changes[file_path]["after"] = write_data["content"]

    # Process main session turns
    for turn in session.turns:
        process_turn(turn)

    # Also process subagent files that belong to THIS session
    # Filter by session_id to exclude subagents from other sessions
    sessions_path = Path(sessions_dir)
    if sessions_path.exists():
        for agent_file in sessions_path.glob("agent-*.jsonl"):
            try:
                agent_session = parse_session_file(agent_file)
                # Only include subagents that belong to this session
                if agent_session and agent_session.session_id == session.session_id:
                    for agent_turn in agent_session.turns:
                        process_turn(agent_turn)
            except Exception as e:
                logger.debug(f"Failed to parse agent file {agent_file}: {e}")

    return file_changes


def build_file_diffs_from_file_changes(
    file_changes: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert file changes dict to file_diffs format for HTML rendering.

    Args:
        file_changes: Output from collect_all_file_changes_from_session

    Returns:
        List of file_diff dicts compatible with diff_view.py renderers
    """
    import difflib
    from pathlib import Path

    # Extension to highlight.js language mapping
    EXT_TO_HLJS_LANG = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".html": "html",
        ".css": "css",
        ".sh": "bash",
        ".bash": "bash",
        ".toml": "toml",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".rb": "ruby",
        ".sql": "sql",
        ".xml": "xml",
    }

    file_diffs = []

    for file_path, change_info in sorted(file_changes.items()):
        before = change_info.get("before") or ""
        after = change_info.get("after") or ""
        is_new_file = change_info.get("is_new_file", False)

        # Skip if no actual change
        if before == after:
            continue

        # Generate unified diff
        before_lines = before.splitlines(keepends=True)
        after_lines = after.splitlines(keepends=True)

        # Ensure trailing newlines
        if before_lines and not before_lines[-1].endswith("\n"):
            before_lines[-1] += "\n"
        if after_lines and not after_lines[-1].endswith("\n"):
            after_lines[-1] += "\n"

        diff_lines = list(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                n=3,
            )
        )

        if diff_lines:
            added = sum(
                1 for line in diff_lines
                if line.startswith("+") and not line.startswith("+++")
            )
            removed = sum(
                1 for line in diff_lines
                if line.startswith("-") and not line.startswith("---")
            )

            ext = Path(file_path).suffix.lower()
            lang = EXT_TO_HLJS_LANG.get(ext, "plaintext")

            file_diffs.append({
                "path": file_path,
                "lang": lang,
                "is_new": is_new_file,
                "is_deleted": False,
                "diff_lines": diff_lines[2:],  # Skip --- and +++ headers
                "added": added,
                "removed": removed,
            })

    return file_diffs
