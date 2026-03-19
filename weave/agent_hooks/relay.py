"""Lightweight relay — reads a hook event from stdin and forwards to the daemon.

This module uses **only stdlib** so it starts fast (no heavy imports).  Cursor
hooks have a 5-second timeout; this script typically completes in <50 ms.

If the daemon is not running the relay silently succeeds (fire-and-forget),
so hooks never block or error the IDE.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

DEFAULT_PORT = 6346
TIMEOUT_S = 3.0  # total relay timeout; well within Cursor's 5 s hook limit


def relay(port: int | None = None) -> None:
    """Read one hook event from stdin and POST it to the running daemon.

    Exits silently (code 0) on any error so the IDE is never blocked.

    Args:
        port: Daemon port.  Defaults to ``WEAVE_AGENT_HOOKS_PORT`` env or
              6346.
    """
    port = port or int(os.environ.get("WEAVE_AGENT_HOOKS_PORT", DEFAULT_PORT))
    url = f"http://127.0.0.1:{port}/event"

    try:
        payload = sys.stdin.buffer.read()
        if not payload:
            return

        # Validate JSON so we don't bother the daemon with garbage
        json.loads(payload)

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            _ = resp.read()
    except Exception:
        # Daemon not running, malformed JSON, timeout — all silently ignored.
        pass
