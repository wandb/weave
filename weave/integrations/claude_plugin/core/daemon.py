#!/usr/bin/env python3
"""Daemon process for Claude Code Weave tracing.

Note: File backup timestamp filtering was removed in favor of messageId-based
linking from session_parser. See diff_view.py for the same fix.

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
import time
from pathlib import Path
from typing import Any

# Setup logging before other imports
DEBUG_LOG_DIR = Path("/tmp/weave-claude-logs")


def get_debug_log_path(session_id: str) -> Path:
    """Get the debug log file path for a specific session."""
    DEBUG_LOG_DIR.mkdir(parents=True, exist_ok=True)
    return DEBUG_LOG_DIR / f"daemon-{session_id}.log"


def setup_logging(session_id: str | None = None) -> logging.Logger:
    """Configure logging with optional file output for debugging.

    Args:
        session_id: Optional session ID for per-session log files in debug mode.
                   If provided and DEBUG is set, creates a session-specific log file.
    """
    level = logging.DEBUG if os.environ.get("DEBUG") else logging.WARNING

    logger = logging.getLogger("weave.integrations.claude_plugin.daemon")
    logger.setLevel(level)
    logger.handlers.clear()

    # Always add stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(stderr_handler)

    # Add file handler in debug mode with session-specific log file
    if os.environ.get("DEBUG") and session_id:
        try:
            log_path = get_debug_log_path(session_id)
            file_handler = logging.FileHandler(log_path, mode="a")
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
            )
            logger.addHandler(file_handler)

            # Also capture weave.trace warnings/errors (batch processor, future executor)
            # These are critical for debugging session sync issues like validation errors
            weave_trace_handler = logging.FileHandler(log_path, mode="a")
            weave_trace_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
            )
            weave_trace_handler.setLevel(logging.WARNING)  # Only WARNING+ to avoid noise
            logging.getLogger("weave.trace").addHandler(weave_trace_handler)

            # Log the session start marker for easy identification
            logger.info(f"=== Daemon started for session {session_id} ===")
        except Exception:
            pass

    return logger


# Initialize with basic logging (will be reconfigured with session_id in main)
logger = setup_logging()

# Import after logging setup
import weave
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.view_utils import set_call_view

from weave.integrations.claude_plugin.session.session_parser import (
    Session,
    TokenUsage,
    ToolCall,
    Turn,
    is_system_message,
    parse_session_file,
)
from weave.integrations.claude_plugin.core.socket_client import get_socket_path
from weave.integrations.claude_plugin.core.state import StateManager
from weave.integrations.claude_plugin.utils import (
    BufferedToolResult,
    ToolResultBuffer,
    extract_question_from_text,
    generate_session_name,
    get_git_info,
    get_subagent_display_name,
    get_tool_display_name,
    get_turn_display_name,
    truncate,
    sanitize_tool_input,
    reconstruct_call,
    log_tool_call,
    MAX_TOOL_INPUT_LENGTH,
    MAX_TOOL_OUTPUT_LENGTH,
    INACTIVITY_TIMEOUT,
    SUBAGENT_DETECTION_TIMEOUT,
)
from weave.integrations.claude_plugin.views.diff_view import (
    generate_session_diff_html,
    generate_turn_diff_html,
)
try:
    from weave.integrations.claude_plugin.secret_scanner import get_secret_scanner
except ImportError:
    get_secret_scanner = lambda: None  # No-op if secret_scanner not installed
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Compaction message prefix - Claude uses this when context is compacted
COMPACTION_PREFIX = "This session is being continued from a previous conversation"


def is_compaction_message(content: str) -> bool:
    """Check if a message is a context compaction/continuation message."""
    if not content:
        return False
    return content.strip().startswith(COMPACTION_PREFIX)


@dataclass
class SubagentTracker:
    """Tracks a subagent through its lifecycle: pending -> tailing -> finished."""

    # Set at detection time (Task tool with subagent_type)
    tool_use_id: str
    turn_call_id: str
    detected_at: datetime
    parent_session_id: str
    subagent_type: str | None = None  # The subagent type from Task tool input

    # Set once file is found and matched
    agent_id: str | None = None
    transcript_path: Path | None = None
    subagent_call_id: str | None = None
    last_processed_line: int = 0
    logged_tool_ids: set[str] = field(default_factory=set)

    @property
    def is_tailing(self) -> bool:
        """True if we've found the file and started tailing."""
        return self.subagent_call_id is not None


@dataclass
class InlineParentTracker:
    """Tracks PlanMode through its lifecycle.

    PlanMode creates a parent container for subsequent tool calls during planning,
    similar to subagents but without a separate transcript file.
    """

    tool_use_id: str
    parent_turn_call_id: str
    detected_at: datetime
    call_id: str | None = None  # Set when activated (first turn detected)

    @property
    def is_active(self) -> bool:
        """True if the inline parent call has been created."""
        return self.call_id is not None

    @property
    def op_name(self) -> str:
        """The Weave op name for PlanMode."""
        return "claude_code.plan_mode"

    @property
    def display_name(self) -> str:
        """The display name for the Weave call."""
        return "PlanMode"


class WeaveDaemon:
    """Daemon for real-time Weave tracing of Claude Code sessions."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.socket_path = get_socket_path(session_id)
        self.running = False
        self.last_activity = time.monotonic()

        # State from file
        self.project: str | None = None
        self.transcript_path: Path | None = None
        self.last_processed_line: int = 0

        # Weave state
        self.weave_client: Any = None
        self.processor: Any | None = None  # SessionProcessor, initialized when weave starts
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

        # Inline parent tracking (PlanMode only)
        # Only one inline parent can be active at a time
        self._pending_inline_parent: InlineParentTracker | None = None

        # Question tracking for Q&A flows
        # Text-based: stores the question from previous turn's output
        self._pending_question: str | None = None
        # AskUserQuestion tool: maps tool_use_id -> (call_id, questions)
        self._pending_question_calls: dict[str, tuple[str, list[dict[str, Any]]]] = {}

        # Pending tool calls waiting for results: tool_use_id -> (name, inputs, timestamp)
        # Used for real-time tool call logging when tool_result arrives
        self._pending_tool_calls: dict[str, tuple[str, dict[str, Any], datetime]] = {}

        # Buffered tool results for parallel grouping detection
        self._tool_buffer = ToolResultBuffer()

        # Tool calls already logged in real-time (to avoid duplicate logging at turn finish)
        self._logged_tool_call_ids: set[str] = set()

        # Pending Skill tool calls: tool_use_id -> (skill_name, started_at)
        # Used to detect skill expansions and attach them to the Skill call
        self._pending_skill_calls: dict[str, tuple[str, datetime]] = {}

        # Subagent file snapshots to aggregate into parent turn
        # Maps turn_call_id -> list of Content objects
        self._subagent_file_snapshots: dict[str, list[Any]] = {}

        # Compaction tracking - count how many times context was compacted
        self.compaction_count: int = 0

        # Track redacted secrets count
        self._redacted_count: int = 0

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

            # Initialize SessionProcessor
            from weave.integrations.claude_plugin.session.session_processor import SessionProcessor
            self.processor = SessionProcessor(
                client=self.weave_client,
                project=self.project,
                source="plugin",
            )

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
            self.current_turn_call_id = session_data.get("turn_call_id")
            self.turn_number = session_data.get("turn_number", 0)
            self.total_tool_calls = session_data.get("total_tool_calls", 0)
            self.tool_counts = session_data.get("tool_counts", {})

            # Restore pending question for Q&A context tracking
            self._pending_question = session_data.get("pending_question")

            # Restore compaction count
            self.compaction_count = session_data.get("compaction_count", 0)

            # Update daemon PID in state
            session_data["daemon_pid"] = os.getpid()
            state.save_session(self.session_id, session_data)

        logger.info(
            f"Loaded state: project={self.project}, "
            f"last_processed_line={self.last_processed_line}, "
            f"turn_number={self.turn_number}, "
            f"session_call_id={self.session_call_id}, "
            f"current_turn_call_id={self.current_turn_call_id}"
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
                "pending_question": self._pending_question,
                "compaction_count": self.compaction_count,
            })
            state.save_session(self.session_id, session_data)

    def _get_sessions_directory(self) -> Path | None:
        """Get the sessions directory containing transcript files."""
        if not self.transcript_path:
            return None
        return self.transcript_path.parent

    async def _scan_for_subagent_files(self) -> None:
        """Scan for agent-*.jsonl files matching pending subagents."""
        # Get pending (non-tailing) trackers
        pending = [t for t in self._subagent_trackers.values() if not t.is_tailing]
        if not pending:
            return

        sessions_dir = self._get_sessions_directory()
        if not sessions_dir or not sessions_dir.exists():
            return

        # Get earliest detection time for filtering
        earliest = min(t.detected_at for t in pending)

        for agent_file in sessions_dir.glob("agent-*.jsonl"):
            try:
                # Skip files created before any pending subagent
                file_ctime = agent_file.stat().st_ctime
                if file_ctime < earliest.timestamp():
                    continue

                # Parse first few lines to check sessionId
                session = parse_session_file(agent_file)
                if not session:
                    continue

                # Verify sessionId matches our parent session
                if session.session_id != self.session_id:
                    continue

                # Match! Start tailing
                await self._start_tailing_subagent(session, agent_file)

            except Exception as e:
                logger.debug(f"Error checking agent file {agent_file}: {e}")

    async def _start_tailing_subagent(self, session: Session, agent_file: Path) -> None:
        """Create subagent call and start tailing the file."""
        if not self.weave_client:
            return

        # Find the tracker (match by parent session)
        tracker = next(
            (t for t in self._subagent_trackers.values()
             if not t.is_tailing and t.parent_session_id == session.session_id),
            None
        )
        if not tracker:
            logger.debug(f"No pending tracker for subagent file {agent_file}")
            return

        # Update tracker with file info
        tracker.agent_id = session.agent_id
        tracker.transcript_path = agent_file
        self._subagent_by_agent_id[session.agent_id] = tracker

        # Build display name using helper that strips common prefixes
        first_prompt = session.first_user_prompt() or ""
        display_name = get_subagent_display_name(first_prompt, session.agent_id)

        # Determine parent: prefer current turn, fall back to session
        parent_id = tracker.turn_call_id or self.session_call_id
        parent_call = reconstruct_call(
            project_id=self.weave_client._project_id(),
            call_id=parent_id,
            trace_id=self.trace_id,
            parent_id=self.session_call_id if tracker.turn_call_id else None,
        )

        # Create subagent call with ChatView-compatible inputs
        from weave.integrations.claude_plugin.session.session_processor import SessionProcessor
        subagent_call = self.weave_client.create_call(
            op="claude_code.subagent",
            inputs=SessionProcessor.build_subagent_inputs(
                first_prompt, session.agent_id, tracker.subagent_type
            ),
            parent=parent_call,
            display_name=display_name,
            attributes={"agent_id": session.agent_id, "is_sidechain": True},
            use_stack=False,
        )

        tracker.subagent_call_id = subagent_call.id

        logger.info(f"Started tailing subagent {session.agent_id} (type={tracker.subagent_type}): {subagent_call.id}")

        # Process any existing content
        await self._process_subagent_updates(tracker)

    async def _process_subagent_updates(self, tracker: SubagentTracker) -> None:
        """Process new lines in subagent transcript file."""
        if not tracker.transcript_path or not tracker.subagent_call_id:
            return

        if not tracker.transcript_path.exists():
            return

        # Count lines in file
        with open(tracker.transcript_path) as f:
            lines = f.readlines()
        total_lines = len(lines)

        # Skip if no new lines
        if total_lines <= tracker.last_processed_line:
            return

        # Re-parse the full file to get session data
        # (Could be optimized to parse incrementally, but this is simpler)
        session = parse_session_file(tracker.transcript_path)
        if not session:
            return

        # Reconstruct subagent call as parent
        subagent_call = reconstruct_call(
            project_id=self.weave_client._project_id(),
            call_id=tracker.subagent_call_id,
            trace_id=self.trace_id,
            parent_id=tracker.turn_call_id,
        )

        # Log tool calls from all turns
        # For simple subagents (single turn), log flat under subagent
        # Only log tool calls that have results - we may see tool_use before
        # tool_result is written to the file
        for turn in session.turns:
            for tool_call in turn.all_tool_calls():
                # Skip if already logged
                if tool_call.id in tracker.logged_tool_ids:
                    continue

                # Skip if no result yet - we'll log it on the next iteration
                # when the tool_result has been written to the file
                if not tool_call.result:
                    continue

                tracker.logged_tool_ids.add(tool_call.id)

                tool_name = tool_call.name

                log_tool_call(
                    tool_name=tool_name,
                    tool_input=tool_call.input,
                    tool_output=str(tool_call.result) if tool_call.result else None,
                    tool_use_id=tool_call.id,
                    duration_ms=tool_call.duration_ms(),
                    parent=subagent_call,
                )

        tracker.last_processed_line = total_lines
        logger.debug(f"Processed subagent {tracker.agent_id} up to line {total_lines}")

    def _cleanup_stale_subagent_trackers(self) -> None:
        """Clean up trackers for subagents whose files never appeared."""
        now = datetime.now(timezone.utc)
        stale_tool_ids = [
            tracker.tool_use_id
            for tracker in self._subagent_trackers.values()
            if not tracker.is_tailing
            and (now - tracker.detected_at).total_seconds() > SUBAGENT_DETECTION_TIMEOUT
        ]

        for tool_id in stale_tool_ids:
            tracker = self._subagent_trackers.pop(tool_id, None)
            if tracker:
                logger.warning(
                    f"Subagent file not found after {SUBAGENT_DETECTION_TIMEOUT}s: "
                    f"tool_id={tool_id}"
                )

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
        self.last_activity = time.monotonic()

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
        self.last_activity = time.monotonic()

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
        elif event == "Feedback":
            return await self._handle_feedback(payload)
        else:
            logger.warning(f"Unknown event: {event}")
            return {"status": "error", "message": f"Unknown event: {event}"}

    async def _handle_session_start(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle SessionStart - initialize state but don't create session call yet.

        Session call is created on UserPromptSubmit when the actual user prompt
        is available in the payload. Creating it here would result in empty
        first_prompt since no user message exists at SessionStart time.
        """
        # Update transcript path from payload
        transcript_path = payload.get("transcript_path")
        if transcript_path:
            self.transcript_path = Path(transcript_path)

        # Don't create session call here - wait for UserPromptSubmit
        # which has the actual user prompt in the payload
        return {"status": "ok", "trace_url": self.trace_url, "session_id": self.session_id}

    async def _handle_user_prompt_submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle UserPromptSubmit - ensure session exists, return trace URL.

        Detects session continuation (when session_ended is True) and creates
        a new trace with "Continued: " prefix instead of appending to the
        finished session.
        """
        # Check if this is a continuation of a previously ended session
        if self.session_call_id:
            is_continuation = await self._check_session_continuation()
            if is_continuation:
                logger.info(f"Detected session continuation for {self.session_id}")
                return await self._create_continuation_session_call(payload)
            # Session exists and isn't a continuation - continue normally
            return {"status": "ok", "trace_url": self.trace_url, "session_id": self.session_id}

        # No session call yet - create a fresh one
        return await self._create_session_call(payload)

    async def _check_session_continuation(self) -> bool:
        """Check if this session is being continued after previously ending.

        Detection approaches (in order):
        1. State-based: Check if session_ended flag is True
        2. API-based fallback: Query Weave API to check if call has ended_at set

        Returns:
            True if session was previously ended and is being continued
        """
        # Primary detection: check session_ended flag in state
        with StateManager() as state:
            session_data = state.get_session(self.session_id)
            if session_data and session_data.get("session_ended"):
                logger.debug("Continuation detected via session_ended flag")
                return True

        # Fallback: Query Weave API to check if session call is finished
        # This handles edge cases where state might be out of sync
        if self.session_call_id and self.weave_client:
            try:
                call = self.weave_client.get_call(
                    self.session_call_id,
                    columns=["ended_at"],
                )
                if call.ended_at is not None:
                    logger.debug("Continuation detected via API (ended_at set)")
                    return True
            except Exception as e:
                logger.debug(f"Could not query session call status: {e}")

        return False

    async def _create_continuation_session_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new session call for a continued session.

        Creates a new trace with "Continued: " prefix and links to the
        original session via continuation_of attribute. The display name
        is generated from the new user prompt, not the original session.
        """
        if not self.weave_client or not self.processor:
            return {"status": "error", "message": "Weave not initialized"}

        user_prompt = payload.get("prompt", "")
        cwd = payload.get("cwd")
        previous_call_id = self.session_call_id
        git_branch: str | None = None
        claude_code_version: str | None = None

        # Get continuation count from state
        with StateManager() as state:
            session_data = state.get_session(self.session_id) or {}
            continuation_count = session_data.get("continuation_count", 0)

        # Parse session file to get metadata and real prompt if needed
        if self.transcript_path and self.transcript_path.exists():
            session = parse_session_file(self.transcript_path)
            if session:
                # Extract metadata from session
                git_branch = session.git_branch
                claude_code_version = session.version

                # If prompt is empty or system-like, use real first prompt
                if not user_prompt or is_system_message(user_prompt):
                    real_prompt = session.first_user_prompt()
                    if real_prompt:
                        user_prompt = real_prompt

        # Generate display name from the continuation's first prompt
        from weave.integrations.claude_plugin.utils import generate_session_name
        base_name, _ = generate_session_name(user_prompt)
        continuation_display_name = f"Continued: {base_name}"

        # Increment continuation count
        continuation_count += 1

        # Create new session call with continuation naming
        session_call, display_name = self.processor.create_session_call(
            session_id=self.session_id,
            first_prompt=user_prompt,
            cwd=cwd,
            display_name=continuation_display_name,
            continuation_of=previous_call_id,
            git_branch=git_branch,
            claude_code_version=claude_code_version,
        )

        # Reset daemon state for the new session
        self.session_call_id = session_call.id
        self.trace_id = session_call.trace_id
        self.trace_url = session_call.ui_url
        self.current_turn_call_id = None
        self.turn_number = 0
        self.total_tool_calls = 0
        self.tool_counts = {}
        self._current_turn_tool_calls = []
        self._pending_question = None
        self.compaction_count = 0
        self._redacted_count = 0

        # Update state with new session info and clear session_ended
        with StateManager() as state:
            session_data = state.get_session(self.session_id) or {}
            session_data.update({
                "session_call_id": self.session_call_id,
                "trace_id": self.trace_id,
                "trace_url": self.trace_url,
                "turn_call_id": None,
                "turn_number": 0,
                "total_tool_calls": 0,
                "tool_counts": {},
                "session_ended": False,  # Clear the ended flag
                "continuation_count": continuation_count,
                "pending_question": None,
                "compaction_count": 0,
            })
            state.save_session(self.session_id, session_data)

        # Flush to ensure call is sent
        self.weave_client.flush()

        logger.info(f"Created continuation session call: {self.session_call_id} (continuation #{continuation_count})")
        return {"status": "ok", "trace_url": self.trace_url, "session_id": self.session_id}

    async def _create_session_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create the session-level Weave call using SessionProcessor."""
        if not self.weave_client or not self.processor:
            return {"status": "error", "message": "Weave not initialized"}

        user_prompt = payload.get("prompt", "")
        cwd = payload.get("cwd")
        git_branch: str | None = None
        claude_code_version: str | None = None

        # Parse session file to get metadata and real prompt if needed
        if self.transcript_path and self.transcript_path.exists():
            session = parse_session_file(self.transcript_path)
            if session:
                # Extract metadata from session
                git_branch = session.git_branch
                claude_code_version = session.version

                # If prompt is empty or system-like (warmup subagent), use real first prompt
                if not user_prompt or is_system_message(user_prompt):
                    real_prompt = session.first_user_prompt()
                    if real_prompt:
                        user_prompt = real_prompt
                        logger.debug(f"Using real first prompt from transcript: {user_prompt[:50]!r}")

        # Use SessionProcessor to create session call
        session_call, _ = self.processor.create_session_call(
            session_id=self.session_id,
            first_prompt=user_prompt,
            cwd=cwd,
            git_branch=git_branch,
            claude_code_version=claude_code_version,
        )

        self.session_call_id = session_call.id
        self.trace_id = session_call.trace_id
        self.trace_url = session_call.ui_url

        # Save state
        self._save_state()

        # Flush to ensure call is sent
        self.weave_client.flush()

        logger.info(f"Created session call: {self.session_call_id}")
        return {"status": "ok", "trace_url": self.trace_url, "session_id": self.session_id}

    async def _handle_stop(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle Stop - finish current turn with full data.

        In DEBUG mode, also triggers daemon shutdown to pick up code changes.
        """
        # Process remaining lines from session file to capture turn data
        await self._process_session_file()

        # Flush all remaining buffered tool results before finishing turn
        # force=True ensures we don't wait for aging - log everything now
        self._flush_buffered_tool_results(force=True)

        # Note: PlanMode inline parents are finished by ExitPlanMode, not Stop

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
        """Handle SubagentStop - finish existing call or fall back to full processing.

        Uses fast path if we're already tailing the subagent, otherwise falls back
        to the original behavior of processing the entire file at once.
        """
        agent_id_from_payload = payload.get("agent_id")
        transcript_path = payload.get("agent_transcript_path")

        logger.info(f"SubagentStop: agent_id={agent_id_from_payload}, transcript={transcript_path}")

        # Check if we're already tailing this subagent (FAST PATH)
        tracker = self._subagent_by_agent_id.get(agent_id_from_payload)

        if tracker and tracker.is_tailing:
            logger.info(f"SubagentStop: fast path for tailed subagent {agent_id_from_payload}")

            # Process any remaining content
            await self._process_subagent_updates(tracker)

            # Finish the subagent call
            subagent_call = reconstruct_call(
                project_id=self.weave_client._project_id(),
                call_id=tracker.subagent_call_id,
                trace_id=self.trace_id,
                parent_id=tracker.turn_call_id,
            )

            # Parse file for final output
            session = parse_session_file(tracker.transcript_path)
            total_usage = None
            tool_counts: dict[str, int] = {}

            # Collect file snapshots from all subagent turns (list format)
            file_snapshots: list[Any] = []

            if session:
                # Aggregate usage and tool counts
                total_usage = session.total_usage()
                for turn in session.turns:
                    for tc in turn.all_tool_calls():
                        tool_counts[tc.name] = tool_counts.get(tc.name, 0) + 1

                # Load file backups from all turns
                for turn in session.turns:
                    for fb in turn.file_backups:
                        content = fb.load_content(session.session_id)
                        if content:
                            file_snapshots.append(content)

            # Build output in Message format using shared helper
            from weave.integrations.claude_plugin.session.session_processor import SessionProcessor
            output = SessionProcessor.build_subagent_output(session)

            if file_snapshots:
                output["file_snapshots"] = file_snapshots
                logger.debug(f"Subagent captured {len(file_snapshots)} file snapshots")

                # Store file snapshots for parent turn aggregation
                turn_call_id = tracker.turn_call_id
                if turn_call_id not in self._subagent_file_snapshots:
                    self._subagent_file_snapshots[turn_call_id] = []
                self._subagent_file_snapshots[turn_call_id].extend(file_snapshots)
                logger.debug(f"Stored {len(file_snapshots)} file snapshots for parent turn {turn_call_id}")

            # Build summary (metadata)
            model = session.primary_model() if session else None
            subagent_call.summary = {
                "turn_count": len(session.turns) if session else 0,
                "tool_call_count": sum(tool_counts.values()),
                "tool_counts": tool_counts,
                "model": model,
            }
            if model and total_usage:
                subagent_call.summary["usage"] = {model: total_usage.to_weave_usage()}

            self.weave_client.finish_call(
                subagent_call,
                output=output,
            )
            self.weave_client.flush()

            # Cleanup trackers
            if tracker.tool_use_id in self._subagent_trackers:
                del self._subagent_trackers[tracker.tool_use_id]
            if agent_id_from_payload in self._subagent_by_agent_id:
                del self._subagent_by_agent_id[agent_id_from_payload]

            logger.info(f"SubagentStop: finished tailed subagent {agent_id_from_payload}")
            return {"status": "ok"}

        # FALLBACK PATH: Not tailing, use original behavior
        logger.info(f"SubagentStop: fallback path for {agent_id_from_payload} (not tailed)")

        # Clean up any orphaned tracker
        if tracker and tracker.tool_use_id in self._subagent_trackers:
            del self._subagent_trackers[tracker.tool_use_id]

        # Original implementation continues below...
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

        # Build display name using helper that strips common prefixes
        # Use agent_id from payload as fallback (more reliable than parsed)
        agent_id = agent_session.agent_id or agent_id_from_payload or "unknown"
        first_prompt = agent_session.first_user_prompt() or ""
        display_name = get_subagent_display_name(first_prompt, agent_id)

        # Determine parent: prefer current turn, fall back to session
        # This attaches the subagent to the turn that spawned it, not the session
        parent_id = self.current_turn_call_id or self.session_call_id
        parent_call = reconstruct_call(
            project_id=self.weave_client._project_id(),
            call_id=parent_id,
            trace_id=self.trace_id,
            parent_id=self.session_call_id if self.current_turn_call_id else None,
        )

        # Create subagent call with ChatView-compatible inputs
        # Use tracker's subagent_type if available (from when Task tool was detected)
        from weave.integrations.claude_plugin.session.session_processor import SessionProcessor
        subagent_type = tracker.subagent_type if tracker else None
        subagent_call = self.weave_client.create_call(
            op="claude_code.subagent",
            inputs=SessionProcessor.build_subagent_inputs(first_prompt, agent_id, subagent_type),
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

                log_tool_call(
                    tool_name=tool_name,
                    tool_input=tool_call.input,
                    tool_output=str(tool_call.result) if tool_call.result else None,
                    tool_use_id=tool_call.id,
                    duration_ms=tool_call.duration_ms(),
                    parent=subagent_call,
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

                    log_tool_call(
                        tool_name=tool_name,
                        tool_input=tool_call.input,
                        tool_output=str(tool_call.result) if tool_call.result else None,
                        tool_use_id=tool_call.id,
                        duration_ms=tool_call.duration_ms(),
                        parent=turn_call,
                    )
                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

                # Finish turn call with response
                turn_response = None
                if turn.assistant_messages:
                    turn_response = turn.assistant_messages[-1].get_text()

                turn_usage = turn.total_usage()
                turn_model = turn.primary_model()

                # Set summary (metadata)
                turn_call.summary = {
                    "model": turn_model,
                    "tool_call_count": len(turn.all_tool_calls()),
                }
                if turn_model and turn_usage:
                    turn_call.summary["usage"] = {turn_model: turn_usage.to_weave_usage()}

                self.weave_client.finish_call(
                    turn_call,
                    output={
                        "response": truncate(turn_response, 5000) if turn_response else None,
                    },
                )

        # Aggregate token usage across all turns
        total_usage = agent_session.total_usage()

        # Collect file snapshots from all subagent turns (list format)
        file_snapshots: list[Any] = []
        for turn in agent_session.turns:
            for fb in turn.file_backups:
                content = fb.load_content(agent_session.session_id)
                if content:
                    file_snapshots.append(content)

        # Build output in Message format using shared helper
        subagent_output = SessionProcessor.build_subagent_output(agent_session)

        if file_snapshots:
            subagent_output["file_snapshots"] = file_snapshots
            logger.debug(f"Subagent captured {len(file_snapshots)} file snapshots")

        # Build summary (metadata)
        model = agent_session.primary_model()
        subagent_call.summary = {
            "turn_count": len(agent_session.turns),
            "tool_call_count": sum(tool_counts.values()),
            "tool_counts": tool_counts,
            "model": model,
        }
        if model and total_usage:
            subagent_call.summary["usage"] = {model: total_usage.to_weave_usage()}

        # Finish subagent call with aggregated output
        self.weave_client.finish_call(
            subagent_call,
            output=subagent_output,
        )
        self.weave_client.flush()

        logger.info(f"Created subagent trace: {agent_id} with {sum(tool_counts.values())} tool calls")
        return {"status": "ok"}

    async def _handle_session_end(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle SessionEnd - finish session and shutdown."""
        # Process any remaining data
        await self._process_session_file()

        # Finish any active inline parent
        if self._pending_inline_parent and self._pending_inline_parent.is_active:
            await self._finish_inline_parent()

        # Finish any open turn
        if self.current_turn_call_id:
            await self._finish_current_turn()

        # Finish session call
        if self.session_call_id and self.weave_client:
            session_call = reconstruct_call(
                project_id=self.weave_client._project_id(),
                call_id=self.session_call_id,
                trace_id=self.trace_id,
                parent_id=None,
            )

            # Build session output (for Content objects like file_snapshots)
            session_output: dict[str, Any] = {}

            # Build session summary with aggregated stats
            session_summary: dict[str, Any] = {
                "turn_count": self.turn_number,
                "tool_call_count": self.total_tool_calls,
                "tool_call_breakdown": self.tool_counts,
                "end_reason": payload.get("reason", "unknown"),
            }

            # Include compaction count if any compactions occurred
            if self.compaction_count > 0:
                session_summary["compaction_count"] = self.compaction_count

            # Parse session for additional data and diff view
            diff_html: str | None = None  # Will be set if session has file changes
            if self.transcript_path and self.transcript_path.exists():
                session = parse_session_file(self.transcript_path)
                if session:
                    # Add aggregated usage from session
                    total_usage = session.total_usage()
                    model_name = session.primary_model()
                    session_summary["model"] = model_name
                    # Usage in summary must be model-keyed for Weave schema
                    if model_name and total_usage:
                        session_summary["usage"] = {
                            model_name: total_usage.to_weave_usage()
                        }
                    session_summary["duration_ms"] = session.duration_ms()

                    # Get cwd from session for resolving relative paths
                    cwd = session.cwd
                    # Get sessions directory for finding subagent files
                    sessions_dir = self.transcript_path.parent

                    # Generate session-level diff view showing all file changes
                    # NOTE: Defer set_call_view until after session_call.summary is assigned
                    # to avoid the summary assignment overwriting the views
                    diff_html = generate_session_diff_html(
                        session,
                        cwd=cwd,
                        sessions_dir=sessions_dir,
                        project=self.project,
                        first_prompt=session.first_user_prompt(),
                    )
                    if diff_html:
                        logger.debug("Generated session diff HTML view (will attach after summary assignment)")
                    else:
                        logger.debug("No session diff HTML generated (no file changes)")

                # Capture git info for teleport feature
                if session and session.cwd:
                    git_info = get_git_info(session.cwd)
                    if git_info:
                        session_summary["git"] = git_info
                        logger.debug(f"Attached git info: branch={git_info.get('branch')}")

                # Collect file snapshots with secret scanning (using SessionProcessor helper)
                # Includes: session.jsonl + all modified/created files
                if session and self.processor:
                    scanner = get_secret_scanner()
                    file_snapshots_list, redaction_count = self.processor.collect_session_file_snapshots_with_scanner(
                        session=session,
                        sessions_dir=sessions_dir,
                        secret_scanner=scanner,
                    )
                    self._redacted_count += redaction_count
                    if file_snapshots_list:
                        session_output["file_snapshots"] = file_snapshots_list
                        logger.debug(f"Attached {len(file_snapshots_list)} file snapshots to output")

            # Include redacted_secrets count if any secrets were redacted
            if self._redacted_count > 0:
                session_summary["redacted_secrets"] = self._redacted_count

            # Set summary on call object before finishing (finish_call deep-merges call.summary)
            session_call.summary = session_summary

            # Attach HTML view AFTER summary assignment to avoid being overwritten
            if diff_html:
                set_call_view(
                    call=session_call,
                    client=self.weave_client,
                    name="file_changes",
                    content=diff_html,
                    extension="html",
                    mimetype="text/html",
                )
                logger.debug("Attached session diff HTML view to summary.weave.views")

            logger.debug(f"Calling finish_call for session {self.session_call_id}")
            logger.debug(f"Session output keys: {list(session_output.keys())}")
            logger.debug(f"Session summary keys: {list(session_summary.keys())}")
            self.weave_client.finish_call(session_call, output=session_output)
            logger.debug("finish_call completed, calling flush")

            # Log pending jobs before flush
            if hasattr(self.weave_client, '_get_pending_jobs'):
                jobs = self.weave_client._get_pending_jobs()
                logger.debug(f"Pending jobs before flush: {jobs}")

            self.weave_client.flush()

            # Log pending jobs after flush
            if hasattr(self.weave_client, '_get_pending_jobs'):
                jobs = self.weave_client._get_pending_jobs()
                logger.debug(f"Pending jobs after flush: {jobs}")

            logger.info(f"Finished session call: {self.session_call_id}")

        # Update state timestamp (cleanup happens automatically after RETENTION_DAYS)
        # Don't delete state here - session may be resumed with --continue
        with StateManager() as state:
            session_data = state.get_session(self.session_id)
            if session_data:
                session_data["session_ended"] = True
                state.save_session(self.session_id, session_data)

        # Trigger shutdown
        self.running = False
        return {"status": "ok"}

    async def _handle_feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle Feedback - add reaction/note to session call."""
        if not self.weave_client or not self.session_call_id:
            return {"status": "error", "message": "No active session"}

        emoji = payload.get("emoji")
        note = payload.get("note")

        try:
            # Get the session call
            session_call = self.weave_client.get_call(self.session_call_id)

            # Add reaction
            if emoji:
                session_call.feedback.add_reaction(emoji, creator="user")

            # Add note if provided
            if note:
                session_call.feedback.add_note(note, creator="user")

            logger.info(f"Added feedback to session: emoji={emoji}, has_note={bool(note)}")
            return {"status": "ok"}

        except Exception as e:
            logger.error(f"Failed to add feedback: {e}")
            return {"status": "error", "message": str(e)}

    async def _run_file_tailer(self) -> None:
        """Tail the session file for new content."""
        if not self.transcript_path:
            logger.warning("No transcript path, file tailer not starting")
            return

        logger.debug(f"Starting file tailer for {self.transcript_path}")

        while self.running:
            try:
                # Process parent session transcript
                await self._process_session_file()

                # Scan for subagent files (only if pending trackers)
                await self._scan_for_subagent_files()

                # Process updates for all tailing subagents
                for tracker in list(self._subagent_trackers.values()):
                    if tracker.is_tailing:
                        await self._process_subagent_updates(tracker)

                # Clean up stale trackers (file never appeared)
                self._cleanup_stale_subagent_trackers()

                # Flush aged buffered tool results with parallel grouping
                # This provides real-time feedback while allowing parallel detection
                self._flush_buffered_tool_results()

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

                # Process new lines - count ALL lines (including empty) to match skip logic
                old_line_num = self.last_processed_line
                line_num = self.last_processed_line
                for line in f:
                    line_num += 1  # Count every physical line to match f.readline() skip
                    line = line.strip()
                    if not line:
                        continue  # Skip processing but line was counted

                    try:
                        obj = json.loads(line)
                        await self._process_session_line(obj, line_num)
                    except json.JSONDecodeError:
                        pass

                self.last_processed_line = line_num

                # Save state after processing to prevent duplicate calls on restart
                if line_num > old_line_num:
                    self._save_state()

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

        # Parse message timestamp for tool result duration calculation
        from weave.integrations.claude_plugin.session.session_parser import parse_timestamp
        msg_timestamp_str = obj.get("timestamp")
        msg_timestamp = (
            parse_timestamp(msg_timestamp_str)
            if msg_timestamp_str
            else datetime.now(timezone.utc)
        )

        # Parse user content and images first to check if this is a real prompt
        msg_data = obj.get("message", {})
        content = msg_data.get("content", "")
        user_text = ""
        user_images = []

        if isinstance(content, str):
            user_text = content
        elif isinstance(content, list):
            text_parts = []
            # Collect tool results for batched logging with parallel grouping
            pending_tool_results: list[tuple[str, dict[str, Any]]] = []
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
                elif c.get("type") == "tool_result":
                    tool_use_id = c.get("tool_use_id", "")
                    # Handle AskUserQuestion results
                    if tool_use_id in self._pending_question_calls:
                        await self._finish_question_call(tool_use_id, c)
                    # Buffer tool results for grouped logging
                    # We buffer instead of logging immediately to allow parallel grouping:
                    # - Claude sends each tool_result in separate user messages
                    # - By buffering, we can group tools with close timestamps
                    # - Aged results (> 1s) are flushed with parallel grouping
                    elif tool_use_id in self._pending_tool_calls:
                        tool_name, tool_input, tool_timestamp = self._pending_tool_calls[tool_use_id]

                        # Extract result content
                        result_content = c.get("content", "")
                        if isinstance(result_content, list):
                            text_parts = []
                            for item in result_content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    text_parts.append(item.get("text", ""))
                            result_content = "\n".join(text_parts)

                        # Check if this is an error result
                        is_error = c.get("is_error", False)

                        # Buffer for grouped logging
                        # msg_timestamp is when the tool_result was received (user message)
                        # tool_timestamp is when the tool_use was sent (assistant message)
                        self._tool_buffer.add(
                            tool_use_id=tool_use_id,
                            name=tool_name,
                            input=tool_input,
                            timestamp=tool_timestamp,
                            result=result_content,
                            result_timestamp=msg_timestamp,
                            is_error=is_error,
                        )
                        del self._pending_tool_calls[tool_use_id]
            user_text = "\n".join(text_parts)

        # Skip if no real content (tool results only) - don't trigger interruption check
        if not user_text.strip():
            return

        # Skip system-generated messages (Caveat:, XML tags, etc.)
        if is_system_message(user_text):
            return

        # Check for skill expansion - don't create new turn for these
        # Skill expansions start with "Base directory for this skill:"
        if self._pending_skill_calls and user_text.strip().startswith("Base directory for this skill:"):
            await self._handle_skill_expansion(user_text)
            return

        # Check for pending PlanMode that needs activation
        # The first user message after detecting EnterPlanMode is the plan's "first turn"
        if self._pending_inline_parent and not self._pending_inline_parent.is_active:
            # This user message is the inline parent's first turn - activate it
            await self._activate_inline_parent(user_text)
            return  # Don't create a new turn, the inline parent is now active

        # Check for interrupted previous turn - only for actual new user prompts
        if self.current_turn_call_id:
            # If there's an active inline parent, finish it first (interrupted)
            if self._pending_inline_parent and self._pending_inline_parent.is_active:
                await self._finish_inline_parent(output={"interrupted": True})

            # Previous turn was interrupted - finish it
            await self._finish_current_turn(interrupted=True)

        # Increment turn number
        self.turn_number += 1

        # Check for compaction (context continuation)
        is_compacted = is_compaction_message(user_text)
        if is_compacted:
            self.compaction_count += 1
            logger.debug(f"Detected compaction event #{self.compaction_count}")

        # Log images if present (for debugging)
        if user_images:
            logger.debug(f"Turn {self.turn_number} has {len(user_images)} images")

        # Get pending question from previous turn for Q&A context
        pending_question = self._pending_question
        if pending_question:
            logger.debug(f"Added question context: {pending_question[:50]}...")
            self._pending_question = None  # Clear after using

        # Reconstruct session call as parent
        session_call = reconstruct_call(
            project_id=self.weave_client._project_id(),
            call_id=self.session_call_id,
            trace_id=self.trace_id,
            parent_id=None,
        )

        # Use SessionProcessor to create turn call
        turn_call = self.processor.create_turn_call(
            parent=session_call,
            turn_number=self.turn_number,
            user_message=user_text,
            pending_question=pending_question,
            images=user_images if user_images else None,
            is_compacted=is_compacted,
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

        # Get the actual message timestamp from JSONL (not poll time)
        # This is critical for parallel tool detection - poll timing can exceed
        # the 1000ms threshold even for truly parallel calls
        from weave.integrations.claude_plugin.session.session_parser import parse_timestamp
        msg_timestamp_str = obj.get("timestamp")
        msg_timestamp = (
            parse_timestamp(msg_timestamp_str)
            if msg_timestamp_str
            else datetime.now(timezone.utc)
        )

        # Reconstruct turn call as parent
        turn_call = reconstruct_call(
            project_id=self.weave_client._project_id(),
            call_id=self.current_turn_call_id,
            trace_id=self.trace_id,
            parent_id=self.session_call_id,
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

                    # NEW: Create full lifecycle tracker for proactive tailing
                    tracker = SubagentTracker(
                        tool_use_id=tool_id,
                        turn_call_id=self.current_turn_call_id,
                        detected_at=datetime.now(timezone.utc),
                        parent_session_id=self.session_id,
                        subagent_type=tool_input.get("subagent_type"),
                    )
                    self._subagent_trackers[tool_id] = tracker

                    logger.debug(f"Subagent detected: tool_id={tool_id}, type={tracker.subagent_type}, will scan for file")
                    continue

                # Handle EnterPlanMode tool - creates inline parent container
                if tool_name == "EnterPlanMode":
                    self._pending_inline_parent = InlineParentTracker(
                        tool_use_id=tool_id,
                        parent_turn_call_id=self.current_turn_call_id,
                        detected_at=datetime.now(timezone.utc),
                    )
                    logger.debug("EnterPlanMode detected, waiting for first turn")
                    continue

                # Handle ExitPlanMode tool - finishes plan mode inline parent
                if tool_name == "ExitPlanMode":
                    if self._pending_inline_parent and self._pending_inline_parent.is_active:
                        # Capture plan from ExitPlanMode input for output
                        plan = tool_input.get("plan")
                        await self._finish_inline_parent(
                            output={"plan": plan} if plan else {}
                        )
                        logger.debug("ExitPlanMode: finished plan mode inline parent")
                    continue

                # Handle Skill tool - track for skill expansion detection
                if tool_name == "Skill":
                    skill = tool_input.get("skill", "unknown")
                    self._pending_skill_calls[tool_id] = (skill, datetime.now(timezone.utc))
                    logger.debug(f"Skill tool detected: {skill} ({tool_id})")
                    # Don't track as pending tool call - handled specially
                    continue

                # Handle SlashCommand tool - similar to Skill
                if tool_name == "SlashCommand":
                    command = tool_input.get("command", "unknown")
                    # Track as skill expansion (slash commands expand similarly)
                    self._pending_skill_calls[tool_id] = (command, datetime.now(timezone.utc))
                    logger.debug(f"SlashCommand tool detected: {command} ({tool_id})")
                    continue

                # Handle AskUserQuestion tool - creates Q&A sub-call
                if tool_name == "AskUserQuestion":
                    questions = tool_input.get("questions", [])
                    if questions:
                        # Extract question text for display
                        question_texts = []
                        for q in questions:
                            q_text = q.get("question", "")
                            if q_text:
                                question_texts.append(q_text)

                        display_name = question_texts[0][:50] if question_texts else "Question"
                        if len(question_texts) > 1:
                            display_name += f" (+{len(question_texts) - 1} more)"

                        # Create question call as child of current turn
                        question_call = self.weave_client.create_call(
                            op="claude_code.question",
                            inputs={"questions": questions},
                            parent=turn_call,
                            display_name=f"Q: {display_name}",
                            use_stack=False,
                        )

                        # Track for later completion when tool_result arrives
                        self._pending_question_calls[tool_id] = (
                            question_call.id,
                            questions,
                        )
                        logger.debug(f"Created question call for {len(questions)} questions")
                    continue

                # Track pending tool call with full info for real-time logging
                # when the tool_result arrives in a subsequent user message
                # Use actual message timestamp (not poll time) for parallel detection
                self._pending_tool_calls[tool_id] = (
                    tool_name,
                    tool_input,
                    msg_timestamp,
                )
                self._current_turn_tool_calls.append(tool_id)

                logger.debug(f"Tracked pending tool call: {tool_name} ({tool_id})")

    async def _finish_current_turn(self, interrupted: bool = False) -> None:
        """Finish the current turn call with file snapshots and diff view.

        Note: This method has streaming-specific logic (real-time tool call logging,
        thinking traces, inline parent handling) that differs from the batch-oriented
        processor.finish_turn_call(). Full migration would require design work to
        handle both real-time and batch processing patterns. For now, we use the
        processor's helper functions where applicable (e.g., extract_question_from_text).
        """
        if not self.weave_client or not self.current_turn_call_id:
            return

        turn_call = reconstruct_call(
            project_id=self.weave_client._project_id(),
            call_id=self.current_turn_call_id,
            trace_id=self.trace_id,
            parent_id=self.session_call_id,
        )

        # Parse session file to get turn and session data
        session, turn, turn_index = await self._get_current_turn_data()

        # Log tool calls from the parsed turn (which has results linked)
        if turn:
            await self._log_turn_tool_calls(turn, turn_call)

        output: dict[str, Any] = {}
        if interrupted:
            output["interrupted"] = True
            output["status"] = "[interrupted]"

        if turn:
            usage = turn.total_usage()

            # Collect thinking content for separate thinking trace
            thinking_content_parts = []
            thinking_usage = TokenUsage(requests=0)
            for msg in turn.assistant_messages:
                if msg.thinking_content:
                    thinking_content_parts.append(msg.thinking_content)
                    thinking_usage = thinking_usage + msg.usage

            # Create thinking trace if there's thinking content
            if thinking_content_parts:
                aggregated_thinking = "\n\n".join(thinking_content_parts)
                weave.log_call(
                    op="claude_code.thinking",
                    inputs={"content": aggregated_thinking},
                    output={"usage": thinking_usage.to_weave_usage()},
                    display_name="Thinking...",
                    parent=turn_call,
                    use_stack=False,
                )
                logger.debug(f"Created thinking trace with {len(thinking_content_parts)} blocks")

            # Build output using shared helper from SessionProcessor
            from weave.integrations.claude_plugin.session.session_processor import SessionProcessor
            turn_output, assistant_text, _ = SessionProcessor.build_turn_output(
                turn, interrupted=interrupted
            )
            output.update(turn_output)

            # Summary contains metadata (model, usage keyed by model, counts, duration)
            model = turn.primary_model()
            turn_call.summary = {
                "model": model,
                "tool_call_count": len(turn.all_tool_calls()),
                "duration_ms": turn.duration_ms(),
            }
            if model and usage:
                turn_call.summary["usage"] = {model: usage.to_weave_usage()}

            # Detect if turn ends with a question (for Q&A context tracking)
            # Store full assistant text so the next turn can include it as context
            pending_q = extract_question_from_text(assistant_text)
            if pending_q and not interrupted:
                # Store full assistant text for Q&A context, not just the question
                self._pending_question = assistant_text
                turn_call.summary["ends_with_question"] = truncate(pending_q, 500)
                logger.debug(f"Detected trailing question: {pending_q[:50]}...")

            # Load file backups as Content objects (list format)
            # Backups are already linked to turns via messageId in session_parser,
            # so we trust that association rather than timestamp filtering
            file_snapshots: list[Any] = []

            if turn.file_backups and session:
                for fb in turn.file_backups:
                    content = fb.load_content(session.session_id)
                    if content:
                        file_snapshots.append(content)

            # Merge file snapshots from subagents that ran during this turn
            if self.current_turn_call_id in self._subagent_file_snapshots:
                subagent_snapshots = self._subagent_file_snapshots.pop(self.current_turn_call_id)
                file_snapshots.extend(subagent_snapshots)
                logger.debug(f"Merged {len(subagent_snapshots)} file snapshots from subagents")

            if file_snapshots:
                output["file_snapshots"] = file_snapshots
                logger.debug(f"Captured {len(file_snapshots)} total file snapshots")

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
                    cwd=session.cwd,
                    user_prompt=turn.user_message.content,
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

        # Mark interrupted turns with an exception so they show as failed in Weave
        exception: BaseException | None = None
        if interrupted:
            exception = InterruptedError("Interrupted by user")

        self.weave_client.finish_call(turn_call, output=output, exception=exception)
        self.weave_client.flush()

        logger.debug(f"Finished turn {self.turn_number}")
        self.current_turn_call_id = None

    async def _log_turn_tool_calls(self, turn: Turn, turn_call: "Call") -> None:
        """Log all tool calls from a turn with their results.

        This is called at turn finish time when the session file has been parsed
        and tool_use/tool_result have been linked together, so we have the actual
        output for each tool call.

        Tool calls are grouped by parallel execution - when multiple tools run
        within 1 second of each other, they're wrapped in a Parallel container.

        Args:
            turn: The parsed Turn object containing tool calls with results
            turn_call: The parent turn call to attach tool calls to
        """
        if not self.weave_client:
            return

        from weave.integrations.claude_plugin.utils import (
            log_tool_calls_grouped,
            _generate_parallel_display_name,
        )

        # Tools to skip (handled elsewhere)
        skip_tools = {
            "Task",  # Task with subagent_type handled by SubagentStop
            "EnterPlanMode",
            "ExitPlanMode",
            "AskUserQuestion",
            "Skill",
            "SlashCommand",
        }

        # Determine parent: inline parent if active, otherwise turn
        if self._pending_inline_parent and self._pending_inline_parent.is_active:
            tool_parent = reconstruct_call(
                project_id=self.weave_client._project_id(),
                call_id=self._pending_inline_parent.call_id,
                trace_id=self.trace_id,
                parent_id=self._pending_inline_parent.parent_turn_call_id,
            )
        else:
            tool_parent = turn_call

        # Get grouped tool calls and filter out already-logged and special tools
        groups = turn.grouped_tool_calls()
        filtered_groups: list[list[ToolCall]] = []

        for group in groups:
            filtered = [
                tc for tc in group
                if tc.id not in self._logged_tool_call_ids
                and tc.name not in skip_tools
                and not (tc.name == "Task" and tc.input.get("subagent_type"))
            ]
            if filtered:
                filtered_groups.append(filtered)

        # Log grouped tool calls
        calls_created = log_tool_calls_grouped(
            tool_call_groups=filtered_groups,
            parent=tool_parent,
        )

        # Update counts
        for group in filtered_groups:
            for tc in group:
                self.tool_counts[tc.name] = self.tool_counts.get(tc.name, 0) + 1
                self.total_tool_calls += 1
                logger.debug(f"Logged tool call: {tc.name} (result={'yes' if tc.result else 'no'})")

        # Clear tracked tool calls for this turn
        self._current_turn_tool_calls = []
        self._logged_tool_call_ids.clear()
        self._pending_tool_calls.clear()

    async def _handle_skill_expansion(self, skill_content: str) -> None:
        """Handle a skill expansion message - log Skill tool call without creating new turn.

        Skill expansions are sent as user messages but should be attached to the
        Skill tool call that triggered them, not create a new turn.

        Args:
            skill_content: The skill expansion content (markdown documentation)
        """
        if not self.weave_client or not self.current_turn_call_id:
            self._pending_skill_calls.clear()
            return

        # Reconstruct turn call as parent
        turn_call = reconstruct_call(
            project_id=self.weave_client._project_id(),
            call_id=self.current_turn_call_id,
            trace_id=self.trace_id,
            parent_id=self.session_call_id,
        )

        # Log each pending skill call with its expansion
        for tool_id, (skill_name, started_at) in self._pending_skill_calls.items():
            # Skip if already logged (prevents duplicates on reprocessing)
            if tool_id in self._logged_tool_call_ids:
                logger.debug(f"Skipping already-logged skill: {skill_name} ({tool_id})")
                continue

            # Calculate duration
            ended_at = datetime.now(timezone.utc)
            duration_ms = int((ended_at - started_at).total_seconds() * 1000)

            # Determine tool type from skill_name (Skill vs SlashCommand)
            is_slash_command = skill_name.startswith("/")
            tool_type = "SlashCommand" if is_slash_command else "Skill"

            log_tool_call(
                tool_name=tool_type,
                tool_input={"skill": skill_name} if not is_slash_command else {"command": skill_name},
                tool_output=skill_content,
                tool_use_id=tool_id,
                duration_ms=duration_ms,
                parent=turn_call,
                max_output_length=10000,
            )

            # Update counts
            self.tool_counts[tool_type] = self.tool_counts.get(tool_type, 0) + 1
            self.total_tool_calls += 1

            # Mark as logged to avoid duplicate logging at turn finish
            self._logged_tool_call_ids.add(tool_id)

            logger.debug(f"Logged skill expansion: {skill_name}")

        # Clear pending skills
        self._pending_skill_calls.clear()

        # Flush to ensure calls are sent
        self.weave_client.flush()

    async def _activate_inline_parent(self, prompt: str) -> None:
        """Activate a pending PlanMode with its first turn content.

        This creates the Weave call for the PlanMode, making it the active
        container for subsequent tool calls during planning.
        """
        if not self._pending_inline_parent or not self.weave_client:
            return

        tracker = self._pending_inline_parent

        # Reconstruct parent turn call
        parent_turn = reconstruct_call(
            project_id=self.weave_client._project_id(),
            call_id=tracker.parent_turn_call_id,
            trace_id=self.trace_id,
            parent_id=self.session_call_id,
        )

        # Create the inline parent call as child of the turn
        inline_parent_call = self.weave_client.create_call(
            op=tracker.op_name,
            inputs={
                "prompt": truncate(prompt, 2000),
            },
            parent=parent_turn,
            display_name=tracker.display_name,
            use_stack=False,
        )

        # Mark as active
        tracker.call_id = inline_parent_call.id

        logger.debug(f"Activated inline parent: {tracker.display_name}")

    async def _finish_inline_parent(self, output: dict[str, Any] | None = None) -> None:
        """Finish the active inline parent call.

        Args:
            output: Optional output data to include in the finished call.
        """
        if not self._pending_inline_parent or not self._pending_inline_parent.is_active:
            return

        if not self.weave_client:
            self._pending_inline_parent = None
            return

        tracker = self._pending_inline_parent

        # Reconstruct the inline parent call
        inline_parent_call = reconstruct_call(
            project_id=self.weave_client._project_id(),
            call_id=tracker.call_id,
            trace_id=self.trace_id,
            parent_id=tracker.parent_turn_call_id,
        )

        self.weave_client.finish_call(inline_parent_call, output=output or {})

        logger.debug(f"Finished inline parent: {tracker.display_name}")
        self._pending_inline_parent = None

    async def _finish_question_call(
        self, tool_use_id: str, tool_result: dict[str, Any]
    ) -> None:
        """Finish a pending AskUserQuestion call with the user's answers.

        Args:
            tool_use_id: The ID of the tool_use that created the question call.
            tool_result: The tool_result content from the user message.
        """
        if tool_use_id not in self._pending_question_calls:
            return

        if not self.weave_client:
            del self._pending_question_calls[tool_use_id]
            return

        call_id, questions = self._pending_question_calls[tool_use_id]

        # Parse the answers from the tool result
        # Format: "User has answered your questions: \"Q1\"=\"A1\". \"Q2\"=\"A2\"..."
        result_content = tool_result.get("content", "")
        answers: list[str] = []

        if isinstance(result_content, str):
            import re

            # Match patterns like: "Question text"="Answer text"
            pattern = r'"([^"]+)"="([^"]+)"'
            matches = re.findall(pattern, result_content)

            # Build answers array in order matching the questions
            question_to_answer = {q: a for q, a in matches}
            for q in questions:
                q_text = q.get("question", "")
                if q_text in question_to_answer:
                    answers.append(question_to_answer[q_text])
                else:
                    # Fallback: if we can't match, use empty string
                    answers.append("")

            # If no matches at all, store raw content as single answer
            if not matches:
                answers = [result_content]

        question_call = reconstruct_call(
            project_id=self.weave_client._project_id(),
            call_id=call_id,
            trace_id=self.trace_id,
            parent_id=self.current_turn_call_id,
        )

        self.weave_client.finish_call(
            question_call,
            output={"answers": answers},
        )

        logger.debug(f"Finished question call with {len(answers)} answers")
        del self._pending_question_calls[tool_use_id]

    async def _log_pending_tool_calls_grouped(
        self, tool_results: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Log multiple pending tool calls with parallel grouping.

        Tool calls with started_at timestamps within 1000ms of each other are
        considered parallel and wrapped in a claude_code.parallel container.

        This is called when multiple tool_results arrive in the same user message,
        which indicates they may have been executed in parallel.

        Args:
            tool_results: List of (tool_use_id, tool_result_content) tuples
        """
        if not tool_results:
            return

        if not self.weave_client or not self.current_turn_call_id:
            # Clear pending state for all tools
            for tool_use_id, _ in tool_results:
                if tool_use_id in self._pending_tool_calls:
                    del self._pending_tool_calls[tool_use_id]
            return

        # Build list of (tool_use_id, tool_result, name, input, started_at)
        tool_data: list[tuple[str, dict, str, dict, datetime]] = []
        for tool_use_id, tool_result in tool_results:
            if tool_use_id in self._pending_tool_calls:
                name, input_data, started_at = self._pending_tool_calls[tool_use_id]
                tool_data.append((tool_use_id, tool_result, name, input_data, started_at))

        if not tool_data:
            return

        # Sort by started_at timestamp
        tool_data.sort(key=lambda x: x[4])

        # Group by timestamp proximity (1000ms threshold, matching session_parser)
        PARALLEL_THRESHOLD_MS = 1000
        groups: list[list[tuple[str, dict, str, dict, datetime]]] = []
        current_group: list[tuple[str, dict, str, dict, datetime]] = [tool_data[0]]

        for td in tool_data[1:]:
            prev_started = current_group[-1][4]
            gap_ms = abs((td[4] - prev_started).total_seconds() * 1000)

            if gap_ms <= PARALLEL_THRESHOLD_MS:
                current_group.append(td)
            else:
                groups.append(current_group)
                current_group = [td]
        groups.append(current_group)

        # Determine parent: inline parent if active, otherwise turn
        if self._pending_inline_parent and self._pending_inline_parent.is_active:
            tool_parent = reconstruct_call(
                project_id=self.weave_client._project_id(),
                call_id=self._pending_inline_parent.call_id,
                trace_id=self.trace_id,
                parent_id=self._pending_inline_parent.parent_turn_call_id,
            )
        else:
            tool_parent = reconstruct_call(
                project_id=self.weave_client._project_id(),
                call_id=self.current_turn_call_id,
                trace_id=self.trace_id,
                parent_id=self.session_call_id,
            )

        # Log each group
        for group in groups:
            if len(group) == 1:
                # Single tool - log directly
                tool_use_id, tool_result, tool_name, tool_input, started_at = group[0]
                self._log_single_tool_call(
                    tool_use_id, tool_result, tool_name, tool_input, started_at, tool_parent
                )
            else:
                # Multiple tools - create parallel wrapper
                self._log_parallel_tool_calls(group, tool_parent)

        # Flush to ensure calls are sent
        self.weave_client.flush()

    def _log_single_tool_call(
        self,
        tool_use_id: str,
        tool_result: dict[str, Any],
        tool_name: str,
        tool_input: dict[str, Any],
        started_at: datetime,
        parent: Any,
    ) -> None:
        """Log a single tool call (helper for grouped logging)."""
        # Extract result content
        result_content = tool_result.get("content", "")
        if isinstance(result_content, list):
            text_parts = []
            for item in result_content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            result_content = "\n".join(text_parts)

        # Calculate duration
        ended_at = datetime.now(timezone.utc)
        duration_ms = int((ended_at - started_at).total_seconds() * 1000)

        log_tool_call(
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=result_content,
            tool_use_id=tool_use_id,
            duration_ms=duration_ms,
            parent=parent,
            max_output_length=10000,
        )

        # Update counts and tracking
        self.tool_counts[tool_name] = self.tool_counts.get(tool_name, 0) + 1
        self.total_tool_calls += 1

        if tool_use_id in self._pending_tool_calls:
            del self._pending_tool_calls[tool_use_id]
        self._logged_tool_call_ids.add(tool_use_id)
        if tool_use_id in self._current_turn_tool_calls:
            self._current_turn_tool_calls.remove(tool_use_id)

        logger.debug(f"Logged tool call: {tool_name} ({tool_use_id})")

    def _log_parallel_tool_calls(
        self,
        group: list[tuple[str, dict, str, dict, datetime]],
        parent: Any,
    ) -> None:
        """Log a group of parallel tool calls with a wrapper.

        Args:
            group: List of (tool_use_id, tool_result, name, input, started_at) tuples
            parent: Parent call for the parallel wrapper
        """
        from collections import Counter

        # Generate display name from tool names
        tool_names = [g[2] for g in group]  # g[2] is tool_name
        counts = Counter(tool_names)
        parts = []
        for name, count in counts.most_common():
            if count > 1:
                parts.append(f"{name} x{count}")
            else:
                parts.append(name)
        display_name = f"Parallel ({', '.join(parts)})"

        # Calculate timing for the parallel group
        started_at = min(g[4] for g in group)
        ended_at = datetime.now(timezone.utc)

        # Create parallel wrapper
        parallel_call = self.weave_client.create_call(
            op="claude_code.parallel",
            inputs={
                "tool_count": len(group),
                "tools": tool_names,
            },
            parent=parent,
            display_name=display_name,
            attributes={"is_parallel_group": True},
            use_stack=False,
        )

        # Log each tool under the parallel wrapper
        for tool_use_id, tool_result, tool_name, tool_input, tool_started_at in group:
            self._log_single_tool_call(
                tool_use_id, tool_result, tool_name, tool_input, tool_started_at, parallel_call
            )

        # Finish parallel wrapper
        self.weave_client.finish_call(
            parallel_call,
            output={"completed": len(group)},
        )

        logger.debug(f"Logged parallel group: {display_name}")

    def _flush_buffered_tool_results(self, force: bool = False) -> None:
        """Flush buffered tool results with parallel grouping.

        Args:
            force: If True, flush all buffered results immediately (used at Stop)
        """
        if self._tool_buffer.is_empty():
            return

        if not self.weave_client or not self.current_turn_call_id:
            self._tool_buffer.clear()
            return

        # Get ready groups from buffer
        groups = self._tool_buffer.get_ready_to_flush(force=force)
        if not groups:
            return

        # Determine parent: inline parent if active, otherwise turn
        if self._pending_inline_parent and self._pending_inline_parent.is_active:
            tool_parent = reconstruct_call(
                project_id=self.weave_client._project_id(),
                call_id=self._pending_inline_parent.call_id,
                trace_id=self.trace_id,
                parent_id=self._pending_inline_parent.parent_turn_call_id,
            )
        else:
            tool_parent = reconstruct_call(
                project_id=self.weave_client._project_id(),
                call_id=self.current_turn_call_id,
                trace_id=self.trace_id,
                parent_id=self.session_call_id,
            )

        # Log each group
        for group in groups:
            if len(group) == 1:
                self._log_single_tool_from_buffer(group[0], tool_parent)
            else:
                self._log_parallel_tools_from_buffer(group, tool_parent)

        # Remove logged tools from buffer
        self._tool_buffer.remove(groups)

        # Flush to send calls
        self.weave_client.flush()

    def _log_single_tool_from_buffer(
        self,
        tool: BufferedToolResult,
        parent: Any,
    ) -> None:
        """Log a single buffered tool call."""
        # Calculate duration from actual message timestamps (tool_use to tool_result)
        # This is the time between when Claude sent the tool call and when the result was written
        duration_ms = int((tool.result_timestamp - tool.timestamp).total_seconds() * 1000)

        log_tool_call(
            tool_name=tool.name,
            tool_input=tool.input,
            tool_output=tool.result,
            tool_use_id=tool.tool_use_id,
            duration_ms=duration_ms,
            parent=parent,
            max_output_length=10000,
            is_error=tool.is_error,
        )

        # Update counts and tracking
        self.tool_counts[tool.name] = self.tool_counts.get(tool.name, 0) + 1
        self.total_tool_calls += 1
        self._logged_tool_call_ids.add(tool.tool_use_id)

        if tool.tool_use_id in self._current_turn_tool_calls:
            self._current_turn_tool_calls.remove(tool.tool_use_id)

        logger.debug(f"Logged tool call: {tool.name} ({tool.tool_use_id})")

    def _log_parallel_tools_from_buffer(
        self,
        group: list[BufferedToolResult],
        parent: Any,
    ) -> None:
        """Log a group of parallel buffered tool calls with a wrapper."""
        from collections import Counter

        # Generate display name from tool names
        tool_names = [t.name for t in group]
        counts = Counter(tool_names)
        parts = []
        for name, count in counts.most_common():
            if count > 1:
                parts.append(f"{name} x{count}")
            else:
                parts.append(name)
        display_name = f"Parallel ({', '.join(parts)})"

        # Calculate timing for the parallel group using actual message timestamps
        started_at = min(t.timestamp for t in group)
        ended_at = max(t.result_timestamp for t in group)

        # Create parallel wrapper
        parallel_call = self.weave_client.create_call(
            op="claude_code.parallel",
            inputs={
                "tool_count": len(group),
                "tools": tool_names,
            },
            parent=parent,
            display_name=display_name,
            attributes={"is_parallel_group": True},
            use_stack=False,
        )

        # Log each tool under the parallel wrapper
        for tool in group:
            self._log_single_tool_from_buffer(tool, parallel_call)

        # Finish parallel wrapper
        self.weave_client.finish_call(
            parallel_call,
            output={"completed": len(group)},
        )

        logger.debug(f"Logged parallel group: {display_name}")

    async def _log_pending_tool_call(
        self, tool_use_id: str, tool_result: dict[str, Any]
    ) -> None:
        """Log a pending tool call now that its result has arrived.

        NOTE: This is now only used as a fallback. The primary path is
        _flush_buffered_tool_results which handles parallel grouping.

        This enables real-time streaming of tool calls - they appear in the trace
        as soon as their results are available, rather than waiting for turn finish.

        Args:
            tool_use_id: The ID of the tool_use.
            tool_result: The tool_result content from the user message.
        """
        if tool_use_id not in self._pending_tool_calls:
            return

        if not self.weave_client or not self.current_turn_call_id:
            del self._pending_tool_calls[tool_use_id]
            return

        tool_name, tool_input, started_at = self._pending_tool_calls[tool_use_id]

        # Extract result content
        result_content = tool_result.get("content", "")
        if isinstance(result_content, list):
            # Handle structured content (e.g., images, multiple blocks)
            text_parts = []
            for item in result_content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            result_content = "\n".join(text_parts)

        # Calculate duration
        ended_at = datetime.now(timezone.utc)
        duration_ms = int((ended_at - started_at).total_seconds() * 1000)

        # Determine parent: inline parent if active, otherwise turn
        if self._pending_inline_parent and self._pending_inline_parent.is_active:
            tool_parent = reconstruct_call(
                project_id=self.weave_client._project_id(),
                call_id=self._pending_inline_parent.call_id,
                trace_id=self.trace_id,
                parent_id=self._pending_inline_parent.parent_turn_call_id,
            )
        else:
            tool_parent = reconstruct_call(
                project_id=self.weave_client._project_id(),
                call_id=self.current_turn_call_id,
                trace_id=self.trace_id,
                parent_id=self.session_call_id,
            )

        # Log the tool call
        log_tool_call(
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=result_content,
            tool_use_id=tool_use_id,
            duration_ms=duration_ms,
            parent=tool_parent,
            max_output_length=10000,
        )

        # Update counts
        self.tool_counts[tool_name] = self.tool_counts.get(tool_name, 0) + 1
        self.total_tool_calls += 1

        # Remove from pending and mark as logged
        del self._pending_tool_calls[tool_use_id]
        # Track that we've logged this tool call (to avoid duplicate at turn finish)
        self._logged_tool_call_ids.add(tool_use_id)
        # Remove from current turn tool calls since we've already logged it
        if tool_use_id in self._current_turn_tool_calls:
            self._current_turn_tool_calls.remove(tool_use_id)

        # Flush to ensure the call is sent immediately
        self.weave_client.flush()

        logger.debug(f"Logged tool call in real-time: {tool_name} ({tool_use_id})")

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

            current_time = time.monotonic()
            idle_time = current_time - self.last_activity

            if idle_time > INACTIVITY_TIMEOUT:
                logger.info(f"Inactivity timeout ({idle_time:.0f}s), shutting down")
                self.running = False
                break


async def main(session_id: str) -> None:
    """Main entry point."""
    global logger
    # Reconfigure logging with session_id for per-session log files
    logger = setup_logging(session_id)

    daemon = WeaveDaemon(session_id)
    await daemon.start()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m weave.integrations.claude_plugin.daemon <session_id>")
        sys.exit(1)

    session_id = sys.argv[1]
    asyncio.run(main(session_id))
