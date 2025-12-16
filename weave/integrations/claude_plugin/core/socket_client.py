"""Socket client for hook-to-daemon communication.

This module provides a client for hooks to communicate with the daemon
process via Unix domain sockets.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Socket location
SOCKET_DIR = Path.home() / ".cache" / "weave"


def get_socket_path(session_id: str) -> Path:
    """Get the Unix socket path for a session's daemon."""
    return SOCKET_DIR / f"daemon-{session_id}.sock"


class DaemonClient:
    """Client for communicating with the daemon process.

    Usage:
        client = DaemonClient(session_id)
        if not client.is_daemon_running():
            client.start_daemon()
        response = client.send_event("UserPromptSubmit", payload)
    """

    def __init__(self, session_id: str, timeout: float = 5.0):
        """Initialize daemon client.

        Args:
            session_id: Claude Code session ID
            timeout: Socket timeout in seconds
        """
        self.session_id = session_id
        self.socket_path = get_socket_path(session_id)
        self.timeout = timeout

    def is_daemon_running(self) -> bool:
        """Check if the daemon is running by attempting socket connection."""
        if not self.socket_path.exists():
            return False

        sock = None
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect(str(self.socket_path))
            return True
        except (socket.error, OSError):
            return False
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    def is_process_alive(self, pid: int) -> bool:
        """Check if a process with given PID is alive."""
        try:
            os.kill(pid, 0)  # Signal 0 just checks existence
            return True
        except OSError:
            return False

    def cleanup_stale_socket(self) -> None:
        """Remove socket file if daemon is not running."""
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
                logger.debug(f"Cleaned up stale socket: {self.socket_path}")
            except OSError as e:
                logger.warning(f"Failed to clean up socket: {e}")

    def start_daemon(self) -> bool:
        """Start the daemon process.

        Returns:
            True if daemon started successfully
        """
        SOCKET_DIR.mkdir(parents=True, exist_ok=True)

        # Clean up any stale socket
        self.cleanup_stale_socket()

        try:
            # Start daemon as detached subprocess
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "weave.integrations.claude_plugin.core.daemon",
                    self.session_id,
                ],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )

            # Wait for socket to appear (up to 3 seconds)
            for _ in range(30):
                time.sleep(0.1)
                if self.is_daemon_running():
                    logger.debug(f"Daemon started for session {self.session_id}")
                    return True

            logger.warning(f"Daemon did not start within timeout for {self.session_id}")
            return False

        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            return False

    def send_event(
        self,
        event_name: str,
        payload: dict[str, Any],
        wait_response: bool = True,
    ) -> dict[str, Any] | None:
        """Send an event to the daemon.

        Args:
            event_name: Hook event name (SessionStart, UserPromptSubmit, etc.)
            payload: Hook payload
            wait_response: Whether to wait for and return response

        Returns:
            Response dict from daemon, or None on error
        """
        message = {
            "event": event_name,
            "payload": payload,
        }

        sock = None
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect(str(self.socket_path))

            # Send message with newline delimiter
            sock.sendall((json.dumps(message) + "\n").encode())

            if wait_response:
                # Read response
                response_data = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response_data += chunk
                    if b"\n" in response_data:
                        break

                if response_data:
                    return json.loads(response_data.decode().strip())

            return {"status": "ok"}

        except socket.timeout:
            logger.warning(f"Timeout sending {event_name} to daemon")
            return None
        except (socket.error, OSError) as e:
            logger.warning(f"Socket error sending {event_name}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid response from daemon: {e}")
            return None
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass


def ensure_daemon_running(session_id: str, daemon_pid: int | None = None) -> DaemonClient:
    """Ensure daemon is running, starting it if necessary.

    Args:
        session_id: Claude Code session ID
        daemon_pid: PID from state file to check

    Returns:
        DaemonClient connected to running daemon
    """
    client = DaemonClient(session_id)

    if client.is_daemon_running():
        return client

    # Check if stored PID is alive
    if daemon_pid and client.is_process_alive(daemon_pid):
        # Process alive but socket not available - wait a bit
        time.sleep(0.5)
        if client.is_daemon_running():
            return client

    # Daemon not running - start it
    client.cleanup_stale_socket()
    client.start_daemon()

    return client
