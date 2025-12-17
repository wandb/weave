#!/usr/bin/env python3
"""CLI for sending feedback to a Claude Code session.

Usage:
    python -m weave.integrations.claude_plugin.feedback <session_id> <emoji> [note]

Examples:
    python -m weave.integrations.claude_plugin.feedback abc123 "🤩" "Great session!"
    python -m weave.integrations.claude_plugin.feedback abc123 "😊"
"""

from __future__ import annotations

import sys

from weave.integrations.claude_plugin.core.socket_client import DaemonClient
from weave.integrations.claude_plugin.core.state import StateManager


def main() -> int:
    """Send feedback to a Claude Code session daemon."""
    if len(sys.argv) < 3:
        print("Usage: python -m weave.integrations.claude_plugin.feedback <session_id> <emoji> [note]", file=sys.stderr)
        return 1

    session_id = sys.argv[1]
    emoji = sys.argv[2]
    note = sys.argv[3] if len(sys.argv) > 3 else None

    # Create client and send feedback
    client = DaemonClient(session_id)

    if not client.is_daemon_running():
        # Check if we have state for this session to start daemon
        with StateManager() as state:
            session_data = state.get_session(session_id)

        if not session_data:
            print(f"Error: No session state found for {session_id}", file=sys.stderr)
            return 1

        # Start the daemon
        print(f"Starting daemon for session {session_id}...", file=sys.stderr)
        if not client.start_daemon():
            print(f"Error: Failed to start daemon for session {session_id}", file=sys.stderr)
            return 1

    payload = {"emoji": emoji}
    if note:
        payload["note"] = note

    response = client.send_event("Feedback", payload)

    if response is None:
        print("Error: Failed to send feedback", file=sys.stderr)
        return 1

    if response.get("status") == "error":
        print(f"Error: {response.get('message', 'Unknown error')}", file=sys.stderr)
        return 1

    print(f"Feedback sent: {emoji}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
