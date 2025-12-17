#!/usr/bin/env python3
"""Entry point for Claude Code hook invocations.

This module is invoked by Claude Code hooks. It relays events to the
daemon process, starting the daemon if necessary.

Usage (via hook configuration):
    python -m weave.integrations.claude_plugin.hook

Configuration:
    WEAVE_PROJECT: Required. Weave project in "entity/project" format.
    WEAVE_HOOK_DISABLED: Optional. Set to any value to disable tracing.
    DEBUG: Optional. Set to "1" to enable debug logging.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# Debug log file
DEBUG_LOG_FILE = Path("/tmp/weave-claude-debug.log")


def setup_logging() -> logging.Logger:
    """Configure logging with optional file output for debugging."""
    level = logging.DEBUG if os.environ.get("DEBUG") else logging.WARNING

    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    logger.handlers.clear()

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(stderr_handler)

    if os.environ.get("DEBUG"):
        try:
            file_handler = logging.FileHandler(DEBUG_LOG_FILE, mode="a")
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
            )
            logger.addHandler(file_handler)
        except Exception:
            pass

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
        logger.debug("WEAVE_PROJECT not set, skipping")
        sys.exit(0)

    # Read hook payload from stdin
    try:
        payload: dict[str, Any] = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse hook payload: {e}")
        sys.exit(1)

    event_name = payload.get("hook_event_name")
    session_id = payload.get("session_id")

    if not event_name:
        logger.error("Missing hook_event_name in payload")
        sys.exit(1)

    if not session_id:
        logger.error("Missing session_id in payload")
        sys.exit(1)

    logger.debug(f"Event: {event_name} | Session: {session_id}")

    # Check if tracing is enabled (config file or local override)
    from weave.integrations.claude_plugin.config import is_enabled

    cwd = payload.get("cwd", os.getcwd())
    if not is_enabled(cwd):
        logger.debug("Weave tracing disabled via config")
        # Return disabled message for UserPromptSubmit
        if event_name == "UserPromptSubmit":
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": "Weave tracing is disabled. Run /weave:enable to enable tracing.",
                }
            }
            print(json.dumps(result))
        sys.exit(0)

    # Import here to avoid startup overhead
    from weave.integrations.claude_plugin.core.socket_client import (
        DaemonClient,
        ensure_daemon_running,
    )
    from weave.integrations.claude_plugin.core.state import (
        StateManager,
        create_session_data,
    )

    # For SessionStart, initialize state before starting daemon
    if event_name == "SessionStart":
        transcript_path = payload.get("transcript_path")
        cwd = payload.get("cwd")

        with StateManager() as state:
            existing = state.get_session(session_id)
            if not existing:
                session_data = create_session_data(
                    project=project,
                    transcript_path=transcript_path,
                )
                state.save_session(session_id, session_data, cwd=cwd)
                logger.debug(f"Initialized state for {session_id}")

    # Get daemon PID from state for liveness check
    daemon_pid = None
    with StateManager() as state:
        session_data = state.get_session(session_id)
        if session_data:
            daemon_pid = session_data.get("daemon_pid")

    # Ensure daemon is running
    try:
        client = ensure_daemon_running(session_id, daemon_pid)
    except Exception as e:
        logger.error(f"Failed to connect to daemon: {e}")
        sys.exit(1)

    # Send event to daemon
    try:
        # Wait for response on UserPromptSubmit (need trace URL)
        wait_response = event_name in ("SessionStart", "UserPromptSubmit")
        response = client.send_event(event_name, payload, wait_response=wait_response)

        if response:
            logger.debug(f"Daemon response: {response}")

            # Return trace URL for UserPromptSubmit
            if event_name == "UserPromptSubmit" and response.get("trace_url"):
                # Include session_id so feedback commands can find the session
                trace_url = response["trace_url"]
                session_id = response.get("session_id", "")
                context_parts = [f"Weave tracing active: {trace_url}"]
                if session_id:
                    context_parts.append(f"Weave session_id: {session_id}")

                result = {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": "\n".join(context_parts),
                    }
                }
                print(json.dumps(result))
        else:
            logger.warning("No response from daemon")

    except Exception as e:
        logger.error(f"Error sending event to daemon: {e}")
        if os.environ.get("DEBUG"):
            import traceback
            traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
