"""Tests for hook.py - Claude Code hook entry point."""

import io
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_creates_logger_with_warning_level_by_default(self):
        """Should create logger with WARNING level when DEBUG not set."""
        from weave.integrations.claude_plugin.core.hook import setup_logging

        with patch.dict("os.environ", {}, clear=True):
            logger = setup_logging()
            # Default level should be WARNING (no DEBUG env var)
            import logging

            assert logger.level == logging.WARNING

    def test_creates_logger_with_debug_level_when_enabled(self):
        """Should create logger with DEBUG level when DEBUG=1."""
        from weave.integrations.claude_plugin.core.hook import setup_logging

        with patch.dict("os.environ", {"DEBUG": "1"}, clear=False):
            logger = setup_logging()
            import logging

            assert logger.level == logging.DEBUG


class TestHookMain:
    """Tests for the main() hook entry point."""

    def test_exits_when_disabled_via_env(self):
        """Should exit 0 when WEAVE_HOOK_DISABLED is set."""
        from weave.integrations.claude_plugin.core.hook import main

        with patch.dict("os.environ", {"WEAVE_HOOK_DISABLED": "1"}, clear=False):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0

    def test_exits_when_no_project(self):
        """Should exit 0 when WEAVE_PROJECT is not set."""
        from weave.integrations.claude_plugin.core.hook import main

        # Create clean environment without WEAVE_PROJECT or WEAVE_HOOK_DISABLED
        clean_env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("WEAVE_PROJECT", "WEAVE_HOOK_DISABLED")
        }
        with patch.dict("os.environ", clean_env, clear=True):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0

    @pytest.mark.disable_logging_error_check
    def test_exits_on_invalid_json(self):
        """Should exit 1 when stdin contains invalid JSON."""
        from weave.integrations.claude_plugin.core.hook import main

        with patch.dict("os.environ", {"WEAVE_PROJECT": "test/project"}, clear=False):
            with patch.object(sys, "stdin", io.StringIO("not valid json")):
                with pytest.raises(SystemExit) as exc:
                    main()
                assert exc.value.code == 1

    @pytest.mark.disable_logging_error_check
    def test_exits_when_missing_event_name(self):
        """Should exit 1 when hook_event_name is missing."""
        from weave.integrations.claude_plugin.core.hook import main

        payload = {"session_id": "test-session"}
        with patch.dict("os.environ", {"WEAVE_PROJECT": "test/project"}, clear=False):
            with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
                with pytest.raises(SystemExit) as exc:
                    main()
                assert exc.value.code == 1

    @pytest.mark.disable_logging_error_check
    def test_exits_when_missing_session_id(self):
        """Should exit 1 when session_id is missing."""
        from weave.integrations.claude_plugin.core.hook import main

        payload = {"hook_event_name": "UserPromptSubmit"}
        with patch.dict("os.environ", {"WEAVE_PROJECT": "test/project"}, clear=False):
            with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
                with pytest.raises(SystemExit) as exc:
                    main()
                assert exc.value.code == 1

    def test_exits_when_tracing_disabled_via_config(self):
        """Should exit 0 when tracing disabled via config."""
        from weave.integrations.claude_plugin.core.hook import main

        payload = {
            "hook_event_name": "Stop",
            "session_id": "test-session",
            "cwd": "/test/dir",
        }
        with patch.dict("os.environ", {"WEAVE_PROJECT": "test/project"}, clear=False):
            with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
                with patch(
                    "weave.integrations.claude_plugin.config.is_enabled",
                    return_value=False,
                ):
                    with pytest.raises(SystemExit) as exc:
                        main()
                    assert exc.value.code == 0

    def test_returns_disabled_message_for_user_prompt_when_disabled(self, capsys):
        """Should return disabled message for UserPromptSubmit when tracing disabled."""
        from weave.integrations.claude_plugin.core.hook import main

        payload = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "test-session",
            "cwd": "/test/dir",
        }
        with patch.dict("os.environ", {"WEAVE_PROJECT": "test/project"}, clear=False):
            with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
                with patch(
                    "weave.integrations.claude_plugin.config.is_enabled",
                    return_value=False,
                ):
                    with pytest.raises(SystemExit) as exc:
                        main()
                    assert exc.value.code == 0

                    # Check that disabled message was printed
                    captured = capsys.readouterr()
                    output = json.loads(captured.out)
                    assert "hookSpecificOutput" in output
                    assert (
                        "disabled"
                        in output["hookSpecificOutput"]["additionalContext"].lower()
                    )

    def test_initializes_state_on_session_start(self):
        """Should initialize state for SessionStart event."""
        from weave.integrations.claude_plugin.core.hook import main

        payload = {
            "hook_event_name": "SessionStart",
            "session_id": "test-session-123",
            "transcript_path": "/tmp/transcript.jsonl",
            "cwd": "/test/dir",
        }

        mock_client = MagicMock()
        mock_client.send_event.return_value = {"status": "ok"}

        mock_state_manager = MagicMock()
        mock_state_manager.__enter__ = MagicMock(return_value=mock_state_manager)
        mock_state_manager.__exit__ = MagicMock(return_value=False)
        mock_state_manager.get_session.return_value = None

        with patch.dict("os.environ", {"WEAVE_PROJECT": "test/project"}, clear=False):
            with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
                with patch(
                    "weave.integrations.claude_plugin.config.is_enabled",
                    return_value=True,
                ):
                    with patch(
                        "weave.integrations.claude_plugin.core.state.StateManager",
                        return_value=mock_state_manager,
                    ):
                        with patch(
                            "weave.integrations.claude_plugin.core.socket_client.ensure_daemon_running",
                            return_value=mock_client,
                        ):
                            with patch(
                                "weave.integrations.claude_plugin.core.state.create_session_data",
                                return_value={"project": "test/project"},
                            ) as mock_create:
                                main()
                                mock_create.assert_called_once()
                                mock_state_manager.save_session.assert_called_once()

    def test_sends_event_to_daemon(self):
        """Should send event to daemon and handle response."""
        from weave.integrations.claude_plugin.core.hook import main

        payload = {
            "hook_event_name": "Stop",
            "session_id": "test-session",
            "cwd": "/test/dir",
        }

        mock_client = MagicMock()
        mock_client.send_event.return_value = {"status": "ok"}

        mock_state_manager = MagicMock()
        mock_state_manager.__enter__ = MagicMock(return_value=mock_state_manager)
        mock_state_manager.__exit__ = MagicMock(return_value=False)
        mock_state_manager.get_session.return_value = {"daemon_pid": 12345}

        with patch.dict("os.environ", {"WEAVE_PROJECT": "test/project"}, clear=False):
            with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
                with patch(
                    "weave.integrations.claude_plugin.config.is_enabled",
                    return_value=True,
                ):
                    with patch(
                        "weave.integrations.claude_plugin.core.state.StateManager",
                        return_value=mock_state_manager,
                    ):
                        with patch(
                            "weave.integrations.claude_plugin.core.socket_client.ensure_daemon_running",
                            return_value=mock_client,
                        ):
                            main()
                            mock_client.send_event.assert_called_once_with(
                                "Stop", payload, wait_response=False
                            )

    def test_returns_trace_url_for_user_prompt(self, capsys):
        """Should return trace URL for UserPromptSubmit event."""
        from weave.integrations.claude_plugin.core.hook import main

        payload = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "test-session",
            "cwd": "/test/dir",
        }

        mock_client = MagicMock()
        mock_client.send_event.return_value = {
            "trace_url": "https://weave.wandb.ai/trace/123",
            "session_id": "test-session",
        }

        mock_state_manager = MagicMock()
        mock_state_manager.__enter__ = MagicMock(return_value=mock_state_manager)
        mock_state_manager.__exit__ = MagicMock(return_value=False)
        mock_state_manager.get_session.return_value = {"daemon_pid": 12345}

        with patch.dict("os.environ", {"WEAVE_PROJECT": "test/project"}, clear=False):
            with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
                with patch(
                    "weave.integrations.claude_plugin.config.is_enabled",
                    return_value=True,
                ):
                    with patch(
                        "weave.integrations.claude_plugin.core.state.StateManager",
                        return_value=mock_state_manager,
                    ):
                        with patch(
                            "weave.integrations.claude_plugin.core.socket_client.ensure_daemon_running",
                            return_value=mock_client,
                        ):
                            main()

                            # Check output
                            captured = capsys.readouterr()
                            output = json.loads(captured.out)
                            assert "hookSpecificOutput" in output
                            assert (
                                "https://weave.wandb.ai/trace/123"
                                in output["hookSpecificOutput"]["additionalContext"]
                            )

    @pytest.mark.disable_logging_error_check
    def test_exits_on_daemon_connection_failure(self):
        """Should exit 1 when daemon connection fails."""
        from weave.integrations.claude_plugin.core.hook import main

        payload = {
            "hook_event_name": "Stop",
            "session_id": "test-session",
            "cwd": "/test/dir",
        }

        mock_state_manager = MagicMock()
        mock_state_manager.__enter__ = MagicMock(return_value=mock_state_manager)
        mock_state_manager.__exit__ = MagicMock(return_value=False)
        mock_state_manager.get_session.return_value = {"daemon_pid": 12345}

        with patch.dict("os.environ", {"WEAVE_PROJECT": "test/project"}, clear=False):
            with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
                with patch(
                    "weave.integrations.claude_plugin.config.is_enabled",
                    return_value=True,
                ):
                    with patch(
                        "weave.integrations.claude_plugin.core.state.StateManager",
                        return_value=mock_state_manager,
                    ):
                        with patch(
                            "weave.integrations.claude_plugin.core.socket_client.ensure_daemon_running",
                            side_effect=Exception("Connection refused"),
                        ):
                            with pytest.raises(SystemExit) as exc:
                                main()
                            assert exc.value.code == 1

    @pytest.mark.disable_logging_error_check
    def test_exits_on_send_event_failure(self):
        """Should exit 1 when send_event raises exception."""
        from weave.integrations.claude_plugin.core.hook import main

        payload = {
            "hook_event_name": "Stop",
            "session_id": "test-session",
            "cwd": "/test/dir",
        }

        mock_client = MagicMock()
        mock_client.send_event.side_effect = Exception("Send failed")

        mock_state_manager = MagicMock()
        mock_state_manager.__enter__ = MagicMock(return_value=mock_state_manager)
        mock_state_manager.__exit__ = MagicMock(return_value=False)
        mock_state_manager.get_session.return_value = {"daemon_pid": 12345}

        with patch.dict("os.environ", {"WEAVE_PROJECT": "test/project"}, clear=False):
            with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
                with patch(
                    "weave.integrations.claude_plugin.config.is_enabled",
                    return_value=True,
                ):
                    with patch(
                        "weave.integrations.claude_plugin.core.state.StateManager",
                        return_value=mock_state_manager,
                    ):
                        with patch(
                            "weave.integrations.claude_plugin.core.socket_client.ensure_daemon_running",
                            return_value=mock_client,
                        ):
                            with pytest.raises(SystemExit) as exc:
                                main()
                            assert exc.value.code == 1

    def test_waits_for_response_on_session_start(self):
        """Should wait for response on SessionStart event."""
        from weave.integrations.claude_plugin.core.hook import main

        payload = {
            "hook_event_name": "SessionStart",
            "session_id": "test-session",
            "transcript_path": "/tmp/transcript.jsonl",
            "cwd": "/test/dir",
        }

        mock_client = MagicMock()
        mock_client.send_event.return_value = {"status": "ok"}

        mock_state_manager = MagicMock()
        mock_state_manager.__enter__ = MagicMock(return_value=mock_state_manager)
        mock_state_manager.__exit__ = MagicMock(return_value=False)
        mock_state_manager.get_session.return_value = {"daemon_pid": 12345}

        with patch.dict("os.environ", {"WEAVE_PROJECT": "test/project"}, clear=False):
            with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
                with patch(
                    "weave.integrations.claude_plugin.config.is_enabled",
                    return_value=True,
                ):
                    with patch(
                        "weave.integrations.claude_plugin.core.state.StateManager",
                        return_value=mock_state_manager,
                    ):
                        with patch(
                            "weave.integrations.claude_plugin.core.socket_client.ensure_daemon_running",
                            return_value=mock_client,
                        ):
                            with patch(
                                "weave.integrations.claude_plugin.core.state.create_session_data",
                                return_value={"project": "test/project"},
                            ):
                                main()
                                # SessionStart should wait for response
                                mock_client.send_event.assert_called_once_with(
                                    "SessionStart", payload, wait_response=True
                                )
