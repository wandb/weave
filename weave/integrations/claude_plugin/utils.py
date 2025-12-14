"""Shared utilities for Claude Code plugin.

This module provides common utilities used by both the real-time hook
handlers and the batch import script.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import weave
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.view_utils import set_call_view

logger = logging.getLogger(__name__)

# Truncation limits for tool call logging
MAX_TOOL_INPUT_LENGTH = 5000
MAX_TOOL_OUTPUT_LENGTH = 10000
MAX_PROMPT_LENGTH = 2000

# Timeout values (seconds)
DAEMON_STARTUP_TIMEOUT = 3.0
INACTIVITY_TIMEOUT = 600
SUBAGENT_DETECTION_TIMEOUT = 10


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


def get_turn_display_name(turn_number: int, user_prompt: str) -> str:
    """Generate a clean display name for a turn.

    Handles special cases like slash commands and XML tags to avoid showing
    raw XML in display names.

    Args:
        turn_number: The turn number (1-indexed)
        user_prompt: The raw user prompt text

    Returns:
        Display name like "Turn 1: /plugin" or "Turn 2: Fix the bug..."
    """
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


def truncate(s: str | None, max_len: int = MAX_TOOL_INPUT_LENGTH) -> str | None:
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
    max_length: int = MAX_TOOL_INPUT_LENGTH,
) -> dict[str, Any]:
    """Sanitize tool input by truncating long string values.

    Args:
        tool_input: Dictionary of tool input parameters
        max_length: Maximum length for string values (default MAX_TOOL_INPUT_LENGTH)

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
    call_id: str,
    trace_id: str,
    parent_id: str | None = None,
) -> "Call":
    """Reconstruct a minimal Call object for use as a parent reference.

    This creates a Call object that can be used as a parent for weave.log_call()
    without needing the full call data. Used when logging child calls to an
    existing trace.

    Args:
        project_id: Weave project ID (e.g., "entity/project")
        call_id: The call ID to reconstruct
        trace_id: The trace ID this call belongs to
        parent_id: Optional parent call ID

    Returns:
        Call object suitable for use as parent in weave.log_call()
    """
    from weave.trace.call import Call

    return Call(
        _op_name="",
        project_id=project_id,
        trace_id=trace_id,
        parent_id=parent_id,
        inputs={},
        id=call_id,
    )


def log_tool_call(
    tool_name: str,
    tool_input: dict[str, Any],
    tool_output: str | None,
    tool_use_id: str,
    duration_ms: int,
    parent: Any,
    max_input_length: int = MAX_TOOL_INPUT_LENGTH,
    max_output_length: int = MAX_TOOL_OUTPUT_LENGTH,
    *,
    # Edit tool specific data for generating HTML diff views
    original_file: str | None = None,
    structured_patch: list[dict[str, Any]] | None = None,
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

    Returns:
        The created Call object
    """
    # Sanitize inputs
    sanitized_input = sanitize_tool_input(tool_input, max_input_length)

    # Generate display name
    tool_display = get_tool_display_name(tool_name, tool_input)

    # Build output dict
    output = {"result": truncate(tool_output, max_output_length)} if tool_output else None

    # For tools with HTML views (TodoWrite, Edit), we need to attach the view
    # BEFORE finishing the call, so we use create_call + set_call_view + finish_call
    needs_html_view = (
        tool_name == "TodoWrite"
        or (tool_name == "Edit" and structured_patch is not None)
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
            )

            # Attach HTML view BEFORE finishing
            if tool_name == "TodoWrite":
                from weave.integrations.claude_plugin.diff_view import generate_todo_html

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
                from weave.integrations.claude_plugin.diff_view import (
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

            # Now finish the call
            client.finish_call(call, output=output)
            return call
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
            )
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
        from weave.integrations.claude_plugin.session_title import (
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
                return f"WebFetch: {domain}"
            except Exception:
                pass
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

        return {
            "remote": remote,
            "branch": branch,
            "commit": commit,
        }
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug(f"Failed to get git info for {cwd}: {e}")
        return None


def extract_question_from_text(text: str) -> str | None:
    """Extract the trailing question from assistant text output.

    Used for Q&A context tracking - when an assistant response ends with a
    question, we want to capture it so it can be added as context to the
    next turn's input (via 'in_response_to' field).

    Handles two patterns:
    1. "**Next question:**" marker - extracts the first line with "?" after this marker
    2. Last paragraph ending with "?" - extracts up to and including the first "?"

    Args:
        text: Assistant text output

    Returns:
        The trailing question if found, or None
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # Pattern 1: Check for "**Next question:**" marker (case-insensitive)
    next_question_marker = "**next question:**"
    lower_text = text.lower()
    if next_question_marker in lower_text:
        # Find the marker position in original text
        marker_pos = lower_text.index(next_question_marker)
        after_marker = text[marker_pos + len(next_question_marker) :]

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
