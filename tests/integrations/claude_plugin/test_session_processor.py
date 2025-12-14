"""Tests for SessionProcessor factory class."""

import pytest
from unittest.mock import MagicMock
from pathlib import Path
import tempfile
import os


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


class TestCreateTurnCall:
    """Test SessionProcessor.create_turn_call()."""

    def test_create_turn_call_basic(self):
        """Verify create_turn_call creates turn with correct structure."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock()
        mock_parent = MagicMock()

        processor = SessionProcessor(client=mock_client, project="entity/project")

        processor.create_turn_call(
            parent=mock_parent,
            turn_number=1,
            user_message="Help me fix this bug",
        )

        call_kwargs = mock_client.create_call.call_args.kwargs
        assert call_kwargs["op"] == "claude_code.turn"
        assert call_kwargs["parent"] is mock_parent
        assert call_kwargs["inputs"]["user_message"] == "Help me fix this bug"
        assert call_kwargs["attributes"]["turn_number"] == 1
        assert "Turn 1:" in call_kwargs["display_name"]

    def test_create_turn_call_with_pending_question(self):
        """Verify pending_question is added to inputs."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock()

        processor = SessionProcessor(client=mock_client, project="entity/project")

        processor.create_turn_call(
            parent=MagicMock(),
            turn_number=2,
            user_message="Yes, use TypeScript",
            pending_question="Which language should I use?",
        )

        call_kwargs = mock_client.create_call.call_args.kwargs
        assert call_kwargs["inputs"]["in_response_to"] == "Which language should I use?"

    def test_create_turn_call_compacted(self):
        """Verify compacted turns get special display name."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock()

        processor = SessionProcessor(client=mock_client, project="entity/project")

        processor.create_turn_call(
            parent=MagicMock(),
            turn_number=5,
            user_message="This session is being continued...",
            is_compacted=True,
        )

        call_kwargs = mock_client.create_call.call_args.kwargs
        assert "Compacted" in call_kwargs["display_name"]
        assert call_kwargs["attributes"]["compacted"] is True


class TestFileSnapshotCollection:
    """Test SessionProcessor file snapshot helpers."""

    def test_collect_turn_file_snapshots(self):
        """Verify _collect_turn_file_snapshots returns Content objects."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor
        from weave.integrations.claude_plugin.session_parser import Turn, FileBackup

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        # Create mock turn with file backups
        mock_turn = MagicMock(spec=Turn)
        mock_fb = MagicMock(spec=FileBackup)
        mock_content = MagicMock()
        mock_fb.load_content.return_value = mock_content
        mock_turn.file_backups = [mock_fb]

        result = processor._collect_turn_file_snapshots(mock_turn, "session-123")

        assert len(result) == 1
        assert result[0] is mock_content
        mock_fb.load_content.assert_called_once_with("session-123")

    def test_collect_turn_file_snapshots_skips_failed_loads(self):
        """Verify None results from load_content are skipped."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        mock_turn = MagicMock()
        mock_fb1 = MagicMock()
        mock_fb1.load_content.return_value = None  # Failed load
        mock_fb2 = MagicMock()
        mock_content = MagicMock()
        mock_fb2.load_content.return_value = mock_content
        mock_turn.file_backups = [mock_fb1, mock_fb2]

        result = processor._collect_turn_file_snapshots(mock_turn, "session-123")

        assert len(result) == 1
        assert result[0] is mock_content

    def test_collect_session_file_snapshots_includes_session_file(self):
        """Verify session JSONL file is included."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        # Create temp directory with session file
        with tempfile.TemporaryDirectory() as tmpdir:
            sessions_dir = Path(tmpdir)
            session_file = sessions_dir / "session-123.jsonl"
            session_file.write_text('{"type": "test"}')

            mock_session = MagicMock()
            mock_session.session_id = "session-123"
            mock_session.cwd = None
            mock_session.get_all_changed_files.return_value = []

            result = processor._collect_session_file_snapshots(mock_session, sessions_dir)

            # Should have at least the session file
            assert len(result) >= 1

    def test_collect_session_file_snapshots_includes_changed_files(self):
        """Verify changed files from disk are included."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        with tempfile.TemporaryDirectory() as tmpdir:
            sessions_dir = Path(tmpdir)
            cwd = Path(tmpdir) / "project"
            cwd.mkdir()

            # Create a "changed" file
            changed_file = cwd / "test.py"
            changed_file.write_text("print('hello')")

            mock_session = MagicMock()
            mock_session.session_id = "session-123"
            mock_session.cwd = str(cwd)
            mock_session.get_all_changed_files.return_value = ["test.py"]

            result = processor._collect_session_file_snapshots(mock_session, sessions_dir)

            # Should include the changed file
            assert len(result) >= 1


class TestFinishTurnCall:
    """Test SessionProcessor.finish_turn_call()."""

    def test_finish_turn_call_builds_output(self):
        """Verify finish_turn_call builds correct output structure."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        mock_turn_call = MagicMock()
        mock_turn = MagicMock()
        mock_turn.assistant_messages = []
        mock_turn.all_tool_calls.return_value = []
        mock_turn.total_usage.return_value = None
        mock_turn.primary_model.return_value = "claude-3"
        mock_turn.duration_ms.return_value = 1000
        mock_turn.file_backups = []
        mock_turn.raw_messages = None
        mock_turn.user_message = MagicMock()
        mock_turn.user_message.content = "test prompt"

        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.turns = [mock_turn]
        mock_session.cwd = None

        processor.finish_turn_call(
            turn_call=mock_turn_call,
            turn=mock_turn,
            session=mock_session,
            turn_index=0,
        )

        mock_client.finish_call.assert_called_once()
        call_args = mock_client.finish_call.call_args
        output = call_args.kwargs.get("output") or call_args[1].get("output", {})

        assert "response" in output
        assert "tool_call_count" in output
        assert output["tool_call_count"] == 0

    def test_finish_turn_call_returns_extracted_question(self):
        """Verify pending question is extracted and returned."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        mock_turn_call = MagicMock()
        mock_msg = MagicMock()
        mock_msg.get_text.return_value = "Here's my answer. What would you like to do next?"

        mock_turn = MagicMock()
        mock_turn.assistant_messages = [mock_msg]
        mock_turn.all_tool_calls.return_value = []
        mock_turn.total_usage.return_value = None
        mock_turn.primary_model.return_value = "claude-3"
        mock_turn.duration_ms.return_value = 1000
        mock_turn.file_backups = []
        mock_turn.raw_messages = None
        mock_turn.user_message = MagicMock()
        mock_turn.user_message.content = "test"

        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.turns = [mock_turn]
        mock_session.cwd = None

        result = processor.finish_turn_call(
            turn_call=mock_turn_call,
            turn=mock_turn,
            session=mock_session,
            turn_index=0,
        )

        assert result is not None
        assert "?" in result

    def test_finish_turn_call_interrupted_returns_none(self):
        """Verify interrupted turns don't extract questions."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        mock_turn_call = MagicMock()
        mock_msg = MagicMock()
        mock_msg.get_text.return_value = "What would you like?"

        mock_turn = MagicMock()
        mock_turn.assistant_messages = [mock_msg]
        mock_turn.all_tool_calls.return_value = []
        mock_turn.total_usage.return_value = None
        mock_turn.primary_model.return_value = "claude-3"
        mock_turn.duration_ms.return_value = 1000
        mock_turn.file_backups = []
        mock_turn.raw_messages = None
        mock_turn.user_message = MagicMock()
        mock_turn.user_message.content = "test"

        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.turns = [mock_turn]
        mock_session.cwd = None

        result = processor.finish_turn_call(
            turn_call=mock_turn_call,
            turn=mock_turn,
            session=mock_session,
            turn_index=0,
            interrupted=True,
        )

        assert result is None
