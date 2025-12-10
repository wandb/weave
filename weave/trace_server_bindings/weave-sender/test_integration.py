#!/usr/bin/env python3
"""Integration test for weave-sender with UDS."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path


def test_basic_flow():
    """Test basic init -> enqueue -> stats -> shutdown flow over UDS."""
    binary_path = Path(__file__).parent / "weave-sender"
    if not binary_path.exists():
        print(f"Binary not found at {binary_path}, building...")
        subprocess.run(["go", "build", "-o", "weave-sender", "."], cwd=binary_path.parent, check=True)

    # Use a temp socket path
    socket_path = Path(tempfile.gettempdir()) / f"weave-sender-test-{os.getpid()}.sock"

    # Clean up any existing socket
    if socket_path.exists():
        socket_path.unlink()

    # Start the server
    print(f"Starting server on {socket_path}...")
    proc = subprocess.Popen(
        [str(binary_path), "-socket", str(socket_path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    # Wait for socket to be available
    for _ in range(50):
        if socket_path.exists():
            break
        time.sleep(0.1)
    else:
        proc.terminate()
        raise RuntimeError("Server did not start")

    # Connect to server
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(str(socket_path))
    sock.settimeout(5.0)

    def send(method: str, params: dict = None) -> dict:
        req = {"id": 1, "method": method, "params": params or {}}
        sock.sendall((json.dumps(req) + "\n").encode())

        response_data = b""
        while b"\n" not in response_data:
            chunk = sock.recv(4096)
            if not chunk:
                raise RuntimeError("Connection closed")
            response_data += chunk

        return json.loads(response_data.split(b"\n")[0])

    try:
        # Test init
        print("Testing init...")
        resp = send("init", {
            "server_url": "http://localhost:9999",  # Won't actually connect
        })
        assert resp.get("result", {}).get("ok") is True, f"Init failed: {resp}"
        print("  OK")

        # Test enqueue
        print("Testing enqueue...")
        resp = send("enqueue", {
            "items": [
                {
                    "type": "start",
                    "payload": {"start": {"id": "test-1", "trace_id": "trace-1"}},
                },
                {
                    "type": "end",
                    "payload": {"end": {"id": "test-1"}},
                },
            ]
        })
        assert "ids" in resp.get("result", {}), f"Enqueue failed: {resp}"
        ids = resp["result"]["ids"]
        assert len(ids) == 2, f"Expected 2 ids, got {ids}"
        print(f"  OK - ids: {ids}")

        # Test stats
        print("Testing stats...")
        resp = send("stats")
        stats = resp.get("result", {})
        assert "queue_size" in stats, f"Stats failed: {resp}"
        print(f"  OK - stats: {stats}")

        # Test multiple clients can connect
        print("Testing second client connection...")
        sock2 = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock2.connect(str(socket_path))
        sock2.settimeout(5.0)

        req = {"id": 1, "method": "stats", "params": {}}
        sock2.sendall((json.dumps(req) + "\n").encode())
        response_data = b""
        while b"\n" not in response_data:
            chunk = sock2.recv(4096)
            if not chunk:
                raise RuntimeError("Connection closed")
            response_data += chunk
        resp2 = json.loads(response_data.split(b"\n")[0])
        assert "queue_size" in resp2.get("result", {}), f"Second client stats failed: {resp2}"
        sock2.close()
        print("  OK - second client connected successfully")

        # Test shutdown
        print("Testing shutdown...")
        resp = send("shutdown")
        assert resp.get("result", {}).get("ok") is True, f"Shutdown failed: {resp}"
        print("  OK")

        print("\nAll tests passed!")

    finally:
        sock.close()
        proc.terminate()
        proc.wait(timeout=5)
        if socket_path.exists():
            socket_path.unlink()


if __name__ == "__main__":
    test_basic_flow()
