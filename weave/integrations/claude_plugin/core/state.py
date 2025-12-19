"""State persistence for Claude Code hooks.

Each hook invocation is a separate process, so state must be persisted
to disk to maintain context across hook events. This module provides
a consolidated state file with automatic cleanup of old entries.

State is stored in ~/.cache/weave/claude-plugin.json with file locking
to handle concurrent hook invocations.
"""

from __future__ import annotations

import fcntl
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# State file location
STATE_DIR = Path.home() / ".cache" / "weave"
STATE_FILE = STATE_DIR / "claude-plugin.json"
LOCK_FILE = STATE_DIR / "claude-plugin.lock"

# Cleanup entries older than this
RETENTION_DAYS = 7


def _now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _is_expired(last_updated: str) -> bool:
    """Check if a timestamp is older than RETENTION_DAYS."""
    try:
        updated = datetime.fromisoformat(last_updated)
        # Handle naive datetimes by assuming UTC
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    except (ValueError, TypeError):
        # Invalid timestamp - treat as expired
        return True
    else:
        return updated < cutoff


def _cleanup_expired(data: dict[str, Any]) -> dict[str, Any]:
    """Remove session entries older than RETENTION_DAYS."""
    sessions = data.get("sessions", {})
    cwds = data.get("cwds", {})

    # Find expired sessions
    expired = [
        sid
        for sid, sdata in sessions.items()
        if _is_expired(sdata.get("last_updated", ""))
    ]

    # Remove expired sessions
    for sid in expired:
        del sessions[sid]
        logger.debug(f"Cleaned up expired session: {sid}")

    # Clean up cwds index
    for cwd in list(cwds.keys()):
        cwds[cwd] = [s for s in cwds[cwd] if s not in expired]
        if not cwds[cwd]:
            del cwds[cwd]

    return data


def _read_state_file() -> dict[str, Any]:
    """Read the state file, returning empty structure if not exists."""
    if not STATE_FILE.exists():
        return {"sessions": {}, "cwds": {}}

    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read state file: {e}")
        return {"sessions": {}, "cwds": {}}


def _write_state_file(data: dict[str, Any]) -> None:
    """Write the state file atomically."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Write to temp file then rename for atomicity
    temp_file = STATE_FILE.with_suffix(".tmp")
    try:
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2)
        temp_file.rename(STATE_FILE)
    except OSError as e:
        logger.warning(f"Failed to write state file: {e}")
        if temp_file.exists():
            temp_file.unlink()


class StateManager:
    """Manages consolidated state for all Claude Code sessions.

    Provides thread-safe access to the state file with automatic
    cleanup of expired entries.

    Usage:
        with StateManager() as state:
            session = state.get_session("session-id")
            session["turn_number"] = 5
            state.save_session("session-id", session)
    """

    def __init__(self) -> None:
        self._lock_file: Any = None
        self._data: dict[str, Any] = {}

    def __enter__(self) -> StateManager:
        """Acquire lock and load state."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        # Open and lock
        self._lock_file = open(LOCK_FILE, "w")
        fcntl.flock(self._lock_file, fcntl.LOCK_EX)

        # Load data
        self._data = _read_state_file()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Release lock."""
        if self._lock_file:
            fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            self._lock_file.close()
            self._lock_file = None

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session data by ID.

        Args:
            session_id: Claude Code session ID

        Returns:
            Session data dict or None if not found
        """
        return self._data.get("sessions", {}).get(session_id)

    def save_session(
        self,
        session_id: str,
        session_data: dict[str, Any],
        cwd: str | None = None,
    ) -> None:
        """Save session data.

        Args:
            session_id: Claude Code session ID
            session_data: Session data to save
            cwd: Working directory (updates cwds index if provided)
        """
        # Ensure sessions dict exists
        if "sessions" not in self._data:
            self._data["sessions"] = {}
        if "cwds" not in self._data:
            self._data["cwds"] = {}

        # Update timestamp
        session_data["last_updated"] = _now_iso()

        # Save session
        self._data["sessions"][session_id] = session_data

        # Update cwds index
        if cwd:
            if cwd not in self._data["cwds"]:
                self._data["cwds"][cwd] = []
            if session_id not in self._data["cwds"][cwd]:
                self._data["cwds"][cwd].append(session_id)

        # Cleanup and write
        self._data = _cleanup_expired(self._data)
        _write_state_file(self._data)

    def delete_session(self, session_id: str) -> None:
        """Delete a session and clean up cwds index.

        Args:
            session_id: Claude Code session ID to delete
        """
        sessions = self._data.get("sessions", {})
        cwds = self._data.get("cwds", {})

        # Remove from sessions
        if session_id in sessions:
            del sessions[session_id]

        # Remove from cwds index
        for cwd in list(cwds.keys()):
            if session_id in cwds[cwd]:
                cwds[cwd].remove(session_id)
            if not cwds[cwd]:
                del cwds[cwd]

        _write_state_file(self._data)

    def get_sessions_by_cwd(self, cwd: str) -> list[str]:
        """Get all session IDs for a working directory.

        Args:
            cwd: Working directory path

        Returns:
            List of session IDs
        """
        return self._data.get("cwds", {}).get(cwd, [])


# Convenience functions for simpler usage


def load_session(session_id: str) -> dict[str, Any] | None:
    """Load session data (acquires lock briefly).

    Args:
        session_id: Claude Code session ID

    Returns:
        Session data dict or None if not found
    """
    with StateManager() as state:
        return state.get_session(session_id)


def save_session(
    session_id: str,
    session_data: dict[str, Any],
    cwd: str | None = None,
) -> None:
    """Save session data (acquires lock briefly).

    Args:
        session_id: Claude Code session ID
        session_data: Session data to save
        cwd: Working directory (updates cwds index if provided)
    """
    with StateManager() as state:
        state.save_session(session_id, session_data, cwd)


def delete_session(session_id: str) -> None:
    """Delete a session (acquires lock briefly).

    Args:
        session_id: Claude Code session ID to delete
    """
    with StateManager() as state:
        state.delete_session(session_id)


# Helper to create initial session data


def create_session_data(
    project: str,
    entity: str | None = None,
    session_call_id: str | None = None,
    trace_id: str | None = None,
    trace_url: str | None = None,
    turn_call_id: str | None = None,
    turn_number: int = 0,
    total_tool_calls: int = 0,
    tool_counts: dict[str, int] | None = None,
    daemon_pid: int | None = None,
    last_processed_line: int = 0,
    transcript_path: str | None = None,
    continuation_count: int = 0,
) -> dict[str, Any]:
    """Create a new session data dict with all fields.

    Args:
        project: Weave project name
        entity: Weave entity (resolved from API)
        session_call_id: Weave call ID for the session
        trace_id: Weave trace ID
        trace_url: Weave trace URL for additionalContext
        turn_call_id: Current turn's call ID
        turn_number: Number of turns
        total_tool_calls: Total tool call count
        tool_counts: Tool counts by name
        daemon_pid: PID of the daemon process for this session
        last_processed_line: Line number in session file processed up to
        transcript_path: Path to the session JSONL file
        continuation_count: Number of times this session has been continued

    Returns:
        Session data dict
    """
    return {
        "project": project,
        "entity": entity,
        "session_call_id": session_call_id,
        "trace_id": trace_id,
        "trace_url": trace_url,
        "turn_call_id": turn_call_id,
        "turn_number": turn_number,
        "total_tool_calls": total_tool_calls,
        "tool_counts": tool_counts or {},
        "daemon_pid": daemon_pid,
        "last_processed_line": last_processed_line,
        "transcript_path": transcript_path,
        "continuation_count": continuation_count,
        "last_updated": _now_iso(),
    }
