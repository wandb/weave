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
