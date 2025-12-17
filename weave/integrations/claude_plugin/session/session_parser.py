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
from typing import Any

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
    ".md": "text/plain",
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
    """Token usage from Claude API response.

    Each instance represents usage from one or more API requests. The `requests`
    field tracks how many requests contributed to this usage, which is important
    for accurate aggregation when summing usage across multiple assistant messages.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    requests: int = 1  # Number of API requests this usage represents

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
        """Convert to Weave's expected usage format for automatic tracking.

        Important: prompt_tokens/input_tokens should only include non-cached tokens
        for accurate cost calculation. Weave calculates cost as:
            prompt_tokens * prompt_token_cost + completion_tokens * completion_token_cost

        Cache tokens have different pricing (cache_read is ~10x cheaper) and are
        included as separate fields for informational purposes.
        """
        return {
            # For cost calculation: only non-cached input tokens
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total(),  # Informational: all tokens processed
            # Standard naming aliases
            "prompt_tokens": self.input_tokens,
            "completion_tokens": self.output_tokens,
            # Cache breakdown (informational, not used in cost calc)
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "requests": self.requests,
        }

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens
            + other.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens
            + other.cache_read_input_tokens,
            requests=self.requests + other.requests,
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
    is_error: bool = False  # True if tool_result had is_error=True
    explicit_duration_ms: int | None = None  # From toolUseResult.durationMs if available

    def duration_ms(self) -> int | None:
        """Get tool execution duration in milliseconds.

        Prefers explicit_duration_ms (from toolUseResult.durationMs) when available,
        as this is the actual execution time reported by Claude Code. Falls back to
        calculating from message timestamps (result_timestamp - timestamp).
        """
        # Prefer explicit duration from toolUseResult.durationMs (actual execution time)
        if self.explicit_duration_ms is not None:
            return self.explicit_duration_ms
        # Fall back to message timestamp delta
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
        except (FileNotFoundError, PermissionError, UnicodeDecodeError, OSError) as e:
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
    thinking_content: str | None = None

    def get_text(self) -> str:
        return "\n".join(self.text_content)


@dataclass
class UserMessage:
    """A user message."""

    uuid: str
    content: str
    timestamp: datetime.datetime
    images: list[Content] = field(default_factory=list)


@dataclass
class Turn:
    """A conversation turn: user message + assistant response(s)."""

    user_message: UserMessage
    assistant_messages: list[AssistantMessage] = field(default_factory=list)
    # Raw JSON payloads from the session file for this turn
    raw_messages: list[dict[str, Any]] = field(default_factory=list)
    # File backups associated with this turn (from file-history-snapshot)
    file_backups: list[FileBackup] = field(default_factory=list)
    # Skill expansion content (from Skill tool call result)
    skill_expansion: str | None = None

    def total_usage(self) -> TokenUsage:
        """Aggregate token usage across all assistant messages in this turn."""
        total = TokenUsage(requests=0)  # Start with zero for proper accumulation
        for msg in self.assistant_messages:
            total = total + msg.usage
        return total

    def all_tool_calls(self) -> list[ToolCall]:
        """Get all tool calls from all assistant messages."""
        calls = []
        for msg in self.assistant_messages:
            calls.extend(msg.tool_calls)
        return calls

    def grouped_tool_calls(
        self, parallel_threshold_ms: int = 1000
    ) -> list[list[ToolCall]]:
        """Group tool calls by parallel execution.

        Tool calls with timestamps within the threshold are considered parallel.
        Returns a list of groups, where each group is a list of ToolCall objects.
        Groups preserve the order of tool calls within the turn.

        Args:
            parallel_threshold_ms: Max milliseconds between tool calls to consider
                them parallel. Default 1000ms (1 second).

        Returns:
            List of tool call groups. Single-tool groups contain one ToolCall,
            parallel groups contain 2+ ToolCalls that were executed concurrently.
        """
        all_calls = self.all_tool_calls()
        if not all_calls:
            return []

        groups: list[list[ToolCall]] = []
        current_group: list[ToolCall] = [all_calls[0]]

        for tc in all_calls[1:]:
            prev_tc = current_group[-1]
            gap_ms = abs((tc.timestamp - prev_tc.timestamp).total_seconds() * 1000)

            if gap_ms <= parallel_threshold_ms:
                current_group.append(tc)
            else:
                groups.append(current_group)
                current_group = [tc]

        groups.append(current_group)
        return groups

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


def is_skill_expansion(content: str) -> bool:
    """Check if a message is a skill expansion (not a new turn).

    Skill expansions start with "Base directory for this skill:" and contain
    the skill's documentation. They should be attached to the Skill tool call
    that triggered them, not create a new turn.
    """
    if not content or not content.strip():
        return False
    return content.strip().startswith("Base directory for this skill:")


@dataclass
class Session:
    """A Claude Code session containing multiple turns."""

    session_id: str
    filename: str  # Basename of the session file
    git_branch: str | None
    cwd: str | None
    version: str | None
    turns: list[Turn] = field(default_factory=list)
    # Subagent-specific fields (only set for agent-*.jsonl files)
    agent_id: str | None = None  # e.g., "abc12345" from agent-abc12345.jsonl
    is_sidechain: bool = False  # True if this is a subagent session

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
        total = TokenUsage(requests=0)  # Start with zero for proper accumulation
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

    def get_modified_files(self) -> set[str]:
        """Get file paths that were modified during the session.

        Modified files are those that have file backups, meaning they existed
        before the session and were changed.

        Returns:
            Set of file paths that were modified
        """
        modified: set[str] = set()
        for turn in self.turns:
            for fb in turn.file_backups:
                modified.add(fb.file_path)
        return modified

    def get_created_files(self) -> set[str]:
        """Get file paths that were created during the session.

        Created files are those written via the Write tool that did NOT have
        a backup (meaning they didn't exist before the session).

        Returns:
            Set of file paths that were created
        """
        modified = self.get_modified_files()
        created: set[str] = set()

        for turn in self.turns:
            for tc in turn.all_tool_calls():
                if tc.name == "Write":
                    file_path = tc.input.get("file_path", "")
                    if file_path and file_path not in modified:
                        created.add(file_path)
        return created

    def get_all_changed_files(self) -> set[str]:
        """Get all file paths that were created or modified during the session.

        Returns:
            Set of all changed file paths (union of created and modified)
        """
        return self.get_created_files() | self.get_modified_files()


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
                            except (ValueError, TypeError) as e:
                                logger.debug(f"Failed to parse backup timestamp '{backup_time_str}': {e}")
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
                        # Subagent-specific fields
                        "agentId": obj.get("agentId"),
                        "isSidechain": obj.get("isSidechain", False),
                    }
                elif session_info:
                    # Update fields that may have been None in the first message
                    if not session_info.get("cwd") and obj.get("cwd"):
                        session_info["cwd"] = obj.get("cwd")
                    if not session_info.get("gitBranch") and obj.get("gitBranch"):
                        session_info["gitBranch"] = obj.get("gitBranch")

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
        agent_id=session_info.get("agentId"),
        is_sidechain=session_info.get("isSidechain", False),
    )

    pending_tool_calls: dict[str, ToolCall] = {}
    current_turn: Turn | None = None

    for msg in messages:
        msg_type = msg.get("type")
        timestamp = parse_timestamp(msg.get("timestamp", "1970-01-01T00:00:00Z"))

        if msg_type == "user":
            user_content = ""
            user_images: list[Content] = []
            msg_data = msg.get("message", {})
            content = msg_data.get("content", "")

            if isinstance(content, str):
                user_content = content
            elif isinstance(content, list):
                text_parts = []
                for c in content:
                    if c.get("type") == "text":
                        text_parts.append(c.get("text", ""))
                    elif c.get("type") == "image":
                        # Extract image from base64 source
                        source = c.get("source", {})
                        if source.get("type") == "base64" and source.get("data"):
                            try:
                                image_content = Content.from_base64(
                                    source["data"],
                                    mimetype=source.get("media_type"),
                                )
                                user_images.append(image_content)
                            except (ValueError, TypeError, KeyError) as e:
                                logger.debug(f"Failed to parse image: {e}")
                    elif c.get("type") == "tool_result":
                        tool_use_id = c.get("tool_use_id")
                        if tool_use_id in pending_tool_calls:
                            tc = pending_tool_calls[tool_use_id]
                            result_content = c.get("content", "")
                            # Handle both string and list-format tool results
                            if isinstance(result_content, str):
                                tc.result = result_content[:10000]
                            elif isinstance(result_content, list):
                                # List of content blocks - extract text from each
                                text_parts_result = []
                                for block in result_content:
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        text_parts_result.append(block.get("text", ""))
                                tc.result = "\n".join(text_parts_result)[:10000]
                            tc.result_timestamp = timestamp
                            # Capture error status from tool_result
                            tc.is_error = c.get("is_error", False)
                            # Extract explicit duration from toolUseResult if available
                            # This is the actual tool execution time reported by Claude Code
                            tool_use_result = msg.get("toolUseResult", {})
                            if isinstance(tool_use_result, dict):
                                explicit_duration = tool_use_result.get("durationMs")
                                if explicit_duration is not None:
                                    tc.explicit_duration_ms = explicit_duration
                user_content = "\n".join(text_parts)

            # Only create a new turn if there's actual user text content
            # (not just tool results, empty messages, system messages, or skill expansions)
            if user_content.strip() and not is_system_message(user_content) and not is_skill_expansion(user_content):
                if current_turn:
                    session.turns.append(current_turn)
                current_turn = Turn(
                    user_message=UserMessage(
                        uuid=msg.get("uuid", ""),
                        content=user_content,
                        timestamp=timestamp,
                        images=user_images,
                    ),
                    raw_messages=[msg],  # Start collecting raw payloads
                )
            elif current_turn:
                # Tool result messages and skill expansions belong to current turn
                current_turn.raw_messages.append(msg)
                # Store skill expansion content for later attachment to Skill tool call
                if is_skill_expansion(user_content):
                    current_turn.skill_expansion = user_content

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
            thinking_content = None

            if isinstance(content, list):
                for c in content:
                    if c.get("type") == "text":
                        text_content.append(c.get("text", ""))
                    elif c.get("type") == "thinking":
                        thinking_content = c.get("thinking", "")
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
                thinking_content=thinking_content,
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
