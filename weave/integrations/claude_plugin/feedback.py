#!/usr/bin/env python3
"""CLI for sending feedback to a Claude Code session.

Usage:
    python -m weave.integrations.claude_plugin.feedback <session_id> <emoji> [note]

Examples:
    python -m weave.integrations.claude_plugin.feedback abc123 "🤩" "Great session!"
    python -m weave.integrations.claude_plugin.feedback abc123 "😊"
"""

from __future__ import annotations

import json
import sys

from weave.integrations.claude_plugin.socket_client import DaemonClient


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
        print(f"Error: No daemon running for session {session_id}", file=sys.stderr)
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

    return 0


if __name__ == "__main__":
    sys.exit(main())
