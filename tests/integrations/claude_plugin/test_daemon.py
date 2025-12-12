"""Tests for Claude plugin daemon."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestWeaveDaemon:
    """Test the WeaveDaemon class."""

    def test_socket_path_generation(self):
        """Test socket path is generated correctly."""
        from weave.integrations.claude_plugin.socket_client import get_socket_path

        path = get_socket_path("test-session-123")
        assert path.name == "daemon-test-session-123.sock"
        assert ".cache/weave" in str(path)

    def test_daemon_client_not_running(self):
        """Test daemon client detects when daemon is not running."""
        from weave.integrations.claude_plugin.socket_client import DaemonClient

        client = DaemonClient("nonexistent-session")
        assert not client.is_daemon_running()

    def test_state_manager_with_new_fields(self):
        """Test state manager handles new daemon fields."""
        from weave.integrations.claude_plugin.state import (
            StateManager,
            create_session_data,
        )

        session_data = create_session_data(
            project="test/project",
            daemon_pid=12345,
            last_processed_line=100,
            transcript_path="/path/to/session.jsonl",
            trace_url="https://example.com/trace",
        )

        assert session_data["daemon_pid"] == 12345
        assert session_data["last_processed_line"] == 100
        assert session_data["transcript_path"] == "/path/to/session.jsonl"
        assert session_data["trace_url"] == "https://example.com/trace"


class TestDaemonClient:
    """Test the DaemonClient class."""

    def test_cleanup_stale_socket(self, tmp_path):
        """Test cleanup of stale socket files."""
        from weave.integrations.claude_plugin.socket_client import DaemonClient

        # Create a fake socket file
        with patch(
            "weave.integrations.claude_plugin.socket_client.SOCKET_DIR",
            tmp_path,
        ):
            client = DaemonClient("test-session")
            client.socket_path = tmp_path / "daemon-test-session.sock"
            client.socket_path.touch()

            assert client.socket_path.exists()
            client.cleanup_stale_socket()
            assert not client.socket_path.exists()

    def test_is_process_alive(self):
        """Test process liveness check."""
        import os

        from weave.integrations.claude_plugin.socket_client import DaemonClient

        client = DaemonClient("test")

        # Current process should be alive
        assert client.is_process_alive(os.getpid())

        # Non-existent PID should not be alive
        assert not client.is_process_alive(999999999)
