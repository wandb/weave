"""Shared utilities for Claude Code plugin.

This module provides common utilities used by both the real-time hook
handlers and the batch import script.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def truncate(s: str | None, max_len: int = 5000) -> str | None:
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

    return tool_name


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
