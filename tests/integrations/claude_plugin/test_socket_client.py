"""Tests for socket_client.py."""

from __future__ import annotations

import os
import socket
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from weave.integrations.claude_plugin.core.socket_client import (
    SOCKET_DIR,
    DaemonClient,
    ensure_daemon_running,
    get_socket_path,
)


class TestDaemonClientInit:
    """Tests for DaemonClient initialization."""

    def test_default_timeout(self):
        """Default timeout is 5.0 seconds."""
        client = DaemonClient("test-session-id")
        assert client.timeout == 5.0

    def test_custom_timeout(self):
        """Custom timeout is respected."""
        client = DaemonClient("test-session-id", timeout=10.0)
        assert client.timeout == 10.0

    def test_socket_path_format(self):
        """Socket path follows format ~/.cache/weave/daemon-{session_id}.sock."""
        session_id = "test-session-123"
        client = DaemonClient(session_id)
        expected_path = SOCKET_DIR / f"daemon-{session_id}.sock"
        assert client.socket_path == expected_path
        assert str(client.socket_path).endswith(f"daemon-{session_id}.sock")


class TestDaemonClientIsDaemonRunning:
    """Tests for DaemonClient.is_daemon_running()."""

    def test_returns_false_when_socket_missing(self):
        """Returns False when socket file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = "test-session-nonexistent"
            client = DaemonClient(session_id)
            # Override socket path to temp location
            client.socket_path = Path(tmpdir) / "nonexistent.sock"
            assert not client.is_daemon_running()

    def test_returns_true_on_successful_connection(self):
        """Mock successful socket connection returns True."""
        client = DaemonClient("test-session-id")

        # Mock socket to simulate successful connection
        mock_sock = mock.MagicMock()

        with mock.patch("socket.socket", return_value=mock_sock):
            with mock.patch("pathlib.Path.exists", return_value=True):
                result = client.is_daemon_running()

                # Verify socket operations were called
                mock_sock.settimeout.assert_called_once_with(1.0)
                mock_sock.connect.assert_called_once_with(str(client.socket_path))
                mock_sock.close.assert_called_once()

                assert result is True

    def test_returns_false_on_socket_error(self):
        """Returns False when socket connection fails."""
        client = DaemonClient("test-session-id")

        # Mock socket to raise error on connect
        mock_sock = mock.MagicMock()
        mock_sock.connect.side_effect = socket.error("Connection refused")

        with mock.patch("socket.socket", return_value=mock_sock):
            with mock.patch("pathlib.Path.exists", return_value=True):
                result = client.is_daemon_running()
                assert result is False

    def test_returns_false_on_os_error(self):
        """Returns False when OSError occurs."""
        client = DaemonClient("test-session-id")

        # Mock socket to raise OSError
        mock_sock = mock.MagicMock()
        mock_sock.connect.side_effect = OSError("Permission denied")

        with mock.patch("socket.socket", return_value=mock_sock):
            with mock.patch("pathlib.Path.exists", return_value=True):
                result = client.is_daemon_running()
                assert result is False

    def test_cleans_up_socket_on_error(self):
        """Socket is closed even when error occurs."""
        client = DaemonClient("test-session-id")

        # Mock socket to raise error on connect
        mock_sock = mock.MagicMock()
        mock_sock.connect.side_effect = socket.error("Connection refused")

        with mock.patch("socket.socket", return_value=mock_sock):
            with mock.patch("pathlib.Path.exists", return_value=True):
                client.is_daemon_running()

                # Verify socket was closed despite error
                mock_sock.close.assert_called_once()


class TestDaemonClientIsProcessAlive:
    """Tests for DaemonClient.is_process_alive()."""

    def test_current_process_is_alive(self):
        """Current process (os.getpid()) returns True."""
        client = DaemonClient("test-session-id")
        current_pid = os.getpid()
        assert client.is_process_alive(current_pid) is True

    def test_invalid_pid_returns_false(self):
        """Invalid PID like 999999999 returns False."""
        client = DaemonClient("test-session-id")
        assert client.is_process_alive(999999999) is False

    def test_os_error_returns_false(self):
        """OSError during process check returns False."""
        client = DaemonClient("test-session-id")

        with mock.patch("os.kill", side_effect=OSError("No such process")):
            assert client.is_process_alive(12345) is False


class TestDaemonClientCleanupStaleSocket:
    """Tests for DaemonClient.cleanup_stale_socket()."""

    def test_removes_existing_socket(self):
        """Removes socket file if it exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = DaemonClient("test-session-id")
            socket_path = Path(tmpdir) / "test.sock"
            socket_path.touch()  # Create file
            client.socket_path = socket_path

            assert socket_path.exists()
            client.cleanup_stale_socket()
            assert not socket_path.exists()

    def test_no_error_when_socket_missing(self):
        """No error when socket doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = DaemonClient("test-session-id")
            client.socket_path = Path(tmpdir) / "nonexistent.sock"

            # Should not raise
            client.cleanup_stale_socket()

    def test_logs_warning_on_cleanup_error(self, caplog):
        """Logs warning when cleanup fails."""
        import logging

        client = DaemonClient("test-session-id")

        with caplog.at_level(logging.WARNING, logger="weave.integrations.claude_plugin.core.socket_client"):
            with mock.patch("pathlib.Path.exists", return_value=True):
                with mock.patch("pathlib.Path.unlink", side_effect=OSError("Permission denied")):
                    client.cleanup_stale_socket()

                    # Check that warning was logged
                    assert any("Failed to clean up socket" in record.message for record in caplog.records)


class TestDaemonClientStartDaemon:
    """Tests for DaemonClient.start_daemon()."""

    def test_creates_socket_directory(self):
        """Creates socket directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = DaemonClient("test-session-id")
            socket_dir = Path(tmpdir) / "test-dir"
            client.socket_path = socket_dir / "daemon.sock"

            with mock.patch("weave.integrations.claude_plugin.core.socket_client.SOCKET_DIR", socket_dir):
                with mock.patch("subprocess.Popen"):
                    with mock.patch.object(client, "is_daemon_running", return_value=True):
                        client.start_daemon()

                        assert socket_dir.exists()

    def test_cleans_up_stale_socket_before_start(self):
        """Cleans up stale socket before starting daemon."""
        client = DaemonClient("test-session-id")

        with mock.patch.object(client, "cleanup_stale_socket") as mock_cleanup:
            with mock.patch("subprocess.Popen"):
                with mock.patch.object(client, "is_daemon_running", return_value=True):
                    client.start_daemon()

                    mock_cleanup.assert_called_once()

    def test_starts_daemon_process(self):
        """Starts daemon process with correct arguments."""
        session_id = "test-session-123"
        client = DaemonClient(session_id)

        with mock.patch("subprocess.Popen") as mock_popen:
            with mock.patch.object(client, "is_daemon_running", return_value=True):
                with mock.patch("weave.integrations.claude_plugin.core.socket_client.SOCKET_DIR") as mock_dir:
                    mock_dir.mkdir = mock.MagicMock()
                    client.start_daemon()

                    # Verify subprocess.Popen was called with correct args
                    mock_popen.assert_called_once()
                    args = mock_popen.call_args
                    assert args[0][0][0] == mock.ANY  # sys.executable
                    assert args[0][0][1:] == ["-m", "weave.integrations.claude_plugin.core.daemon", session_id]
                    assert args[1]["start_new_session"] is True
                    assert args[1]["stdout"] == subprocess.DEVNULL
                    assert args[1]["stderr"] == subprocess.DEVNULL
                    assert args[1]["stdin"] == subprocess.DEVNULL

    def test_returns_true_when_daemon_starts(self):
        """Returns True when daemon starts successfully."""
        client = DaemonClient("test-session-id")

        with mock.patch("subprocess.Popen"):
            with mock.patch.object(client, "is_daemon_running", return_value=True):
                with mock.patch("weave.integrations.claude_plugin.core.socket_client.SOCKET_DIR") as mock_dir:
                    mock_dir.mkdir = mock.MagicMock()
                    result = client.start_daemon()

                    assert result is True

    def test_returns_false_on_timeout(self):
        """Returns False when daemon doesn't start within timeout."""
        client = DaemonClient("test-session-id")

        with mock.patch("subprocess.Popen"):
            with mock.patch.object(client, "is_daemon_running", return_value=False):
                with mock.patch("time.sleep"):  # Speed up test
                    with mock.patch("weave.integrations.claude_plugin.core.socket_client.SOCKET_DIR") as mock_dir:
                        mock_dir.mkdir = mock.MagicMock()
                        result = client.start_daemon()

                        assert result is False

    def test_returns_false_on_exception(self, caplog):
        """Returns False when exception occurs."""
        import logging

        client = DaemonClient("test-session-id")

        # Suppress error logs during this test
        with caplog.at_level(logging.CRITICAL):
            with mock.patch("subprocess.Popen", side_effect=Exception("Test error")):
                with mock.patch("weave.integrations.claude_plugin.core.socket_client.SOCKET_DIR") as mock_dir:
                    mock_dir.mkdir = mock.MagicMock()
                    result = client.start_daemon()

                    assert result is False


class TestDaemonClientSendEvent:
    """Tests for DaemonClient.send_event()."""

    def test_sends_event_successfully(self):
        """Sends event and receives response."""
        client = DaemonClient("test-session-id")

        # Mock socket
        mock_sock = mock.MagicMock()
        mock_sock.recv.return_value = b'{"status": "ok", "data": "test"}\n'

        with mock.patch("socket.socket", return_value=mock_sock):
            result = client.send_event("TestEvent", {"key": "value"})

            # Verify socket operations
            mock_sock.settimeout.assert_called_once_with(client.timeout)
            mock_sock.connect.assert_called_once_with(str(client.socket_path))
            mock_sock.sendall.assert_called_once()
            mock_sock.close.assert_called_once()

            # Verify result
            assert result == {"status": "ok", "data": "test"}

    def test_formats_message_correctly(self):
        """Message is formatted with event and payload."""
        client = DaemonClient("test-session-id")

        mock_sock = mock.MagicMock()
        mock_sock.recv.return_value = b'{"status": "ok"}\n'

        with mock.patch("socket.socket", return_value=mock_sock):
            client.send_event("TestEvent", {"key": "value"})

            # Check the message sent
            sent_data = mock_sock.sendall.call_args[0][0]
            assert b'"event": "TestEvent"' in sent_data
            assert b'"payload": {"key": "value"}' in sent_data
            assert sent_data.endswith(b"\n")

    def test_returns_none_on_timeout(self):
        """Returns None when socket times out."""
        client = DaemonClient("test-session-id")

        mock_sock = mock.MagicMock()
        mock_sock.connect.side_effect = socket.timeout("Timed out")

        with mock.patch("socket.socket", return_value=mock_sock):
            result = client.send_event("TestEvent", {"key": "value"})

            assert result is None

    def test_returns_none_on_socket_error(self):
        """Returns None when socket error occurs."""
        client = DaemonClient("test-session-id")

        mock_sock = mock.MagicMock()
        mock_sock.connect.side_effect = socket.error("Connection refused")

        with mock.patch("socket.socket", return_value=mock_sock):
            result = client.send_event("TestEvent", {"key": "value"})

            assert result is None

    def test_returns_none_on_os_error(self):
        """Returns None when OSError occurs."""
        client = DaemonClient("test-session-id")

        mock_sock = mock.MagicMock()
        mock_sock.connect.side_effect = OSError("Permission denied")

        with mock.patch("socket.socket", return_value=mock_sock):
            result = client.send_event("TestEvent", {"key": "value"})

            assert result is None

    def test_returns_none_on_json_decode_error(self):
        """Returns None when response is invalid JSON."""
        client = DaemonClient("test-session-id")

        mock_sock = mock.MagicMock()
        mock_sock.recv.return_value = b'invalid json\n'

        with mock.patch("socket.socket", return_value=mock_sock):
            result = client.send_event("TestEvent", {"key": "value"})

            assert result is None

    def test_wait_response_false(self):
        """Returns ok status without waiting for response."""
        client = DaemonClient("test-session-id")

        mock_sock = mock.MagicMock()

        with mock.patch("socket.socket", return_value=mock_sock):
            result = client.send_event("TestEvent", {"key": "value"}, wait_response=False)

            # Should not call recv
            mock_sock.recv.assert_not_called()

            # Should return ok status
            assert result == {"status": "ok"}

    def test_cleans_up_socket_on_error(self):
        """Socket is closed even when error occurs."""
        client = DaemonClient("test-session-id")

        mock_sock = mock.MagicMock()
        mock_sock.connect.side_effect = socket.error("Connection refused")

        with mock.patch("socket.socket", return_value=mock_sock):
            client.send_event("TestEvent", {"key": "value"})

            # Verify socket was closed despite error
            mock_sock.close.assert_called_once()


class TestGetSocketPath:
    """Tests for get_socket_path() function."""

    def test_returns_correct_path(self):
        """Returns path in format ~/.cache/weave/daemon-{session_id}.sock."""
        session_id = "test-session-456"
        path = get_socket_path(session_id)

        assert path == SOCKET_DIR / f"daemon-{session_id}.sock"
        assert str(path).endswith(f"daemon-{session_id}.sock")

    def test_different_session_ids(self):
        """Different session IDs produce different paths."""
        path1 = get_socket_path("session-1")
        path2 = get_socket_path("session-2")

        assert path1 != path2
        assert "session-1" in str(path1)
        assert "session-2" in str(path2)


class TestEnsureDaemonRunning:
    """Tests for ensure_daemon_running() function."""

    def test_returns_client_when_already_running(self):
        """When daemon running, returns client without starting new one."""
        session_id = "test-session-id"

        with mock.patch.object(DaemonClient, "is_daemon_running", return_value=True):
            with mock.patch.object(DaemonClient, "start_daemon") as mock_start:
                client = ensure_daemon_running(session_id)

                # Verify daemon was not started
                mock_start.assert_not_called()

                # Verify client was created with correct session ID
                assert client.session_id == session_id

    def test_starts_daemon_when_not_running(self):
        """When daemon not running, starts it."""
        session_id = "test-session-id"

        with mock.patch.object(DaemonClient, "is_daemon_running", return_value=False):
            with mock.patch.object(DaemonClient, "cleanup_stale_socket"):
                with mock.patch.object(DaemonClient, "start_daemon") as mock_start:
                    client = ensure_daemon_running(session_id)

                    # Verify daemon was started
                    mock_start.assert_called_once()

                    # Verify client was created
                    assert client.session_id == session_id

    def test_checks_daemon_pid_when_provided(self):
        """Checks if daemon PID is alive when provided."""
        session_id = "test-session-id"
        daemon_pid = os.getpid()  # Use current process as valid PID

        with mock.patch.object(DaemonClient, "is_daemon_running") as mock_running:
            # First call returns False, second returns True
            mock_running.side_effect = [False, True]

            with mock.patch.object(DaemonClient, "is_process_alive", return_value=True):
                with mock.patch("time.sleep"):
                    client = ensure_daemon_running(session_id, daemon_pid=daemon_pid)

                    # Verify we checked if daemon is running twice
                    assert mock_running.call_count == 2

                    # Verify client was created
                    assert client.session_id == session_id

    def test_starts_daemon_when_pid_not_alive(self):
        """Starts daemon when stored PID is not alive."""
        session_id = "test-session-id"
        daemon_pid = 999999999  # Invalid PID

        with mock.patch.object(DaemonClient, "is_daemon_running", return_value=False):
            with mock.patch.object(DaemonClient, "is_process_alive", return_value=False):
                with mock.patch.object(DaemonClient, "cleanup_stale_socket"):
                    with mock.patch.object(DaemonClient, "start_daemon") as mock_start:
                        client = ensure_daemon_running(session_id, daemon_pid=daemon_pid)

                        # Verify daemon was started
                        mock_start.assert_called_once()

    def test_cleans_up_stale_socket_before_start(self):
        """Cleans up stale socket before starting daemon."""
        session_id = "test-session-id"

        with mock.patch.object(DaemonClient, "is_daemon_running", return_value=False):
            with mock.patch.object(DaemonClient, "cleanup_stale_socket") as mock_cleanup:
                with mock.patch.object(DaemonClient, "start_daemon"):
                    ensure_daemon_running(session_id)

                    # Verify cleanup was called
                    mock_cleanup.assert_called_once()
