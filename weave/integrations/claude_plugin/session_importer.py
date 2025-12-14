"""Import Claude Code session files into Weave as traces.

This module converts Claude Code session JSONL files into Weave call traces,
enabling rich analytics on historic coding sessions.

Trace Structure:
    Session (trace root) - display_name from summarizer
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

import logging
import re
import time
from pathlib import Path
from typing import Any

import weave
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.view_utils import set_call_view
from weave.type_wrappers.Content.content import Content

from .diff_view import generate_session_diff_html, generate_turn_diff_html
from .diff_utils import (
    extract_edit_data_from_raw_messages,
    generate_html_from_structured_patch,
)
from .session_parser import Session, parse_session_file
from .utils import (
    extract_question_from_text,
    generate_session_name,
    get_tool_display_name,
    get_turn_display_name,
    log_tool_call,
    truncate,
)

logger = logging.getLogger(__name__)

# Regex to match UUID-style session filenames (not agent-xxxx files)
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jsonl$",
    re.IGNORECASE,
)

# Regex to extract agentId from Task tool results
AGENT_ID_PATTERN = re.compile(r"^agentId:\s*(\w+)", re.MULTILINE)


def is_uuid_filename(filename: str) -> bool:
    """Check if filename matches UUID pattern (not agent-xxxx files)."""
    return UUID_PATTERN.match(filename) is not None


def extract_agent_id(tool_result: str | None) -> str | None:
    """Extract agentId from Task tool result.

    Task tool results contain lines like:
        agentId: abc123

    Args:
        tool_result: The tool result string from a Task call

    Returns:
        The extracted agent ID, or None if not found
    """
    if not tool_result:
        return None
    match = AGENT_ID_PATTERN.search(tool_result)
    return match.group(1) if match else None


def discover_session_files(sessions_dir: Path, most_recent_only: bool = True) -> list[Path]:
    """Find session files in a directory.

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


def _expand_subagent(
    agent_id: str,
    parent_call: Any,
    sessions_dir: Path,
    client: Any,
) -> int:
    """Expand a subagent's tool calls as children of the parent Task call.

    When a Task tool is invoked with subagent_type, it spawns a subagent that
    runs in a separate agent-{agentId}.jsonl file. This function parses that
    file and creates child traces for each tool call the subagent made.

    For Edit tool calls, extracts structured patch data from raw messages to
    generate HTML diff views (since subagent files don't have file-history-snapshot).

    Args:
        agent_id: The agent ID extracted from the Task tool result
        parent_call: The Task tool call to attach children to
        sessions_dir: Directory containing the agent files
        client: Weave client for creating calls

    Returns:
        Number of calls created
    """
    from weave.integrations.claude_plugin.diff_utils import (
        extract_edit_data_from_raw_messages,
    )

    # Find the agent file
    agent_file = sessions_dir / f"agent-{agent_id}.jsonl"
    if not agent_file.exists():
        logger.debug(f"Agent file not found: {agent_file}")
        return 0

    # Parse the subagent session
    try:
        subagent_session = parse_session_file(agent_file)
    except Exception as e:
        logger.warning(f"Failed to parse agent file {agent_file}: {e}")
        return 0

    if not subagent_session or not subagent_session.turns:
        logger.debug(f"Agent session has no turns: {agent_file}")
        return 0

    calls_created = 0

    # Import each turn's tool calls as children of the Task call
    for turn in subagent_session.turns:
        # Extract Edit tool data from raw messages for this turn
        # This provides originalFile and structuredPatch for HTML diff generation
        edit_data_list = extract_edit_data_from_raw_messages(turn.raw_messages)

        # Build a mapping from file_path to Edit data (use the last edit for each file)
        edit_data_by_file: dict[str, dict[str, Any]] = {}
        for edit_data in edit_data_list:
            file_path = edit_data.get("file_path")
            if file_path:
                edit_data_by_file[file_path] = edit_data

        for tc in turn.all_tool_calls():
            # For Edit calls, try to get structured patch data for HTML diff view
            original_file = None
            structured_patch = None

            if tc.name == "Edit":
                file_path = tc.input.get("file_path")
                if file_path and file_path in edit_data_by_file:
                    edit_data = edit_data_by_file[file_path]
                    original_file = edit_data.get("original_file")
                    structured_patch = edit_data.get("structured_patch")

            log_tool_call(
                tool_name=tc.name,
                tool_input=tc.input,
                tool_output=tc.result,
                tool_use_id=tc.id,
                duration_ms=tc.duration_ms() or 0,
                parent=parent_call,
                original_file=original_file,
                structured_patch=structured_patch,
            )
            calls_created += 1

    logger.debug(f"Expanded subagent {agent_id}: {calls_created} tool calls")
    return calls_created


def _import_session_to_weave(
    session: Session,
    session_file_path: Path,
    use_ollama: bool = True,
) -> tuple[int, int, int]:
    """Import a session using weave.log_call().

    Args:
        session: Parsed session data
        session_file_path: Path to the original session JSONL file
        use_ollama: Whether to use Ollama for generating display names

    Returns: (turns, tool_calls, calls_created)
    """
    # Get the client for creating calls with summary views
    client = require_weave_client()

    usage = session.total_usage()
    model = session.primary_model()

    # Get first real user prompt for naming (matches daemon behavior)
    first_prompt = session.first_user_prompt()

    # Generate display name using the FIRST prompt (matches daemon behavior)
    # The first prompt best represents what the session is about
    if use_ollama and first_prompt:
        display_name, suggested_branch = generate_session_name(first_prompt)
    else:
        display_name = session.session_id
        suggested_branch = ""

    # Build file_snapshots list (matches daemon format)
    file_snapshots_list: list[Any] = []

    # Determine the claude directory from the session file path
    # Session files are in ~/.claude/projects/<project>/session.jsonl
    claude_dir = session_file_path.parent.parent.parent  # Go up from projects/<project> to .claude

    # 1. Load the session file as a Content object
    try:
        session_content = Content.from_path(
            session_file_path,
            metadata={
                "session_id": session.session_id,
                "filename": session.filename,
                "relative_path": "session.jsonl",
            },
        )
        file_snapshots_list.append(session_content)
    except Exception as e:
        logger.debug(f"Failed to load session file as Content: {e}")

    # 2. Add earliest backup for each modified file (state BEFORE session)
    from weave.integrations.claude_plugin.session_parser import FileBackup

    earliest_backups: dict[str, FileBackup] = {}
    for turn in session.turns:
        for fb in turn.file_backups:
            if not fb.backup_filename:
                continue
            existing = earliest_backups.get(fb.file_path)
            # Keep the earliest backup (lowest version or earliest time)
            if not existing or fb.backup_time < existing.backup_time:
                earliest_backups[fb.file_path] = fb

    for file_path, fb in sorted(earliest_backups.items()):
        content = fb.load_content(session.session_id, claude_dir=claude_dir)
        if content:
            file_snapshots_list.append(content)

    # 3. Add current state of all changed files (if they exist)
    if session.cwd:
        from pathlib import Path as PathLib

        cwd_path = PathLib(session.cwd)
        all_changed = session.get_all_changed_files()
        for file_path in all_changed:
            try:
                # Handle both absolute and relative paths
                if PathLib(file_path).is_absolute():
                    abs_path = PathLib(file_path)
                    try:
                        rel_path = abs_path.relative_to(cwd_path)
                    except ValueError:
                        rel_path = PathLib(abs_path.name)
                else:
                    rel_path = PathLib(file_path)
                    abs_path = cwd_path / file_path

                if abs_path.exists():
                    file_content = Content.from_path(
                        abs_path,
                        metadata={
                            "original_path": str(file_path),
                            "relative_path": str(rel_path),
                        },
                    )
                    file_snapshots_list.append(file_content)
            except Exception as e:
                logger.debug(f"Failed to attach file {file_path}: {e}")

    # Build session output (Content objects only, matches daemon)
    session_output: dict[str, Any] = {}
    if file_snapshots_list:
        session_output["file_snapshots"] = file_snapshots_list

    # Build session summary (metadata, matches daemon format)
    session_summary: dict[str, Any] = {
        "turn_count": len(session.turns),
        "tool_call_count": session.total_tool_calls(),
        "tool_call_breakdown": session.tool_call_counts(),
        "duration_ms": session.duration_ms(),
        "model": model,
        "session_started_at": session.started_at().isoformat() if session.started_at() else None,
        "session_ended_at": session.ended_at().isoformat() if session.ended_at() else None,
    }

    # Usage in summary must be model-keyed for Weave schema (matches daemon)
    if model and usage:
        session_summary["usage"] = {
            model: usage.to_weave_usage()
        }

    # Create the session-level call (root of the trace)
    # Use create_call to get mutable call object for summary/views
    session_call = client.create_call(
        op="claude_code.session",
        inputs={
            "session_id": session.session_id,
            "cwd": session.cwd,
            "git_branch": session.git_branch,
            "claude_code_version": session.version,
            "suggested_branch_name": suggested_branch or None,
            "first_prompt": truncate(first_prompt, 1000),
        },
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

    # Generate session-level diff view showing all file changes (matches daemon)
    sessions_dir = session_file_path.parent
    diff_html = generate_session_diff_html(
        session,
        cwd=session.cwd,
        sessions_dir=sessions_dir,
    )

    # If file-history-based diff failed, try using Edit tool data as fallback
    # Collect Edit data from all turns in the session AND subagent files
    if not diff_html:
        all_edit_data: list[dict[str, Any]] = []

        # 1. Collect from main session turns
        for turn in session.turns:
            if turn.raw_messages:
                edit_data_list = extract_edit_data_from_raw_messages(turn.raw_messages)
                all_edit_data.extend(edit_data_list)

        # 2. Collect from subagent files (Task calls with subagent_type)
        for turn in session.turns:
            for tc in turn.all_tool_calls():
                if tc.name == "Task" and tc.input.get("subagent_type"):
                    agent_id = extract_agent_id(tc.result)
                    if agent_id:
                        agent_file = sessions_dir / f"agent-{agent_id}.jsonl"
                        if agent_file.exists():
                            try:
                                agent_session = parse_session_file(agent_file)
                                if agent_session:
                                    for agent_turn in agent_session.turns:
                                        if agent_turn.raw_messages:
                                            edit_data_list = extract_edit_data_from_raw_messages(
                                                agent_turn.raw_messages
                                            )
                                            all_edit_data.extend(edit_data_list)
                            except Exception as e:
                                logger.debug(f"Failed to parse agent file {agent_file}: {e}")

        if all_edit_data:
            # Generate combined diff view from all Edit tool data
            html_parts = []
            for edit_data in all_edit_data:
                file_path = edit_data.get("file_path", "unknown")
                original_file = edit_data.get("original_file", "")
                structured_patch = edit_data.get("structured_patch", [])
                if structured_patch:
                    edit_html = generate_html_from_structured_patch(
                        file_path=file_path,
                        original_content=original_file,
                        structured_patch=structured_patch,
                    )
                    if edit_html:
                        html_parts.append(edit_html)
            if html_parts:
                diff_html = "\n".join(html_parts)

    # Set summary on call object before finishing
    session_call.summary = session_summary

    # Attach HTML view after summary assignment
    if diff_html:
        set_call_view(
            call=session_call,
            client=client,
            name="file_changes",
            content=diff_html,
            extension="html",
            mimetype="text/html",
        )

    # Finish the session call with output
    client.finish_call(session_call, output=session_output)

    calls_created = 1
    total_tool_calls = 0

    # Track pending question from previous turn for Q&A context
    pending_question: str | None = None

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

        # Get user content and display name
        user_content = turn.user_message.content
        turn_display_name = get_turn_display_name(i, user_content)

        # Load file backups as weave.Content objects (list format, matches daemon)
        # Determine the claude directory from the session file path
        # Session files are in ~/.claude/projects/<project>/session.jsonl
        claude_dir = session_file_path.parent.parent.parent  # Go up from projects/<project> to .claude
        file_snapshots: list[Any] = []
        for fb in turn.file_backups:
            content = fb.load_content(session.session_id, claude_dir=claude_dir)
            if content:
                file_snapshots.append(content)

        # Build turn output (matches daemon format)
        turn_output: dict[str, Any] = {
            "response": truncate(assistant_text),
            "tool_call_count": len(turn.all_tool_calls()),
        }

        # Add file snapshots to output if any were loaded
        if file_snapshots:
            turn_output["file_snapshots"] = file_snapshots

        # Build turn summary (metadata, matches daemon format)
        turn_summary: dict[str, Any] = {
            "model": turn_model,
            "tool_call_count": len(turn.all_tool_calls()),
            "duration_ms": turn.duration_ms(),
            "response_preview": truncate(assistant_text, 200),
        }

        # Usage in summary must be model-keyed for Weave schema
        if turn_model and turn_usage:
            turn_summary["usage"] = {turn_model: turn_usage.to_weave_usage()}

        # Generate HTML diff view for this turn
        # First try file-history-based diff generation
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

        # If file-history-based diff failed, try using Edit tool data as fallback
        # This handles cases where file-history-snapshot entries are empty/absent
        if not diff_html and turn.raw_messages:
            edit_data_list = extract_edit_data_from_raw_messages(turn.raw_messages)
            if edit_data_list:
                # Generate simple diff view from first Edit's structured patch
                # For multiple edits, we show them all
                html_parts = []
                for edit_data in edit_data_list:
                    file_path = edit_data.get("file_path", "unknown")
                    original_file = edit_data.get("original_file", "")
                    structured_patch = edit_data.get("structured_patch", [])
                    if structured_patch:
                        edit_html = generate_html_from_structured_patch(
                            file_path=file_path,
                            original_content=original_file,
                            structured_patch=structured_patch,
                        )
                        if edit_html:
                            html_parts.append(edit_html)
                if html_parts:
                    diff_html = "\n".join(html_parts)

        # Build turn inputs (matches daemon format)
        turn_inputs: dict[str, Any] = {
            "user_message": truncate(user_content),
        }

        # Add Q&A context if previous turn ended with a question
        if pending_question:
            turn_inputs["in_response_to"] = pending_question

        # Create turn call
        turn_call = client.create_call(
            op="claude_code.turn",
            inputs=turn_inputs,
            parent=session_call,
            attributes={
                "turn_number": i,
                "model": turn_model,
                "tool_count": len(turn.all_tool_calls()),
                "file_backup_count": len(file_snapshots),
            },
            display_name=turn_display_name,
            use_stack=False,
        )

        # Set summary on call object before finishing
        turn_call.summary = turn_summary

        # Set view if we have diffs
        if diff_html:
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
        # Use shared log_tool_call for consistent formatting and TodoWrite HTML views
        for tc in turn.all_tool_calls():
            # For Skill calls, use the skill expansion as output if available
            tool_output = tc.result
            if tc.name == "Skill" and turn.skill_expansion:
                tool_output = turn.skill_expansion

            tool_call = log_tool_call(
                tool_name=tc.name,
                tool_input=tc.input,
                tool_output=tool_output,
                tool_use_id=tc.id,
                duration_ms=tc.duration_ms() or 0,
                parent=turn_call,
            )
            calls_created += 1
            total_tool_calls += 1

            # Expand subagent traces for Task calls with subagent_type
            if tc.name == "Task" and tc.input.get("subagent_type"):
                agent_id = extract_agent_id(tc.result)
                if agent_id:
                    subagent_calls = _expand_subagent(
                        agent_id=agent_id,
                        parent_call=tool_call,
                        sessions_dir=sessions_dir,
                        client=client,
                    )
                    calls_created += subagent_calls
                    total_tool_calls += subagent_calls

        # Extract question from this turn's response for Q&A context tracking
        # This will be added to the next turn's inputs as 'in_response_to'
        pending_question = extract_question_from_text(assistant_text)

    return len(session.turns), total_tool_calls, calls_created


def import_session(
    session_path: Path,
    dry_run: bool = False,
    use_ollama: bool = True,
) -> tuple[int, int, int]:
    """Import a single session file.

    Args:
        session_path: Path to the session JSONL file
        dry_run: If True, show what would be imported without importing
        use_ollama: Whether to use Ollama for generating display names

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
        turns, tool_calls, calls = _import_session_to_weave(
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


def import_sessions(
    path: Path,
    project: str,
    full: bool = False,
    dry_run: bool = False,
    use_ollama: bool = True,
    verbose: bool = False,
) -> dict[str, Any]:
    """Import Claude Code sessions from a file or directory into Weave.

    Args:
        path: Path to a session file or directory containing sessions
        project: Weave project in "entity/project" format
        full: If True and path is a directory, import all sessions (default: most recent only)
        dry_run: If True, show what would be imported without importing
        use_ollama: Whether to use Ollama for generating display names
        verbose: If True, enable verbose logging

    Returns:
        Summary dict with import statistics
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Collect session files
    session_files: list[Path] = []
    if path.is_file():
        session_files = [path]
    elif path.is_dir():
        session_files = discover_session_files(path, most_recent_only=not full)
    else:
        raise ValueError(f"Path does not exist: {path}")

    if not session_files:
        raise ValueError("No session files found (only UUID-named files are imported, agent-* files are skipped)")

    if full:
        logger.info(f"Found {len(session_files)} session files (--full mode, excluding agent-* files)")
    else:
        logger.info(f"Importing most recent session: {session_files[0].name}")

    # Initialize Weave
    if dry_run:
        logger.info(f"[DRY RUN] Would initialize Weave project: {project}")
    else:
        weave.init(project)
        logger.info(f"Initialized Weave project: {project}")

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
                dry_run=dry_run,
                use_ollama=use_ollama,
            )
            if turns > 0:
                total_turns += turns
                total_tool_calls += tool_calls
                total_calls += calls
                imported += 1

            # Small delay between sessions in full mode to avoid overwhelming the API
            if full and not dry_run and i < len(session_files) - 1:
                time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error importing {session_path.name}: {e}")
            if verbose:
                import traceback
                traceback.print_exc()

    # Build summary
    summary = {
        "sessions_imported": imported,
        "total_turns": total_turns,
        "total_tool_calls": total_tool_calls,
        "total_weave_calls": total_calls,
        "total_tokens": total_tokens,
    }

    # Log summary
    logger.info("")
    logger.info("=" * 50)
    logger.info("Import Summary")
    logger.info("=" * 50)
    logger.info(f"Sessions imported: {imported}")
    logger.info(f"Total turns: {total_turns}")
    logger.info(f"Total tool calls: {total_tool_calls}")
    logger.info(f"Total Weave calls: {total_calls}")
    logger.info(f"Total tokens: {total_tokens:,}")

    if not dry_run and imported > 0:
        # Try to extract entity/project from the weave client for accurate URL
        try:
            client = require_weave_client()
            entity = client.entity
            proj = client.project
            traces_url = f"https://wandb.ai/{entity}/{proj}/weave/traces"
            summary["traces_url"] = traces_url
            logger.info("")
            logger.info(f"View traces: {traces_url}")
        except Exception as e:
            # Fall back to simple split if client extraction fails
            if "/" in project:
                entity, proj = project.split("/", 1)
                traces_url = f"https://wandb.ai/{entity}/{proj}/weave/traces"
                summary["traces_url"] = traces_url
                logger.info("")
                logger.info(f"View traces: {traces_url}")
            else:
                logger.debug(f"Could not generate traces URL: {e}")

    return summary
