#!/usr/bin/env python3
"""Daemon process for Claude Code Weave tracing.

This daemon:
1. Listens on a Unix socket for hook events
2. Tails the session JSONL file for real-time data
3. Creates Weave traces reactively as content appears
4. Shuts down after inactivity timeout or SessionEnd

Usage:
    python -m weave.integrations.claude_plugin.daemon <session_id>
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

# Setup logging before other imports
DEBUG_LOG_FILE = Path("/tmp/weave-claude-daemon.log")


def setup_logging() -> logging.Logger:
    """Configure logging with optional file output for debugging."""
    level = logging.DEBUG if os.environ.get("DEBUG") else logging.WARNING

    logger = logging.getLogger("weave.integrations.claude_plugin.daemon")
    logger.setLevel(level)
    logger.handlers.clear()

    # Always add stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(stderr_handler)

    # Add file handler in debug mode
    if os.environ.get("DEBUG"):
        try:
            file_handler = logging.FileHandler(DEBUG_LOG_FILE, mode="a")
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
            )
            logger.addHandler(file_handler)
        except Exception:
            pass

    return logger


logger = setup_logging()

# Import after logging setup
import weave
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.view_utils import set_call_view

from weave.integrations.claude_plugin.session_parser import (
    Session,
    Turn,
    is_system_message,
    parse_session_file,
)
from weave.integrations.claude_plugin.socket_client import get_socket_path
from weave.integrations.claude_plugin.state import StateManager
from weave.integrations.claude_plugin.utils import (
    generate_session_name,
    get_tool_display_name,
    truncate,
)
from weave.integrations.claude_plugin.diff_view import generate_turn_diff_html
from dataclasses import dataclass
from datetime import datetime, timezone

# Inactivity timeout (10 minutes)
INACTIVITY_TIMEOUT = 600


@dataclass
class SubagentTracker:
    """Tracks a subagent through its lifecycle: pending -> tailing -> finished."""

    # Set at detection time (Task tool with subagent_type)
    tool_use_id: str
    turn_call_id: str
    detected_at: datetime
    parent_session_id: str

    # Set once file is found and matched
    agent_id: str | None = None
    transcript_path: Path | None = None
    subagent_call_id: str | None = None
    last_processed_line: int = 0

    @property
    def is_tailing(self) -> bool:
        """True if we've found the file and started tailing."""
        return self.subagent_call_id is not None


class WeaveDaemon:
    """Daemon for real-time Weave tracing of Claude Code sessions."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.socket_path = get_socket_path(session_id)
        self.running = False
        self.last_activity = asyncio.get_event_loop().time()

        # State from file
        self.project: str | None = None
        self.transcript_path: Path | None = None
        self.last_processed_line: int = 0

        # Weave state
        self.weave_client: Any = None
        self.session_call_id: str | None = None
        self.trace_id: str | None = None
        self.trace_url: str | None = None
        self.current_turn_call_id: str | None = None
        self.turn_number: int = 0

        # Tracking
        self.total_tool_calls: int = 0
        self.tool_counts: dict[str, int] = {}
        self._current_turn_tool_calls: list[str] = []
        # Track pending subagent Task tool calls: tool_use_id -> turn_call_id
        self._pending_subagent_tasks: dict[str, str] = {}  # Keep for backwards compat

        # NEW: Full lifecycle tracking for proactive subagent tailing
        # Primary index: tool_use_id (known at detection)
        self._subagent_trackers: dict[str, SubagentTracker] = {}
        # Secondary index: agent_id (known once file found, for SubagentStop lookup)
        self._subagent_by_agent_id: dict[str, SubagentTracker] = {}

    async def start(self) -> None:
        """Start the daemon."""
        logger.info(f"Starting daemon for session {self.session_id}")

        # Load state
        if not self._load_state():
            logger.error("Failed to load state, exiting")
            return

        # Initialize Weave
        if self.project:
            weave.init(self.project)
            self.weave_client = require_weave_client()

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown)

        self.running = True

        # Start tasks
        await asyncio.gather(
            self._run_socket_server(),
            self._run_file_tailer(),
            self._run_inactivity_checker(),
        )

    def _load_state(self) -> bool:
        """Load session state from file."""
        with StateManager() as state:
            session_data = state.get_session(self.session_id)
            if not session_data:
                logger.warning(f"No state found for session {self.session_id}")
                return False

            self.project = session_data.get("project")
            transcript_path = session_data.get("transcript_path")
            if transcript_path:
                self.transcript_path = Path(transcript_path)
            self.last_processed_line = session_data.get("last_processed_line", 0)

            # Restore Weave state if session already started
            self.session_call_id = session_data.get("session_call_id")
            self.trace_id = session_data.get("trace_id")
            self.trace_url = session_data.get("trace_url")
            self.turn_number = session_data.get("turn_number", 0)
            self.total_tool_calls = session_data.get("total_tool_calls", 0)
            self.tool_counts = session_data.get("tool_counts", {})

            # Update daemon PID in state
            session_data["daemon_pid"] = os.getpid()
            state.save_session(self.session_id, session_data)

        logger.info(
            f"Loaded state: project={self.project}, "
            f"last_processed_line={self.last_processed_line}, "
            f"turn_number={self.turn_number}, "
            f"session_call_id={self.session_call_id}"
        )
        return True

    def _save_state(self) -> None:
        """Save current state to file."""
        logger.info(
            f"Saving state: last_processed_line={self.last_processed_line}, "
            f"turn_number={self.turn_number}"
        )
        with StateManager() as state:
            session_data = state.get_session(self.session_id) or {}
            session_data.update({
                "session_call_id": self.session_call_id,
                "trace_id": self.trace_id,
                "trace_url": self.trace_url,
                "turn_call_id": self.current_turn_call_id,
                "turn_number": self.turn_number,
                "total_tool_calls": self.total_tool_calls,
                "tool_counts": self.tool_counts,
                "last_processed_line": self.last_processed_line,
                "daemon_pid": os.getpid(),
            })
            state.save_session(self.session_id, session_data)

    def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        logger.info("Shutdown signal received")
        self.running = False

    async def _run_socket_server(self) -> None:
        """Run the Unix socket server."""
        # Remove existing socket
        if self.socket_path.exists():
            self.socket_path.unlink()

        server = await asyncio.start_unix_server(
            self._handle_connection,
            path=str(self.socket_path),
        )

        logger.debug(f"Socket server listening on {self.socket_path}")

        async with server:
            while self.running:
                await asyncio.sleep(0.1)

        # Cleanup
        server.close()
        await server.wait_closed()
        if self.socket_path.exists():
            self.socket_path.unlink()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a socket connection from a hook."""
        self.last_activity = asyncio.get_event_loop().time()

        try:
            data = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not data:
                return

            message = json.loads(data.decode())
            event = message.get("event")
            payload = message.get("payload", {})

            logger.debug(f"Received event: {event}")

            response = await self._handle_event(event, payload)

            writer.write((json.dumps(response) + "\n").encode())
            await writer.drain()

        except asyncio.TimeoutError:
            logger.warning("Connection timeout")
        except Exception as e:
            logger.error(f"Error handling connection: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _handle_event(
        self,
        event: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle a hook event."""
        self.last_activity = asyncio.get_event_loop().time()

        if event == "SessionStart":
            return await self._handle_session_start(payload)
        elif event == "UserPromptSubmit":
            return await self._handle_user_prompt_submit(payload)
        elif event == "Stop":
            return await self._handle_stop(payload)
        elif event == "SubagentStop":
            return await self._handle_subagent_stop(payload)
        elif event == "SessionEnd":
            return await self._handle_session_end(payload)
        else:
            logger.warning(f"Unknown event: {event}")
            return {"status": "error", "message": f"Unknown event: {event}"}

    async def _handle_session_start(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle SessionStart - create session trace if needed."""
        # Update transcript path from payload
        transcript_path = payload.get("transcript_path")
        if transcript_path:
            self.transcript_path = Path(transcript_path)

        # Create session call if not exists
        if not self.session_call_id:
            return await self._create_session_call(payload)

        return {"status": "ok", "trace_url": self.trace_url}

    async def _handle_user_prompt_submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle UserPromptSubmit - ensure session exists, return trace URL."""
        # Create session call if not exists (handles first turn)
        if not self.session_call_id:
            return await self._create_session_call(payload)

        return {"status": "ok", "trace_url": self.trace_url}

    async def _create_session_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create the session-level Weave call."""
        if not self.weave_client:
            return {"status": "error", "message": "Weave not initialized"}

        user_prompt = payload.get("prompt", "")
        cwd = payload.get("cwd")

        # If prompt is empty or system-like (warmup subagent), find real first user prompt
        # This handles the case where Claude fires warmup subagents before the actual user prompt
        if not user_prompt or is_system_message(user_prompt):
            if self.transcript_path and self.transcript_path.exists():
                session = parse_session_file(self.transcript_path)
                if session:
                    real_prompt = session.first_user_prompt()
                    if real_prompt:
                        user_prompt = real_prompt
                        logger.debug(f"Using real first prompt from transcript: {user_prompt[:50]!r}")

        # Generate session name
        display_name, suggested_branch = generate_session_name(user_prompt)

        # Create session call
        session_call = self.weave_client.create_call(
            op="claude_code.session",
            inputs={
                "session_id": self.session_id,
                "cwd": cwd,
                "suggested_branch_name": suggested_branch or None,
                "first_prompt": truncate(user_prompt, 1000),
            },
            attributes={
                "session_id": self.session_id,
                "source": "claude-code-plugin",
            },
            display_name=display_name,
            use_stack=False,
        )

        self.session_call_id = session_call.id
        self.trace_id = session_call.trace_id
        self.trace_url = session_call.ui_url

        # Save state
        self._save_state()

        # Flush to ensure call is sent
        self.weave_client.flush()

        logger.info(f"Created session call: {self.session_call_id}")
        return {"status": "ok", "trace_url": self.trace_url}

    async def _handle_stop(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle Stop - finish current turn with full data.

        In DEBUG mode, also triggers daemon shutdown to pick up code changes.
        """
        # Process remaining lines from session file to capture turn data
        await self._process_session_file()

        # Finish current turn if open
        if self.current_turn_call_id:
            await self._finish_current_turn()

        self._save_state()

        # In DEBUG mode, shutdown after each turn to pick up code changes
        if os.environ.get("DEBUG"):
            logger.info("DEBUG mode: shutting down daemon to reload code")
            self.running = False

        return {"status": "ok"}

    async def _handle_subagent_stop(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle SubagentStop - process subagent transcript and create trace.

        Creates a subagent call as a child of the TURN (not session) with:
        - For simple subagents (single turn): tool calls directly under subagent
        - For complex subagents (multiple turns/user interaction): turn hierarchy preserved
        - Final response captured in output
        """
        # Claude Code sends agent_transcript_path for the subagent's file
        # (transcript_path is the parent session's file)
        transcript_path = payload.get("agent_transcript_path")
        agent_id_from_payload = payload.get("agent_id")
        logger.info(f"SubagentStop: agent_transcript_path={transcript_path}, agent_id={agent_id_from_payload}")

        if not transcript_path:
            logger.warning("SubagentStop: missing agent_transcript_path in payload")
            return {"status": "error", "message": "No agent_transcript_path"}

        # Verify the file exists and log its name
        path = Path(transcript_path)
        logger.info(f"SubagentStop: file exists={path.exists()}, filename={path.name}")

        # Parse the subagent transcript
        agent_session = parse_session_file(path)
        if not agent_session:
            logger.warning(f"SubagentStop: failed to parse {transcript_path}")
            return {"status": "ok"}

        # Log what we parsed to help debug
        logger.info(
            f"SubagentStop: parsed session_id={agent_session.session_id}, "
            f"agent_id={agent_session.agent_id}, "
            f"is_sidechain={agent_session.is_sidechain}, "
            f"turns={len(agent_session.turns)}"
        )
        first_prompt_preview = (agent_session.first_user_prompt() or "")[:100]
        logger.info(f"SubagentStop: first_prompt={first_prompt_preview!r}")

        if not agent_session.turns:
            logger.debug(f"SubagentStop: no turns in {transcript_path}")
            return {"status": "ok"}

        if not self.weave_client or not self.session_call_id:
            return {"status": "error", "message": "No active session"}

        # Build display name: "SubAgent: {prompt}"
        # Use agent_id from payload as fallback (more reliable than parsed)
        agent_id = agent_session.agent_id or agent_id_from_payload or "unknown"
        first_prompt = agent_session.first_user_prompt() or ""
        if first_prompt:
            display_name = f"SubAgent: {truncate(first_prompt, 50)}"
        else:
            display_name = f"SubAgent: {agent_id}"

        from weave.trace.call import Call

        # Determine parent: prefer current turn, fall back to session
        # This attaches the subagent to the turn that spawned it, not the session
        parent_id = self.current_turn_call_id or self.session_call_id
        parent_call = Call(
            _op_name="",
            project_id=self.weave_client._project_id(),
            trace_id=self.trace_id,
            parent_id=self.session_call_id if self.current_turn_call_id else None,
            inputs={},
            id=parent_id,
        )

        # Create subagent call as child of turn (or session if no turn)
        subagent_call = self.weave_client.create_call(
            op="claude_code.subagent",
            inputs={
                "agent_id": agent_id,
                "prompt": truncate(first_prompt, 2000),
            },
            parent=parent_call,
            display_name=display_name,
            attributes={"agent_id": agent_id, "is_sidechain": True},
            use_stack=False,
        )

        # Collect all tool calls and counts
        tool_counts: dict[str, int] = {}

        # Check if this is a "simple" subagent (single turn, no user interaction)
        # Simple subagents get a flat structure: tool calls directly under subagent
        # Complex subagents (multiple turns) preserve the turn hierarchy
        is_simple_subagent = len(agent_session.turns) == 1

        if is_simple_subagent:
            # Flat structure: tool calls directly under subagent
            turn = agent_session.turns[0]
            for tool_call in turn.all_tool_calls():
                tool_name = tool_call.name

                # Sanitize input
                sanitized_input = {}
                for k, v in tool_call.input.items():
                    if isinstance(v, str) and len(v) > 5000:
                        sanitized_input[k] = truncate(v)
                    else:
                        sanitized_input[k] = v

                tool_display = get_tool_display_name(tool_name, tool_call.input)

                weave.log_call(
                    op=f"claude_code.tool.{tool_name}",
                    inputs=sanitized_input,
                    output={"result": truncate(str(tool_call.result), 5000)} if tool_call.result else None,
                    attributes={"tool_name": tool_name},
                    display_name=tool_display,
                    parent=subagent_call,
                    use_stack=False,
                )
                tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
        else:
            # Complex subagent: preserve turn hierarchy
            for turn_idx, turn in enumerate(agent_session.turns, 1):
                turn_prompt = turn.user_message.content if turn.user_message else ""
                turn_preview = truncate(turn_prompt, 50) or f"Turn {turn_idx}"

                # Create turn call as child of subagent
                turn_call = self.weave_client.create_call(
                    op="claude_code.turn",
                    inputs={"user_message": truncate(turn_prompt, 5000)},
                    parent=subagent_call,
                    display_name=f"Turn {turn_idx}: {turn_preview}",
                    attributes={"turn_number": turn_idx},
                    use_stack=False,
                )

                # Log tool calls as children of turn
                for tool_call in turn.all_tool_calls():
                    tool_name = tool_call.name

                    # Sanitize input
                    sanitized_input = {}
                    for k, v in tool_call.input.items():
                        if isinstance(v, str) and len(v) > 5000:
                            sanitized_input[k] = truncate(v)
                        else:
                            sanitized_input[k] = v

                    tool_display = get_tool_display_name(tool_name, tool_call.input)

                    weave.log_call(
                        op=f"claude_code.tool.{tool_name}",
                        inputs=sanitized_input,
                        output={"result": truncate(str(tool_call.result), 5000)} if tool_call.result else None,
                        attributes={"tool_name": tool_name},
                        display_name=tool_display,
                        parent=turn_call,
                        use_stack=False,
                    )
                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

                # Finish turn call with response and usage
                turn_response = None
                if turn.assistant_messages:
                    turn_response = turn.assistant_messages[-1].get_text()

                turn_usage = turn.total_usage()
                self.weave_client.finish_call(
                    turn_call,
                    output={
                        "response": truncate(turn_response, 5000) if turn_response else None,
                        "usage": turn_usage.to_weave_usage() if turn_usage else None,
                        "tool_call_count": len(turn.all_tool_calls()),
                    },
                )

        # Get final assistant output for subagent summary
        final_output = None
        if agent_session.turns:
            last_turn = agent_session.turns[-1]
            if last_turn.assistant_messages:
                final_output = last_turn.assistant_messages[-1].get_text()

        # Aggregate token usage across all turns
        total_usage = agent_session.total_usage()

        # Finish subagent call with aggregated output
        self.weave_client.finish_call(
            subagent_call,
            output={
                "response": truncate(final_output, 10000) if final_output else None,
                "turn_count": len(agent_session.turns),
                "tool_call_count": sum(tool_counts.values()),
                "tool_counts": tool_counts,
                "usage": total_usage.to_weave_usage() if total_usage else None,
            },
        )
        self.weave_client.flush()

        logger.info(f"Created subagent trace: {agent_id} with {sum(tool_counts.values())} tool calls")
        return {"status": "ok"}

    async def _handle_session_end(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle SessionEnd - finish session and shutdown."""
        # Process any remaining data
        await self._process_session_file()

        # Finish any open turn
        if self.current_turn_call_id:
            await self._finish_current_turn()

        # Finish session call
        if self.session_call_id and self.weave_client:
            from weave.trace.call import Call

            session_call = Call(
                _op_name="",
                project_id=self.weave_client._project_id(),
                trace_id=self.trace_id,
                parent_id=None,
                inputs={},
                id=self.session_call_id,
            )

            output = {
                "turn_count": self.turn_number,
                "tool_call_count": self.total_tool_calls,
                "tool_call_breakdown": self.tool_counts,
                "end_reason": payload.get("reason", "unknown"),
            }

            self.weave_client.finish_call(session_call, output=output)
            self.weave_client.flush()

            logger.info(f"Finished session call: {self.session_call_id}")

        # Clean up state
        with StateManager() as state:
            state.delete_session(self.session_id)

        # Trigger shutdown
        self.running = False
        return {"status": "ok"}

    async def _run_file_tailer(self) -> None:
        """Tail the session file for new content."""
        if not self.transcript_path:
            logger.warning("No transcript path, file tailer not starting")
            return

        logger.debug(f"Starting file tailer for {self.transcript_path}")

        while self.running:
            try:
                await self._process_session_file()
            except Exception as e:
                logger.error(f"Error processing session file: {e}")

            await asyncio.sleep(0.5)  # Poll every 500ms

    async def _process_session_file(self) -> None:
        """Process new lines from the session file."""
        if not self.transcript_path or not self.transcript_path.exists():
            return

        try:
            with open(self.transcript_path) as f:
                # Skip already processed lines
                for _ in range(self.last_processed_line):
                    f.readline()

                # Process new lines
                line_num = self.last_processed_line
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    line_num += 1
                    try:
                        obj = json.loads(line)
                        await self._process_session_line(obj, line_num)
                    except json.JSONDecodeError:
                        pass

                self.last_processed_line = line_num

        except Exception as e:
            logger.error(f"Error reading session file: {e}")

    async def _process_session_line(self, obj: dict[str, Any], line_num: int) -> None:
        """Process a single line from the session file."""
        msg_type = obj.get("type")

        if msg_type == "user":
            await self._handle_user_message(obj, line_num)
        elif msg_type == "assistant":
            await self._handle_assistant_message(obj, line_num)

    async def _handle_user_message(self, obj: dict[str, Any], line_num: int) -> None:
        """Handle a user message from the session file - create turn call."""
        if not self.weave_client or not self.session_call_id:
            return

        # Parse user content and images first to check if this is a real prompt
        msg_data = obj.get("message", {})
        content = msg_data.get("content", "")
        user_text = ""
        user_images = []

        if isinstance(content, str):
            user_text = content
        elif isinstance(content, list):
            text_parts = []
            for c in content:
                if c.get("type") == "text":
                    text_parts.append(c.get("text", ""))
                elif c.get("type") == "image":
                    source = c.get("source", {})
                    if source.get("type") == "base64" and source.get("data"):
                        try:
                            from weave.type_wrappers.Content.content import Content
                            image_content = Content.from_base64(
                                source["data"],
                                mimetype=source.get("media_type"),
                            )
                            user_images.append(image_content)
                        except Exception as e:
                            logger.debug(f"Failed to parse image: {e}")
            user_text = "\n".join(text_parts)

        # Skip if no real content (tool results only) - don't trigger interruption check
        if not user_text.strip():
            return

        # Check for interrupted previous turn - only for actual new user prompts
        if self.current_turn_call_id:
            # Previous turn was interrupted - finish it
            await self._finish_current_turn(interrupted=True)

        # Increment turn number
        self.turn_number += 1

        # Create turn call
        from weave.trace.call import Call

        # Reconstruct session call as parent
        session_call = Call(
            _op_name="",
            project_id=self.weave_client._project_id(),
            trace_id=self.trace_id,
            parent_id=None,
            inputs={},
            id=self.session_call_id,
        )

        turn_preview = truncate(user_text, 50) or f"Turn {self.turn_number}"

        # Build inputs with images
        turn_inputs: dict[str, Any] = {
            "user_message": truncate(user_text, 5000),
        }
        if user_images:
            turn_inputs["images"] = user_images
            logger.debug(f"Turn {self.turn_number} has {len(user_images)} images")

        turn_call = self.weave_client.create_call(
            op="claude_code.turn",
            inputs=turn_inputs,
            parent=session_call,
            attributes={
                "turn_number": self.turn_number,
            },
            display_name=f"Turn {self.turn_number}: {turn_preview}",
            use_stack=False,
        )

        self.current_turn_call_id = turn_call.id
        self._current_turn_tool_calls = []

        logger.debug(f"Created turn {self.turn_number}: {turn_call.id}")

    async def _handle_assistant_message(self, obj: dict[str, Any], line_num: int) -> None:
        """Handle an assistant message - create tool calls as children of turn."""
        if not self.weave_client or not self.current_turn_call_id:
            return

        msg_data = obj.get("message", {})
        content = msg_data.get("content", [])

        if not isinstance(content, list):
            return

        # Reconstruct turn call as parent
        from weave.trace.call import Call
        turn_call = Call(
            _op_name="",
            project_id=self.weave_client._project_id(),
            trace_id=self.trace_id,
            parent_id=self.session_call_id,
            inputs={},
            id=self.current_turn_call_id,
        )

        for c in content:
            if c.get("type") == "tool_use":
                tool_name = c.get("name", "unknown")
                tool_input = c.get("input", {})
                tool_id = c.get("id", "")

                # Skip Task tools with subagent_type - they'll be handled by SubagentStop
                # This prevents duplicate logging (once as tool, once as subagent)
                if tool_name == "Task" and tool_input.get("subagent_type"):
                    # Track this for SubagentStop to know which turn to attach to
                    self._pending_subagent_tasks[tool_id] = self.current_turn_call_id
                    logger.debug(f"Skipping Task tool with subagent_type, will be handled by SubagentStop: {tool_id}")
                    continue

                # Sanitize input
                sanitized_input = {}
                for k, v in tool_input.items():
                    if isinstance(v, str) and len(v) > 5000:
                        sanitized_input[k] = truncate(v)
                    else:
                        sanitized_input[k] = v

                tool_display = get_tool_display_name(tool_name, tool_input)

                # Create tool call (we'll finish it when we see the result)
                # For now, log it immediately since we may not see results in order
                weave.log_call(
                    op=f"claude_code.tool.{tool_name}",
                    inputs=sanitized_input,
                    output=None,  # Will be updated when we see tool_result
                    attributes={
                        "tool_name": tool_name,
                        "tool_use_id": tool_id,
                    },
                    display_name=tool_display,
                    parent=turn_call,
                    use_stack=False,
                )

                # Update counts
                self.tool_counts[tool_name] = self.tool_counts.get(tool_name, 0) + 1
                self.total_tool_calls += 1

                logger.debug(f"Created tool call: {tool_name}")

    async def _finish_current_turn(self, interrupted: bool = False) -> None:
        """Finish the current turn call with file snapshots and diff view."""
        if not self.weave_client or not self.current_turn_call_id:
            return

        from weave.trace.call import Call

        turn_call = Call(
            _op_name="",
            project_id=self.weave_client._project_id(),
            trace_id=self.trace_id,
            parent_id=self.session_call_id,
            inputs={},
            id=self.current_turn_call_id,
        )

        # Parse session file to get turn and session data
        session, turn, turn_index = await self._get_current_turn_data()

        output: dict[str, Any] = {}
        if interrupted:
            output["interrupted"] = True
            output["status"] = "[interrupted]"

        if turn:
            usage = turn.total_usage()

            # Collect assistant text
            assistant_text = ""
            for msg in turn.assistant_messages:
                text = msg.get_text()
                if text:
                    assistant_text += text + "\n"

            output.update({
                "model": turn.primary_model(),
                "usage": usage.to_weave_usage(),
                "response": truncate(assistant_text.strip()),
                "tool_call_count": len(turn.all_tool_calls()),
                "duration_ms": turn.duration_ms(),
            })

            # Load file backups as Content objects
            # Only include backups created DURING this turn (by backup_time)
            if turn.file_backups and session:
                from weave.type_wrappers.Content.content import Content
                file_snapshots: dict[str, Content] = {}
                turn_start = turn.started_at()
                # Get next turn's start time as upper bound, or use a far future date
                next_turn_start = None
                if turn_index + 1 < len(session.turns):
                    next_turn_start = session.turns[turn_index + 1].started_at()

                for fb in turn.file_backups:
                    # Filter: only include backups created during this turn's window
                    if fb.backup_time < turn_start:
                        continue  # Backup from before this turn
                    if next_turn_start and fb.backup_time >= next_turn_start:
                        continue  # Backup from a later turn

                    content = fb.load_content(session.session_id)
                    if content:
                        file_snapshots[fb.file_path] = content

                if file_snapshots:
                    output["file_snapshots"] = file_snapshots
                    logger.debug(f"Captured {len(file_snapshots)} file snapshots")

            # Generate diff HTML for summary view
            if session:
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
                    set_call_view(
                        call=turn_call,
                        client=self.weave_client,
                        name="file_changes",
                        content=diff_html,
                        extension="html",
                        mimetype="text/html",
                    )
                    logger.debug("Attached diff HTML view to turn")

        self.weave_client.finish_call(turn_call, output=output)
        self.weave_client.flush()

        logger.debug(f"Finished turn {self.turn_number}")
        self.current_turn_call_id = None

    async def _get_current_turn_data(self) -> tuple[Session | None, Turn | None, int]:
        """Get data for the current turn from the session file.

        Returns:
            Tuple of (session, turn, turn_index) where turn_index is 0-based
        """
        if not self.transcript_path:
            return None, None, 0

        # Re-parse session file to get latest turn data
        session = parse_session_file(self.transcript_path)
        if not session or not session.turns:
            return None, None, 0

        # Get the latest turn (should be current)
        turn_index = len(session.turns) - 1
        turn = session.turns[turn_index]

        return session, turn, turn_index

    async def _run_inactivity_checker(self) -> None:
        """Check for inactivity and shutdown if idle too long."""
        while self.running:
            await asyncio.sleep(60)  # Check every minute

            current_time = asyncio.get_event_loop().time()
            idle_time = current_time - self.last_activity

            if idle_time > INACTIVITY_TIMEOUT:
                logger.info(f"Inactivity timeout ({idle_time:.0f}s), shutting down")
                self.running = False
                break


async def main(session_id: str) -> None:
    """Main entry point."""
    daemon = WeaveDaemon(session_id)
    await daemon.start()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m weave.integrations.claude_plugin.daemon <session_id>")
        sys.exit(1)

    session_id = sys.argv[1]
    asyncio.run(main(session_id))
