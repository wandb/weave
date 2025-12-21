"""Tests for session end handling in WeaveDaemon."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
from datetime import datetime, timezone

from weave.integrations.claude_plugin.core.daemon import WeaveDaemon


class TestSessionEnd:
    """Tests for _handle_session_end."""

    @pytest.fixture
    def daemon(self):
        """Create daemon with mocked dependencies."""
        daemon = WeaveDaemon("test-session-123")
        daemon.weave_client = MagicMock()
        daemon.session_call_id = "session-call-456"
        daemon.trace_id = "trace-abc"
        daemon.current_turn_call_id = None
        daemon.turn_number = 5
        daemon.total_tool_calls = 10
        daemon.tool_counts = {"Read": 3, "Write": 2}
        daemon.compaction_count = 0
        daemon._redacted_count = 0
        daemon._pending_inline_parent = None
        daemon.transcript_path = None
        daemon.project = "test-project"

        # Mock weave client methods
        daemon.weave_client._project_id = MagicMock(return_value="test-project")
        daemon.weave_client.finish_call = MagicMock()
        daemon.weave_client.flush = MagicMock()

        return daemon

    @pytest.mark.anyio
    async def test_session_end_includes_compaction_count(self, daemon):
        """Session end metadata includes compaction count."""
        daemon.compaction_count = 3
        payload = {"reason": "user_ended"}

        with patch(
            "weave.integrations.claude_plugin.core.daemon.reconstruct_call"
        ) as mock_reconstruct:
            mock_call = MagicMock()
            mock_reconstruct.return_value = mock_call

            await daemon._handle_session_end(payload)

        # Verify summary was set on call
        assert hasattr(mock_call, "summary")
        summary = mock_call.summary
        assert summary.get("compaction_count") == 3
        assert summary.get("turn_count") == 5
        assert summary.get("tool_call_count") == 10
        assert summary.get("end_reason") == "user_ended"

    @pytest.mark.anyio
    async def test_session_end_with_file_snapshots(self, daemon, tmp_path):
        """Session end captures file snapshots from changed files."""
        # Create a test session file with file changes
        session_file = tmp_path / "test-session-123.jsonl"
        session_data = [
            {"type": "context", "cwd": str(tmp_path), "sessionId": "test-session-123"},
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Write",
                            "input": {"file_path": str(tmp_path / "test.py")},
                        }
                    ]
                },
            },
        ]
        session_file.write_text("\n".join([str(s) for s in session_data]))

        # Create the changed file
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        daemon.transcript_path = session_file

        payload = {"reason": "user_ended"}

        with patch(
            "weave.integrations.claude_plugin.core.daemon.reconstruct_call"
        ) as mock_reconstruct, patch(
            "weave.integrations.claude_plugin.core.daemon.parse_session_file"
        ) as mock_parse, patch(
            "weave.integrations.claude_plugin.core.daemon.get_secret_scanner"
        ) as mock_scanner, patch(
            "weave.integrations.claude_plugin.core.daemon.generate_session_diff_html"
        ) as mock_diff, patch(
            "weave.integrations.claude_plugin.core.daemon.StateManager"
        ):
            mock_call = MagicMock()
            mock_reconstruct.return_value = mock_call

            # Mock session parser
            mock_session = MagicMock()
            mock_session.cwd = str(tmp_path)
            mock_session.session_id = "test-session-123"
            mock_session.total_usage.return_value = None
            mock_session.primary_model.return_value = "claude-opus-4"
            mock_session.duration_ms.return_value = 10000
            mock_session.first_user_prompt.return_value = "test prompt"
            mock_session.get_all_changed_files.return_value = [str(test_file)]
            mock_parse.return_value = mock_session

            # Mock scanner
            mock_scanner_instance = MagicMock()
            mock_scanner_instance.scan_content = MagicMock(
                side_effect=lambda content: (content, 0)
            )
            mock_scanner.return_value = mock_scanner_instance

            # Mock diff generation
            mock_diff.return_value = None

            await daemon._handle_session_end(payload)

        # Verify finish_call was called with output containing file_snapshots
        finish_call = daemon.weave_client.finish_call
        assert finish_call.called
        call_args = finish_call.call_args
        output = call_args[1].get("output", {})

        # File snapshots should be in output
        assert "file_snapshots" in output or daemon.transcript_path is not None

    @pytest.mark.anyio
    async def test_session_end_captures_git_metadata(self, daemon, tmp_path):
        """Session end captures git branch and commit info."""
        # Create a test session file
        session_file = tmp_path / "test-session-123.jsonl"
        session_data = [
            {"type": "context", "cwd": str(tmp_path), "sessionId": "test-session-123"}
        ]
        session_file.write_text("\n".join([str(s) for s in session_data]))

        daemon.transcript_path = session_file
        payload = {"reason": "user_ended"}

        git_info = {
            "branch": "feature/test",
            "commit": "abc123",
            "remote": "origin",
        }

        with patch(
            "weave.integrations.claude_plugin.core.daemon.reconstruct_call"
        ) as mock_reconstruct, patch(
            "weave.integrations.claude_plugin.core.daemon.parse_session_file"
        ) as mock_parse, patch(
            "weave.integrations.claude_plugin.core.daemon.get_git_info"
        ) as mock_git, patch(
            "weave.integrations.claude_plugin.core.daemon.get_secret_scanner"
        ) as mock_scanner, patch(
            "weave.integrations.claude_plugin.core.daemon.generate_session_diff_html"
        ) as mock_diff, patch(
            "weave.integrations.claude_plugin.core.daemon.StateManager"
        ):
            mock_call = MagicMock()
            mock_reconstruct.return_value = mock_call

            # Mock session parser
            mock_session = MagicMock()
            mock_session.cwd = str(tmp_path)
            mock_session.session_id = "test-session-123"
            mock_session.total_usage.return_value = None
            mock_session.primary_model.return_value = "claude-opus-4"
            mock_session.duration_ms.return_value = 10000
            mock_session.first_user_prompt.return_value = "test prompt"
            mock_session.get_all_changed_files.return_value = []
            mock_parse.return_value = mock_session

            # Mock git info
            mock_git.return_value = git_info

            # Mock scanner
            mock_scanner.return_value = None

            # Mock diff to return None (no HTML generated)
            mock_diff.return_value = None

            await daemon._handle_session_end(payload)

        # Verify summary includes git info
        assert hasattr(mock_call, "summary")
        summary = mock_call.summary
        assert summary.get("git") == git_info

    @pytest.mark.anyio
    async def test_session_end_without_compaction(self, daemon):
        """Session end does not include compaction_count if zero."""
        daemon.compaction_count = 0
        payload = {"reason": "user_ended"}

        with patch(
            "weave.integrations.claude_plugin.core.daemon.reconstruct_call"
        ) as mock_reconstruct:
            mock_call = MagicMock()
            mock_reconstruct.return_value = mock_call

            await daemon._handle_session_end(payload)

        # Verify summary does not include compaction_count
        assert hasattr(mock_call, "summary")
        summary = mock_call.summary
        assert "compaction_count" not in summary

    @pytest.mark.anyio
    async def test_session_end_sets_running_false(self, daemon):
        """Session end sets daemon.running to False."""
        daemon.running = True
        payload = {"reason": "user_ended"}

        with patch(
            "weave.integrations.claude_plugin.core.daemon.reconstruct_call"
        ) as mock_reconstruct:
            mock_call = MagicMock()
            mock_reconstruct.return_value = mock_call

            result = await daemon._handle_session_end(payload)

        # Verify daemon is no longer running
        assert daemon.running is False
        assert result == {"status": "ok"}

    @pytest.mark.anyio
    async def test_session_end_includes_redacted_count(self, daemon):
        """Session end includes redacted_secrets count when > 0."""
        daemon._redacted_count = 5
        payload = {"reason": "user_ended"}

        with patch(
            "weave.integrations.claude_plugin.core.daemon.reconstruct_call"
        ) as mock_reconstruct:
            mock_call = MagicMock()
            mock_reconstruct.return_value = mock_call

            await daemon._handle_session_end(payload)

        # Verify summary includes redacted_secrets
        assert hasattr(mock_call, "summary")
        summary = mock_call.summary
        assert summary.get("redacted_secrets") == 5

    @pytest.mark.anyio
    async def test_session_end_finishes_active_turn(self, daemon):
        """Session end finishes any active turn call."""
        daemon.current_turn_call_id = "turn-call-789"
        payload = {"reason": "user_ended"}

        with patch.object(
            daemon, "_finish_current_turn", new_callable=AsyncMock
        ) as mock_finish_turn, patch(
            "weave.integrations.claude_plugin.core.daemon.reconstruct_call"
        ) as mock_reconstruct:
            mock_call = MagicMock()
            mock_reconstruct.return_value = mock_call

            await daemon._handle_session_end(payload)

        # Verify turn was finished
        assert mock_finish_turn.called

    @pytest.mark.anyio
    async def test_session_end_processes_session_file(self, daemon):
        """Session end processes any remaining data from session file."""
        payload = {"reason": "user_ended"}

        with patch.object(
            daemon, "_process_session_file", new_callable=AsyncMock
        ) as mock_process, patch(
            "weave.integrations.claude_plugin.core.daemon.reconstruct_call"
        ) as mock_reconstruct:
            mock_call = MagicMock()
            mock_reconstruct.return_value = mock_call

            await daemon._handle_session_end(payload)

        # Verify session file was processed
        assert mock_process.called
