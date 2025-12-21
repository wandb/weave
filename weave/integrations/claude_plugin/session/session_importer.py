"""Import Claude Code session files into Weave as traces.

This module converts Claude Code session JSONL files into Weave call traces,
enabling rich analytics on historic coding sessions.

Trace Structure:
    Session (trace root) - display_name from summarizer
    ├── Turn 1: User prompt → Assistant response (tool_calls in output)
    ├── Turn 2: User prompt → Assistant response (tool_calls in output)
    │   └── SubAgent (if Task tool spawned one)
    └── ...

Each turn captures:
    - User message content (in inputs.messages)
    - Assistant response with embedded tool_calls (in output)
    - Token usage (input, output, cache) - in summary
    - Model used
    - File snapshots and diff views

Tool calls are embedded in the turn/subagent output using OpenAI format,
enabling ChatView rendering without requiring separate child traces.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import weave
from weave.integrations.claude_plugin.core.state import (
    load_session as get_session_state,
)
from weave.integrations.claude_plugin.session.session_parser import (
    Session,
    parse_session_file,
)
from weave.integrations.claude_plugin.utils import (
    generate_session_name,
    reconstruct_call,
    truncate,
)
from weave.trace.context.weave_client_context import require_weave_client
from weave.type_wrappers.Content.content import Content

if TYPE_CHECKING:
    from weave.integrations.claude_plugin.views.cli_output import ImportResult

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


def _build_subagent_inputs(
    prompt: str,
    agent_id: str | None = None,
    subagent_type: str | None = None,
) -> dict[str, Any]:
    """Build subagent inputs in ChatView-compatible format.

    Creates inputs with `messages` array for ChatView detection,
    similar to turn inputs.

    Args:
        prompt: The subagent's prompt/task description
        agent_id: Optional agent ID for metadata
        subagent_type: Optional subagent type from Task tool input

    Returns:
        Input dict with messages array for ChatView compatibility
    """
    inputs: dict[str, Any] = {
        # Anthropic-format messages for chat view detection
        "messages": [{"role": "user", "content": truncate(prompt, 5000)}],
    }
    if agent_id:
        inputs["agent_id"] = agent_id
    if subagent_type:
        inputs["subagent_type"] = subagent_type
    return inputs


def _build_subagent_output(
    session: Any,
) -> dict[str, Any]:
    """Build subagent output in Message format for ChatView.

    Aggregates assistant text and tool calls across all turns in the
    subagent session to create a unified output.

    Args:
        session: Parsed subagent session with turns

    Returns:
        Output dict in Message format with role, content, tool_calls
    """
    if not session or not session.turns:
        return {
            "role": "assistant",
            "content": "",
            "model": "unknown",
        }

    # Get final assistant response (from last turn's last message)
    final_output = ""
    if session.turns:
        last_turn = session.turns[-1]
        if last_turn.assistant_messages:
            final_output = last_turn.assistant_messages[-1].get_text() or ""

    # Collect all tool calls across all turns
    all_tool_calls = []
    for turn in session.turns:
        for tc in turn.all_tool_calls():
            tool_call_entry: dict[str, Any] = {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.input) if tc.input else "{}",
                },
            }
            if tc.result is not None:
                tool_call_entry["response"] = {
                    "role": "tool",
                    "content": truncate(tc.result),
                    "tool_call_id": tc.id,
                }
            all_tool_calls.append(tool_call_entry)

    # Build Message format output
    model = session.primary_model()
    output: dict[str, Any] = {
        "role": "assistant",
        "content": truncate(final_output),
        "model": model or "unknown",
    }

    if all_tool_calls:
        output["tool_calls"] = all_tool_calls

    return output


def _build_turn_output(
    turn: Any,
    *,
    interrupted: bool = False,
) -> tuple[dict[str, Any], str, str]:
    """Build turn output in Message format for ChatView.

    Creates output compatible with Weave's ChatView Message format:
    - role: "assistant"
    - content: Main text response (string)
    - model: Model name
    - reasoning_content: Thinking content (for collapsible UI)
    - tool_calls: Tool calls in OpenAI format with embedded results

    Args:
        turn: Parsed turn data with assistant_messages and tool calls
        interrupted: True if user interrupted this turn

    Returns:
        Tuple of (output_dict, assistant_text, thinking_text)
    """
    model = turn.primary_model()

    # Collect assistant text and thinking content from all assistant messages
    assistant_text = ""
    thinking_text = ""
    for msg in turn.assistant_messages:
        text = msg.get_text()
        if text:
            assistant_text += text + "\n"
        if msg.thinking_content:
            thinking_text += msg.thinking_content + "\n"

    # Build output in Message format for ChatView
    # Note: We use Message format (not Anthropic's native format with type: "message")
    # because the ChatView Anthropic normalizer requires all content blocks to be text-only.
    # By omitting "type", the output passes through as a raw Message object which gives us:
    # - reasoning_content: Collapsible "Thinking" UI
    # - tool_calls: Expandable tool calls with embedded results
    # Note: Don't truncate turn content - it's the primary output and truncation
    # breaks Q&A detection when questions appear at the end of long responses
    output: dict[str, Any] = {
        "role": "assistant",
        "content": assistant_text.strip(),
        "model": model or "claude-sonnet-4-20250514",
    }

    # Add thinking/reasoning content for collapsible UI
    # Note: Don't truncate reasoning either - it's important context
    if thinking_text.strip():
        output["reasoning_content"] = thinking_text.strip()

    # Add tool calls with results in OpenAI format for expandable tool UI
    tool_calls = turn.all_tool_calls()
    if tool_calls:
        output["tool_calls"] = []
        for tc in tool_calls:
            tool_call_entry: dict[str, Any] = {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.input) if tc.input else "{}",
                },
            }
            # Include tool result as response if available
            if tc.result is not None:
                tool_call_entry["response"] = {
                    "role": "tool",
                    "content": truncate(tc.result),
                    "tool_call_id": tc.id,
                }
            output["tool_calls"].append(tool_call_entry)

    if interrupted:
        output["interrupted"] = True
        output["stop_reason"] = "user_interrupt"

    return output, assistant_text.strip(), thinking_text.strip()


def discover_session_files(
    sessions_dir: Path, most_recent_only: bool = True
) -> list[Path]:
    """Find session files in a directory.

    Only includes files with UUID-style names, filtering out agent-xxxx files.

    Args:
        sessions_dir: Directory to search
        most_recent_only: If True, return only the most recently modified file

    Returns:
        List of session file paths, sorted by modification time (newest first)
    """
    files = [f for f in sessions_dir.glob("*.jsonl") if is_uuid_filename(f.name)]

    # Sort by modification time, newest first
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    if most_recent_only and files:
        return [files[0]]

    return files


def _create_subagent_call(
    agent_id: str,
    parent_call: Any,
    sessions_dir: Path,
    client: Any,
    session_id: str,
    trace_id: str,
    subagent_type: str | None = None,
    include_tool_traces: bool = False,
) -> tuple[int, list[Any]]:
    """Create a subagent call with tool calls embedded in output.

    When a Task tool is invoked with subagent_type, it spawns a subagent that
    runs in a separate agent-{agentId}.jsonl file. This function parses that
    file and creates a claude_code.subagent call with ChatView-compatible
    inputs/outputs, matching the daemon's pattern.

    Tool calls are embedded in the subagent output using build_subagent_output(),
    which creates OpenAI-format tool_calls with results. When include_tool_traces
    is True, also creates child traces for each tool call.

    Also collects file snapshots from all turns for attachment to the parent turn.

    Args:
        agent_id: The agent ID extracted from the Task tool result
        parent_call: The turn call to attach the subagent to
        sessions_dir: Directory containing the agent files
        client: Weave client for creating calls
        session_id: Main session ID for loading file backups from file-history
        trace_id: Trace ID for reconstructing calls
        subagent_type: Optional subagent type from Task tool input
        include_tool_traces: If True, create child traces for each tool call

    Returns:
        Tuple of (calls_created, file_snapshots)
    """
    # Find the agent file
    agent_file = sessions_dir / f"agent-{agent_id}.jsonl"
    if not agent_file.exists():
        logger.debug(f"Agent file not found: {agent_file}")
        return 0, []

    # Parse the subagent session
    try:
        subagent_session = parse_session_file(agent_file)
    except Exception as e:
        logger.warning(f"Failed to parse agent file {agent_file}: {e}")
        return 0, []

    if not subagent_session or not subagent_session.turns:
        logger.debug(f"Agent session has no turns: {agent_file}")
        return 0, []

    # Build display name using helper that strips common prefixes
    first_prompt = subagent_session.first_user_prompt() or ""
    from weave.integrations.claude_plugin.utils import get_subagent_display_name

    display_name = get_subagent_display_name(first_prompt, agent_id)

    # Create subagent call with ChatView-compatible inputs and timestamp from parsed session
    subagent_call = client.create_call(
        op="claude_code.subagent",
        inputs=_build_subagent_inputs(first_prompt, agent_id, subagent_type),
        parent=parent_call,
        display_name=display_name,
        attributes={"agent_id": agent_id, "is_sidechain": True},
        use_stack=False,
        started_at=subagent_session.started_at(),
    )

    # Collect file snapshots and count tools from all turns
    file_snapshots: list[Any] = []
    file_paths_seen: set[str] = set()  # Avoid duplicates
    tool_counts: dict[str, int] = {}
    calls_created = 1  # Count the subagent call itself

    for turn in subagent_session.turns:
        # Pre-extract Edit tool data for this turn if we need tool traces
        edit_data_by_path: dict[str, dict] = {}
        if include_tool_traces and turn.raw_messages:
            from weave.integrations.ag_ui.views.diff_utils import (
                extract_edit_data_from_raw_messages,
            )

            for edit_data in extract_edit_data_from_raw_messages(turn.raw_messages):
                file_path = edit_data.get("file_path")
                if file_path:
                    edit_data_by_path[file_path] = edit_data

        # Count tool calls for summary
        for tc in turn.all_tool_calls():
            tool_counts[tc.name] = tool_counts.get(tc.name, 0) + 1

        # Log tool calls with parallel grouping (subagents often use parallel calls)
        if include_tool_traces:
            from weave.integrations.claude_plugin.utils import log_tool_calls_grouped

            calls_created += log_tool_calls_grouped(
                tool_call_groups=turn.grouped_tool_calls(),
                parent=subagent_call,
                edit_data_by_path=edit_data_by_path,
            )

        # Collect file snapshots from this turn's file backups
        # Note: Use main session_id (not agent_id) since file-history is stored
        # under the main session UUID, not the short agent ID
        for fb in turn.file_backups:
            if fb.file_path not in file_paths_seen:
                content = fb.load_content(session_id)
                if content:
                    file_snapshots.append(content)
                    file_paths_seen.add(fb.file_path)

        # Also collect file content from Write tool calls in raw messages
        # This captures new files created in subagents (which don't have file-history)
        if turn.raw_messages:
            from weave.integrations.ag_ui.views.diff_utils import (
                extract_write_data_from_raw_messages,
            )

            write_data_list = extract_write_data_from_raw_messages(turn.raw_messages)
            for write_data in write_data_list:
                file_path = write_data["file_path"]
                if file_path not in file_paths_seen:
                    file_content = write_data["content"]
                    # Create a Content object for the new file
                    try:
                        content = Content.from_bytes(
                            file_content.encode("utf-8"),
                            metadata={
                                "original_path": file_path,
                                "relative_path": Path(file_path).name,
                                "source": "write_tool",
                            },
                        )
                        file_snapshots.append(content)
                        file_paths_seen.add(file_path)
                    except Exception:
                        pass

    # Build output in Message format using shared helper
    # This embeds all tool calls with their results in OpenAI format
    subagent_output = _build_subagent_output(subagent_session)

    if file_snapshots:
        subagent_output["file_snapshots"] = file_snapshots

    # Build summary (metadata)
    total_usage = subagent_session.total_usage()
    model = subagent_session.primary_model()
    subagent_call.summary = {
        "turn_count": len(subagent_session.turns),
        "tool_call_count": sum(tool_counts.values()),
        "tool_counts": tool_counts,
        "model": model,
    }
    if model and total_usage:
        subagent_call.summary["usage"] = {model: total_usage.to_weave_usage()}

    # Generate and attach HTML diff view for subagent's file changes
    # Collect all edit data from all turns
    all_edit_data: list[dict] = []
    for turn in subagent_session.turns:
        if turn.raw_messages:
            from weave.integrations.ag_ui.views.diff_utils import (
                extract_edit_data_from_raw_messages,
            )

            all_edit_data.extend(extract_edit_data_from_raw_messages(turn.raw_messages))

    if all_edit_data:
        from weave.integrations.claude_plugin.utils import set_call_view
        from weave.integrations.ag_ui.views.diff_view import (
            DIFF_HTML_STYLES,
            _build_file_diffs_from_edit_data,
            _render_file_diff_html,
        )

        # Get cwd from the subagent session for relative paths
        cwd = subagent_session.cwd

        file_diffs = _build_file_diffs_from_edit_data(all_edit_data)
        if file_diffs:
            # Generate HTML with same styling as turn diffs
            html_parts = [
                "<!DOCTYPE html>",
                "<html><head>",
                f"<style>{DIFF_HTML_STYLES}</style>",
                "</head><body>",
                '<div class="diff-view">',
                '<div class="diff-header"><span class="diff-title">SubAgent File Changes</span></div>',
            ]
            # Render each file diff
            for file_diff in file_diffs:
                _render_file_diff_html(html_parts, file_diff, cwd=cwd)
            html_parts.append("</div></body></html>")
            diff_html = "\n".join(html_parts)

            set_call_view(
                call=subagent_call,
                client=client,
                name="file_changes",
                content=diff_html,
                extension="html",
                mimetype="text/html",
            )

    # Finish the subagent call
    client.finish_call(
        subagent_call, output=subagent_output, ended_at=subagent_session.ended_at()
    )

    logger.debug(
        f"Created subagent {agent_id}: {calls_created} calls, {sum(tool_counts.values())} tool calls, {len(file_snapshots)} file snapshots"
    )
    return calls_created, file_snapshots


def _import_session_to_weave(
    session: Session,
    session_file_path: Path,
    use_ollama: bool = True,
    include_tool_traces: bool = False,
) -> tuple[int, int, int, str]:
    """Import a session using ClaudeParser + AgentTraceBuilder.

    This is the new event-based approach that replaces SessionProcessor:
    1. ClaudeParser parses session → events
    2. AgentTraceBuilder processes events → Weave traces
    3. Hooks handle diff views

    Args:
        session: Parsed session data (already parsed from session_file_path)
        session_file_path: Path to the original session JSONL file
        use_ollama: Whether to use Ollama for generating display names
        include_tool_traces: If True, create child traces for each tool call

    Returns: (turns, tool_calls, calls_created, call_id)
    """
    from weave.integrations.claude_plugin.parser import ClaudeParser
    from weave.integrations.ag_ui.trace_builder import AgentTraceBuilder
    from weave.integrations.ag_ui.views.diff_view import generate_turn_diff_html
    from weave.integrations.claude_plugin.utils import (
        generate_session_name,
        get_git_info,
    )
    from weave.trace.view_utils import set_call_view

    client = require_weave_client()
    sessions_dir = session_file_path.parent

    # Pre-populate turn_data_map for hooks
    # Map step_id to turn data for diff view generation
    turn_data_map: dict[str, dict] = {}
    for turn_idx, turn in enumerate(session.turns):
        step_id = f"{session.session_id}-turn-{turn_idx}"
        turn_data_map[step_id] = {
            "turn": turn,
            "turn_index": turn_idx,
        }

    # Hook for attaching turn-level diff views
    def on_step_finished(event: Any, call: Any) -> None:
        """Attach turn-level diff view after step finishes."""
        # Get turn data from our tracking dict
        turn_data = turn_data_map.get(event.step_id)
        if not turn_data:
            return

        turn = turn_data["turn"]
        turn_index = turn_data["turn_index"]

        # Generate diff view
        diff_html = generate_turn_diff_html(
            turn=turn,
            turn_index=turn_index,
            all_turns=session.turns,
            session_id=session.session_id,
            turn_number=turn_index + 1,
            tool_count=len(turn.all_tool_calls()),
            model=turn.primary_model(),
            historic_mode=True,
            cwd=session.cwd,
            user_prompt=turn.user_message.content if turn.user_message else None,
        )

        if diff_html:
            set_call_view(
                call=call,
                client=client,
                name="file_changes",
                content=diff_html,
                extension="html",
                mimetype="text/html",
            )

    # Create trace builder with hooks
    builder = AgentTraceBuilder(
        weave_client=client,
        agent_name="Claude Code",
        on_step_finished=on_step_finished,
        create_tool_traces=include_tool_traces,
    )

    # Generate events from the already-parsed Session object
    # Instead of re-parsing the file, use the parser's internal event generator
    parser = ClaudeParser()
    events = parser._generate_events(session, scanner=None)

    # Process all events through the builder
    builder.process_events(events)

    # Get the session call to extract metadata
    session_call = builder._run_calls.get(session.session_id)
    if not session_call:
        raise RuntimeError("Session call was not created")

    session_call_id = session_call.id

    # Update session call display name if using Ollama
    if use_ollama:
        first_prompt = session.first_user_prompt()
        if first_prompt:
            display_name, _ = generate_session_name(first_prompt)
            # Note: display_name is already set during call creation via RunStartedEvent,
            # but we can update it here if needed
            # For now, we'll keep the one generated in the builder

    # Attach session-level summary with file snapshots
    # Collect file snapshots from all turns (already tracked by builder)
    usage = session.total_usage()
    model = session.primary_model()

    summary = {
        "turn_count": len(session.turns),
        "tool_call_count": session.total_tool_calls(),
        "tool_call_breakdown": session.tool_call_counts(),
        "duration_ms": session.duration_ms(),
        "model": model,
    }
    if model and usage:
        summary["usage"] = {model: usage.to_weave_usage()}

    # Add git info if available
    if session.cwd:
        git_info = get_git_info(session.cwd)
        if git_info:
            summary["git"] = git_info

    # Update the session call summary (merge with existing)
    if hasattr(session_call, "summary") and session_call.summary:
        session_call.summary.update(summary)
    else:
        session_call.summary = summary

    # Attach session-level diff view
    from weave.integrations.ag_ui.views.diff_view import generate_session_diff_html

    session_diff_html = generate_session_diff_html(
        session=session,
        sessions_dir=sessions_dir,
    )
    if session_diff_html:
        set_call_view(
            call=session_call,
            client=client,
            name="file_changes",
            content=session_diff_html,
            extension="html",
            mimetype="text/html",
        )

    # Attach file snapshots to session output
    from weave.integrations.ag_ui.views.diff_utils import (
        collect_all_file_changes_from_session,
    )

    file_changes = collect_all_file_changes_from_session(session, sessions_dir)
    file_snapshots = []

    if session.cwd:
        cwd_path = Path(session.cwd)
        for file_path, change_info in file_changes.items():
            after_content = change_info.get("after")
            if not after_content:
                continue

            try:
                abs_path = Path(file_path)
                if cwd_path and abs_path.is_absolute():
                    try:
                        rel_path = abs_path.relative_to(cwd_path)
                    except ValueError:
                        rel_path = Path(abs_path.name)
                else:
                    rel_path = abs_path

                ext = abs_path.suffix.lower()
                ext_to_mimetype = {
                    ".py": "text/x-python",
                    ".js": "text/javascript",
                    ".ts": "text/typescript",
                    ".json": "application/json",
                    ".yaml": "text/yaml",
                    ".md": "text/plain",
                    ".html": "text/html",
                }
                mimetype = ext_to_mimetype.get(ext, "text/plain")

                content_obj = Content(
                    content=after_content.encode("utf-8"),
                    mimetype=mimetype,
                    extension=ext or ".txt",
                    metadata={
                        "original_path": str(file_path),
                        "relative_path": str(rel_path),
                        "source": "edit_data",
                    },
                )
                file_snapshots.append(content_obj)
            except Exception:
                pass

    # Add session JSONL file itself
    session_file = sessions_dir / f"{session.session_id}.jsonl"
    if session_file.exists():
        try:
            session_content = Content.from_path(
                session_file,
                metadata={
                    "session_id": session.session_id,
                    "filename": session_file.name,
                    "relative_path": "session.jsonl",
                },
            )
            file_snapshots.insert(0, session_content)
        except Exception:
            pass

    # Get the existing output or create new one
    # Note: We need to access the call's output after it's been finished
    # For now, we'll store file_snapshots separately and attach them
    # This is a limitation - we may need to re-finish the call
    if file_snapshots:
        # Re-finish the session call with file snapshots
        # First, get existing output
        existing_output = getattr(session_call, "output", {}) or {}
        if isinstance(existing_output, dict):
            existing_output["file_snapshots"] = file_snapshots
        else:
            existing_output = {"file_snapshots": file_snapshots}

        # Note: The builder already finished the call, so we need to update it
        # This is a bit hacky - ideally we'd attach snapshots before finishing
        # For now, just attach as an attribute
        session_call.file_snapshots = file_snapshots

    # Count calls created
    # 1 session + N turns + (optionally N tool calls per turn)
    calls_created = 1 + len(session.turns)
    if include_tool_traces:
        # Each tool call creates a separate trace
        calls_created += session.total_tool_calls()

    return len(session.turns), session.total_tool_calls(), calls_created, session_call_id


def init_weave_quiet(project: str) -> None:
    """Initialize Weave without verbose output.

    Args:
        project: Weave project in "entity/project" format
    """
    weave.init(project)


def import_session_with_result(
    session_path: Path,
    dry_run: bool = False,
    use_ollama: bool = True,
    include_details: bool = True,
    include_tool_traces: bool = False,
) -> ImportResult:
    """Import a single session file and return structured result.

    Args:
        session_path: Path to the session JSONL file
        dry_run: If True, show what would be imported without importing
        use_ollama: Whether to use Ollama for generating display names
        include_details: If True, include session details for visualization
        include_tool_traces: If True, create child traces for each tool call

    Returns:
        ImportResult with session details and success/error status
    """
    from weave.integrations.claude_plugin.views.cli_output import (
        ImportResult,
        extract_session_details,
    )

    try:
        session = parse_session_file(session_path)
        if not session:
            return ImportResult(
                session_name=session_path.name,
                session_id="",
                turns=0,
                tool_calls=0,
                weave_calls=0,
                tokens=0,
                display_name="",
                success=False,
                error="Failed to parse session file",
            )

        if not session.turns:
            return ImportResult(
                session_name=session_path.name,
                session_id=session.session_id,
                turns=0,
                tool_calls=0,
                weave_calls=0,
                tokens=0,
                display_name="",
                success=False,
                error="No turns found in session",
            )

        # Check if session is currently being traced by daemon (active session)
        session_state = get_session_state(session.session_id)
        if session_state and not session_state.get("session_ended"):
            return ImportResult(
                session_name=session_path.name,
                session_id=session.session_id,
                turns=len(session.turns),
                tool_calls=session.total_tool_calls(),
                weave_calls=0,
                tokens=session.total_usage().total(),
                display_name="",
                success=False,
                error="Session is currently active (being traced by daemon)",
            )

        turns = len(session.turns)
        tool_calls = session.total_tool_calls()
        usage = session.total_usage()

        # Generate display name
        first_prompt = session.first_user_prompt()
        if use_ollama and first_prompt:
            display_name, _ = generate_session_name(first_prompt)
        else:
            display_name = session.session_id

        # Extract session details for visualization (single session imports)
        session_details = extract_session_details(session) if include_details else None

        if dry_run:
            # Estimate calls: 1 session + turns + tool_calls
            calls = 1 + turns + tool_calls
            return ImportResult(
                session_name=session_path.name,
                session_id=session.session_id,
                turns=turns,
                tool_calls=tool_calls,
                weave_calls=calls,
                tokens=usage.total(),
                display_name=display_name,
                success=True,
                session_details=session_details,
            )
        else:
            # Actually import using weave.log_call()
            turns, tool_calls, calls, call_id = _import_session_to_weave(
                session,
                session_file_path=session_path,
                use_ollama=use_ollama,
                include_tool_traces=include_tool_traces,
            )
            return ImportResult(
                session_name=session_path.name,
                session_id=session.session_id,
                turns=turns,
                tool_calls=tool_calls,
                weave_calls=calls,
                tokens=usage.total(),
                display_name=display_name,
                success=True,
                session_details=session_details,
                call_id=call_id,
            )

    except Exception as e:
        logger.debug(f"Error importing {session_path.name}: {e}")
        return ImportResult(
            session_name=session_path.name,
            session_id="",
            turns=0,
            tool_calls=0,
            weave_calls=0,
            tokens=0,
            display_name="",
            success=False,
            error=str(e),
        )


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
        turns, tool_calls, calls, _session_call_id = _import_session_to_weave(
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
        raise ValueError(
            "No session files found (only UUID-named files are imported, agent-* files are skipped)"
        )

    if full:
        logger.info(
            f"Found {len(session_files)} session files (--full mode, excluding agent-* files)"
        )
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
            logger.exception(f"Error importing {session_path.name}")
            if verbose:
                import traceback

                traceback.print_exc()

    # Build summary
    summary: dict[str, int | str] = {
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
