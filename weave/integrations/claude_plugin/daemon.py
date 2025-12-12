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

from weave.integrations.claude_plugin.session_parser import (
    Session,
    Turn,
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

# Inactivity timeout (10 minutes)
INACTIVITY_TIMEOUT = 600


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

        logger.debug(f"Loaded state: project={self.project}, transcript={self.transcript_path}")
        return True

    def _save_state(self) -> None:
        """Save current state to file."""
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
        """Handle Stop - finish current turn with full data."""
        # Process remaining lines from session file to capture turn data
        await self._process_session_file()

        # Finish current turn if open
        if self.current_turn_call_id:
            await self._finish_current_turn()

        self._save_state()
        return {"status": "ok"}

    async def _handle_subagent_stop(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle SubagentStop - process subagent transcript."""
        transcript_path = payload.get("transcript_path")
        if not transcript_path:
            return {"status": "error", "message": "No transcript_path"}

        # TODO: Implement subagent processing
        logger.debug(f"SubagentStop for {transcript_path}")
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

        # Check for interrupted previous turn
        if self.current_turn_call_id:
            # Previous turn was interrupted - finish it
            await self._finish_current_turn(interrupted=True)

        # Parse user content and images
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

        # Skip if no real content (tool results only)
        if not user_text.strip():
            return

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
        """Finish the current turn call."""
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

        # Parse session file to get turn data
        turn_data = await self._get_current_turn_data()

        output: dict[str, Any] = {}
        if interrupted:
            output["interrupted"] = True

        if turn_data:
            output.update({
                "model": turn_data.get("model"),
                "usage": turn_data.get("usage"),
                "response": turn_data.get("response"),
                "tool_call_count": turn_data.get("tool_call_count", 0),
            })

        self.weave_client.finish_call(turn_call, output=output)
        self.weave_client.flush()

        logger.debug(f"Finished turn {self.turn_number}")
        self.current_turn_call_id = None

    async def _get_current_turn_data(self) -> dict[str, Any] | None:
        """Get data for the current turn from the session file."""
        if not self.transcript_path:
            return None

        # Re-parse session file to get latest turn data
        session = parse_session_file(self.transcript_path)
        if not session or not session.turns:
            return None

        # Get the latest turn (should be current)
        turn = session.turns[-1]
        usage = turn.total_usage()

        # Collect assistant text
        assistant_text = ""
        for msg in turn.assistant_messages:
            text = msg.get_text()
            if text:
                assistant_text += text + "\n"

        return {
            "model": turn.primary_model(),
            "usage": usage.to_weave_usage(),
            "response": truncate(assistant_text.strip()),
            "tool_call_count": len(turn.all_tool_calls()),
        }

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
