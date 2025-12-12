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
from pathlib import Path
from typing import Any

import weave
from weave.trace.call import Call
from weave.trace.context.weave_client_context import require_weave_client

from weave.integrations.claude_plugin.session_parser import (
    Turn,
    parse_session_file,
)
from weave.integrations.claude_plugin.state import (
    StateManager,
    create_session_data,
)
from weave.integrations.claude_plugin.utils import (
    generate_session_name,
    get_tool_display_name,
    truncate,
)

logger = logging.getLogger(__name__)


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


def _build_turn_output(turn: Turn | None, interrupted: bool = False) -> dict[str, Any]:
    """Build the output dict for a turn call.

    Args:
        turn: The turn data (may be None if not found in transcript)
        interrupted: Whether the turn was interrupted by user

    Returns:
        Output dict for the turn call
    """
    output: dict[str, Any] = {}

    if interrupted:
        output["interrupted"] = True

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
    turn = None
    if transcript_path:
        session = parse_session_file(Path(transcript_path))
        if session and session.turns and turn_number <= len(session.turns):
            turn = session.turns[turn_number - 1]

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
    output = _build_turn_output(turn, interrupted=True)
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
            # Parse transcript to get session metadata
            session = None
            if transcript_path:
                session = parse_session_file(Path(transcript_path))

            # Generate session name
            prompt_for_naming = user_prompt or (
                session.first_user_prompt() if session else ""
            )
            display_name, suggested_branch = generate_session_name(prompt_for_naming)

            # Create session call
            session_call = client.create_call(
                op="claude_code.session",
                inputs={
                    "session_id": session_id,
                    "cwd": cwd,
                    "suggested_branch_name": suggested_branch or None,
                    "first_prompt": truncate(prompt_for_naming, 1000),
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
            turn_preview = truncate(user_prompt, 50) or "Turn 1"
            turn_call = client.create_call(
                op="claude_code.turn",
                inputs={
                    "user_message": truncate(user_prompt, 5000),
                },
                parent=session_call,
                attributes={
                    "turn_number": turn_number,
                },
                display_name=f"Turn {turn_number}: {turn_preview}",
                use_stack=False,
            )

            session_data["turn_call_id"] = turn_call.id
            state.save_session(session_id, session_data, cwd=cwd)

            # Flush to ensure calls are sent
            client.flush()

            logger.debug(
                f"UserPromptSubmit: created session {session_call.id} and turn {turn_call.id}"
            )

            # Return trace URL for first turn
            return {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": f"Weave tracing active: {session_call.ui_url}",
                }
            }

        else:
            # Subsequent turn - reconstruct session call as parent
            session_call = _reconstruct_parent_call(
                client._project_id(),
                session_call_id,
                trace_id,
            )

            # Create turn call
            turn_preview = truncate(user_prompt, 50) or f"Turn {turn_number}"
            turn_call = client.create_call(
                op="claude_code.turn",
                inputs={
                    "user_message": truncate(user_prompt, 5000),
                },
                parent=session_call,
                attributes={
                    "turn_number": turn_number,
                },
                display_name=f"Turn {turn_number}: {turn_preview}",
                use_stack=False,
            )

            session_data["turn_call_id"] = turn_call.id
            state.save_session(session_id, session_data, cwd=cwd)

            client.flush()

            logger.debug(f"UserPromptSubmit: created turn {turn_call.id}")
            return None


def handle_stop(payload: dict[str, Any], project: str) -> dict[str, Any] | None:
    """Handle Stop hook event.

    Parses the transcript to get full turn data (tool calls, tokens, response)
    and finishes the current turn call.

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

        # Parse transcript to get current turn data
        turn = None
        turn_number = session_data.get("turn_number", 0)
        if transcript_path:
            session = parse_session_file(Path(transcript_path))
            if session and session.turns and turn_number <= len(session.turns):
                turn = session.turns[turn_number - 1]

        # Reconstruct turn call to finish it
        turn_call = _reconstruct_parent_call(
            client._project_id(),
            turn_call_id,
            trace_id,
        )

        # Log tool calls
        if turn:
            _log_tool_calls(turn, turn_call, session_data)

        # Build and finish turn
        output = _build_turn_output(turn)
        client.finish_call(turn_call, output=output)

        # Clear turn state (but keep session state)
        session_data["turn_call_id"] = None
        state.save_session(session_id, session_data)

        client.flush()

        logger.debug(
            f"Stop: finished turn {turn_number} with {output.get('tool_call_count', 0)} tool calls"
        )
        return None


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

        # Finish the session call
        client.finish_call(session_call, output=session_output)

        # Clean up state
        state.delete_session(session_id)

        client.flush()
        logger.debug(f"SessionEnd: finished session {session_id}")
        return None
