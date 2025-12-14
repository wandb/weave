"""Utilities for reconstructing file diffs from Edit tool call data.

Claude Code Edit tool results contain rich data that can be used to reconstruct
file diffs without relying on file-history-snapshot entries:

- originalFile: The complete original file content before the edit
- structuredPatch: Array of diff hunks with line information

This is particularly useful for subagent files, which do NOT record
file-history-snapshot entries even when they make Edit calls.
"""

from __future__ import annotations

import html
import logging
from typing import Any

logger = logging.getLogger(__name__)


def structured_patch_to_unified_diff(
    file_path: str,
    structured_patch: list[dict[str, Any]],
) -> str:
    """Convert a structuredPatch to unified diff format.

    Args:
        file_path: Path to the file being edited
        structured_patch: Array of patch hunks from Claude Code's toolUseResult

    Returns:
        Unified diff string
    """
    lines = []
    lines.append(f"--- {file_path}")
    lines.append(f"+++ {file_path}")

    for hunk in structured_patch:
        old_start = hunk.get("oldStart", 1)
        old_lines = hunk.get("oldLines", 0)
        new_start = hunk.get("newStart", 1)
        new_lines = hunk.get("newLines", 0)

        # Unified diff hunk header
        lines.append(f"@@ -{old_start},{old_lines} +{new_start},{new_lines} @@")

        # Add the diff lines (they already have the +/- prefix)
        for line in hunk.get("lines", []):
            lines.append(line)

    return "\n".join(lines)


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


def generate_html_from_structured_patch(
    file_path: str,
    original_content: str,
    structured_patch: list[dict[str, Any]],
) -> str:
    """Generate HTML diff view from structuredPatch data.

    Args:
        file_path: Path to the file being edited
        original_content: The original file content
        structured_patch: Array of patch hunks from Claude Code's toolUseResult

    Returns:
        HTML string containing a diff view
    """
    # Get the new content by applying the patch
    new_content = apply_structured_patch(original_content, structured_patch)

    # Generate a simple side-by-side diff view
    html_parts = []
    html_parts.append('<div class="diff-view" style="font-family: monospace;">')
    html_parts.append(f'<h3>{html.escape(file_path)}</h3>')

    for hunk in structured_patch:
        old_start = hunk.get("oldStart", 1)
        html_parts.append(
            f'<div class="diff-hunk" style="margin: 10px 0; '
            f'background: #f5f5f5; padding: 5px;">'
        )
        html_parts.append(
            f'<div class="hunk-header" style="color: #666;">@@ Line {old_start} @@</div>'
        )

        for line in hunk.get("lines", []):
            escaped_line = html.escape(line[1:] if len(line) > 0 else "")

            if line.startswith("-"):
                html_parts.append(
                    f'<div class="diff-removed" style="background: #ffdddd; '
                    f'color: #cc0000;">- {escaped_line}</div>'
                )
            elif line.startswith("+"):
                html_parts.append(
                    f'<div class="diff-added" style="background: #ddffdd; '
                    f'color: #008800;">+ {escaped_line}</div>'
                )
            else:
                html_parts.append(
                    f'<div class="diff-context" style="color: #666;">  {escaped_line}</div>'
                )

        html_parts.append("</div>")

    html_parts.append("</div>")
    return "\n".join(html_parts)


def aggregate_file_patches(
    edits: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Aggregate multiple edits to the same file.

    When multiple Edit calls modify the same file, we want to show:
    - The original content (from the first edit)
    - The final content (after applying all edits)

    Args:
        edits: List of edit data dicts with file_path, original_file, structured_patch

    Returns:
        Dict mapping file_path to aggregated edit data
    """
    aggregated: dict[str, dict[str, Any]] = {}

    for edit in edits:
        file_path = edit.get("file_path")
        if not file_path:
            continue

        if file_path not in aggregated:
            # First edit to this file - use its original as the baseline
            aggregated[file_path] = {
                "original_content": edit.get("original_file", ""),
                "patches": [],
            }

        aggregated[file_path]["patches"].append(edit.get("structured_patch", []))

    return aggregated


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
