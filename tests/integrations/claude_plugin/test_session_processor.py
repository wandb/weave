"""Tests for SessionProcessor factory class."""

import pytest
from unittest.mock import MagicMock


class TestSessionProcessorInit:
    """Test SessionProcessor initialization."""

    def test_init_stores_client_and_project(self):
        """Verify client and project are stored."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        processor = SessionProcessor(
            client=mock_client,
            project="entity/project",
            source="plugin",
        )

        assert processor.client is mock_client
        assert processor.project == "entity/project"
        assert processor.source == "plugin"

    def test_init_default_source_is_plugin(self):
        """Verify default source is 'plugin'."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        assert processor.source == "plugin"


class TestCreateSessionCall:
    """Test SessionProcessor.create_session_call()."""

    def test_create_session_call_returns_call_object(self):
        """Verify create_session_call returns a Call with expected fields."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        mock_call = MagicMock()
        mock_call.id = "call-123"
        mock_call.trace_id = "trace-456"
        mock_call.ui_url = "https://wandb.ai/..."
        mock_client.create_call.return_value = mock_call

        processor = SessionProcessor(client=mock_client, project="entity/project")

        result = processor.create_session_call(
            session_id="session-abc",
            first_prompt="Help me refactor this code",
            cwd="/path/to/project",
        )

        assert result is mock_call
        mock_client.create_call.assert_called_once()

        # Verify call arguments
        call_kwargs = mock_client.create_call.call_args.kwargs
        assert call_kwargs["op"] == "claude_code.session"
        assert call_kwargs["inputs"]["session_id"] == "session-abc"
        assert call_kwargs["inputs"]["cwd"] == "/path/to/project"
        assert "first_prompt" in call_kwargs["inputs"]
        assert call_kwargs["attributes"]["session_id"] == "session-abc"
        assert call_kwargs["attributes"]["source"] == "claude-code-plugin"
        assert call_kwargs["use_stack"] is False

    def test_create_session_call_truncates_long_prompt(self):
        """Verify first_prompt is truncated to 1000 chars."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock()

        processor = SessionProcessor(client=mock_client, project="entity/project")

        long_prompt = "x" * 2000
        processor.create_session_call(
            session_id="session-abc",
            first_prompt=long_prompt,
        )

        call_kwargs = mock_client.create_call.call_args.kwargs
        # Should be truncated with "...[truncated]" suffix
        assert len(call_kwargs["inputs"]["first_prompt"]) <= 1014  # 1000 + "...[truncated]"

    def test_create_session_call_source_import(self):
        """Verify source='import' produces correct attribute."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock()

        processor = SessionProcessor(
            client=mock_client, project="entity/project", source="import"
        )

        processor.create_session_call(session_id="abc", first_prompt="test")

        call_kwargs = mock_client.create_call.call_args.kwargs
        assert call_kwargs["attributes"]["source"] == "claude-code-import"
