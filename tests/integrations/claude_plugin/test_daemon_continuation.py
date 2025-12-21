"""Tests for session continuation detection in WeaveDaemon."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from pathlib import Path

from weave.integrations.claude_plugin.core.daemon import WeaveDaemon


class TestSessionContinuation:
    """Tests for _check_session_continuation and _create_continuation_session_call."""

    @pytest.fixture
    def daemon(self):
        """Create a WeaveDaemon with mocked dependencies."""
        daemon = WeaveDaemon.__new__(WeaveDaemon)
        daemon.session_id = "test-session-123"
        daemon.session_call_id = "test-call-456"
        daemon.weave_client = MagicMock()
        daemon.transcript_path = None
        return daemon

    @pytest.mark.anyio
    async def test_check_session_continuation_when_not_ended(self, daemon):
        """Continuation check returns False when session not ended."""
        # Mock StateManager to return session without session_ended flag
        # Also mock weave_client to return a call with ended_at=None (not ended)
        mock_call = MagicMock()
        mock_call.ended_at = None
        daemon.weave_client.get_call.return_value = mock_call

        with patch(
            "weave.integrations.claude_plugin.core.daemon.StateManager"
        ) as mock_state:
            mock_state_ctx = MagicMock()
            mock_state_ctx.get_session.return_value = {
                "session_id": "test-session-123",
                "session_ended": False,
            }
            mock_state.return_value.__enter__.return_value = mock_state_ctx
            mock_state.return_value.__exit__.return_value = None

            result = await daemon._check_session_continuation()

            assert result is False
            mock_state_ctx.get_session.assert_called_once_with("test-session-123")

    @pytest.mark.anyio
    async def test_check_session_continuation_when_ended(self, daemon):
        """Continuation check returns True when session was ended."""
        # Mock StateManager to return session with session_ended=True
        with patch(
            "weave.integrations.claude_plugin.core.daemon.StateManager"
        ) as mock_state:
            mock_state_ctx = MagicMock()
            mock_state_ctx.get_session.return_value = {
                "session_id": "test-session-123",
                "session_ended": True,
            }
            mock_state.return_value.__enter__.return_value = mock_state_ctx
            mock_state.return_value.__exit__.return_value = None

            result = await daemon._check_session_continuation()

            assert result is True
            mock_state_ctx.get_session.assert_called_once_with("test-session-123")

    @pytest.mark.anyio
    async def test_check_session_continuation_fallback_to_api(self, daemon):
        """Continuation check falls back to API when state has no session_ended."""
        # Mock StateManager to return session without session_ended flag
        # Mock weave_client to return a call with ended_at set
        mock_call = MagicMock()
        mock_call.ended_at = "2024-01-01T00:00:00Z"
        daemon.weave_client.get_call.return_value = mock_call

        with patch(
            "weave.integrations.claude_plugin.core.daemon.StateManager"
        ) as mock_state:
            mock_state_ctx = MagicMock()
            mock_state_ctx.get_session.return_value = {
                "session_id": "test-session-123",
            }  # No session_ended field
            mock_state.return_value.__enter__.return_value = mock_state_ctx
            mock_state.return_value.__exit__.return_value = None

            result = await daemon._check_session_continuation()

            assert result is True
            daemon.weave_client.get_call.assert_called_once_with(
                "test-call-456", columns=["ended_at"]
            )

    @pytest.mark.anyio
    async def test_check_session_continuation_api_not_ended(self, daemon):
        """Continuation check returns False when API shows call not ended."""
        # Mock StateManager to return session without session_ended flag
        # Mock weave_client to return a call with ended_at=None
        mock_call = MagicMock()
        mock_call.ended_at = None
        daemon.weave_client.get_call.return_value = mock_call

        with patch(
            "weave.integrations.claude_plugin.core.daemon.StateManager"
        ) as mock_state:
            mock_state_ctx = MagicMock()
            mock_state_ctx.get_session.return_value = {
                "session_id": "test-session-123",
            }  # No session_ended field
            mock_state.return_value.__enter__.return_value = mock_state_ctx
            mock_state.return_value.__exit__.return_value = None

            result = await daemon._check_session_continuation()

            assert result is False

    @pytest.mark.anyio
    async def test_create_continuation_session_call_basic(self, daemon):
        """Continuation creates new session call with proper naming."""
        daemon.session_call_id = "previous-call-id"
        daemon.trace_id = "previous-trace-id"
        daemon.trace_url = "https://example.com/trace/previous"
        daemon.current_turn_call_id = "turn-123"
        daemon.turn_number = 5
        daemon.total_tool_calls = 10
        daemon.tool_counts = {"Bash": 3, "Read": 7}
        daemon._current_turn_tool_calls = ["tool1", "tool2"]
        daemon._pending_question = "What is this?"
        daemon.compaction_count = 2
        daemon._redacted_count = 1

        # Mock the session call creation
        mock_call = MagicMock()
        mock_call.id = "new-call-id"
        mock_call.trace_id = "new-trace-id"
        mock_call.ui_url = "https://example.com/trace/new"
        daemon.weave_client.create_call.return_value = mock_call
        daemon.weave_client.flush = MagicMock()

        payload = {
            "prompt": "Continue the work",
            "cwd": "/path/to/work",
        }

        with patch(
            "weave.integrations.claude_plugin.core.daemon.StateManager"
        ) as mock_state, patch(
            "weave.integrations.claude_plugin.core.daemon.generate_session_name"
        ) as mock_gen_name, patch(
            "weave.integrations.claude_plugin.core.daemon.get_hostname"
        ) as mock_hostname:
            mock_state_ctx = MagicMock()
            mock_state_ctx.get_session.return_value = {
                "continuation_count": 0,
            }
            mock_state.return_value.__enter__.return_value = mock_state_ctx
            mock_state.return_value.__exit__.return_value = None

            mock_gen_name.return_value = ("Continue the work", None)
            mock_hostname.return_value = "test-host"

            result = await daemon._create_continuation_session_call(payload)

            # Verify result
            assert result["status"] == "ok"
            assert result["trace_url"] == "https://example.com/trace/new"
            assert result["session_id"] == "test-session-123"

            # Verify create_call was called with "Continued: " prefix
            call_args = daemon.weave_client.create_call.call_args
            assert call_args[1]["display_name"] == "Continued: Continue the work"
            assert call_args[1]["op"] == "claude_code.session"
            assert call_args[1]["inputs"]["session_id"] == "test-session-123"
            assert call_args[1]["inputs"]["cwd"] == "/path/to/work"
            assert call_args[1]["inputs"]["first_prompt"] == "Continue the work"
            assert (
                call_args[1]["attributes"]["continuation_of"] == "previous-call-id"
            )

            # Verify daemon state was reset
            assert daemon.session_call_id == "new-call-id"
            assert daemon.trace_id == "new-trace-id"
            assert daemon.trace_url == "https://example.com/trace/new"
            assert daemon.current_turn_call_id is None
            assert daemon.turn_number == 0
            assert daemon.total_tool_calls == 0
            assert daemon.tool_counts == {}
            assert daemon._current_turn_tool_calls == []
            assert daemon._pending_question is None
            assert daemon.compaction_count == 0
            assert daemon._redacted_count == 0

            # Verify state was saved with session_ended=False and continuation_count=1
            save_call = mock_state_ctx.save_session.call_args
            assert save_call[0][0] == "test-session-123"
            saved_data = save_call[0][1]
            assert saved_data["session_ended"] is False
            assert saved_data["continuation_count"] == 1
            assert saved_data["session_call_id"] == "new-call-id"
            assert saved_data["trace_id"] == "new-trace-id"

            # Verify flush was called
            daemon.weave_client.flush.assert_called_once()

    @pytest.mark.anyio
    async def test_continuation_increments_counter(self, daemon):
        """Multiple continuations increment the counter."""
        daemon.session_call_id = "previous-call-id"

        # Mock the session call creation
        mock_call = MagicMock()
        mock_call.id = "new-call-id"
        mock_call.trace_id = "new-trace-id"
        mock_call.ui_url = "https://example.com/trace/new"
        daemon.weave_client.create_call.return_value = mock_call
        daemon.weave_client.flush = MagicMock()

        payload = {
            "prompt": "Continue again",
            "cwd": "/path/to/work",
        }

        with patch(
            "weave.integrations.claude_plugin.core.daemon.StateManager"
        ) as mock_state, patch(
            "weave.integrations.claude_plugin.core.daemon.generate_session_name"
        ) as mock_gen_name, patch(
            "weave.integrations.claude_plugin.core.daemon.get_hostname"
        ) as mock_hostname:
            mock_state_ctx = MagicMock()
            # Start with continuation_count=2
            mock_state_ctx.get_session.return_value = {
                "continuation_count": 2,
            }
            mock_state.return_value.__enter__.return_value = mock_state_ctx
            mock_state.return_value.__exit__.return_value = None

            mock_gen_name.return_value = ("Continue again", None)
            mock_hostname.return_value = "test-host"

            await daemon._create_continuation_session_call(payload)

            # Verify continuation_count was incremented to 3
            save_call = mock_state_ctx.save_session.call_args
            saved_data = save_call[0][1]
            assert saved_data["continuation_count"] == 3

    @pytest.mark.anyio
    async def test_create_continuation_without_weave_client(self, daemon):
        """Continuation returns error when Weave not initialized."""
        daemon.weave_client = None

        payload = {"prompt": "Test", "cwd": "/path"}

        result = await daemon._create_continuation_session_call(payload)

        assert result["status"] == "error"
        assert result["message"] == "Weave not initialized"

    @pytest.mark.anyio
    async def test_check_session_continuation_no_session_data(self, daemon):
        """Continuation check handles missing session data gracefully."""
        # Mock StateManager to return None (no session data)
        # Also mock weave_client to return a call with ended_at=None
        mock_call = MagicMock()
        mock_call.ended_at = None
        daemon.weave_client.get_call.return_value = mock_call

        with patch(
            "weave.integrations.claude_plugin.core.daemon.StateManager"
        ) as mock_state:
            mock_state_ctx = MagicMock()
            mock_state_ctx.get_session.return_value = None  # No session data
            mock_state.return_value.__enter__.return_value = mock_state_ctx
            mock_state.return_value.__exit__.return_value = None

            result = await daemon._check_session_continuation()

            assert result is False
            mock_state_ctx.get_session.assert_called_once_with("test-session-123")

    @pytest.mark.anyio
    async def test_check_session_continuation_api_error(self, daemon):
        """Continuation check handles API errors gracefully."""
        # Mock StateManager to return session without session_ended
        # Mock weave_client to raise an exception
        daemon.weave_client.get_call.side_effect = Exception("API error")

        with patch(
            "weave.integrations.claude_plugin.core.daemon.StateManager"
        ) as mock_state:
            mock_state_ctx = MagicMock()
            mock_state_ctx.get_session.return_value = {}  # No session_ended field
            mock_state.return_value.__enter__.return_value = mock_state_ctx
            mock_state.return_value.__exit__.return_value = None

            result = await daemon._check_session_continuation()

            # Should return False when API fails
            assert result is False
