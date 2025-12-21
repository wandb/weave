"""Tests for feedback.py - CLI for sending session feedback."""

import sys
from unittest.mock import MagicMock, patch


class TestFeedbackMain:
    """Tests for the feedback main function."""

    def test_returns_error_without_args(self):
        """Should return 1 with usage message when no args provided."""
        from weave.integrations.claude_plugin.views.feedback import main

        with patch.object(sys, "argv", ["feedback"]):
            result = main()
            assert result == 1

    def test_returns_error_with_only_session_id(self):
        """Should return 1 when only session_id provided."""
        from weave.integrations.claude_plugin.views.feedback import main

        with patch.object(sys, "argv", ["feedback", "session-123"]):
            result = main()
            assert result == 1

    def test_sends_feedback_when_daemon_running(self):
        """Should send feedback when daemon is running."""
        from weave.integrations.claude_plugin.views.feedback import main

        mock_client = MagicMock()
        mock_client.is_daemon_running.return_value = True
        mock_client.send_event.return_value = {"status": "ok"}

        with patch.object(sys, "argv", ["feedback", "session-123", "🤩"]):
            with patch(
                "weave.integrations.claude_plugin.views.feedback.DaemonClient",
                return_value=mock_client,
            ):
                result = main()
                assert result == 0
                mock_client.send_event.assert_called_once_with(
                    "Feedback", {"emoji": "🤩"}
                )

    def test_includes_note_when_provided(self):
        """Should include note in feedback payload."""
        from weave.integrations.claude_plugin.views.feedback import main

        mock_client = MagicMock()
        mock_client.is_daemon_running.return_value = True
        mock_client.send_event.return_value = {"status": "ok"}

        with patch.object(
            sys, "argv", ["feedback", "session-123", "😊", "Great session!"]
        ):
            with patch(
                "weave.integrations.claude_plugin.views.feedback.DaemonClient",
                return_value=mock_client,
            ):
                result = main()
                assert result == 0
                mock_client.send_event.assert_called_once_with(
                    "Feedback", {"emoji": "😊", "note": "Great session!"}
                )

    def test_starts_daemon_when_not_running(self):
        """Should start daemon if not running and state exists."""
        from weave.integrations.claude_plugin.views.feedback import main

        mock_client = MagicMock()
        mock_client.is_daemon_running.return_value = False
        mock_client.start_daemon.return_value = True
        mock_client.send_event.return_value = {"status": "ok"}

        mock_state_manager = MagicMock()
        mock_state_manager.__enter__ = MagicMock(return_value=mock_state_manager)
        mock_state_manager.__exit__ = MagicMock(return_value=False)
        mock_state_manager.get_session.return_value = {"session_id": "session-123"}

        with patch.object(sys, "argv", ["feedback", "session-123", "🤩"]):
            with patch(
                "weave.integrations.claude_plugin.views.feedback.DaemonClient",
                return_value=mock_client,
            ):
                with patch(
                    "weave.integrations.claude_plugin.views.feedback.StateManager",
                    return_value=mock_state_manager,
                ):
                    result = main()
                    assert result == 0
                    mock_client.start_daemon.assert_called_once()

    def test_returns_error_when_no_session_state(self):
        """Should return 1 when session state not found."""
        from weave.integrations.claude_plugin.views.feedback import main

        mock_client = MagicMock()
        mock_client.is_daemon_running.return_value = False

        mock_state_manager = MagicMock()
        mock_state_manager.__enter__ = MagicMock(return_value=mock_state_manager)
        mock_state_manager.__exit__ = MagicMock(return_value=False)
        mock_state_manager.get_session.return_value = None

        with patch.object(sys, "argv", ["feedback", "session-123", "🤩"]):
            with patch(
                "weave.integrations.claude_plugin.views.feedback.DaemonClient",
                return_value=mock_client,
            ):
                with patch(
                    "weave.integrations.claude_plugin.views.feedback.StateManager",
                    return_value=mock_state_manager,
                ):
                    result = main()
                    assert result == 1

    def test_returns_error_when_daemon_start_fails(self):
        """Should return 1 when daemon fails to start."""
        from weave.integrations.claude_plugin.views.feedback import main

        mock_client = MagicMock()
        mock_client.is_daemon_running.return_value = False
        mock_client.start_daemon.return_value = False

        mock_state_manager = MagicMock()
        mock_state_manager.__enter__ = MagicMock(return_value=mock_state_manager)
        mock_state_manager.__exit__ = MagicMock(return_value=False)
        mock_state_manager.get_session.return_value = {"session_id": "session-123"}

        with patch.object(sys, "argv", ["feedback", "session-123", "🤩"]):
            with patch(
                "weave.integrations.claude_plugin.views.feedback.DaemonClient",
                return_value=mock_client,
            ):
                with patch(
                    "weave.integrations.claude_plugin.views.feedback.StateManager",
                    return_value=mock_state_manager,
                ):
                    result = main()
                    assert result == 1

    def test_returns_error_when_send_fails(self):
        """Should return 1 when send_event returns None."""
        from weave.integrations.claude_plugin.views.feedback import main

        mock_client = MagicMock()
        mock_client.is_daemon_running.return_value = True
        mock_client.send_event.return_value = None

        with patch.object(sys, "argv", ["feedback", "session-123", "🤩"]):
            with patch(
                "weave.integrations.claude_plugin.views.feedback.DaemonClient",
                return_value=mock_client,
            ):
                result = main()
                assert result == 1

    def test_returns_error_on_error_response(self):
        """Should return 1 when server returns error status."""
        from weave.integrations.claude_plugin.views.feedback import main

        mock_client = MagicMock()
        mock_client.is_daemon_running.return_value = True
        mock_client.send_event.return_value = {
            "status": "error",
            "message": "Session ended",
        }

        with patch.object(sys, "argv", ["feedback", "session-123", "🤩"]):
            with patch(
                "weave.integrations.claude_plugin.views.feedback.DaemonClient",
                return_value=mock_client,
            ):
                result = main()
                assert result == 1
