"""Shared utilities for Claude Code plugin.

This module provides common utilities used by both the real-time hook
handlers and the batch import script.
"""

from __future__ import annotations

import logging
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import weave
from weave.integrations.claude_plugin.constants import (
    DaemonConfig,
    ParallelGrouping,
    PromptLimits,
    ToolCallLimits,
)
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.view_utils import set_call_view

if TYPE_CHECKING:
    from weave.integrations.claude_plugin.session.session_parser import ToolCall
    from weave.trace.call import Call

logger = logging.getLogger(__name__)

# Re-export constants for backward compatibility
MAX_TOOL_INPUT_LENGTH = ToolCallLimits.MAX_INPUT_LENGTH
MAX_TOOL_OUTPUT_LENGTH = ToolCallLimits.MAX_OUTPUT_LENGTH
MAX_PROMPT_LENGTH = PromptLimits.MAX_PROMPT_LENGTH
DAEMON_STARTUP_TIMEOUT = DaemonConfig.STARTUP_TIMEOUT_SECONDS
INACTIVITY_TIMEOUT = DaemonConfig.INACTIVITY_TIMEOUT_SECONDS
SUBAGENT_DETECTION_TIMEOUT = DaemonConfig.SUBAGENT_DETECTION_TIMEOUT_SECONDS

# Boilerplate phrases to remove from subagent prompts for cleaner display names
# These are replaced (not just prefix-stripped) to preserve meaningful parts
# e.g., "Review the implementation of X" → "Review X"
SUBAGENT_BOILERPLATE_REPLACEMENTS = [
    # Remove "the implementation of/the implementation" but keep surrounding words
    # Order matters - check longer patterns first
    (" the implementation of ", " "),
    (" the implementation", ""),  # Handles end-of-string case
    # Remove "You are implementing" entirely (no useful context)
    ("You are implementing ", ""),
    ("You are ", ""),
    # Remove filler phrases
    ("Please implement ", "Implement "),
    ("Please review ", "Review "),
    ("Your task is to ", ""),
    ("Your task: ", ""),
]


# Regex patterns for extracting command info from XML-tagged messages
_COMMAND_NAME_PATTERN = re.compile(r"<command-name>([^<]+)</command-name>")
_COMMAND_MESSAGE_PATTERN = re.compile(r"<command-message>([^<]+)</command-message>")
_COMMAND_OUTPUT_PATTERN = re.compile(
    r"<local-command-(stdout|stderr)>([^<]*)</local-command-(?:stdout|stderr)>"
)
# Pattern to extract content from any XML tag for display names
_XML_TAG_CONTENT_PATTERN = re.compile(r"<([a-z-]+)>([^<]*)</\1>")


def extract_slash_command(text: str) -> str | None:
    """Extract slash command name from XML-tagged message.

    Tries <command-name> first, then falls back to <command-message>.
    Handles formats like:
    - <command-name>/weave:feedback</command-name>
    - <command-message>weave:feedback is running...</command-message>

    Args:
        text: Message content that may contain command XML tags

    Returns:
        The command name (e.g., "/weave:feedback") or None if not a command message
    """
    if not text:
        return None

    # Try <command-name> first (contains the actual /command)
    match = _COMMAND_NAME_PATTERN.search(text)
    if match:
        return match.group(1).strip()

    # Fall back to <command-message> (may need to add / prefix)
    match = _COMMAND_MESSAGE_PATTERN.search(text)
    if match:
        cmd = match.group(1).strip()
        # Remove "is running..." suffix if present
        if " is running" in cmd:
            cmd = cmd.split(" is running")[0].strip()
        # Add / prefix if not present
        if cmd and not cmd.startswith("/"):
            cmd = "/" + cmd
        return cmd

    return None


def extract_xml_tag_content(text: str) -> str | None:
    """Extract content from XML-tagged messages for display.

    Handles messages like:
    - <local-command-stdout>See ya!</local-command-stdout>
    - <command-message>weave:feedback is running...</command-message>

    Args:
        text: Message content that may contain XML tags

    Returns:
        The extracted content, or None if not an XML-tagged message
    """
    if not text:
        return None

    text_stripped = text.strip()
    if not text_stripped.startswith("<"):
        return None

    match = _XML_TAG_CONTENT_PATTERN.search(text_stripped)
    if match:
        return match.group(2).strip()

    return None


def get_subagent_display_name(
    prompt: str,
    agent_id: str | None = None,
    max_len: int = 50,
) -> str:
    """Generate a clean display name for a subagent.

    Removes common boilerplate phrases from the prompt to show more
    meaningful content in the limited display space.

    Examples:
        "Review the implementation of auth flow" → "SubAgent: Review auth flow"
        "You are implementing a new feature" → "SubAgent: a new feature"

    Args:
        prompt: The subagent's full prompt/task description
        agent_id: Optional agent ID to use as fallback
        max_len: Maximum length for the display name preview

    Returns:
        Display name like "SubAgent: Review auth flow" or "SubAgent: abc123"
    """
    if prompt:
        cleaned = prompt.strip()
        # Apply boilerplate replacements (case-insensitive)
        for pattern, replacement in SUBAGENT_BOILERPLATE_REPLACEMENTS:
            # Case-insensitive replacement
            lower_cleaned = cleaned.lower()
            lower_pattern = pattern.lower()
            if lower_pattern in lower_cleaned:
                idx = lower_cleaned.index(lower_pattern)
                cleaned = cleaned[:idx] + replacement + cleaned[idx + len(pattern) :]

        # Clean up any double spaces and strip
        cleaned = " ".join(cleaned.split()).strip()

        # Truncate the cleaned prompt
        preview = truncate(cleaned, max_len) or cleaned[:max_len]
        if preview:
            return f"SubAgent: {preview}"

    # Fall back to agent ID if no meaningful prompt
    if agent_id:
        return f"SubAgent: {agent_id}"

    return "SubAgent"


def get_turn_display_name(
    turn_number: int,
    user_prompt: str,
    in_response_to: str | None = None,
) -> str:
    """Generate a clean display name for a turn.

    Handles special cases like slash commands, XML tags, and Q&A flows
    to provide meaningful display names.

    Args:
        turn_number: The turn number (1-indexed)
        user_prompt: The raw user prompt text
        in_response_to: Full assistant context for Q&A flows (may contain full message)

    Returns:
        Display name like "Turn 1: /plugin", "Q&A 2: Which file?", etc.
    """
    # Q&A flow - extract question from context for display name
    if in_response_to:
        # Extract just the question for the display name
        question = extract_question_from_text(in_response_to)
        question_preview = truncate(question or in_response_to, 50)
        return f"Q&A {turn_number}: {question_preview}"

    # Check if this is a slash command message
    slash_command = extract_slash_command(user_prompt)
    if slash_command:
        return f"Turn {turn_number}: {slash_command}"

    # Check if this is an XML-tagged message (e.g., <local-command-stdout>)
    xml_content = extract_xml_tag_content(user_prompt)
    if xml_content:
        turn_preview = truncate(xml_content, 50) or f"Turn {turn_number}"
        return f"Turn {turn_number}: {turn_preview}"

    # Regular prompt - truncate to 50 chars
    turn_preview = truncate(user_prompt, 50) or f"Turn {turn_number}"
    return f"Turn {turn_number}: {turn_preview}"


def is_command_output(text: str) -> bool:
    """Check if text is a command output message.

    Args:
        text: Message content to check

    Returns:
        True if this is a <local-command-stdout> or <local-command-stderr> message
    """
    if not text:
        return False
    text_stripped = text.strip()
    return text_stripped.startswith(
        ("<local-command-stdout>", "<local-command-stderr>")
    )


def extract_command_output(text: str) -> str:
    """Extract content from command output XML tags.

    Args:
        text: Message with <local-command-stdout>content</local-command-stdout>

    Returns:
        The extracted content, or empty string if no match
    """
    if not text:
        return ""
    match = _COMMAND_OUTPUT_PATTERN.search(text)
    if match:
        return match.group(2).strip()
    return ""


def truncate(
    s: str | None, max_len: int = ToolCallLimits.MAX_INPUT_LENGTH
) -> str | None:
    """Truncate a string to max_len characters.

    Args:
        s: String to truncate
        max_len: Maximum length (default 5000)

    Returns:
        Truncated string with "...[truncated]" suffix, or None if input is None
    """
    if s is None:
        return None
    if len(s) <= max_len:
        return s
    return s[:max_len] + "...[truncated]"


def sanitize_tool_input(
    tool_input: dict[str, Any],
    max_length: int = ToolCallLimits.MAX_INPUT_LENGTH,
) -> dict[str, Any]:
    """Sanitize tool input by truncating long string values.

    Args:
        tool_input: Dictionary of tool input parameters
        max_length: Maximum length for string values (default ToolCallLimits.MAX_INPUT_LENGTH)

    Returns:
        New dictionary with long strings truncated
    """
    sanitized = {}
    for k, v in tool_input.items():
        if isinstance(v, str) and len(v) > max_length:
            sanitized[k] = truncate(v, max_length)
        else:
            sanitized[k] = v
    return sanitized


def reconstruct_call(
    project_id: str,
    call_id: str | None,
    trace_id: str | None,
    parent_id: str | None = None,
) -> Call:
    """Reconstruct a minimal Call object for use as a parent reference.

    This creates a Call object that can be used as a parent for weave.log_call()
    without needing the full call data. Used when logging child calls to an
    existing trace.

    Args:
        project_id: Weave project ID (e.g., "entity/project")
        call_id: The call ID to reconstruct (must not be None)
        trace_id: The trace ID this call belongs to (must not be None)
        parent_id: Optional parent call ID

    Returns:
        Call object suitable for use as parent in weave.log_call()

    Raises:
        ValueError: If call_id or trace_id is None
    """
    if call_id is None:
        raise ValueError("call_id is required to reconstruct a Call")
    if trace_id is None:
        raise ValueError("trace_id is required to reconstruct a Call")

    from weave.trace.call import Call

    return Call(
        _op_name="",
        project_id=project_id,
        trace_id=trace_id,
        parent_id=parent_id,
        inputs={},
        id=call_id,
    )


class ToolCallError(Exception):
    """Exception raised when a tool call fails."""

    pass


class SessionParseError(Exception):
    """Exception raised when session parsing fails."""

    pass


class FileBackupError(Exception):
    """Exception raised when file backup operations fail."""

    pass


class DaemonConnectionError(Exception):
    """Exception raised when daemon socket connection fails."""

    pass


@dataclass
class BufferedToolResult:
    """A tool result waiting to be logged with parallel grouping.

    Replaces the fragile tuple-based buffering:
    (name, input, tool_use_timestamp, result_content, is_error)
    """

    tool_use_id: str
    name: str
    input: dict[str, Any]
    timestamp: datetime  # When tool_use was sent (from assistant message)
    result: str
    result_timestamp: datetime  # When tool_result was received (from user message)
    is_error: bool = False


class ToolResultBuffer:
    """Buffer for tool results enabling parallel grouping detection.

    Tools are buffered until "aged" to allow parallel tool results to arrive
    before committing to grouping decisions. Tools within PARALLEL_THRESHOLD_MS
    of each other are considered parallel and logged under a wrapper call.

    Usage:
        buffer = ToolResultBuffer()
        buffer.add(tool_use_id, name, input, timestamp, result, is_error)

        # Periodically flush aged results
        ready = buffer.get_ready_to_flush()
        for group in ready:
            log_group(group)
        buffer.remove(ready)

        # At turn end, flush everything
        ready = buffer.get_ready_to_flush(force=True)
    """

    TOOL_AGE_THRESHOLD_MS = ParallelGrouping.TOOL_AGE_THRESHOLD_MS
    PARALLEL_THRESHOLD_MS = ParallelGrouping.THRESHOLD_MS

    def __init__(self) -> None:
        self._buffer: dict[str, BufferedToolResult] = {}

    def add(
        self,
        tool_use_id: str,
        name: str,
        input: dict[str, Any],
        timestamp: datetime,
        result: str,
        result_timestamp: datetime,
        is_error: bool = False,
    ) -> None:
        """Add a tool result to the buffer."""
        self._buffer[tool_use_id] = BufferedToolResult(
            tool_use_id=tool_use_id,
            name=name,
            input=input,
            timestamp=timestamp,
            result=result,
            result_timestamp=result_timestamp,
            is_error=is_error,
        )

    def is_empty(self) -> bool:
        """Check if buffer has any results."""
        return len(self._buffer) == 0

    def clear(self) -> None:
        """Clear all buffered results."""
        self._buffer.clear()

    def get_ready_to_flush(self, force: bool = False) -> list[list[BufferedToolResult]]:
        """Get tool result groups ready to be logged.

        Args:
            force: If True, return all buffered results (used at turn end)

        Returns:
            List of groups. Each group is a list of BufferedToolResult objects
            that should be logged together (parallel if len > 1).
        """
        if not self._buffer:
            return []

        now = datetime.now(timezone.utc)

        if force:
            # Return all buffered results
            ready = list(self._buffer.values())
        else:
            # Smart aging: only flush tools that are aged AND in complete groups
            all_tools = sorted(self._buffer.values(), key=lambda x: x.timestamp)

            # Find oldest tool's age
            oldest_age_ms = (now - all_tools[0].timestamp).total_seconds() * 1000
            if oldest_age_ms <= self.TOOL_AGE_THRESHOLD_MS:
                return []  # Nothing aged yet

            # Find all tools in the same parallel group as oldest
            ready = [all_tools[0]]
            for tool in all_tools[1:]:
                prev_ts = ready[-1].timestamp
                gap_ms = (tool.timestamp - prev_ts).total_seconds() * 1000
                if gap_ms <= self.PARALLEL_THRESHOLD_MS:
                    ready.append(tool)
                else:
                    break

            # Check if ALL tools in group are aged
            newest_age_ms = (now - ready[-1].timestamp).total_seconds() * 1000
            if newest_age_ms <= self.TOOL_AGE_THRESHOLD_MS:
                return []  # Not all aged yet

        if not ready:
            return []

        # Group by timestamp proximity
        ready.sort(key=lambda x: x.timestamp)
        groups: list[list[BufferedToolResult]] = []
        current_group: list[BufferedToolResult] = [ready[0]]

        for tool in ready[1:]:
            prev_ts = current_group[-1].timestamp
            gap_ms = abs((tool.timestamp - prev_ts).total_seconds() * 1000)

            if gap_ms <= self.PARALLEL_THRESHOLD_MS:
                current_group.append(tool)
            else:
                groups.append(current_group)
                current_group = [tool]
        groups.append(current_group)

        return groups

    def remove(self, groups: list[list[BufferedToolResult]]) -> None:
        """Remove flushed results from buffer."""
        for group in groups:
            for tool in group:
                self._buffer.pop(tool.tool_use_id, None)


def log_tool_call(
    tool_name: str,
    tool_input: dict[str, Any],
    tool_output: str | None,
    tool_use_id: str,
    duration_ms: int | None,
    parent: Any,
    max_input_length: int = ToolCallLimits.MAX_INPUT_LENGTH,
    max_output_length: int = ToolCallLimits.MAX_OUTPUT_LENGTH,
    *,
    # Edit tool specific data for generating HTML diff views
    original_file: str | None = None,
    structured_patch: list[dict[str, Any]] | None = None,
    # Timestamp overrides for retroactive logging (e.g., session import)
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    # Error handling
    is_error: bool = False,
) -> Any:
    """Log a tool call to Weave with standardized formatting.

    This is the single source of truth for tool call logging format.
    All tool calls (daemon, handlers, real-time, turn finish) should use this.

    For TodoWrite calls, also attaches an HTML view showing the todo list state.
    For Edit calls with structured patch data, generates an HTML diff view.

    Args:
        tool_name: Name of the tool (e.g., "Read", "Grep", "Bash")
        tool_input: Tool input parameters
        tool_output: Tool output/result (can be None)
        tool_use_id: Unique ID for this tool invocation
        duration_ms: How long the tool call took in milliseconds
        parent: Parent Call object for trace hierarchy
        max_input_length: Max length for input string values
        max_output_length: Max length for output string
        original_file: For Edit calls, the original file content before edit
        structured_patch: For Edit calls, the structured patch data from toolUseResult
        started_at: Optional timestamp for when the tool call started (for retroactive logging)
        ended_at: Optional timestamp for when the tool call ended (for retroactive logging)
        is_error: If True, mark the call as failed with an exception

    Returns:
        The created Call object
    """
    # Sanitize inputs
    sanitized_input = sanitize_tool_input(tool_input, max_input_length)

    # Generate display name
    tool_display = get_tool_display_name(tool_name, tool_input)

    # Build output dict
    output = (
        {"result": truncate(tool_output, max_output_length)} if tool_output else None
    )

    # Create exception if this is an error
    exception: BaseException | None = None
    if is_error:
        # Extract error message from tool_output (strip <tool_use_error> tags if present)
        error_msg = tool_output or "Tool call failed"
        if error_msg.startswith("<tool_use_error>") and error_msg.endswith(
            "</tool_use_error>"
        ):
            error_msg = error_msg[16:-17]  # Strip tags
        exception = ToolCallError(error_msg)

    # For tools with HTML views (TodoWrite, Edit), we need to attach the view
    # BEFORE finishing the call, so we use create_call + set_call_view + finish_call
    needs_html_view = tool_name == "TodoWrite" or (
        tool_name == "Edit" and structured_patch is not None
    )

    if needs_html_view:
        try:
            client = require_weave_client()

            # Create the call (but don't finish yet)
            call = client.create_call(
                op=f"claude_code.tool.{tool_name}",
                inputs=sanitized_input,
                attributes={
                    "tool_name": tool_name,
                    "tool_use_id": tool_use_id,
                    "duration_ms": duration_ms,
                },
                display_name=tool_display,
                parent=parent,
                use_stack=False,
                started_at=started_at,
            )

            # Attach HTML view BEFORE finishing
            if tool_name == "TodoWrite":
                from weave.integrations.claude_plugin.views.diff_view import (
                    generate_todo_html,
                )

                todos = tool_input.get("todos", [])
                if todos:
                    html = generate_todo_html(todos)
                    if html:
                        set_call_view(
                            call=call,
                            client=client,
                            name="todos",
                            content=html,
                            extension="html",
                            mimetype="text/html",
                        )

            elif tool_name == "Edit" and structured_patch:
                from weave.integrations.claude_plugin.views.diff_view import (
                    generate_edit_diff_html,
                )

                file_path = tool_input.get("file_path", "unknown")
                html = generate_edit_diff_html(
                    file_path=file_path,
                    original_content=original_file or "",
                    structured_patch=structured_patch,
                )
                if html:
                    set_call_view(
                        call=call,
                        client=client,
                        name="file_diff",
                        content=html,
                        extension="html",
                        mimetype="text/html",
                    )

            # Now finish the call (with exception if error)
            client.finish_call(
                call, output=output, exception=exception, ended_at=ended_at
            )
        except Exception as e:
            logger.debug(f"Failed to log {tool_name} with view: {e}")
            # Fallback to regular log_call if something goes wrong
            return weave.log_call(
                op=f"claude_code.tool.{tool_name}",
                inputs=sanitized_input,
                output=output,
                attributes={
                    "tool_name": tool_name,
                    "tool_use_id": tool_use_id,
                    "duration_ms": duration_ms,
                },
                display_name=tool_display,
                parent=parent,
                use_stack=False,
                exception=exception,
                started_at=started_at,
                ended_at=ended_at,
            )
        else:
            return call
    else:
        return weave.log_call(
            op=f"claude_code.tool.{tool_name}",
            inputs=sanitized_input,
            output=output,
            attributes={
                "tool_name": tool_name,
                "tool_use_id": tool_use_id,
                "duration_ms": duration_ms,
            },
            display_name=tool_display,
            parent=parent,
            use_stack=False,
            exception=exception,
            started_at=started_at,
            ended_at=ended_at,
        )


def _generate_session_name_claude(user_prompt: str) -> str | None:
    """Generate session name using Claude API (same as Claude Code CLI).

    Uses the Claude Code OAuth credentials to call the Anthropic API
    with the same session title logic as the CLI.

    Args:
        user_prompt: The user message to analyze

    Returns:
        Session title string, or None if generation failed
    """
    try:
        from weave.integrations.claude_plugin.session.session_title import (
            generate_session_title,
        )

        return generate_session_title(user_prompt, timeout=10.0)
    except Exception as e:
        logger.debug(f"Claude session title generation failed: {e}")
        return None


def _generate_session_name_ollama(
    user_prompt: str,
    model: str = "hf.co/vanpelt/catnip-summarizer:latest",
) -> tuple[str, str] | None:
    """Generate session name using local Ollama model.

    Args:
        user_prompt: The user message to summarize
        model: Ollama model to use

    Returns:
        Tuple of (display_name, suggested_branch) or None if failed
    """
    try:
        # Truncate prompt if too long
        prompt = user_prompt[:2000] if len(user_prompt) > 2000 else user_prompt

        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            display_name = lines[0].strip() if lines else None
            suggested_branch = lines[1].strip() if len(lines) > 1 else ""
            if display_name:
                return display_name, suggested_branch

    except subprocess.TimeoutExpired:
        logger.debug("Ollama summarizer timed out")
    except FileNotFoundError:
        logger.debug("Ollama not found")
    except Exception as e:
        logger.debug(f"Ollama error: {e}")

    return None


def get_tool_display_name(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Generate a meaningful display name for a tool call.

    Args:
        tool_name: Name of the tool (e.g., "Read", "Grep", "Edit")
        tool_input: Input parameters to the tool

    Returns:
        Human-readable display name
    """
    if tool_name == "Read":
        path = tool_input.get("file_path", "")
        if path:
            filename = Path(path).name
            return f"Read: {filename}"
    elif tool_name == "Grep":
        pattern = tool_input.get("pattern", "")
        if pattern:
            return f"Grep: {pattern[:30]}"
    elif tool_name == "Glob":
        pattern = tool_input.get("pattern", "")
        if pattern:
            return f"Glob: {pattern}"
    elif tool_name == "Edit":
        path = tool_input.get("file_path", "")
        if path:
            filename = Path(path).name
            return f"Edit: {filename}"
    elif tool_name == "Write":
        path = tool_input.get("file_path", "")
        if path:
            filename = Path(path).name
            return f"Write: {filename}"
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if cmd:
            first_word = cmd.split()[0] if cmd.split() else cmd
            return f"Bash: {first_word}"
    elif tool_name == "Task":
        desc = tool_input.get("description", "")
        if desc:
            return f"Task: {desc[:30]}"
    elif tool_name == "WebFetch":
        url = tool_input.get("url", "")
        if url:
            try:
                domain = urlparse(url).netloc
            except Exception:
                pass
            else:
                return f"WebFetch: {domain}"
    elif tool_name == "WebSearch":
        query = tool_input.get("query", "")
        if query:
            return f"WebSearch: {query[:30]}"
    elif tool_name == "Skill":
        skill = tool_input.get("skill", "")
        if skill:
            return f"Skill: {skill}"
    elif tool_name == "SlashCommand":
        command = tool_input.get("command", "")
        if command:
            return f"SlashCommand: {command[:30]}"

    return tool_name


def get_git_info(cwd: str) -> dict[str, str] | None:
    """Get git remote, branch, and commit for a directory.

    Args:
        cwd: Directory path to check for git info

    Returns:
        Dict with 'remote', 'branch', 'commit' keys, or None if not a git repo
    """
    result: dict[str, str] | None = None
    try:
        # Check if directory exists
        if not Path(cwd).exists():
            return None

        # Get origin remote URL
        remote_result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if remote_result.returncode != 0:
            return None
        remote = remote_result.stdout.strip()

        # Get current branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if branch_result.returncode != 0:
            return None
        branch = branch_result.stdout.strip()

        # Get HEAD commit SHA
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if commit_result.returncode != 0:
            return None
        commit = commit_result.stdout.strip()

        result = {
            "remote": remote,
            "branch": branch,
            "commit": commit,
        }
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug(f"Failed to get git info for {cwd}: {e}")
    return result


def extract_question_from_text(text: str) -> str | None:
    """Extract the trailing question from assistant text output.

    Used for Q&A context tracking - when an assistant response ends with a
    question, we want to capture it so it can be added as context to the
    next turn's input (via 'in_response_to' field).

    Handles multiple patterns:
    1. "**Next question:**" or "**Last question:**" marker - extracts the question after this marker
    2. Last paragraph ending with "?" - extracts up to and including the first "?"

    Args:
        text: Assistant text output

    Returns:
        The trailing question if found, or None
    """
    if not text or not text.strip():
        return None

    text = text.strip()
    lower_text = text.lower()

    # Pattern 1: Check for question markers (case-insensitive)
    question_markers = ["**next question:**", "**last question:**"]
    for marker in question_markers:
        if marker in lower_text:
            # Find the marker position in original text
            marker_pos = lower_text.index(marker)
            after_marker = text[marker_pos + len(marker) :]

            # Find the first line with a question mark after the marker
            for line in after_marker.split("\n"):
                line = line.strip()
                if "?" in line:
                    question_end = line.index("?") + 1
                    question = line[:question_end].strip()
                    # Clean up markdown formatting
                    question = _clean_markdown_formatting(question)
                    if question:
                        return question

    # Pattern 2: Fall back to last paragraph
    paragraphs = text.split("\n\n")
    last_para = paragraphs[-1].strip()

    # Check if last paragraph contains a question
    if "?" not in last_para:
        return None

    # Extract up to and including the question mark
    question_end = last_para.index("?") + 1
    question = last_para[:question_end].strip()

    # Clean up markdown formatting
    question = _clean_markdown_formatting(question)

    return question if question else None


def _clean_markdown_formatting(text: str) -> str:
    """Remove markdown formatting from text."""
    if not text:
        return text
    # Remove leading **
    if text.startswith("**"):
        text = text[2:]
    # Remove all remaining **
    text = text.replace("**", "")
    return text.strip()


def generate_session_name(
    user_prompt: str,
    ollama_model: str = "hf.co/vanpelt/catnip-summarizer:latest",
) -> tuple[str, str]:
    """Generate a nice session name and suggested branch.

    Tries multiple methods in order:
    1. Claude API (uses same logic as Claude Code CLI)
    2. Local Ollama model
    3. Fallback to truncating the prompt

    Args:
        user_prompt: The user message to summarize
        ollama_model: Ollama model to use if Claude unavailable

    Returns:
        Tuple of (display_name, suggested_branch_name)
    """
    # Try Claude API first (same as Claude Code CLI)
    claude_title = _generate_session_name_claude(user_prompt)
    if claude_title:
        logger.debug(f"Generated session title via Claude API: {claude_title}")
        return claude_title, ""

    # Try Ollama as fallback
    ollama_result = _generate_session_name_ollama(user_prompt, ollama_model)
    if ollama_result:
        logger.debug(f"Generated session title via Ollama: {ollama_result[0]}")
        return ollama_result

    # Final fallback: use first 50 chars of prompt
    fallback_name = user_prompt[:50].replace("\n", " ").strip()
    if len(user_prompt) > 50:
        fallback_name += "..."
    logger.debug(f"Using fallback session title: {fallback_name}")
    return fallback_name or "Claude Session", ""


def _generate_parallel_display_name(tool_calls: list[ToolCall]) -> str:
    """Generate a display name for a parallel execution group.

    Examples:
        - ["Read", "Read"] -> "Parallel (Read x2)"
        - ["Read", "Grep", "Glob"] -> "Parallel (Read, Grep, Glob)"
        - ["Read", "Read", "Grep"] -> "Parallel (Read x2, Grep)"

    Args:
        tool_calls: List of tool calls in the parallel group

    Returns:
        Human-readable display name
    """
    counts = Counter(tc.name for tc in tool_calls)

    parts = []
    for name, count in counts.most_common():
        if count > 1:
            parts.append(f"{name} x{count}")
        else:
            parts.append(name)

    return f"Parallel ({', '.join(parts)})"


def log_tool_calls_grouped(
    tool_call_groups: list[list[ToolCall]],
    parent: Any,
    *,
    skip_tool_names: set[str] | None = None,
    skip_subagent_tasks: bool = True,
    edit_data_by_path: dict[str, dict] | None = None,
) -> int:
    """Log tool calls with parallel grouping.

    Tool calls in groups of 2+ are wrapped in a `claude_code.parallel` parent call
    to visually indicate parallel execution.

    Args:
        tool_call_groups: Groups of tool calls from Turn.grouped_tool_calls()
        parent: Parent Call object (typically the turn call)
        skip_tool_names: Tool names to skip entirely (e.g., {"EnterPlanMode"})
        skip_subagent_tasks: If True, skip Task tools that have subagent_type
            (these spawn subagent calls and are handled separately)
        edit_data_by_path: Optional map of file_path -> edit data for Edit tool diffs

    Returns:
        Number of calls created (including parallel wrappers)
    """
    skip_names = skip_tool_names or set()
    edit_data = edit_data_by_path or {}
    calls_created = 0

    def should_skip(tc: ToolCall) -> bool:
        """Check if a tool call should be skipped."""
        if tc.name in skip_names:
            return True
        # Skip Task tools that spawn subagents (handled separately)
        if skip_subagent_tasks and tc.name == "Task" and tc.input.get("subagent_type"):
            return True
        return False

    for group in tool_call_groups:
        # Filter out skipped tools
        filtered_group = [tc for tc in group if not should_skip(tc)]
        if not filtered_group:
            continue

        if len(filtered_group) == 1:
            # Single tool - log directly under parent
            tc = filtered_group[0]
            original_file = None
            structured_patch = None
            if tc.name == "Edit":
                file_path = tc.input.get("file_path")
                if file_path and file_path in edit_data:
                    original_file = edit_data[file_path].get("original_file")
                    structured_patch = edit_data[file_path].get("structured_patch")

            log_tool_call(
                tool_name=tc.name,
                tool_input=tc.input or {},
                tool_output=tc.result,
                tool_use_id=tc.id,
                duration_ms=tc.duration_ms(),
                parent=parent,
                original_file=original_file,
                structured_patch=structured_patch,
                started_at=tc.timestamp,
                ended_at=tc.result_timestamp,
                is_error=tc.is_error,
            )
            calls_created += 1
        else:
            # Multiple tools - create parallel wrapper
            client = require_weave_client()

            # Calculate timing for the parallel group
            started_at = min(tc.timestamp for tc in filtered_group)
            result_timestamps = [
                tc.result_timestamp for tc in filtered_group if tc.result_timestamp
            ]
            ended_at = max(result_timestamps) if result_timestamps else None

            # Create parallel wrapper call
            display_name = _generate_parallel_display_name(filtered_group)
            parallel_call = client.create_call(
                op="claude_code.parallel",
                inputs={
                    "tool_count": len(filtered_group),
                    "tools": [tc.name for tc in filtered_group],
                },
                parent=parent,
                display_name=display_name,
                attributes={"is_parallel_group": True},
                use_stack=False,
                started_at=started_at,
            )
            calls_created += 1

            # Log each tool as child of parallel wrapper
            for tc in filtered_group:
                original_file = None
                structured_patch = None
                if tc.name == "Edit":
                    file_path = tc.input.get("file_path")
                    if file_path and file_path in edit_data:
                        original_file = edit_data[file_path].get("original_file")
                        structured_patch = edit_data[file_path].get("structured_patch")

                log_tool_call(
                    tool_name=tc.name,
                    tool_input=tc.input or {},
                    tool_output=tc.result,
                    tool_use_id=tc.id,
                    duration_ms=tc.duration_ms(),
                    parent=parallel_call,
                    original_file=original_file,
                    structured_patch=structured_patch,
                    started_at=tc.timestamp,
                    ended_at=tc.result_timestamp,
                    is_error=tc.is_error,
                )
                calls_created += 1

            # Finish parallel wrapper
            client.finish_call(
                parallel_call,
                output={"completed": len(filtered_group)},
                ended_at=ended_at,
            )

    return calls_created
