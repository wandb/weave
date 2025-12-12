"""Diff view generation for Claude Code file changes.

This module provides GitHub-style diff HTML generation for visualizing
file changes made during Claude Code turns.

Supports two modes:
- Live mode (default): Compare file backup to current disk state
- Historic mode: Compare file backup to previous turn's backup
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from weave.integrations.claude_plugin.session_parser import FileBackup, Turn

# File extension to highlight.js language mapping
EXT_TO_HLJS_LANG: dict[str, str] = {
    ".py": "python",
    ".go": "go",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".sh": "bash",
    ".bash": "bash",
    ".sql": "sql",
    ".html": "xml",
    ".css": "css",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".toml": "ini",
    ".xml": "xml",
}

# Inline CSS for GitHub-style diff view (no external dependencies)
DIFF_HTML_STYLES = """
<style>
*{box-sizing:border-box;margin:0;padding:0}
.diff-view{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;font-size:14px;line-height:1.5;color:#1f2328;background:#fff;max-height:100vh;overflow:auto}
.diff-header{padding:16px 20px;background:linear-gradient(180deg,#f6f8fa 0%,#eaeef2 100%);border-bottom:1px solid #d1d9e0}
.diff-title{font-size:16px;font-weight:600;margin-bottom:4px}
.diff-stats{font-size:13px;color:#656d76}
.diff-stats .add{color:#1a7f37;font-weight:600}
.diff-stats .del{color:#d1242f;font-weight:600}
.diff-file{margin:16px;border:1px solid #d1d9e0;border-radius:6px;overflow:hidden;background:#fff}
.file-header{display:flex;align-items:center;padding:8px 12px;background:#f6f8fa;border-bottom:1px solid #d1d9e0;font-family:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace;font-size:12px}
.file-icon{width:16px;height:16px;margin-right:8px;fill:#656d76}
.file-name{font-weight:600;color:#1f2328}
.file-badge{margin-left:8px;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:500}
.file-badge.new{background:#dafbe1;color:#1a7f37}
.diff-table-wrap{overflow-x:auto;overflow-y:visible}
.diff-table{border-collapse:collapse;font-family:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace;font-size:12px;line-height:20px;min-width:100%}
.diff-table td{vertical-align:top}
.line-num{width:50px;min-width:50px;padding:0 8px;text-align:right;color:#8c959f;background:#f6f8fa;border-right:1px solid #d1d9e0;user-select:none;white-space:nowrap;position:sticky;z-index:1}
.line-num:first-child{left:0}
.line-num:nth-child(2){left:50px}
.line-marker{width:20px;min-width:20px;padding:0 4px;text-align:center;user-select:none;position:sticky;left:100px;z-index:1}
.line-content{padding:0 12px;white-space:pre}
.line-add{background:#dafbe1}
.line-add .line-num{background:#aceebb}
.line-add .line-marker{color:#1a7f37;background:#dafbe1}
.line-del{background:#ffebe9}
.line-del .line-num{background:#ffc0bc}
.line-del .line-marker{color:#d1242f;background:#ffebe9}
.line-hunk{background:#ddf4ff;color:#0969da;font-weight:500}
.line-hunk td{padding:8px 12px;background:#ddf4ff}
.line-ctx .line-marker{color:#8c959f}
.diff-footer{padding:12px 20px;background:#f6f8fa;border-top:1px solid #d1d9e0;font-size:12px;color:#656d76;display:flex;align-items:center;gap:12px}
.footer-dot{color:#d1d9e0}
.hljs{background:transparent!important;padding:0!important}
code{font-family:inherit;display:block}
</style>
"""


def _html_escape(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_turn_diff_html(
    turn: "Turn",
    turn_index: int,
    all_turns: list["Turn"],
    session_id: str,
    *,
    turn_number: int,
    tool_count: int,
    model: str,
    historic_mode: bool = False,
) -> str | None:
    """Generate HTML showing file changes for this turn with syntax highlighting.

    Creates a beautiful GitHub-style diff view with:
    - Inline CSS (no external stylesheets)
    - highlight.js from jsDelivr CDN for syntax highlighting
    - Line numbers for old and new lines
    - Color-coded additions/deletions
    - Scrollable container

    Two modes of operation:
    - Live mode (historic_mode=False): Compare backup to current file on disk.
      Use this when processing hooks in real-time, as the backup represents
      the state BEFORE edits and the file on disk is the state AFTER edits.
    - Historic mode (historic_mode=True): Compare backup to previous turn's backup.
      Use this when importing old sessions, where we need to compare consecutive
      backup snapshots to see what changed between turns.

    Args:
        turn: The current turn to generate diff for
        turn_index: Zero-based index of this turn in the session
        all_turns: All turns in the session (for looking up previous versions)
        session_id: Session ID for loading backup files from file-history
        turn_number: 1-based turn number for display
        tool_count: Number of tool calls in this turn
        model: Model name used for this turn
        historic_mode: If True, compare backup to previous turn's backup (for imports).
                       If False, compare backup to current file on disk (for live hooks).

    Returns:
        HTML string with diff view, or None if no file changes
    """
    # Import here to avoid circular imports
    from weave.integrations.claude_plugin.session_parser import FileBackup

    if not turn.file_backups:
        return None

    # Build map of current turn's file -> latest backup (state BEFORE edits)
    current_backups: dict[str, FileBackup] = {}
    for fb in turn.file_backups:
        if fb.backup_filename:
            existing = current_backups.get(fb.file_path)
            if not existing or fb.version > existing.version:
                current_backups[fb.file_path] = fb

    if not current_backups:
        return None

    # In historic mode, build map of previous turns' file -> latest backup before this turn
    prev_backups: dict[str, FileBackup] = {}
    if historic_mode:
        for prev_turn in all_turns[:turn_index]:
            for fb in prev_turn.file_backups:
                if fb.backup_filename:
                    existing = prev_backups.get(fb.file_path)
                    if not existing or fb.version > existing.version:
                        prev_backups[fb.file_path] = fb

    # Collect file diffs
    file_diffs: list[dict[str, Any]] = []
    total_added = 0
    total_removed = 0

    for file_path in sorted(current_backups.keys()):
        backup_fb = current_backups[file_path]

        # Load backup content (state BEFORE edits in this turn)
        backup_content = backup_fb.load_content(session_id)
        if not backup_content:
            continue

        try:
            backup_text = backup_content.as_string()
        except Exception:
            continue  # Skip binary files

        backup_lines = backup_text.splitlines(keepends=True)
        if backup_lines and not backup_lines[-1].endswith("\n"):
            backup_lines[-1] += "\n"

        # Detect language from file extension
        ext = Path(file_path).suffix.lower()
        lang = EXT_TO_HLJS_LANG.get(ext, "plaintext")

        if historic_mode:
            # Historic mode: Compare this turn's backup to previous turn's backup
            prev_fb = prev_backups.get(file_path)

            # Skip if same version (no change)
            if prev_fb and prev_fb.backup_filename == backup_fb.backup_filename:
                continue

            if prev_fb:
                # File was modified - generate diff from prev to current backup
                prev_content = prev_fb.load_content(session_id)
                if prev_content:
                    try:
                        prev_text = prev_content.as_string()
                        prev_lines = prev_text.splitlines(keepends=True)
                        if prev_lines and not prev_lines[-1].endswith("\n"):
                            prev_lines[-1] += "\n"

                        diff_lines = list(
                            difflib.unified_diff(
                                prev_lines,
                                backup_lines,
                                fromfile=f"a/{file_path}",
                                tofile=f"b/{file_path}",
                                n=3,
                            )
                        )

                        if diff_lines:
                            added = sum(
                                1
                                for line in diff_lines
                                if line.startswith("+") and not line.startswith("+++")
                            )
                            removed = sum(
                                1
                                for line in diff_lines
                                if line.startswith("-") and not line.startswith("---")
                            )
                            total_added += added
                            total_removed += removed

                            file_diffs.append(
                                {
                                    "path": file_path,
                                    "lang": lang,
                                    "is_new": False,
                                    "diff_lines": diff_lines[2:],
                                    "added": added,
                                    "removed": removed,
                                }
                            )
                    except Exception:
                        continue
            else:
                # New file in this turn - show backup content
                total_added += len(backup_lines)
                preview_lines = backup_lines[:100]
                file_diffs.append(
                    {
                        "path": file_path,
                        "lang": lang,
                        "is_new": True,
                        "content_lines": preview_lines,
                        "total_lines": len(backup_lines),
                        "added": len(backup_lines),
                        "removed": 0,
                    }
                )
        else:
            # Live mode: Compare backup (before) to current file on disk (after)
            try:
                disk_path = Path(file_path)
                if not disk_path.is_absolute():
                    # file_path might be relative, skip
                    continue
                if not disk_path.exists():
                    # File was deleted - show as removal
                    diff_lines = list(
                        difflib.unified_diff(
                            backup_lines,
                            [],
                            fromfile=f"a/{file_path}",
                            tofile=f"b/{file_path}",
                            n=3,
                        )
                    )
                    if diff_lines:
                        removed = len(backup_lines)
                        total_removed += removed
                        file_diffs.append(
                            {
                                "path": file_path,
                                "lang": lang,
                                "is_new": False,
                                "diff_lines": diff_lines[2:],
                                "added": 0,
                                "removed": removed,
                            }
                        )
                    continue

                current_text = disk_path.read_text()
                current_lines = current_text.splitlines(keepends=True)
                if current_lines and not current_lines[-1].endswith("\n"):
                    current_lines[-1] += "\n"

                # Generate diff: backup -> current
                diff_lines = list(
                    difflib.unified_diff(
                        backup_lines,
                        current_lines,
                        fromfile=f"a/{file_path}",
                        tofile=f"b/{file_path}",
                        n=3,
                    )
                )

                if diff_lines:
                    added = sum(
                        1
                        for line in diff_lines
                        if line.startswith("+") and not line.startswith("+++")
                    )
                    removed = sum(
                        1
                        for line in diff_lines
                        if line.startswith("-") and not line.startswith("---")
                    )
                    total_added += added
                    total_removed += removed

                    file_diffs.append(
                        {
                            "path": file_path,
                            "lang": lang,
                            "is_new": False,
                            "diff_lines": diff_lines[2:],
                            "added": added,
                            "removed": removed,
                        }
                    )
            except Exception:
                # Can't read file from disk, skip
                continue

    if not file_diffs:
        return None

    # Build HTML
    html_parts: list[str] = []

    # Document start with styles
    html_parts.append("<!DOCTYPE html>")
    html_parts.append('<html lang="en"><head>')
    html_parts.append('<meta charset="utf-8">')
    html_parts.append(
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
    )
    html_parts.append(DIFF_HTML_STYLES)
    # highlight.js from jsDelivr CDN (minimal: core + common languages)
    html_parts.append(
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github.min.css">'
    )
    html_parts.append(
        '<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js"></script>'
    )
    html_parts.append("</head><body>")

    # Main container
    html_parts.append('<div class="diff-view">')

    # Header with stats
    html_parts.append('<div class="diff-header">')
    html_parts.append('<div class="diff-title">File Changes</div>')
    html_parts.append('<div class="diff-stats">')
    html_parts.append(f"{len(file_diffs)} file{'s' if len(file_diffs) != 1 else ''}")
    html_parts.append(f' · <span class="add">+{total_added}</span>')
    html_parts.append(f' · <span class="del">−{total_removed}</span>')
    html_parts.append("</div></div>")

    # File diffs
    for file_diff in file_diffs:
        file_path = file_diff["path"]
        lang = file_diff["lang"]
        is_new = file_diff["is_new"]

        html_parts.append('<div class="diff-file">')

        # File header
        html_parts.append('<div class="file-header">')
        # File icon SVG
        html_parts.append(
            '<svg class="file-icon" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M3.75 1.5a.25.25 0 00-.25.25v12.5c0 .138.112.25.25.25h9.5a.25.25 0 00.25-.25V4.664a.25.25 0 00-.073-.177l-2.914-2.914a.25.25 0 00-.177-.073H3.75zM2 1.75C2 .784 2.784 0 3.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0113.25 16h-9.5A1.75 1.75 0 012 14.25V1.75z"></path></svg>'
        )
        html_parts.append(f'<span class="file-name">{_html_escape(file_path)}</span>')
        if is_new:
            html_parts.append('<span class="file-badge new">NEW</span>')
        html_parts.append("</div>")

        # Diff content - wrap in scrollable container
        html_parts.append('<div class="diff-table-wrap">')
        html_parts.append('<table class="diff-table">')

        if is_new:
            # New file - show content with line numbers
            content_lines = file_diff["content_lines"]
            total_lines = file_diff["total_lines"]

            for i, line in enumerate(content_lines, 1):
                content = _html_escape(line.rstrip("\n\r"))
                html_parts.append('<tr class="line-add">')
                html_parts.append('<td class="line-num"></td>')  # No old line number
                html_parts.append(f'<td class="line-num">{i}</td>')
                html_parts.append('<td class="line-marker">+</td>')
                html_parts.append(
                    f'<td class="line-content"><code class="language-{lang}">{content}</code></td>'
                )
                html_parts.append("</tr>")

            if total_lines > 100:
                html_parts.append('<tr class="line-hunk">')
                html_parts.append(
                    f'<td colspan="4">... {total_lines - 100} more lines</td>'
                )
                html_parts.append("</tr>")
        else:
            # Modified file - show diff
            diff_lines = file_diff["diff_lines"]
            old_line = 0
            new_line = 0

            for line in diff_lines:
                line_text = line.rstrip("\n\r")

                if line_text.startswith("@@"):
                    # Hunk header - extract line numbers
                    html_parts.append('<tr class="line-hunk">')
                    html_parts.append(
                        f'<td colspan="4">{_html_escape(line_text)}</td>'
                    )
                    html_parts.append("</tr>")
                    # Parse line numbers from @@ -old,count +new,count @@
                    match = re.search(r"@@ -(\d+)", line_text)
                    if match:
                        old_line = int(match.group(1)) - 1
                    match = re.search(r"\+(\d+)", line_text)
                    if match:
                        new_line = int(match.group(1)) - 1
                elif line_text.startswith("+"):
                    new_line += 1
                    content = _html_escape(line_text[1:])
                    html_parts.append('<tr class="line-add">')
                    html_parts.append('<td class="line-num"></td>')
                    html_parts.append(f'<td class="line-num">{new_line}</td>')
                    html_parts.append('<td class="line-marker">+</td>')
                    html_parts.append(
                        f'<td class="line-content"><code class="language-{lang}">{content}</code>'
                    )
                    html_parts.append("</td></tr>")
                elif line_text.startswith("-"):
                    old_line += 1
                    content = _html_escape(line_text[1:])
                    html_parts.append('<tr class="line-del">')
                    html_parts.append(f'<td class="line-num">{old_line}</td>')
                    html_parts.append('<td class="line-num"></td>')
                    html_parts.append('<td class="line-marker">−</td>')
                    html_parts.append(
                        f'<td class="line-content"><code class="language-{lang}">{content}</code>'
                    )
                    html_parts.append("</td></tr>")
                else:
                    # Context line
                    old_line += 1
                    new_line += 1
                    content = _html_escape(line_text[1:] if line_text else "")
                    html_parts.append('<tr class="line-ctx">')
                    html_parts.append(f'<td class="line-num">{old_line}</td>')
                    html_parts.append(f'<td class="line-num">{new_line}</td>')
                    html_parts.append('<td class="line-marker"></td>')
                    html_parts.append(
                        f'<td class="line-content"><code class="language-{lang}">{content}</code>'
                    )
                    html_parts.append("</td></tr>")

        html_parts.append("</table></div>")
        html_parts.append("</div>")  # Close diff-file

    # Footer
    html_parts.append('<div class="diff-footer">')
    html_parts.append(f"<span>Turn {turn_number}</span>")
    html_parts.append('<span class="footer-dot">·</span>')
    html_parts.append(f"<span>{tool_count} tool calls</span>")
    html_parts.append('<span class="footer-dot">·</span>')
    html_parts.append(f"<span>{model}</span>")
    html_parts.append("</div>")

    html_parts.append("</div>")  # Close diff-view

    # Initialize highlight.js
    html_parts.append("<script>")
    html_parts.append("document.addEventListener('DOMContentLoaded',()=>{")
    html_parts.append("document.querySelectorAll('code[class*=language-]').forEach(el=>{")
    html_parts.append("try{hljs.highlightElement(el)}catch(e){}});});")
    html_parts.append("</script>")

    html_parts.append("</body></html>")

    return "".join(html_parts)
