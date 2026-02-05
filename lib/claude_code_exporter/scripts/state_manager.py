"""State persistence for Claude Code Weave Exporter.

Manages state between hook invocations using a JSON file.
Each session gets its own state file to avoid conflicts.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


STATE_DIR = Path.home() / ".claude_code_weave"


@dataclass
class SessionState:
    """State for a single Claude Code session."""

    session_id: str
    session_call_id: str | None = None
    session_trace_id: str | None = None
    tool_calls: dict[str, str] = field(default_factory=dict)  # tool_use_id -> call_id
    subagent_stack: list[str] = field(default_factory=list)  # stack of call_ids
    project: str | None = None
    message_count: int = 0  # Counter for user/agent messages
    turn_count: int = 0  # Counter for conversation turns
    current_turn_call_id: str | None = None  # Current turn span

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "session_call_id": self.session_call_id,
            "session_trace_id": self.session_trace_id,
            "tool_calls": self.tool_calls,
            "subagent_stack": self.subagent_stack,
            "project": self.project,
            "message_count": self.message_count,
            "turn_count": self.turn_count,
            "current_turn_call_id": self.current_turn_call_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        """Create state from dictionary."""
        return cls(
            session_id=data["session_id"],
            session_call_id=data.get("session_call_id"),
            session_trace_id=data.get("session_trace_id"),
            tool_calls=data.get("tool_calls", {}),
            subagent_stack=data.get("subagent_stack", []),
            project=data.get("project"),
            message_count=data.get("message_count", 0),
            turn_count=data.get("turn_count", 0),
            current_turn_call_id=data.get("current_turn_call_id"),
        )

    def get_current_parent_id(self) -> str | None:
        """Get the current parent call ID for nesting.

        Returns the top of the subagent stack if non-empty,
        otherwise returns the current turn if active,
        otherwise returns the session call ID.
        """
        if self.subagent_stack:
            return self.subagent_stack[-1]
        if self.current_turn_call_id:
            return self.current_turn_call_id
        return self.session_call_id


class StateManager:
    """Manages persistent state between hook invocations."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._state_file = STATE_DIR / f"state_{session_id}.json"
        self._ensure_state_dir()

    def _ensure_state_dir(self) -> None:
        """Ensure the state directory exists."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)

    def load(self) -> SessionState:
        """Load state from file, creating new state if not found."""
        if self._state_file.exists():
            try:
                with open(self._state_file) as f:
                    data = json.load(f)
                return SessionState.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return SessionState(session_id=self.session_id)

    def save(self, state: SessionState) -> None:
        """Save state to file."""
        with open(self._state_file, "w") as f:
            json.dump(state.to_dict(), f, indent=2)

    def cleanup(self) -> None:
        """Remove the state file."""
        if self._state_file.exists():
            os.remove(self._state_file)

    @classmethod
    def cleanup_all(cls) -> None:
        """Remove all state files (useful for cleanup)."""
        if STATE_DIR.exists():
            for state_file in STATE_DIR.glob("state_*.json"):
                state_file.unlink()
