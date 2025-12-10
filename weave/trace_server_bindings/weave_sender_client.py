"""Python client for the weave-sender Go service.

This module provides a Python interface to the Go-based batching + HTTP
sender service. It communicates with the Go sidecar over a Unix Domain Socket.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Path to the Go binary (relative to this file)
_BINARY_DIR = Path(__file__).parent / "weave-sender"
_BINARY_NAME = "weave-sender"

# Default socket path
_DEFAULT_SOCKET_PATH = Path("/tmp/weave-sender.sock")


def _get_binary_path() -> Path:
    """Get the path to the weave-sender binary."""
    binary_path = _BINARY_DIR / _BINARY_NAME
    if binary_path.exists():
        return binary_path

    raise FileNotFoundError(
        f"weave-sender binary not found. Expected at {binary_path}. "
        "Please build it with: cd weave-sender && go build -o weave-sender ."
    )


class WeaveSenderError(Exception):
    """Error from the weave-sender service."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"WeaveSenderError({code}): {message}")


class WeaveSenderClient:
    """Client for communicating with the weave-sender Go sidecar.

    This client connects to a Go sidecar process over a Unix Domain Socket.
    The sidecar handles batching and sending requests to the Weave server.

    The sidecar is started automatically if not already running.

    Example:
        client = WeaveSenderClient()
        client.init(
            server_url="https://trace.wandb.ai",
            auth=("api", "your-api-key"),
        )

        # Enqueue call start
        client.enqueue([{
            "type": "start",
            "payload": {"start": {...}}
        }])

        # Get stats
        stats = client.stats()
        print(f"Sent: {stats['sent']}, Pending: {stats['pending']}")

        # Disconnect (sidecar keeps running)
        client.disconnect()
    """

    def __init__(self, socket_path: str | Path | None = None):
        self._socket_path = Path(socket_path) if socket_path else _DEFAULT_SOCKET_PATH
        self._socket: socket.socket | None = None
        self._lock = threading.Lock()
        self._request_id = 0
        self._connected = False
        self._initialized = False
        self._process: subprocess.Popen | None = None

    def _ensure_sidecar_running(self) -> None:
        """Ensure the sidecar process is running."""
        # Check if socket exists and is connectable
        if self._socket_path.exists():
            try:
                test_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                test_sock.settimeout(1.0)
                test_sock.connect(str(self._socket_path))
                test_sock.close()
                return  # Sidecar is running
            except (socket.error, OSError):
                # Socket exists but not connectable - stale socket
                try:
                    self._socket_path.unlink()
                except OSError:
                    pass

        # Start the sidecar
        binary_path = _get_binary_path()
        logger.info(f"Starting weave-sender sidecar: {binary_path}")

        self._process = subprocess.Popen(
            [str(binary_path), "-socket", str(self._socket_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        # Start stderr reader thread
        self._stderr_thread = threading.Thread(
            target=self._read_stderr, daemon=True
        )
        self._stderr_thread.start()

        # Wait for socket to be available
        for _ in range(50):  # 5 seconds total
            if self._socket_path.exists():
                try:
                    test_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    test_sock.settimeout(1.0)
                    test_sock.connect(str(self._socket_path))
                    test_sock.close()
                    return  # Sidecar is ready
                except (socket.error, OSError):
                    pass
            time.sleep(0.1)

        raise RuntimeError("Failed to start weave-sender sidecar")

    def _read_stderr(self) -> None:
        """Read stderr from the Go process and log it."""
        if self._process is None or self._process.stderr is None:
            return

        for line in self._process.stderr:
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="replace")
            line = line.strip()
            if line:
                logger.debug(f"[weave-sender] {line}")

    def _connect(self) -> None:
        """Connect to the sidecar."""
        if self._connected:
            return

        self._ensure_sidecar_running()

        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.connect(str(self._socket_path))
        self._socket.settimeout(30.0)  # 30 second timeout for operations
        self._connected = True

    def _disconnect(self) -> None:
        """Disconnect from the sidecar."""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        self._connected = False

    def _send_request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a request to the sidecar and wait for a response."""
        with self._lock:
            if not self._connected:
                self._connect()

            if self._socket is None:
                raise RuntimeError("Not connected to sidecar")

            self._request_id += 1
            request = {
                "id": self._request_id,
                "method": method,
                "params": params or {},
            }

            # Send request
            request_json = json.dumps(request) + "\n"
            self._socket.sendall(request_json.encode("utf-8"))

            # Read response
            response_data = b""
            while b"\n" not in response_data:
                chunk = self._socket.recv(4096)
                if not chunk:
                    raise RuntimeError("Connection closed by sidecar")
                response_data += chunk

            response_line = response_data.split(b"\n")[0]
            response = json.loads(response_line.decode("utf-8"))

            if response.get("error"):
                error = response["error"]
                raise WeaveSenderError(error["code"], error["message"])

            return response.get("result")

    def init(
        self,
        server_url: str,
        auth: tuple[str, str] | None = None,
        headers: dict[str, str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the weave-sender service.

        Args:
            server_url: Base URL of the Weave trace server
            auth: Optional (username, password) tuple for basic auth
            headers: Optional additional HTTP headers
            config: Optional configuration overrides:
                - max_batch_size: Maximum items per batch
                - max_batch_bytes: Maximum bytes per batch
                - flush_interval_ms: Flush interval in milliseconds
                - max_queue_size: Maximum queue size
        """
        params: dict[str, Any] = {
            "server_url": server_url,
        }

        if auth:
            params["auth"] = {"username": auth[0], "password": auth[1]}

        if headers:
            params["headers"] = headers

        if config:
            params["config"] = config

        self._send_request("init", params)
        self._initialized = True

    def enqueue(self, items: list[dict[str, Any]]) -> list[int]:
        """Enqueue items to be sent to the server.

        Args:
            items: List of items to enqueue. Each item should have:
                - type: "start" or "end"
                - payload: The request payload (CallStartReq or CallEndReq)

        Returns:
            List of queue IDs for the enqueued items
        """
        if not self._initialized:
            raise RuntimeError("Client not initialized. Call init() first.")

        result = self._send_request("enqueue", {"items": items})
        return result.get("ids", [])

    def flush(self) -> None:
        """Force flush all pending items."""
        if not self._initialized:
            raise RuntimeError("Client not initialized. Call init() first.")

        self._send_request("flush")

    def wait_idle(self) -> None:
        """Wait until all items have been sent to the server.

        This flushes any pending items and blocks until all in-flight
        HTTP requests complete. Use this for accurate benchmarking.
        """
        if not self._initialized:
            raise RuntimeError("Client not initialized. Call init() first.")

        self._send_request("wait_idle")

    def stats(self) -> dict[str, int]:
        """Get current statistics.

        Returns:
            Dict with keys:
                - sent: Number of items successfully sent
                - failed: Number of items that failed to send
                - pending: Number of items waiting to be sent
                - dropped: Number of items dropped due to queue overflow
                - queue_size: Current queue size
        """
        if not self._initialized:
            raise RuntimeError("Client not initialized. Call init() first.")

        return self._send_request("stats")

    def disconnect(self) -> None:
        """Disconnect from the sidecar.

        The sidecar will continue running and can be reconnected to.
        """
        self._disconnect()
        self._initialized = False

    def shutdown_sidecar(self) -> None:
        """Shutdown the sidecar process.

        This will flush all pending items and stop the sidecar.
        Other clients connected to the same sidecar will be disconnected.
        """
        try:
            self._send_request("shutdown")
        except Exception:
            pass  # Sidecar may have already exited

        self._disconnect()
        self._initialized = False


# Global singleton for convenience
_global_client: WeaveSenderClient | None = None
_global_lock = threading.Lock()


def get_global_client(socket_path: str | Path | None = None) -> WeaveSenderClient:
    """Get the global WeaveSenderClient instance."""
    global _global_client
    with _global_lock:
        if _global_client is None:
            _global_client = WeaveSenderClient(socket_path)
        return _global_client


def init_global_client(
    server_url: str,
    auth: tuple[str, str] | None = None,
    headers: dict[str, str] | None = None,
    config: dict[str, Any] | None = None,
    socket_path: str | Path | None = None,
) -> WeaveSenderClient:
    """Initialize and return the global client."""
    client = get_global_client(socket_path)
    client.init(server_url, auth, headers, config)
    return client
