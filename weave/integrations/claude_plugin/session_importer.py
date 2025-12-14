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

from .diff_utils import extract_edit_data_from_raw_messages
from .session_parser import Session, parse_session_file
from .utils import generate_session_name, log_tool_call

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
    """Import a session using SessionProcessor.

    Args:
        session: Parsed session data
        session_file_path: Path to the original session JSONL file
        use_ollama: Whether to use Ollama for generating display names

    Returns: (turns, tool_calls, calls_created)
    """
    from weave.integrations.claude_plugin.session_processor import SessionProcessor

    client = require_weave_client()
    processor = SessionProcessor(
        client=client,
        project=client._project_id(),
        source="import",
    )

    # Get first real user prompt for naming
    first_prompt = session.first_user_prompt() or ""

    # Create session call
    session_call = processor.create_session_call(
        session_id=session.session_id,
        first_prompt=first_prompt,
        cwd=session.cwd,
        git_branch=session.git_branch,
        claude_code_version=session.version,
    )

    calls_created = 1
    total_tool_calls = 0
    pending_question: str | None = None
    sessions_dir = session_file_path.parent

    # Import each turn
    for i, turn in enumerate(session.turns):
        # Create turn call
        turn_call = processor.create_turn_call(
            parent=session_call,
            turn_number=i + 1,
            user_message=turn.user_message.content if turn.user_message else "",
            pending_question=pending_question,
        )
        calls_created += 1

        # Import tool calls as children of the turn
        for tc in turn.all_tool_calls():
            # Skip Task tools with subagent_type - handled separately after creating the tool call
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

        # Finish turn call (returns extracted question)
        pending_question = processor.finish_turn_call(
            turn_call=turn_call,
            turn=turn,
            session=session,
            turn_index=i,
        )

    # Finish session call
    processor.finish_session_call(
        session_call=session_call,
        session=session,
        sessions_dir=sessions_dir,
    )

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
