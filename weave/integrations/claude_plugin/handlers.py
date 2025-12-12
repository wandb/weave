"""Hook handlers for real-time Weave tracing of Claude Code sessions.

This module implements handlers for Claude Code hook events:
- SessionStart: Initialize state
- UserPromptSubmit: Create session (on first) and turn calls
- Stop: Finish turn with full data from transcript
- SessionEnd: Finish session and cleanup

Each handler is called in a separate process, so state is persisted
to disk between invocations.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import weave
from weave.trace.call import Call
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.view_utils import set_call_view
from weave.type_wrappers.Content.content import Content

from weave.integrations.claude_plugin.diff_view import (
    generate_session_diff_html,
    generate_turn_diff_html,
)
from weave.integrations.claude_plugin.session_parser import (
    Session,
    ToolCall,
    Turn,
    parse_session_file,
)
from weave.integrations.claude_plugin.state import (
    StateManager,
    create_session_data,
)
from weave.integrations.claude_plugin.utils import (
    extract_command_output,
    extract_slash_command,
    generate_session_name,
    get_tool_display_name,
    get_turn_display_name,
    is_command_output,
    truncate,
)

# Use the same logger setup as hook.py for consistent debug output
# Test edit to verify diff view is working correctly
logger = logging.getLogger("weave.integrations.claude_plugin.hook")


def _find_turn_by_prompt(session: Session, prompt_prefix: str) -> Turn | None:
    """Find a turn in the session by matching the user prompt prefix.

    Args:
        session: Parsed session object
        prompt_prefix: First N characters of the user prompt to match

    Returns:
        The matching Turn, or None if not found
    """
    if not session or not session.turns or not prompt_prefix:
        return None

    # Search from the end since we want the most recent matching turn
    for turn in reversed(session.turns):
        turn_text = turn.user_message.content or ""
        if turn_text.startswith(prompt_prefix):
            return turn

    return None


def _reconstruct_parent_call(
    project_id: str,
    call_id: str,
    trace_id: str,
) -> Call:
    """Reconstruct a minimal Call object for use as a parent reference.

    When creating child calls across process boundaries, we need to provide
    a Call object with the correct id and trace_id so the child inherits
    the trace_id and has the correct parent_id.

    Args:
        project_id: Weave project ID
        call_id: The parent call's ID
        trace_id: The trace ID (shared across all calls in the trace)

    Returns:
        A minimal Call object suitable for use as a parent
    """
    return Call(
        _op_name="",
        project_id=project_id,
        trace_id=trace_id,
        parent_id=None,
        inputs={},
        id=call_id,
    )


def _log_tool_calls(
    turn: Turn,
    parent_call: Call,
    session_data: dict[str, Any],
) -> None:
    """Log tool calls from a turn as Weave calls.

    Args:
        turn: The turn containing tool calls
        parent_call: Parent call to attach tool calls to
        session_data: Session data dict to update tool counts
    """
    for tc in turn.all_tool_calls():
        tool_display = get_tool_display_name(tc.name, tc.input)

        # Sanitize input - truncate large values
        sanitized_input = {}
        for k, v in tc.input.items():
            if isinstance(v, str) and len(v) > 5000:
                sanitized_input[k] = truncate(v)
            else:
                sanitized_input[k] = v

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
            parent=parent_call,
            use_stack=False,
        )

        # Update tool counts
        tool_counts = session_data.get("tool_counts", {})
        tool_counts[tc.name] = tool_counts.get(tc.name, 0) + 1
        session_data["tool_counts"] = tool_counts
        session_data["total_tool_calls"] = session_data.get("total_tool_calls", 0) + 1


def _build_turn_output(
    turn: Turn | None,
    session: Session | None = None,
    interrupted: bool = False,
    command_output: str | None = None,
) -> dict[str, Any]:
    """Build the output dict for a turn call.

    Args:
        turn: The turn data (may be None if not found in transcript)
        session: The session data (for loading file backups)
        interrupted: Whether the turn was interrupted by user
        command_output: Output from a slash command to include in response

    Returns:
        Output dict for the turn call
    """
    output: dict[str, Any] = {}

    if interrupted:
        output["interrupted"] = True

    if command_output:
        output["command_output"] = command_output

    if turn:
        turn_usage = turn.total_usage()
        assistant_text = ""
        for msg in turn.assistant_messages:
            text = msg.get_text()
            if text:
                assistant_text += text + "\n"

        output.update(
            {
                "model": turn.primary_model(),
                "usage": turn_usage.to_weave_usage(),
                "response": truncate(assistant_text.strip()),
                "tool_call_count": len(turn.all_tool_calls()),
                "duration_ms": turn.duration_ms(),
            }
        )

        # Include images from user message
        # Images are captured here at Stop time because they're not reliably
        # in the transcript when UserPromptSubmit fires
        if turn.user_message.images:
            output["images"] = turn.user_message.images
            logger.debug(f"_build_turn_output: captured {len(turn.user_message.images)} images")

        # Load file backups as Content objects
        if turn.file_backups and session:
            file_snapshots: dict[str, Content] = {}
            for fb in turn.file_backups:
                content = fb.load_content(session.session_id)
                if content:
                    file_snapshots[fb.file_path] = content
            if file_snapshots:
                output["file_snapshots"] = file_snapshots

    return output


def _finish_interrupted_turn(
    session_data: dict[str, Any],
    transcript_path: str | None,
    client: Any,
) -> None:
    """Finish a turn that was interrupted by the user.

    Called when we detect turn_call_id is still set on a new UserPromptSubmit,
    meaning the previous turn never received a Stop event.

    Args:
        session_data: Session data dict with turn info
        transcript_path: Path to transcript file
        client: Weave client
    """
    turn_call_id = session_data.get("turn_call_id")
    trace_id = session_data.get("trace_id")
    turn_number = session_data.get("turn_number", 0)

    if not turn_call_id or not trace_id:
        return

    logger.debug(f"Finishing interrupted turn {turn_number}")

    # Parse transcript to get the interrupted turn's data
    # Use latest turn since turn_number in state may not match parsed turn count
    turn = None
    session = None
    if transcript_path:
        session = parse_session_file(Path(transcript_path))
        if session and session.turns:
            turn = session.turns[-1]

    # Reconstruct turn call
    turn_call = _reconstruct_parent_call(
        client._project_id(),
        turn_call_id,
        trace_id,
    )

    # Log any tool calls that happened before interruption
    if turn:
        _log_tool_calls(turn, turn_call, session_data)

    # Finish the turn with interrupted flag
    output = _build_turn_output(turn, session=session, interrupted=True)
    client.finish_call(turn_call, output=output)

    # Clear turn state
    session_data["turn_call_id"] = None

    logger.debug(f"Finished interrupted turn {turn_number} with {output.get('tool_call_count', 0)} tool calls")


def handle_session_start(payload: dict[str, Any], project: str) -> dict[str, Any] | None:
    """Handle SessionStart hook event.

    Initializes state with session_id and transcript_path. Does NOT create
    the Weave trace yet - we wait until the first UserPromptSubmit so we
    can use the user's prompt to generate a session name.

    Args:
        payload: Hook payload with session_id, transcript_path, cwd, etc.
        project: Weave project in "entity/project" format

    Returns:
        None (no response needed for SessionStart)
    """
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")
    cwd = payload.get("cwd")

    if not session_id or not transcript_path:
        logger.warning("SessionStart missing session_id or transcript_path")
        return None

    with StateManager() as state:
        # Check if we already have state (session resumed)
        existing = state.get_session(session_id)
        if existing:
            logger.debug(f"Session {session_id} already has state (resumed)")
            return None

        # Create new state (but don't create Weave call yet)
        session_data = create_session_data(project=project)
        state.save_session(session_id, session_data, cwd=cwd)

    logger.debug(f"SessionStart: initialized state for {session_id}")
    return None


def handle_user_prompt_submit(
    payload: dict[str, Any], project: str
) -> dict[str, Any] | None:
    """Handle UserPromptSubmit hook event.

    On the first call, creates the session trace and first turn.
    On subsequent calls, creates a new turn as a child of the session.

    If a previous turn was interrupted (turn_call_id still set), finishes
    that turn first before starting the new one.

    Args:
        payload: Hook payload with session_id, transcript_path, prompt
        project: Weave project in "entity/project" format

    Returns:
        On first call: JSON response with trace URL for additionalContext
        On subsequent calls: None
    """
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")
    user_prompt = payload.get("prompt", "")
    cwd = payload.get("cwd")

    if not session_id:
        logger.warning("UserPromptSubmit missing session_id")
        return None

    # Initialize Weave
    weave.init(project)
    client = require_weave_client()

    # Get entity from client for state tracking
    entity = client.entity

    with StateManager() as state:
        # Load or create session data
        session_data = state.get_session(session_id)
        if not session_data:
            # SessionStart didn't fire or state was lost - create it now
            session_data = create_session_data(project=project, entity=entity)

        # Check for interrupted previous turn
        if session_data.get("turn_call_id"):
            _finish_interrupted_turn(session_data, transcript_path, client)

        # Increment turn number
        turn_number = session_data.get("turn_number", 0) + 1
        session_data["turn_number"] = turn_number

        # First turn - create session call
        session_call_id = session_data.get("session_call_id")
        trace_id = session_data.get("trace_id")

        if not session_call_id or not trace_id:
            # Generate session name from the prompt
            # Note: We don't parse transcript here because the current turn's
            # message may not be written yet when UserPromptSubmit fires
            display_name, suggested_branch = generate_session_name(user_prompt)

            # Create session call
            session_call = client.create_call(
                op="claude_code.session",
                inputs={
                    "session_id": session_id,
                    "cwd": cwd,
                    "suggested_branch_name": suggested_branch or None,
                    "first_prompt": truncate(user_prompt, 1000),
                },
                attributes={
                    "session_id": session_id,
                    "source": "claude-code-plugin",
                },
                display_name=display_name,
                use_stack=False,
            )

            session_data["session_call_id"] = session_call.id
            session_data["trace_id"] = session_call.trace_id
            session_data["entity"] = entity

            # Create first turn call
            # Note: Images are captured at Stop time when transcript is complete
            turn_call = client.create_call(
                op="claude_code.turn",
                inputs={
                    "user_message": truncate(user_prompt, 5000),
                },
                parent=session_call,
                attributes={
                    "turn_number": turn_number,
                },
                display_name=get_turn_display_name(turn_number, user_prompt),
                use_stack=False,
            )

            session_data["turn_call_id"] = turn_call.id
            # Store prompt prefix to identify this turn at Stop time
            session_data["turn_prompt_prefix"] = user_prompt[:200] if user_prompt else ""
            state.save_session(session_id, session_data, cwd=cwd)

            # Flush to ensure calls are sent
            client.flush()

            logger.debug(
                f"UserPromptSubmit: created session {session_call.id} and turn {turn_call.id}"
            )

            # Return trace URL and session_id for first turn
            return {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": f"Weave tracing active: {session_call.ui_url}\nWeave session_id: {session_id}",
                }
            }

        else:
            # Check if this is command output that should be merged with previous turn
            if is_command_output(user_prompt):
                # Don't create a new turn for command output
                # The output will be attached to the previous command turn at Stop time
                logger.debug(
                    f"UserPromptSubmit: skipping turn creation for command output"
                )
                # Decrement turn number since we didn't actually create a turn
                session_data["turn_number"] = turn_number - 1
                # Store the command output to merge with previous turn
                prev_output = session_data.get("pending_command_output", "")
                cmd_output = extract_command_output(user_prompt)
                if cmd_output:
                    session_data["pending_command_output"] = (
                        prev_output + "\n" + cmd_output if prev_output else cmd_output
                    )
                state.save_session(session_id, session_data, cwd=cwd)
                return None

            # Subsequent turn - reconstruct session call as parent
            session_call = _reconstruct_parent_call(
                client._project_id(),
                session_call_id,
                trace_id,
            )

            # Create turn call
            # Note: Images are captured at Stop time when transcript is complete
            # We don't parse transcript here because the current turn's message
            # may not be written yet when UserPromptSubmit fires
            turn_call = client.create_call(
                op="claude_code.turn",
                inputs={
                    "user_message": truncate(user_prompt, 5000),
                },
                parent=session_call,
                attributes={
                    "turn_number": turn_number,
                },
                display_name=get_turn_display_name(turn_number, user_prompt),
                use_stack=False,
            )

            session_data["turn_call_id"] = turn_call.id
            # Store prompt prefix to identify this turn at Stop time
            session_data["turn_prompt_prefix"] = user_prompt[:200] if user_prompt else ""
            # Clear any pending command output since this is a new turn
            session_data["pending_command_output"] = None
            state.save_session(session_id, session_data, cwd=cwd)

            client.flush()

            logger.debug(f"UserPromptSubmit: created turn {turn_call.id}")

            # Return session_id for feedback commands
            return {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": f"Weave tracing active: {session_call.ui_url}\nWeave session_id: {session_id}",
                }
            }


def handle_stop(payload: dict[str, Any], project: str) -> dict[str, Any] | None:
    """Handle Stop hook event.

    Parses the transcript to get full turn data (tool calls, tokens, response)
    and finishes the current turn call. Also loads file backups and generates
    diff HTML for the summary view.

    Args:
        payload: Hook payload with session_id, transcript_path
        project: Weave project in "entity/project" format

    Returns:
        None
    """
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")

    if not session_id:
        logger.warning("Stop missing session_id")
        return None

    with StateManager() as state:
        session_data = state.get_session(session_id)
        if not session_data:
            logger.debug(f"Stop: no state for {session_id}")
            return None

        session_call_id = session_data.get("session_call_id")
        trace_id = session_data.get("trace_id")
        turn_call_id = session_data.get("turn_call_id")

        if not session_call_id or not trace_id or not turn_call_id:
            logger.debug(f"Stop: no active turn for {session_id}")
            return None

        # Initialize Weave
        weave.init(project)
        client = require_weave_client()
        project_id = client._project_id()

        # Parse transcript to get current turn data
        # Find our turn by matching the prompt prefix stored at UserPromptSubmit
        turn = None
        session = None
        turn_index = 0
        turn_number = session_data.get("turn_number", 0)
        turn_prompt_prefix = session_data.get("turn_prompt_prefix", "")
        if transcript_path:
            session = parse_session_file(Path(transcript_path))
            if session and session.turns:
                # Find our turn by matching the stored prompt prefix
                turn = _find_turn_by_prompt(session, turn_prompt_prefix)
                if turn:
                    # Find the index of our turn for diff view
                    try:
                        turn_index = session.turns.index(turn)
                    except ValueError:
                        turn_index = len(session.turns) - 1
                    logger.debug(
                        f"Stop: turn_number={turn_number}, parsed_turns={len(session.turns)}, "
                        f"matched_turn_index={turn_index}, "
                        f"tool_calls={len(turn.all_tool_calls())}, "
                        f"images={len(turn.user_message.images)}"
                    )
                else:
                    # Fallback to latest turn if no match
                    turn = session.turns[-1]
                    turn_index = len(session.turns) - 1
                    logger.debug(
                        f"Stop: turn_number={turn_number}, parsed_turns={len(session.turns)}, "
                        f"no match found, falling back to latest turn"
                    )

        # Reconstruct turn call to finish it
        turn_call = _reconstruct_parent_call(
            project_id,
            turn_call_id,
            trace_id,
        )

        # Log tool calls
        if turn:
            _log_tool_calls(turn, turn_call, session_data)

        # Get any pending command output to include in turn output
        pending_command_output = session_data.get("pending_command_output")

        # Build turn output with file snapshots
        output = _build_turn_output(
            turn, session=session, command_output=pending_command_output
        )

        # Clear pending command output after using it
        if pending_command_output:
            session_data["pending_command_output"] = None

        # Generate diff HTML for summary view
        if turn and session:
            # turn_index was computed above when finding our turn
            diff_html = generate_turn_diff_html(
                turn=turn,
                turn_index=turn_index,
                all_turns=session.turns,
                session_id=session.session_id,
                turn_number=turn_index + 1,  # Display as 1-based
                tool_count=len(turn.all_tool_calls()),
                model=turn.primary_model(),
            )

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

        # Finish the turn call
        client.finish_call(turn_call, output=output)

        # Clear turn state (but keep session state)
        session_data["turn_call_id"] = None
        session_data["turn_prompt_prefix"] = None
        state.save_session(session_id, session_data)

        client.flush()

        logger.debug(
            f"Stop: finished turn {turn_number} with {output.get('tool_call_count', 0)} tool calls"
        )
        return None


def handle_subagent_stop(payload: dict[str, Any], project: str) -> dict[str, Any] | None:
    """Handle SubagentStop hook event.

    Creates a trace for the completed subagent as a child of the parent session.
    Subagents are spawned by the Task tool and run in separate processes.

    The subagent's transcript file contains:
    - sessionId: The PARENT session's UUID (not the subagent's own ID)
    - agentId: The subagent's short ID (e.g., "abc12345")
    - isSidechain: true (marks this as a subagent)

    Args:
        payload: Hook payload with session_id, transcript_path
        project: Weave project in "entity/project" format

    Returns:
        None
    """
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")

    if not session_id or not transcript_path:
        logger.warning("SubagentStop missing session_id or transcript_path")
        return None

    # Parse the subagent transcript
    agent_session = parse_session_file(Path(transcript_path))
    if not agent_session:
        logger.debug(f"SubagentStop: could not parse transcript {transcript_path}")
        return None

    # Get agent metadata from the first message
    agent_id = agent_session.agent_id
    parent_session_id = agent_session.session_id  # Points to parent

    if not parent_session_id:
        logger.debug(f"SubagentStop: no parent session ID in {transcript_path}")
        return None

    with StateManager() as state:
        # Look up the PARENT session's state (not the subagent's)
        parent_state = state.get_session(parent_session_id)
        if not parent_state:
            logger.debug(f"SubagentStop: no state for parent session {parent_session_id}")
            return None

        session_call_id = parent_state.get("session_call_id")
        trace_id = parent_state.get("trace_id")

        if not session_call_id or not trace_id:
            logger.debug(f"SubagentStop: parent session {parent_session_id} not traced")
            return None

        # Initialize Weave
        weave.init(project)
        client = require_weave_client()

        # Reconstruct parent session call for hierarchy
        parent_session_call = _reconstruct_parent_call(
            client._project_id(),
            session_call_id,
            trace_id,
        )

        # Create the subagent call as a child of the session
        agent_display_name = f"Subagent: {agent_id}"
        if agent_session.turns:
            # Use first turn's user message as display hint
            first_prompt = agent_session.first_user_prompt()
            if first_prompt:
                agent_display_name = f"Subagent: {truncate(first_prompt, 40)}"

        subagent_call = client.create_call(
            op="claude_code.subagent",
            inputs={
                "agent_id": agent_id,
                "turn_count": len(agent_session.turns),
            },
            parent=parent_session_call,
            attributes={
                "agent_id": agent_id,
                "is_sidechain": True,
            },
            display_name=agent_display_name,
            use_stack=False,
        )

        # Log tool calls from all turns in the subagent
        total_tool_calls = 0
        for turn in agent_session.turns:
            for tool_call in turn.all_tool_calls():
                total_tool_calls += 1
                _log_single_tool_call(tool_call, subagent_call)

        # Calculate totals
        total_usage = agent_session.total_usage()

        # Finish the subagent call
        output = {
            "turn_count": len(agent_session.turns),
            "tool_call_count": total_tool_calls,
            "input_tokens": total_usage.input_tokens,
            "output_tokens": total_usage.output_tokens,
        }
        client.finish_call(subagent_call, output=output)

        client.flush()

        logger.debug(
            f"SubagentStop: logged subagent {agent_id} with {len(agent_session.turns)} turns, "
            f"{total_tool_calls} tool calls"
        )
        return None


def _log_single_tool_call(tool_call: "ToolCall", parent_call: Any) -> None:
    """Log a single tool call using weave.log_call."""
    weave.log_call(
        op_name=f"claude_code.tool.{tool_call.name}",
        inputs=tool_call.input or {},
        output={"result": truncate(tool_call.result, 5000) if tool_call.result else None},
        parent=parent_call,
        display_name=tool_call.name,
    )


def handle_session_end(payload: dict[str, Any], project: str) -> dict[str, Any] | None:
    """Handle SessionEnd hook event.

    Finishes the session call with aggregated statistics and cleans up
    the state file. Also handles any interrupted turn that wasn't finished.

    Args:
        payload: Hook payload with session_id, reason
        project: Weave project in "entity/project" format

    Returns:
        None
    """
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")
    reason = payload.get("reason", "unknown")

    if not session_id:
        logger.warning("SessionEnd missing session_id")
        return None

    with StateManager() as state:
        session_data = state.get_session(session_id)
        if not session_data:
            logger.debug(f"SessionEnd: no state for {session_id}")
            return None

        session_call_id = session_data.get("session_call_id")
        trace_id = session_data.get("trace_id")

        if not session_call_id or not trace_id:
            # Session was never actually traced (no prompts submitted)
            state.delete_session(session_id)
            return None

        # Initialize Weave
        weave.init(project)
        client = require_weave_client()

        # Handle any interrupted turn first
        if session_data.get("turn_call_id"):
            _finish_interrupted_turn(session_data, transcript_path, client)

        # Parse transcript for final statistics
        session = None
        if transcript_path:
            session = parse_session_file(Path(transcript_path))

        # Reconstruct session call to finish it
        session_call = _reconstruct_parent_call(
            client._project_id(),
            session_call_id,
            trace_id,
        )

        # Build session output with aggregated stats
        session_output: dict[str, Any] = {
            "turn_count": session_data.get("turn_number", 0),
            "tool_call_count": session_data.get("total_tool_calls", 0),
            "tool_call_breakdown": session_data.get("tool_counts", {}),
            "end_reason": reason,
        }

        if session:
            total_usage = session.total_usage()
            session_output["model"] = session.primary_model()
            session_output["usage"] = total_usage.to_weave_usage()
            session_output["duration_ms"] = session.duration_ms()

        # Parse session for diff view and attach session file
        transcript_file_path = Path(transcript_path) if transcript_path else None
        if transcript_file_path and transcript_file_path.exists():
            if session:
                # Generate session-level diff view showing all file changes
                diff_html = generate_session_diff_html(
                    session,
                    cwd=session.cwd,
                    sessions_dir=transcript_file_path.parent,
                )

                if diff_html:
                    set_call_view(
                        call=session_call,
                        client=client,
                        name="file_changes",
                        content=diff_html,
                        extension="html",
                        mimetype="text/html",
                    )
                    logger.debug("Attached session diff HTML view")

            # Attach session JSONL file as Content object
            try:
                session_content = Content.from_path(
                    transcript_file_path,
                    metadata={
                        "session_id": session_id,
                        "filename": transcript_file_path.name,
                    },
                )
                session_output["file_snapshots"] = {
                    "session.jsonl": session_content,
                }
                logger.debug(f"Attached session file: {transcript_file_path.name}")
            except Exception as e:
                logger.debug(f"Failed to attach session file: {e}")

        # Finish the session call
        client.finish_call(session_call, output=session_output)

        # Clean up state
        state.delete_session(session_id)

        client.flush()
        logger.debug(f"SessionEnd: finished session {session_id}")
        return None
