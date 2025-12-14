"""Diff view generation for Claude Code file changes.

This module provides GitHub-style diff HTML generation for visualizing
file changes made during Claude Code turns, as well as HTML views for
TodoWrite tool calls.

Supports two modes for diff views:
- Live mode (default): Compare file backup to current disk state
- Historic mode: Compare file backup to previous turn's backup
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from weave.integrations.claude_plugin.session_parser import FileBackup, Session, Turn

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
.hljs{background:transparent!important;padding:0!important}
code{font-family:inherit;display:block}
.prompt-section{padding:16px 20px;background:#fff;border-bottom:1px solid #d1d9e0}
.prompt-label{font-size:11px;font-weight:600;color:#656d76;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;display:flex;align-items:center;gap:6px}
.prompt-label svg{width:14px;height:14px;fill:#656d76}
.prompt-bubble{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:12px 16px;border-radius:18px 18px 18px 4px;font-size:14px;line-height:1.5;max-width:85%;word-wrap:break-word;white-space:pre-wrap;box-shadow:0 2px 8px rgba(102,126,234,0.25)}
.resume-section{padding:16px 20px;background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);border-bottom:1px solid #0f3460}
.resume-label{font-size:12px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;display:flex;align-items:center;gap:8px}
.resume-label svg{width:16px;height:16px;fill:#94a3b8}
.resume-code-wrap{position:relative;background:#0d1117;border:1px solid #30363d;border-radius:8px;overflow:hidden}
.resume-code{font-family:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace;font-size:13px;color:#58a6ff;padding:14px 50px 14px 16px;margin:0;white-space:nowrap;overflow-x:auto}
.resume-copy-btn{position:absolute;top:50%;right:8px;transform:translateY(-50%);background:#21262d;border:1px solid #30363d;border-radius:6px;padding:8px;cursor:pointer;color:#8b949e;transition:all 0.15s ease}
.resume-copy-btn:hover{background:#30363d;color:#c9d1d9;border-color:#8b949e}
.resume-copy-btn svg{width:16px;height:16px;display:block}
.resume-copy-btn.copied{background:#238636;border-color:#238636;color:#fff}
.resume-copy-btn.copied svg.copy-icon{display:none}
.resume-copy-btn svg.check-icon{display:none}
.resume-copy-btn.copied svg.check-icon{display:block}
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
    cwd: str | None = None,
    user_prompt: str | None = None,
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
        cwd: Current working directory of the session. Used in live mode to resolve
             relative file paths.
        user_prompt: The user's prompt that initiated this turn. Displayed as a chat
             bubble at the top of the diff view for context.

    Returns:
        HTML string with diff view, or None if no file changes
    """
    # Import here to avoid circular imports
    from weave.integrations.claude_plugin.session_parser import FileBackup

    if not turn.file_backups:
        return None

    # Build map of current turn's file -> latest backup (state BEFORE edits)
    # Backups are already correctly linked to turns via messageId in session_parser,
    # so we trust that association rather than timestamp filtering
    current_backups: dict[str, FileBackup] = {}
    for fb in turn.file_backups:
        if not fb.backup_filename:
            continue
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
                    # Try to resolve relative path using session cwd
                    if cwd:
                        disk_path = Path(cwd) / file_path
                    else:
                        # No cwd available, skip relative path
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

    # User prompt chat bubble at the very top (if provided)
    if user_prompt:
        # Truncate very long prompts for display
        display_prompt = user_prompt[:2000] + "..." if len(user_prompt) > 2000 else user_prompt
        html_parts.append('<div class="prompt-section">')
        html_parts.append('<div class="prompt-label">')
        # User icon SVG
        html_parts.append(
            '<svg viewBox="0 0 16 16"><path fill-rule="evenodd" d="M10.5 5a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0zm.061 3.073a4 4 0 10-5.123 0 6.004 6.004 0 00-3.431 5.142.75.75 0 001.498.07 4.5 4.5 0 018.99 0 .75.75 0 101.498-.07 6.005 6.005 0 00-3.432-5.142z"></path></svg>'
        )
        html_parts.append("User Prompt</div>")
        html_parts.append(f'<div class="prompt-bubble">{_html_escape(display_prompt)}</div>')
        html_parts.append("</div>")

    # Header with title and all metadata
    html_parts.append('<div class="diff-header">')
    html_parts.append(f'<div class="diff-title">File Changes for Turn {turn_number}</div>')
    html_parts.append('<div class="diff-stats">')
    html_parts.append(f"{len(file_diffs)} file{'s' if len(file_diffs) != 1 else ''}")
    html_parts.append(f' <span class="add">+{total_added}</span>')
    html_parts.append(f' <span class="del">−{total_removed}</span>')
    html_parts.append(f" · {tool_count} tool call{'s' if tool_count != 1 else ''}")
    html_parts.append(f" · {model}")
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

    html_parts.append("</div>")  # Close diff-view

    # Initialize highlight.js
    html_parts.append("<script>")
    html_parts.append("document.addEventListener('DOMContentLoaded',()=>{")
    html_parts.append("document.querySelectorAll('code[class*=language-]').forEach(el=>{")
    html_parts.append("try{hljs.highlightElement(el)}catch(e){}});});")
    html_parts.append("</script>")

    html_parts.append("</body></html>")

    return "".join(html_parts)


def generate_session_diff_html(
    session: "Session",
    *,
    cwd: str | None = None,
    sessions_dir: Path | None = None,
    project: str | None = None,
) -> str | None:
    """Generate HTML showing all file changes for an entire session.

    Creates a GitHub-style diff view aggregating all file changes across all turns,
    including changes made by subagents. For each modified file, shows the diff
    from the earliest backup (state before first edit) to the current file on disk
    (state at session end).

    Args:
        session: The session to generate diff for
        cwd: Current working directory for resolving relative paths
        sessions_dir: Directory containing session files (for finding subagent files)
        project: Weave project name (e.g., "entity/project") for the resume command

    Returns:
        HTML string with session diff view, or None if no file changes
    """
    from weave.integrations.claude_plugin.session_parser import (
        FileBackup,
        parse_session_file,
    )

    if not session.turns:
        return None

    # Collect all sessions to process (main session + subagents)
    all_sessions = [session]

    # Find and parse subagent session files
    if sessions_dir and sessions_dir.exists():
        for agent_file in sessions_dir.glob("agent-*.jsonl"):
            agent_session = parse_session_file(agent_file)
            if agent_session:
                all_sessions.append(agent_session)

    # Collect earliest backup for each file across all sessions and turns
    # This represents the state BEFORE the first edit to each file
    earliest_backups: dict[str, FileBackup] = {}

    for sess in all_sessions:
        for turn in sess.turns:
            for fb in turn.file_backups:
                if not fb.backup_filename:
                    continue
                existing = earliest_backups.get(fb.file_path)
                # Keep the earliest backup (lowest version or earliest time)
                if not existing or fb.backup_time < existing.backup_time:
                    earliest_backups[fb.file_path] = fb

    if not earliest_backups:
        return None

    # Generate diffs comparing earliest backup -> current file on disk
    file_diffs: list[dict[str, Any]] = []
    total_added = 0
    total_removed = 0

    for file_path in sorted(earliest_backups.keys()):
        backup_fb = earliest_backups[file_path]

        # Load backup content (state BEFORE first edit)
        backup_content = backup_fb.load_content(session.session_id)
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

        # Compare backup to current file on disk
        try:
            disk_path = Path(file_path)
            if not disk_path.is_absolute():
                if cwd:
                    disk_path = Path(cwd) / file_path
                else:
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
                            "is_deleted": True,
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

            # Generate diff: earliest backup -> current
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
                        "is_deleted": False,
                        "diff_lines": diff_lines[2:],
                        "added": added,
                        "removed": removed,
                    }
                )
        except Exception:
            continue

    if not file_diffs:
        return None

    # Build HTML (similar structure to turn diff but with session-level header)
    html_parts: list[str] = []

    html_parts.append("<!DOCTYPE html>")
    html_parts.append('<html lang="en"><head>')
    html_parts.append('<meta charset="utf-8">')
    html_parts.append(
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
    )
    html_parts.append(DIFF_HTML_STYLES)
    html_parts.append(
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github.min.css">'
    )
    html_parts.append(
        '<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js"></script>'
    )
    html_parts.append("</head><body>")

    html_parts.append('<div class="diff-view">')

    # Resume session section (only if project is provided)
    if project and session.session_id:
        teleport_cmd = f"weave teleport {session.session_id} {project}"
        html_parts.append('<div class="resume-section">')
        html_parts.append('<div class="resume-label">')
        # Rocket/teleport icon SVG
        html_parts.append(
            '<svg viewBox="0 0 16 16"><path fill-rule="evenodd" d="M14.064 0a8.75 8.75 0 00-6.187 2.563l-.459.458c-.314.314-.616.641-.904.979H3.31a1.75 1.75 0 00-1.49.833L.11 7.607a.75.75 0 00.418 1.11l3.102.954c.037.051.079.1.124.145l2.429 2.428c.046.046.094.088.145.125l.954 3.102a.75.75 0 001.11.418l2.774-1.707a1.75 1.75 0 00.833-1.49V9.485c.338-.288.665-.59.979-.904l.458-.459A8.75 8.75 0 0016 1.936V1.75A1.75 1.75 0 0014.25 0h-.186zM10.5 10.625c-.088.06-.177.118-.266.175l-2.35 1.521.548 1.783 1.949-1.2a.25.25 0 00.119-.213v-2.066zM3.678 8.116L5.2 5.766c.058-.09.117-.178.176-.266H3.309a.25.25 0 00-.213.119l-1.2 1.95 1.782.547zm5.26-4.493A7.25 7.25 0 0114.063 1.5h.186a.25.25 0 01.25.25v.186a7.25 7.25 0 01-2.123 5.127l-.459.458a15.21 15.21 0 01-2.499 2.02l-2.317 1.5-2.143-2.143 1.5-2.317a15.25 15.25 0 012.02-2.5l.458-.458h.001zM12 5a1 1 0 11-2 0 1 1 0 012 0zm-8.44 9.56a1.5 1.5 0 10-2.12-2.12c-.734.73-1.047 2.332-1.15 3.003a.23.23 0 00.265.265c.671-.103 2.273-.416 3.005-1.148z"></path></svg>'
        )
        html_parts.append("Resume this session</div>")
        html_parts.append('<div class="resume-code-wrap">')
        html_parts.append(f'<pre class="resume-code" id="teleport-cmd">{_html_escape(teleport_cmd)}</pre>')
        html_parts.append('<button class="resume-copy-btn" onclick="copyTeleportCmd()" title="Copy to clipboard">')
        # Copy icon
        html_parts.append('<svg class="copy-icon" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 010 1.5h-1.5a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-1.5a.75.75 0 011.5 0v1.5A1.75 1.75 0 019.25 16h-7.5A1.75 1.75 0 010 14.25v-7.5z"></path><path fill-rule="evenodd" d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0114.25 11h-7.5A1.75 1.75 0 015 9.25v-7.5zm1.75-.25a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-7.5a.25.25 0 00-.25-.25h-7.5z"></path></svg>')
        # Check icon (shown after copy)
        html_parts.append('<svg class="check-icon" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z"></path></svg>')
        html_parts.append("</button>")
        html_parts.append("</div></div>")

    # Session-level header
    html_parts.append('<div class="diff-header">')
    html_parts.append('<div class="diff-title">Session File Changes</div>')
    html_parts.append('<div class="diff-stats">')
    html_parts.append(f"{len(file_diffs)} file{'s' if len(file_diffs) != 1 else ''} changed")
    html_parts.append(f' <span class="add">+{total_added}</span>')
    html_parts.append(f' <span class="del">−{total_removed}</span>')
    html_parts.append(f" · {len(session.turns)} turn{'s' if len(session.turns) != 1 else ''}")
    html_parts.append("</div></div>")

    # File diffs (reuse same structure as turn diff)
    for file_diff in file_diffs:
        file_path = file_diff["path"]
        lang = file_diff["lang"]
        is_deleted = file_diff.get("is_deleted", False)

        html_parts.append('<div class="diff-file">')
        html_parts.append('<div class="file-header">')
        html_parts.append(
            '<svg class="file-icon" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M3.75 1.5a.25.25 0 00-.25.25v12.5c0 .138.112.25.25.25h9.5a.25.25 0 00.25-.25V4.664a.25.25 0 00-.073-.177l-2.914-2.914a.25.25 0 00-.177-.073H3.75zM2 1.75C2 .784 2.784 0 3.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0113.25 16h-9.5A1.75 1.75 0 012 14.25V1.75z"></path></svg>'
        )
        html_parts.append(f'<span class="file-name">{_html_escape(file_path)}</span>')
        if is_deleted:
            html_parts.append('<span class="file-badge" style="background:#ffebe9;color:#d1242f">DELETED</span>')
        html_parts.append("</div>")

        html_parts.append('<div class="diff-table-wrap">')
        html_parts.append('<table class="diff-table">')

        # Render diff lines
        diff_lines = file_diff["diff_lines"]
        old_line = 0
        new_line = 0

        for line in diff_lines:
            if line.startswith("@@"):
                # Parse hunk header for line numbers
                match = re.match(r"@@ -(\d+)", line)
                if match:
                    old_line = int(match.group(1)) - 1
                match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
                if match:
                    new_line = int(match.group(1)) - 1
                html_parts.append('<tr class="line-hunk">')
                html_parts.append(f'<td colspan="4">{_html_escape(line.strip())}</td>')
                html_parts.append("</tr>")
            elif line.startswith("+"):
                new_line += 1
                content = _html_escape(line[1:].rstrip("\n\r"))
                html_parts.append('<tr class="line-add">')
                html_parts.append('<td class="line-num"></td>')
                html_parts.append(f'<td class="line-num">{new_line}</td>')
                html_parts.append('<td class="line-marker">+</td>')
                html_parts.append(
                    f'<td class="line-content"><code class="language-{lang}">{content}</code></td>'
                )
                html_parts.append("</tr>")
            elif line.startswith("-"):
                old_line += 1
                content = _html_escape(line[1:].rstrip("\n\r"))
                html_parts.append('<tr class="line-del">')
                html_parts.append(f'<td class="line-num">{old_line}</td>')
                html_parts.append('<td class="line-num"></td>')
                html_parts.append('<td class="line-marker">−</td>')
                html_parts.append(
                    f'<td class="line-content"><code class="language-{lang}">{content}</code></td>'
                )
                html_parts.append("</tr>")
            else:
                old_line += 1
                new_line += 1
                content = _html_escape(line[1:].rstrip("\n\r") if line else "")
                html_parts.append('<tr class="line-ctx">')
                html_parts.append(f'<td class="line-num">{old_line}</td>')
                html_parts.append(f'<td class="line-num">{new_line}</td>')
                html_parts.append('<td class="line-marker"></td>')
                html_parts.append(
                    f'<td class="line-content"><code class="language-{lang}">{content}</code></td>'
                )
                html_parts.append("</tr>")

        html_parts.append("</table></div>")
        html_parts.append("</div>")

    html_parts.append("</div>")

    html_parts.append("<script>")
    html_parts.append("document.addEventListener('DOMContentLoaded',()=>{")
    html_parts.append("document.querySelectorAll('code[class*=language-]').forEach(el=>{")
    html_parts.append("try{hljs.highlightElement(el)}catch(e){}});});")
    # Copy to clipboard function for teleport command
    html_parts.append("function copyTeleportCmd(){")
    html_parts.append("const cmd=document.getElementById('teleport-cmd');")
    html_parts.append("const btn=document.querySelector('.resume-copy-btn');")
    html_parts.append("if(cmd&&btn){")
    html_parts.append("navigator.clipboard.writeText(cmd.textContent).then(()=>{")
    html_parts.append("btn.classList.add('copied');")
    html_parts.append("setTimeout(()=>btn.classList.remove('copied'),2000);")
    html_parts.append("}).catch(()=>{")
    html_parts.append("const r=document.createRange();r.selectNode(cmd);")
    html_parts.append("window.getSelection().removeAllRanges();window.getSelection().addRange(r);")
    html_parts.append("document.execCommand('copy');window.getSelection().removeAllRanges();")
    html_parts.append("btn.classList.add('copied');setTimeout(()=>btn.classList.remove('copied'),2000);")
    html_parts.append("})}}")
    html_parts.append("</script>")

    html_parts.append("</body></html>")

    return "".join(html_parts)


# Inline CSS for GitHub-style todo view (matches diff view styling)
TODO_HTML_STYLES = """
<style>
*{box-sizing:border-box;margin:0;padding:0}
.todo-view{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;font-size:14px;line-height:1.5;color:#1f2328;background:#fff;max-height:100vh;overflow:auto}
.todo-header{padding:16px 20px;background:linear-gradient(180deg,#f6f8fa 0%,#eaeef2 100%);border-bottom:1px solid #d1d9e0}
.todo-title{font-size:16px;font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:8px}
.todo-title svg{width:18px;height:18px;fill:#656d76}
.todo-stats{font-size:13px;color:#656d76;margin-bottom:12px}
.todo-stats .completed{color:#1a7f37;font-weight:600}
.todo-stats .in-progress{color:#9a6700;font-weight:600}
.todo-stats .pending{color:#656d76;font-weight:600}
.progress-bar{height:8px;background:#e1e4e8;border-radius:4px;overflow:hidden;display:flex}
.progress-completed{background:#1a7f37;transition:width 0.3s ease}
.progress-in-progress{background:#bf8700;transition:width 0.3s ease}
.todo-list{padding:16px 20px}
.todo-item{display:flex;align-items:flex-start;padding:10px 12px;border:1px solid #d1d9e0;border-radius:6px;margin-bottom:8px;background:#fff}
.todo-item:last-child{margin-bottom:0}
.todo-item.completed{background:#f6fef9;border-color:#aceebb}
.todo-item.in-progress{background:#fffbeb;border-color:#f9e2af}
.todo-checkbox{width:20px;height:20px;border-radius:4px;border:2px solid #d1d9e0;margin-right:12px;flex-shrink:0;display:flex;align-items:center;justify-content:center;margin-top:1px}
.todo-item.completed .todo-checkbox{background:#1a7f37;border-color:#1a7f37}
.todo-item.completed .todo-checkbox svg{display:block}
.todo-item.in-progress .todo-checkbox{border-color:#bf8700;background:#fff}
.todo-checkbox svg{display:none;width:12px;height:12px;fill:#fff}
.todo-item.in-progress .todo-checkbox::after{content:'';width:8px;height:8px;background:#bf8700;border-radius:50%;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
.todo-content{flex:1;min-width:0}
.todo-text{color:#1f2328;word-wrap:break-word}
.todo-item.completed .todo-text{color:#656d76;text-decoration:line-through}
.todo-status{font-size:11px;font-weight:500;padding:2px 8px;border-radius:12px;margin-left:8px;white-space:nowrap}
.todo-item.completed .todo-status{background:#dafbe1;color:#1a7f37}
.todo-item.in-progress .todo-status{background:#fff8c5;color:#9a6700}
.todo-item.pending .todo-status{background:#f6f8fa;color:#656d76}
</style>
"""


def generate_todo_html(todos: list[dict[str, str]]) -> str:
    """Generate HTML showing todo list state with GitHub-style styling.

    Creates a clean task list view matching the diff view aesthetic with:
    - Progress bar showing completion status
    - Checkboxes with visual state indicators
    - Color-coded items by status

    Args:
        todos: List of todo items, each with keys:
            - content: The todo text
            - status: One of "pending", "in_progress", "completed"
            - activeForm: Present tense description (optional)

    Returns:
        HTML string with todo view
    """
    if not todos:
        return ""

    # Count by status
    completed = sum(1 for t in todos if t.get("status") == "completed")
    in_progress = sum(1 for t in todos if t.get("status") == "in_progress")
    pending = len(todos) - completed - in_progress

    # Calculate progress percentages
    total = len(todos)
    completed_pct = (completed / total * 100) if total > 0 else 0
    in_progress_pct = (in_progress / total * 100) if total > 0 else 0

    html_parts: list[str] = []

    # Document start with styles
    html_parts.append("<!DOCTYPE html>")
    html_parts.append('<html lang="en"><head>')
    html_parts.append('<meta charset="utf-8">')
    html_parts.append(
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
    )
    html_parts.append(TODO_HTML_STYLES)
    html_parts.append("</head><body>")

    # Main container
    html_parts.append('<div class="todo-view">')

    # Header with stats
    html_parts.append('<div class="todo-header">')
    html_parts.append('<div class="todo-title">')
    # Checklist icon SVG
    html_parts.append(
        '<svg viewBox="0 0 16 16"><path fill-rule="evenodd" d="M2.5 1.75a.25.25 0 01.25-.25h8.5a.25.25 0 01.25.25v7.736a.75.75 0 101.5 0V1.75A1.75 1.75 0 0011.25 0h-8.5A1.75 1.75 0 001 1.75v11.5c0 .966.784 1.75 1.75 1.75h3.17a.75.75 0 000-1.5H2.75a.25.25 0 01-.25-.25V1.75zM4.75 4a.75.75 0 000 1.5h4.5a.75.75 0 000-1.5h-4.5zM4 7.75A.75.75 0 014.75 7h2a.75.75 0 010 1.5h-2A.75.75 0 014 7.75zm11.774 3.537a.75.75 0 00-1.048-1.074l-4.226 4.12-1.685-1.642a.75.75 0 00-1.047 1.073l2.208 2.153a.75.75 0 001.048.001l4.75-4.631z"></path></svg>'
    )
    html_parts.append("Task Progress</div>")

    # Stats line
    html_parts.append('<div class="todo-stats">')
    html_parts.append(f'<span class="completed">{completed} completed</span>')
    if in_progress > 0:
        html_parts.append(f' · <span class="in-progress">{in_progress} in progress</span>')
    if pending > 0:
        html_parts.append(f' · <span class="pending">{pending} pending</span>')
    html_parts.append(f" · {total} total")
    html_parts.append("</div>")

    # Progress bar
    html_parts.append('<div class="progress-bar">')
    html_parts.append(
        f'<div class="progress-completed" style="width:{completed_pct:.1f}%"></div>'
    )
    html_parts.append(
        f'<div class="progress-in-progress" style="width:{in_progress_pct:.1f}%"></div>'
    )
    html_parts.append("</div>")

    html_parts.append("</div>")  # Close header

    # Todo list
    html_parts.append('<div class="todo-list">')

    for todo in todos:
        status = todo.get("status", "pending")
        content = todo.get("content", "")

        html_parts.append(f'<div class="todo-item {status}">')

        # Checkbox
        html_parts.append('<div class="todo-checkbox">')
        # Checkmark SVG (only visible for completed)
        html_parts.append(
            '<svg viewBox="0 0 12 12"><path fill-rule="evenodd" d="M10.28 2.28a.75.75 0 00-1.06-1.06L4.5 5.94 2.78 4.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.06 0l5.25-5.25z"></path></svg>'
        )
        html_parts.append("</div>")

        # Content
        html_parts.append('<div class="todo-content">')
        html_parts.append(f'<span class="todo-text">{_html_escape(content)}</span>')
        html_parts.append("</div>")

        # Status badge
        status_label = status.replace("_", " ").title()
        if status == "in_progress":
            status_label = "In Progress"
        html_parts.append(f'<span class="todo-status">{status_label}</span>')

        html_parts.append("</div>")  # Close todo-item

    html_parts.append("</div>")  # Close todo-list
    html_parts.append("</div>")  # Close todo-view
    html_parts.append("</body></html>")

    return "".join(html_parts)