"""Session parser for Claude Code JSONL files.

This module provides data classes and parsing functions for Claude Code
session files. These can be used by both the real-time hook handlers
and the batch import script.
"""

from __future__ import annotations

import datetime
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from weave.type_wrappers.Content.content import Content

logger = logging.getLogger(__name__)

# Default location for Claude's file and session data
CLAUDE_DIR = Path.home() / ".claude"

# Extension to mimetype mapping for file backups
EXT_TO_MIMETYPE: dict[str, str] = {
    ".py": "text/x-python",
    ".go": "text/x-go",
    ".js": "text/javascript",
    ".ts": "text/typescript",
    ".jsx": "text/javascript",
    ".tsx": "text/typescript",
    ".json": "application/json",
    ".jsonl": "application/x-ndjson",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".sh": "text/x-shellscript",
    ".bash": "text/x-shellscript",
    ".sql": "text/x-sql",
    ".html": "text/html",
    ".css": "text/css",
    ".rs": "text/x-rust",
    ".java": "text/x-java",
    ".c": "text/x-c",
    ".h": "text/x-c",
    ".cpp": "text/x-c++",
    ".hpp": "text/x-c++",
    ".rb": "text/x-ruby",
    ".toml": "text/x-toml",
    ".mod": "text/plain",  # Go modules
    ".sum": "text/plain",  # Go checksums
}


def parse_timestamp(ts: str) -> datetime.datetime:
    """Parse ISO timestamp from Claude session.

    Handles timestamps ending in 'Z' by converting to +00:00.
    """
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.datetime.fromisoformat(ts)


@dataclass
class TokenUsage:
    """Token usage from Claude API response."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TokenUsage:
        return cls(
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            cache_creation_input_tokens=data.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=data.get("cache_read_input_tokens", 0),
        )

    def total_input(self) -> int:
        return (
            self.input_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
        )

    def total(self) -> int:
        return self.total_input() + self.output_tokens

    def to_weave_usage(self) -> dict[str, int]:
        """Convert to Weave's expected usage format for automatic tracking."""
        return {
            "input_tokens": self.total_input(),
            "output_tokens": self.output_tokens,
            "total_tokens": self.total(),
            # Include detailed breakdown
            "prompt_tokens": self.total_input(),
            "completion_tokens": self.output_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "requests": 1,
        }

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens
            + other.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens
            + other.cache_read_input_tokens,
        )


@dataclass
class ToolCall:
    """A tool call made by the assistant."""

    id: str
    name: str
    input: dict[str, Any]
    timestamp: datetime.datetime
    result: str | None = None
    result_timestamp: datetime.datetime | None = None

    def duration_ms(self) -> int | None:
        if self.result_timestamp:
            delta = self.result_timestamp - self.timestamp
            return int(delta.total_seconds() * 1000)
        return None


@dataclass
class FileBackup:
    """A file backup from Claude's file-history system."""

    file_path: str  # Original file path (e.g., "scripts/import_claude_sessions.py")
    backup_filename: str | None  # Backup file name in file-history
    version: int
    backup_time: datetime.datetime
    message_id: str  # Links to the turn's message ID

    def load_content(
        self, session_id: str, claude_dir: Path = CLAUDE_DIR
    ) -> Content | None:
        """Load the file content from Claude's file-history directory.

        Returns a weave.Content object with the file contents, or None if not found.
        """
        # Import here to avoid circular imports and allow use without weave
        from weave.type_wrappers.Content.content import Content

        if not self.backup_filename:
            return None

        backup_path = claude_dir / "file-history" / session_id / self.backup_filename
        if not backup_path.exists():
            logger.debug(f"Backup file not found: {backup_path}")
            return None

        try:
            original_ext = Path(self.file_path).suffix.lower()
            mimetype = EXT_TO_MIMETYPE.get(original_ext, "text/plain")

            return Content.from_bytes(
                backup_path.read_bytes(),
                mimetype=mimetype,
                extension=original_ext or ".txt",
                metadata={
                    "original_path": self.file_path,
                    "backup_filename": self.backup_filename,
                    "version": self.version,
                    "backup_time": self.backup_time.isoformat(),
                    "message_id": self.message_id,
                },
            )
        except Exception as e:
            logger.debug(f"Failed to load backup file {backup_path}: {e}")
            return None


@dataclass
class AssistantMessage:
    """An assistant message with potential tool calls."""

    uuid: str
    model: str
    text_content: list[str]
    tool_calls: list[ToolCall]
    usage: TokenUsage
    timestamp: datetime.datetime

    def get_text(self) -> str:
        return "\n".join(self.text_content)


@dataclass
class UserMessage:
    """A user message."""

    uuid: str
    content: str
    timestamp: datetime.datetime


@dataclass
class Turn:
    """A conversation turn: user message + assistant response(s)."""

    user_message: UserMessage
    assistant_messages: list[AssistantMessage] = field(default_factory=list)
    # Raw JSON payloads from the session file for this turn
    raw_messages: list[dict[str, Any]] = field(default_factory=list)
    # File backups associated with this turn (from file-history-snapshot)
    file_backups: list[FileBackup] = field(default_factory=list)

    def total_usage(self) -> TokenUsage:
        """Aggregate token usage across all assistant messages in this turn."""
        total = TokenUsage()
        for msg in self.assistant_messages:
            total = total + msg.usage
        return total

    def all_tool_calls(self) -> list[ToolCall]:
        """Get all tool calls from all assistant messages."""
        calls = []
        for msg in self.assistant_messages:
            calls.extend(msg.tool_calls)
        return calls

    def primary_model(self) -> str:
        """Get the primary model used in this turn."""
        if self.assistant_messages:
            return self.assistant_messages[0].model
        return "claude-sonnet-4-20250514"

    def started_at(self) -> datetime.datetime:
        return self.user_message.timestamp

    def ended_at(self) -> datetime.datetime:
        if self.assistant_messages:
            last_msg = self.assistant_messages[-1]
            if last_msg.tool_calls:
                tool_calls_with_results = [
                    tc for tc in last_msg.tool_calls if tc.result_timestamp
                ]
                if tool_calls_with_results:
                    return max(tc.result_timestamp for tc in tool_calls_with_results)
            return last_msg.timestamp
        return self.user_message.timestamp

    def duration_ms(self) -> int:
        """Calculate turn duration in milliseconds."""
        delta = self.ended_at() - self.started_at()
        return int(delta.total_seconds() * 1000)


def is_system_message(content: str) -> bool:
    """Check if a message content is a system-generated message that should be skipped.

    These include:
    - Claude's caveat messages about local commands
    - Command execution messages (XML-like tags)
    - System compaction messages
    - Empty or placeholder messages
    """
    if not content or not content.strip():
        return True

    content_stripped = content.strip()

    # Skip placeholder messages
    if content_stripped in ("[system]", "[continuation]"):
        return True

    # Skip XML-like command messages
    xml_prefixes = (
        "<command-name>",
        "<command-message>",
        "<local-command-stdout>",
        "<local-command-stderr>",
        "<system-reminder>",
        "<command-args>",
    )
    if content_stripped.startswith(xml_prefixes):
        return True

    # Skip Claude's caveat messages about local commands
    caveat_prefixes = (
        "Caveat:",
        "CAVEAT:",
        "caveat:",
    )
    if content_stripped.startswith(caveat_prefixes):
        return True

    # Skip very short messages that are likely system-generated
    if len(content_stripped) < 10:
        return True

    return False


@dataclass
class Session:
    """A Claude Code session containing multiple turns."""

    session_id: str
    filename: str  # Basename of the session file
    git_branch: str | None
    cwd: str | None
    version: str | None
    turns: list[Turn] = field(default_factory=list)

    def first_user_prompt(self) -> str:
        """Get the first real user prompt (not system messages)."""
        for turn in self.turns:
            content = turn.user_message.content
            if not is_system_message(content):
                return content
        return ""

    def last_user_prompt(self) -> str:
        """Get the last real user prompt (not system messages)."""
        for turn in reversed(self.turns):
            content = turn.user_message.content
            if not is_system_message(content):
                return content
        return ""

    def started_at(self) -> datetime.datetime | None:
        if self.turns:
            return self.turns[0].started_at()
        return None

    def ended_at(self) -> datetime.datetime | None:
        if self.turns:
            return self.turns[-1].ended_at()
        return None

    def duration_ms(self) -> int | None:
        """Calculate session duration in milliseconds."""
        start = self.started_at()
        end = self.ended_at()
        if start and end:
            delta = end - start
            return int(delta.total_seconds() * 1000)
        return None

    def total_usage(self) -> TokenUsage:
        total = TokenUsage()
        for turn in self.turns:
            total = total + turn.total_usage()
        return total

    def primary_model(self) -> str:
        """Get the most common model used in the session."""
        models: dict[str, int] = defaultdict(int)
        for turn in self.turns:
            models[turn.primary_model()] += 1
        if models:
            return max(models.keys(), key=lambda m: models[m])
        return "claude-sonnet-4-20250514"

    def tool_call_counts(self) -> dict[str, int]:
        """Count tool calls by type."""
        counts: dict[str, int] = defaultdict(int)
        for turn in self.turns:
            for tc in turn.all_tool_calls():
                counts[tc.name] += 1
        return dict(counts)

    def total_tool_calls(self) -> int:
        """Total number of tool calls."""
        return sum(len(t.all_tool_calls()) for t in self.turns)


def parse_session_file(path: Path) -> Session | None:
    """Parse a Claude session JSONL file into a Session object.

    Args:
        path: Path to the session JSONL file

    Returns:
        Session object, or None if parsing fails
    """
    messages: list[dict[str, Any]] = []
    session_info: dict[str, Any] = {}
    # Collect file-history-snapshot entries keyed by messageId
    snapshots_by_message_id: dict[str, list[FileBackup]] = defaultdict(list)

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                msg_type = obj.get("type")

                if msg_type == "queue-operation":
                    continue

                # Parse file-history-snapshot entries
                if msg_type == "file-history-snapshot":
                    snapshot = obj.get("snapshot", {})
                    message_id = snapshot.get("messageId", "")
                    tracked_backups = snapshot.get("trackedFileBackups", {})

                    for file_path, backup_info in tracked_backups.items():
                        if isinstance(backup_info, dict):
                            backup_time_str = backup_info.get("backupTime", "")
                            try:
                                backup_time = (
                                    parse_timestamp(backup_time_str)
                                    if backup_time_str
                                    else datetime.datetime.now(tz=datetime.timezone.utc)
                                )
                            except Exception:
                                backup_time = datetime.datetime.now(
                                    tz=datetime.timezone.utc
                                )

                            file_backup = FileBackup(
                                file_path=file_path,
                                backup_filename=backup_info.get("backupFileName"),
                                version=backup_info.get("version", 0),
                                backup_time=backup_time,
                                message_id=message_id,
                            )
                            snapshots_by_message_id[message_id].append(file_backup)
                    continue

                if not session_info and obj.get("sessionId"):
                    session_info = {
                        "sessionId": obj.get("sessionId"),
                        "gitBranch": obj.get("gitBranch"),
                        "cwd": obj.get("cwd"),
                        "version": obj.get("version"),
                    }

                messages.append(obj)
            except json.JSONDecodeError:
                continue

    if not session_info.get("sessionId"):
        logger.warning(f"No session ID found in {path}")
        return None

    session = Session(
        session_id=session_info["sessionId"],
        filename=path.name,
        git_branch=session_info.get("gitBranch"),
        cwd=session_info.get("cwd"),
        version=session_info.get("version"),
    )

    pending_tool_calls: dict[str, ToolCall] = {}
    current_turn: Turn | None = None

    for msg in messages:
        msg_type = msg.get("type")
        timestamp = parse_timestamp(msg.get("timestamp", "1970-01-01T00:00:00Z"))

        if msg_type == "user":
            user_content = ""
            msg_data = msg.get("message", {})
            content = msg_data.get("content", "")

            if isinstance(content, str):
                user_content = content
            elif isinstance(content, list):
                text_parts = []
                for c in content:
                    if c.get("type") == "text":
                        text_parts.append(c.get("text", ""))
                    elif c.get("type") == "tool_result":
                        tool_use_id = c.get("tool_use_id")
                        if tool_use_id in pending_tool_calls:
                            tc = pending_tool_calls[tool_use_id]
                            result_content = c.get("content", "")
                            if isinstance(result_content, str):
                                tc.result = result_content[:10000]
                            tc.result_timestamp = timestamp
                user_content = "\n".join(text_parts)

            # Only create a new turn if there's actual user text content
            # (not just tool results or empty messages)
            if user_content.strip():
                if current_turn:
                    session.turns.append(current_turn)
                current_turn = Turn(
                    user_message=UserMessage(
                        uuid=msg.get("uuid", ""),
                        content=user_content,
                        timestamp=timestamp,
                    ),
                    raw_messages=[msg],  # Start collecting raw payloads
                )
            elif current_turn:
                # Tool result messages belong to current turn
                current_turn.raw_messages.append(msg)

        elif msg_type == "assistant":
            if not current_turn:
                # Create a placeholder turn for orphan assistant messages
                # This shouldn't happen in normal sessions
                current_turn = Turn(
                    user_message=UserMessage(
                        uuid="",
                        content="[continuation]",
                        timestamp=timestamp,
                    )
                )

            msg_data = msg.get("message", {})
            content = msg_data.get("content", [])
            usage_data = msg_data.get("usage", {})

            text_content = []
            tool_calls = []

            if isinstance(content, list):
                for c in content:
                    if c.get("type") == "text":
                        text_content.append(c.get("text", ""))
                    elif c.get("type") == "tool_use":
                        tc = ToolCall(
                            id=c.get("id", ""),
                            name=c.get("name", "unknown"),
                            input=c.get("input", {}),
                            timestamp=timestamp,
                        )
                        tool_calls.append(tc)
                        pending_tool_calls[tc.id] = tc

            assistant_msg = AssistantMessage(
                uuid=msg.get("uuid", ""),
                model=msg_data.get("model", "unknown"),
                text_content=text_content,
                tool_calls=tool_calls,
                usage=TokenUsage.from_dict(usage_data),
                timestamp=timestamp,
            )
            current_turn.assistant_messages.append(assistant_msg)
            current_turn.raw_messages.append(msg)  # Collect raw payload

    if current_turn:
        session.turns.append(current_turn)

    # Link file backups to turns based on message UUIDs
    # The snapshot messageId corresponds to assistant message UUIDs
    for turn in session.turns:
        for msg in turn.assistant_messages:
            if msg.uuid in snapshots_by_message_id:
                turn.file_backups.extend(snapshots_by_message_id[msg.uuid])
        # Also check user message UUID
        if turn.user_message.uuid in snapshots_by_message_id:
            turn.file_backups.extend(snapshots_by_message_id[turn.user_message.uuid])

    return session
