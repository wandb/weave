#!/usr/bin/env python3
"""Entry point for Claude Code hook invocations.

This module is invoked by Claude Code hooks to enable real-time
Weave tracing of sessions. It reads hook events from stdin and
dispatches to the appropriate handler.

Usage (via hook configuration):
    python -m weave.integrations.claude_plugin.hook

Configuration:
    WEAVE_PROJECT: Required. Weave project in "entity/project" format.
    WEAVE_HOOK_DISABLED: Optional. Set to any value to disable tracing.
    DEBUG: Optional. Set to "1" to enable debug logging to stderr.

Hook events are received as JSON on stdin with the structure:
    {
        "hook_event_name": "SessionStart|UserPromptSubmit|Stop|SessionEnd",
        "session_id": "uuid",
        "transcript_path": "/path/to/session.jsonl",
        "cwd": "/working/directory",
        ...
    }

Responses (if any) are written to stdout as JSON.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# Debug log file - written when DEBUG=1 since Claude Code doesn't capture hook stderr
DEBUG_LOG_FILE = Path("/tmp/weave-claude-debug.log")


def setup_logging() -> logging.Logger:
    """Configure logging with optional file output for debugging."""
    level = logging.DEBUG if os.environ.get("DEBUG") else logging.WARNING

    # Create logger for this module
    logger = logging.getLogger(__name__)
    logger.setLevel(level)

    # Clear any existing handlers
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
                logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
            )
            logger.addHandler(file_handler)
        except Exception:
            pass  # Don't fail if we can't write to /tmp

    return logger


logger = setup_logging()


def main() -> None:
    """Main entry point for hook invocations."""
    logger.debug("=" * 60)
    logger.debug("Weave Claude plugin hook invoked")

    # Check if disabled
    if os.environ.get("WEAVE_HOOK_DISABLED"):
        logger.debug("Weave hook disabled via WEAVE_HOOK_DISABLED")
        sys.exit(0)

    # Get project from environment
    project = os.environ.get("WEAVE_PROJECT")
    if not project:
        # Silent exit if not configured - don't spam user's terminal
        logger.debug("WEAVE_PROJECT not set, skipping")
        sys.exit(0)

    logger.debug(f"WEAVE_PROJECT: {project}")

    # Read hook payload from stdin
    try:
        payload: dict[str, Any] = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse hook payload: {e}")
        sys.exit(1)

    event_name = payload.get("hook_event_name")
    session_id = payload.get("session_id", "unknown")

    if not event_name:
        logger.error("Missing hook_event_name in payload")
        sys.exit(1)

    logger.debug(f"Event: {event_name} | Session: {session_id}")
    logger.debug(f"Payload keys: {list(payload.keys())}")

    # Log additional payload details for UserPromptSubmit to understand image handling
    if event_name == "UserPromptSubmit":
        prompt = payload.get("prompt", "")
        logger.debug(f"UserPromptSubmit prompt preview: {prompt[:100]!r}...")
        # Check for any image-related keys
        for key in payload.keys():
            if "image" in key.lower() or "content" in key.lower() or "pasted" in key.lower():
                val = payload.get(key)
                logger.debug(f"  {key}: {type(val).__name__}, len={len(val) if hasattr(val, '__len__') else 'N/A'}")

    # Import handlers here to avoid startup overhead when disabled
    from weave.integrations.claude_plugin.handlers import (
        handle_session_end,
        handle_session_start,
        handle_stop,
        handle_subagent_stop,
        handle_user_prompt_submit,
    )

    handlers = {
        "SessionStart": handle_session_start,
        "UserPromptSubmit": handle_user_prompt_submit,
        "Stop": handle_stop,
        "SubagentStop": handle_subagent_stop,
        "SessionEnd": handle_session_end,
    }

    handler = handlers.get(event_name)
    if not handler:
        logger.debug(f"No handler for event: {event_name}")
        sys.exit(0)

    try:
        result = handler(payload, project)
        if result:
            # Output JSON response for hooks that support it
            logger.debug(f"Handler returned response: {result}")
            print(json.dumps(result))
        else:
            logger.debug("Handler completed (no response)")
    except Exception as e:
        logger.error(f"Handler error for {event_name}: {e}")
        if os.environ.get("DEBUG"):
            import traceback

            traceback.print_exc(file=sys.stderr)
            # Also write to debug log file
            with open(DEBUG_LOG_FILE, "a") as f:
                traceback.print_exc(file=f)
        sys.exit(1)


if __name__ == "__main__":
    main()
