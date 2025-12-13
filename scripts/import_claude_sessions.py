#!/usr/bin/env python
"""Import Claude Code session files into Weave as traces.

This script converts Claude Code session JSONL files into Weave call traces,
enabling rich analytics on your AI coding sessions.

Usage:
    # Import only the most recent session (default behavior)
    python scripts/import_claude_sessions.py \
        --project "vanpelt/claude-code-sessions" \
        --sessions-dir ~/.claude/projects/-Users-vanpelt-Development-weave

    # Import ALL sessions
    python scripts/import_claude_sessions.py \
        --project "vanpelt/claude-code-sessions" \
        --sessions-dir ~/.claude/projects/-Users-vanpelt-Development-weave \
        --full

    # Import specific session files
    python scripts/import_claude_sessions.py \
        --project "vanpelt/claude-code-sessions" \
        --files session1.jsonl session2.jsonl

    # Dry run to see what would be imported
    python scripts/import_claude_sessions.py \
        --project "vanpelt/claude-code-sessions" \
        --sessions-dir ~/.claude/projects/-Users-vanpelt-Development-weave \
        --dry-run

Trace Structure:
    Session (trace root) - display_name from Ollama summarizer
    ├── Turn 1: User prompt → Assistant response
    │   ├── Tool Call: Read
    │   ├── Tool Call: Grep
    │   └── Tool Call: Edit
    ├── Turn 2: User prompt → Assistant response
    │   └── ...
    └── ...

Each turn captures:
    - User message content
    - Assistant response (text + tool calls)
    - Token usage (input, output, cache) - native Weave tracking
    - Model used
    - Tool call details with inputs/outputs
"""

from __future__ import annotations

import argparse
import datetime
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any

# Add weave to path if running from scripts directory
sys.path.insert(0, str(Path(__file__).parent.parent))

import weave
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.view_utils import set_call_view
from weave.type_wrappers.Content.content import Content

# Import shared code from claude_plugin integration
from weave.integrations.claude_plugin import (
    FileBackup,
    Session,
    TokenUsage,
    Turn,
    generate_session_name,
    generate_turn_diff_html,
    get_tool_display_name,
    is_system_message,
    parse_session_file,
    truncate,
)
from weave.integrations.claude_plugin.session_parser import CLAUDE_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Regex to match UUID-style session filenames (not agent-xxxx files)
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jsonl$",
    re.IGNORECASE,
)


# ============================================================================
# Weave Trace Creation using weave.log_call()
# ============================================================================


def import_session_to_weave(
    session: Session,
    session_file_path: Path,
    use_ollama: bool = True,
) -> tuple[int, int, int]:
    """
    Import a session using weave.log_call().

    Args:
        session: Parsed session data
        session_file_path: Path to the original session JSONL file
        use_ollama: Whether to use Ollama for generating display names

    Returns: (turns, tool_calls, calls_created)
    """
    # Get the client for creating calls with summary views
    client = require_weave_client()
    project_id = client._project_id()

    usage = session.total_usage()
    model = session.primary_model()

    # Get first and last real user prompts
    first_prompt = session.first_user_prompt()
    last_prompt = session.last_user_prompt()

    # Generate display name using Ollama with the LAST prompt (more representative of session)
    # Fall back to first prompt if last is empty
    prompt_for_naming = last_prompt or first_prompt
    if use_ollama and prompt_for_naming:
        display_name, suggested_branch = generate_session_name(prompt_for_naming)
    else:
        display_name = session.session_id
        suggested_branch = ""

    # Load the session file as a Content object
    session_content: Content | None = None
    try:
        session_content = Content.from_path(
            session_file_path,
            metadata={
                "session_id": session.session_id,
                "filename": session.filename,
            },
        )
    except Exception as e:
        logger.debug(f"Failed to load session file as Content: {e}")

    # Build session output
    session_output: dict[str, Any] = {
        # These two keys trigger Weave's native usage tracking
        "model": model,
        "usage": usage.to_weave_usage(),
        # Additional metadata
        "turn_count": len(session.turns),
        "tool_call_count": session.total_tool_calls(),
        "tool_call_breakdown": session.tool_call_counts(),
        "duration_ms": session.duration_ms(),
        "session_started_at": session.started_at().isoformat() if session.started_at() else None,
        "session_ended_at": session.ended_at().isoformat() if session.ended_at() else None,
    }

    # Add session file as Content object
    if session_content:
        session_output["file_snapshots"] = {
            "session.jsonl": session_content,
        }

    # Create the session-level call (root of the trace)
    # Use model + usage at top level for native Weave usage tracking
    session_call = weave.log_call(
        op="claude_code.session",
        inputs={
            "session_id": session.session_id,
            "cwd": session.cwd,
            "git_branch": session.git_branch,
            "claude_code_version": session.version,
            "suggested_branch_name": suggested_branch or None,
            "first_prompt": truncate(first_prompt, 1000),
        },
        output=session_output,
        attributes={
            "session_id": session.session_id,
            "filename": session.filename,
            "git_branch": session.git_branch,
            "source": "claude-code-import",
            "model": model,
        },
        display_name=display_name,
        use_stack=False,
    )

    calls_created = 1
    total_tool_calls = 0

    # Import each turn
    for i, turn in enumerate(session.turns, 1):
        turn_model = turn.primary_model()
        turn_usage = turn.total_usage()

        # Collect assistant text
        assistant_text = ""
        for msg in turn.assistant_messages:
            text = msg.get_text()
            if text:
                assistant_text += text + "\n"

        # Truncate user message for display name
        user_content = turn.user_message.content
        user_preview = user_content[:50].replace("\n", " ")
        if len(user_content) > 50:
            user_preview += "..."

        # Load file backups as weave.Content objects
        file_snapshots: dict[str, Content] = {}
        for fb in turn.file_backups:
            content = fb.load_content(session.session_id)
            if content:
                # Use the original file path as the key
                file_snapshots[fb.file_path] = content

        # Build output dict
        turn_output: dict[str, Any] = {
            # These two keys trigger Weave's native usage tracking
            "model": turn_model,
            "usage": turn_usage.to_weave_usage(),
            # Additional response data
            "response": truncate(assistant_text),
            "tool_call_count": len(turn.all_tool_calls()),
            "duration_ms": turn.duration_ms(),
        }

        # Add file snapshots if any were loaded
        if file_snapshots:
            turn_output["file_snapshots"] = file_snapshots

        # Generate HTML diff view for this turn
        # Note: enumerate is 1-based (i), but generate_turn_diff_html expects 0-based index
        # Use historic_mode=True since we're importing old sessions and need to compare
        # consecutive backups rather than backup vs current disk state
        diff_html = generate_turn_diff_html(
            turn=turn,
            turn_index=i - 1,  # Convert to 0-based
            all_turns=session.turns,
            session_id=session.session_id,
            turn_number=i,
            tool_count=len(turn.all_tool_calls()),
            model=turn_model,
            historic_mode=True,
            cwd=session.cwd,
            user_prompt=user_content,
        )

        # Create turn call using create_call + finish_call to allow setting summary views
        turn_call = client.create_call(
            op="claude_code.turn",
            inputs={
                "user_message": truncate(user_content),
            },
            parent=session_call,
            attributes={
                "turn_number": i,
                "model": turn_model,
                "tool_count": len(turn.all_tool_calls()),
                "file_backup_count": len(file_snapshots),
            },
            display_name=f"Turn {i}: {user_preview}",
            use_stack=False,
        )

        # Set summary with view content if we have diffs
        if diff_html:
            # Use the official set_call_view utility to properly attach the view
            set_call_view(
                call=turn_call,
                client=client,
                name="file_changes",
                content=diff_html,
                extension="html",
                mimetype="text/html",
            )

        # Finish the call with output
        client.finish_call(turn_call, output=turn_output)
        calls_created += 1

        # Import tool calls as children of the turn
        for tc in turn.all_tool_calls():
            # Sanitize input - truncate large values
            sanitized_input = {}
            for k, v in tc.input.items():
                if isinstance(v, str) and len(v) > 5000:
                    sanitized_input[k] = truncate(v)
                else:
                    sanitized_input[k] = v

            # Create a meaningful display name based on tool type
            tool_display = get_tool_display_name(tc.name, tc.input)

            weave.log_call(
                op=f"claude_code.tool.{tc.name}",
                inputs=sanitized_input,
                output={"result": truncate(tc.result, 10000)} if tc.result else None,
                attributes={
                    "tool_name": tc.name,
                    "tool_use_id": tc.id,
                    "duration_ms": tc.duration_ms(),
                },
                display_name=tool_display,
                parent=turn_call,
                use_stack=False,
            )
            calls_created += 1
            total_tool_calls += 1

    return len(session.turns), total_tool_calls, calls_created


# ============================================================================
# Main Import Logic
# ============================================================================


def is_uuid_filename(filename: str) -> bool:
    """Check if filename matches UUID pattern (not agent-xxxx files)."""
    return UUID_PATTERN.match(filename) is not None


def discover_session_files(sessions_dir: Path, most_recent_only: bool = True) -> list[Path]:
    """
    Find session files in a directory.

    Only includes files with UUID-style names, filtering out agent-xxxx files.

    Args:
        sessions_dir: Directory to search
        most_recent_only: If True, return only the most recently modified file

    Returns:
        List of session file paths, sorted by modification time (newest first)
    """
    files = [
        f for f in sessions_dir.glob("*.jsonl")
        if is_uuid_filename(f.name)
    ]

    # Sort by modification time, newest first
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    if most_recent_only and files:
        return [files[0]]

    return files


def import_session(
    session_path: Path,
    dry_run: bool = False,
    use_ollama: bool = True,
) -> tuple[int, int, int]:
    """
    Import a single session file.

    Returns: (turns, tool_calls, calls_created)
    """
    session = parse_session_file(session_path)
    if not session:
        return 0, 0, 0

    if not session.turns:
        logger.info(f"  Skipping {session_path.name}: no turns found")
        return 0, 0, 0

    turns = len(session.turns)
    tool_calls = session.total_tool_calls()
    usage = session.total_usage()

    if dry_run:
        # Generate name even in dry run to show what would be used
        # Use last prompt for naming (more representative of session)
        last_prompt = session.last_user_prompt()
        first_prompt = session.first_user_prompt()
        prompt_for_naming = last_prompt or first_prompt
        if use_ollama and prompt_for_naming:
            display_name, suggested_branch = generate_session_name(prompt_for_naming)
        else:
            display_name = session.session_id
            suggested_branch = ""

        # Estimate calls: 1 session + turns + tool_calls
        calls = 1 + turns + tool_calls
        logger.info(
            f"  [DRY RUN] {session_path.name}:\n"
            f"    Display Name: {display_name}\n"
            f"    Suggested Branch: {suggested_branch or '(none)'}\n"
            f"    Session ID: {session.session_id}\n"
            f"    Turns: {turns}, Tool calls: {tool_calls}\n"
            f"    Tokens: {usage.total():,} (in: {usage.total_input():,}, out: {usage.output_tokens:,})\n"
            f"    Model: {session.primary_model()}"
        )
        return turns, tool_calls, calls
    else:
        # Actually import using weave.log_call()
        turns, tool_calls, calls = import_session_to_weave(
            session,
            session_file_path=session_path,
            use_ollama=use_ollama,
        )
        logger.info(
            f"  Imported {session_path.name}:\n"
            f"    Session ID: {session.session_id}\n"
            f"    Turns: {turns}, Tool calls: {tool_calls}, Weave calls: {calls}\n"
            f"    Tokens: {usage.total():,}"
        )
        return turns, tool_calls, calls


def main():
    parser = argparse.ArgumentParser(
        description="Import Claude Code sessions into Weave",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Weave project (entity/project format)",
    )
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        help="Directory containing Claude session .jsonl files",
    )
    parser.add_argument(
        "--files",
        type=Path,
        nargs="+",
        help="Specific session files to import",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Import ALL sessions (default: only most recent)",
    )
    parser.add_argument(
        "--no-ollama",
        action="store_true",
        help="Skip Ollama summarizer for display names",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and show what would be imported without actually importing",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    use_ollama = not args.no_ollama

    # Collect session files
    session_files: list[Path] = []
    if args.files:
        session_files = [p for p in args.files if p.exists()]
    elif args.sessions_dir:
        # Default: most recent only, unless --full is specified
        session_files = discover_session_files(
            args.sessions_dir,
            most_recent_only=not args.full
        )
    else:
        parser.error("Either --sessions-dir or --files must be provided")

    if not session_files:
        logger.error("No session files found (only UUID-named files are imported, agent-* files are skipped)")
        sys.exit(1)

    if args.full:
        logger.info(f"Found {len(session_files)} session files (--full mode, excluding agent-* files)")
    else:
        logger.info(f"Importing most recent session: {session_files[0].name}")

    # Initialize Weave
    if args.dry_run:
        logger.info(f"[DRY RUN] Would initialize Weave project: {args.project}")
    else:
        weave.init(args.project)
        logger.info(f"Initialized Weave project: {args.project}")

    # Import sessions
    total_turns = 0
    total_tool_calls = 0
    total_calls = 0
    total_tokens = 0
    imported = 0

    for i, session_path in enumerate(session_files):
        try:
            session = parse_session_file(session_path)
            if session:
                total_tokens += session.total_usage().total()

            turns, tool_calls, calls = import_session(
                session_path=session_path,
                dry_run=args.dry_run,
                use_ollama=use_ollama,
            )
            if turns > 0:
                total_turns += turns
                total_tool_calls += tool_calls
                total_calls += calls
                imported += 1

            # Small delay between sessions in full mode to avoid overwhelming the API
            if args.full and not args.dry_run and i < len(session_files) - 1:
                time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error importing {session_path.name}: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()

    # Summary
    logger.info("")
    logger.info("=" * 50)
    logger.info("Import Summary")
    logger.info("=" * 50)
    logger.info(f"Sessions imported: {imported}")
    logger.info(f"Total turns: {total_turns}")
    logger.info(f"Total tool calls: {total_tool_calls}")
    logger.info(f"Total Weave calls: {total_calls}")
    logger.info(f"Total tokens: {total_tokens:,}")

    if not args.dry_run and imported > 0:
        entity, project = args.project.split("/", 1)
        logger.info("")
        logger.info(f"View traces: https://wandb.ai/{entity}/{project}/weave/traces")


if __name__ == "__main__":
    main()
