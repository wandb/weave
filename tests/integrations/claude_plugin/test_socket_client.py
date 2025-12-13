"""Tests for socket_client module."""

import socket
from unittest.mock import MagicMock, patch

import pytest

from weave.integrations.claude_plugin.socket_client import DaemonClient


class TestDaemonClientSendEvent:
    @patch("socket.socket")
    def test_socket_closed_on_success(self, mock_socket_class):
        """Socket should be closed after successful send."""
        mock_socket = MagicMock()
        mock_socket.recv.return_value = b'{"status": "ok"}\n'
        mock_socket_class.return_value = mock_socket

        client = DaemonClient("test-session")
        client.socket_path = MagicMock()
        client.socket_path.exists.return_value = True

        client.send_event("TestEvent", {"data": "test"})

        mock_socket.close.assert_called()

    @patch("socket.socket")
    def test_socket_closed_on_timeout(self, mock_socket_class):
        """Socket should be closed even when timeout occurs."""
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = socket.timeout()
        mock_socket_class.return_value = mock_socket

        client = DaemonClient("test-session")
        client.socket_path = MagicMock()
        client.socket_path.exists.return_value = True

        result = client.send_event("TestEvent", {"data": "test"})

        assert result is None
        mock_socket.close.assert_called()

    @patch("socket.socket")
    def test_socket_closed_on_connection_error(self, mock_socket_class):
        """Socket should be closed even when connection fails."""
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = OSError("Connection refused")
        mock_socket_class.return_value = mock_socket

        client = DaemonClient("test-session")
        client.socket_path = MagicMock()
        client.socket_path.exists.return_value = True

        result = client.send_event("TestEvent", {"data": "test"})

        assert result is None
        mock_socket.close.assert_called()


class TestDaemonClientIsDaemonRunning:
    @patch("socket.socket")
    def test_socket_closed_on_success(self, mock_socket_class):
        """Socket should be closed after successful connection check."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        client = DaemonClient("test-session")
        client.socket_path = MagicMock()
        client.socket_path.exists.return_value = True

        result = client.is_daemon_running()

        assert result is True
        mock_socket.close.assert_called()

    @patch("socket.socket")
    def test_socket_closed_on_connection_error(self, mock_socket_class):
        """Socket should be closed even when connection fails."""
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = OSError("Connection refused")
        mock_socket_class.return_value = mock_socket

        client = DaemonClient("test-session")
        client.socket_path = MagicMock()
        client.socket_path.exists.return_value = True

        result = client.is_daemon_running()

        assert result is False
        mock_socket.close.assert_called()
