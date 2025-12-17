"""Tests for SessionProcessor factory class."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock


class TestSessionProcessorInit:
    """Test SessionProcessor initialization."""

    def test_init_stores_client_and_project(self):
        """Verify client and project are stored."""
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

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
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        assert processor.source == "plugin"


class TestCreateSessionCall:
    """Test SessionProcessor.create_session_call()."""

    def test_create_session_call_returns_call_object(self):
        """Verify create_session_call returns a Call with expected fields."""
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

        mock_client = MagicMock()
        mock_call = MagicMock()
        mock_call.id = "call-123"
        mock_call.trace_id = "trace-456"
        mock_call.ui_url = "https://wandb.ai/..."
        mock_client.create_call.return_value = mock_call

        processor = SessionProcessor(client=mock_client, project="entity/project")

        result_call, result_name = processor.create_session_call(
            session_id="session-abc",
            first_prompt="Help me refactor this code",
            cwd="/path/to/project",
        )

        assert result_call is mock_call
        assert isinstance(result_name, str)  # Display name is returned
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
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

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
        assert (
            len(call_kwargs["inputs"]["first_prompt"]) <= 1014
        )  # 1000 + "...[truncated]"

    def test_create_session_call_source_import(self):
        """Verify source='import' produces correct attribute."""
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

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
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

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
        # Input uses Anthropic message format for chat view detection
        assert "messages" in call_kwargs["inputs"]
        messages = call_kwargs["inputs"]["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Help me fix this bug"
        assert call_kwargs["attributes"]["turn_number"] == 1
        assert "Turn 1:" in call_kwargs["display_name"]

    def test_create_turn_call_with_pending_question(self):
        """Verify pending_question is added to inputs."""
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

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
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

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
        from weave.integrations.claude_plugin.session.session_parser import (
            FileBackup,
            Turn,
        )
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

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
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

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
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

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

            result = processor._collect_session_file_snapshots(
                mock_session, sessions_dir
            )

            # Should have at least the session file
            assert len(result) >= 1

    def test_collect_session_file_snapshots_includes_changed_files(self):
        """Verify changed files from disk are included."""
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

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

            result = processor._collect_session_file_snapshots(
                mock_session, sessions_dir
            )

            # Should include the changed file
            assert len(result) >= 1


class TestFinishTurnCall:
    """Test SessionProcessor.finish_turn_call()."""

    def test_finish_turn_call_builds_output(self):
        """Verify finish_turn_call builds correct output structure."""
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

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

        # Output uses Message format for ChatView (not Anthropic's native format)
        # This enables reasoning_content (collapsible thinking) and tool_calls with results
        assert output["role"] == "assistant"
        assert output["model"] == "claude-3"
        assert "content" in output
        assert isinstance(output["content"], str)  # Content is string, not list
        # Note: "type" is intentionally omitted to avoid Anthropic format detection

        # Summary contains metadata (tool_call_count, model, duration_ms, etc.)
        summary = mock_turn_call.summary
        assert "tool_call_count" in summary
        assert summary["tool_call_count"] == 0
        assert summary["model"] == "claude-3"
        assert summary["duration_ms"] == 1000

    def test_finish_turn_call_returns_extracted_question(self):
        """Verify pending question is extracted and returned."""
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        mock_turn_call = MagicMock()
        mock_msg = MagicMock()
        mock_msg.get_text.return_value = (
            "Here's my answer. What would you like to do next?"
        )

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
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

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

    def test_finish_turn_call_includes_reasoning_content(self):
        """Verify thinking content is included as reasoning_content."""
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        mock_turn_call = MagicMock()
        mock_msg = MagicMock()
        mock_msg.get_text.return_value = "Here's my response."
        mock_msg.thinking_content = "Let me think about this step by step..."

        mock_turn = MagicMock()
        mock_turn.assistant_messages = [mock_msg]
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

        call_args = mock_client.finish_call.call_args
        output = call_args.kwargs.get("output") or call_args[1].get("output", {})

        # reasoning_content should be included for ChatView's collapsible thinking UI
        assert "reasoning_content" in output
        assert "Let me think about this step by step" in output["reasoning_content"]

    def test_finish_turn_call_includes_tool_calls_with_results(self):
        """Verify tool calls are included in OpenAI format with results."""
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        mock_turn_call = MagicMock()
        mock_msg = MagicMock()
        mock_msg.get_text.return_value = "I'll read that file for you."
        mock_msg.thinking_content = None

        # Create mock tool call with result
        mock_tool_call = MagicMock()
        mock_tool_call.id = "toolu_abc123"
        mock_tool_call.name = "Read"
        mock_tool_call.input = {"file_path": "/path/to/file.py"}
        mock_tool_call.result = "def hello():\n    print('Hello, World!')"

        mock_turn = MagicMock()
        mock_turn.assistant_messages = [mock_msg]
        mock_turn.all_tool_calls.return_value = [mock_tool_call]
        mock_turn.total_usage.return_value = None
        mock_turn.primary_model.return_value = "claude-3"
        mock_turn.duration_ms.return_value = 1000
        mock_turn.file_backups = []
        mock_turn.raw_messages = None
        mock_turn.user_message = MagicMock()
        mock_turn.user_message.content = "Read file.py"

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

        call_args = mock_client.finish_call.call_args
        output = call_args.kwargs.get("output") or call_args[1].get("output", {})

        # tool_calls should be in OpenAI format with embedded results
        assert "tool_calls" in output
        assert len(output["tool_calls"]) == 1

        tool_call = output["tool_calls"][0]
        assert tool_call["id"] == "toolu_abc123"
        assert tool_call["type"] == "function"
        assert tool_call["function"]["name"] == "Read"
        assert "/path/to/file.py" in tool_call["function"]["arguments"]

        # Response should be embedded with tool result
        assert "response" in tool_call
        assert tool_call["response"]["role"] == "tool"
        assert "def hello():" in tool_call["response"]["content"]
        assert tool_call["response"]["tool_call_id"] == "toolu_abc123"


class TestBuildTurnOutput:
    """Test SessionProcessor.build_turn_output() static method."""

    def test_build_turn_output_returns_message_format(self):
        """Verify build_turn_output returns proper Message format for ChatView."""
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

        mock_msg = MagicMock()
        mock_msg.get_text.return_value = "Here's my response."
        mock_msg.thinking_content = "Let me think..."

        mock_tool_call = MagicMock()
        mock_tool_call.id = "toolu_123"
        mock_tool_call.name = "Read"
        mock_tool_call.input = {"file_path": "/test.py"}
        mock_tool_call.result = "file content"

        mock_turn = MagicMock()
        mock_turn.assistant_messages = [mock_msg]
        mock_turn.all_tool_calls.return_value = [mock_tool_call]
        mock_turn.primary_model.return_value = "claude-3"

        output, assistant_text, thinking_text = SessionProcessor.build_turn_output(
            mock_turn
        )

        # Verify Message format structure
        assert output["role"] == "assistant"
        assert "Here's my response" in output["content"]
        assert output["model"] == "claude-3"
        assert "Let me think" in output["reasoning_content"]

        # Verify tool_calls in OpenAI format
        assert "tool_calls" in output
        assert len(output["tool_calls"]) == 1
        tc = output["tool_calls"][0]
        assert tc["id"] == "toolu_123"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "Read"
        assert tc["response"]["role"] == "tool"
        assert tc["response"]["content"] == "file content"

        # Verify returned text
        assert "Here's my response" in assistant_text
        assert "Let me think" in thinking_text

    def test_build_turn_output_handles_interrupted(self):
        """Verify interrupted flag is set correctly."""
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

        mock_msg = MagicMock()
        mock_msg.get_text.return_value = "Response"
        mock_msg.thinking_content = None

        mock_turn = MagicMock()
        mock_turn.assistant_messages = [mock_msg]
        mock_turn.all_tool_calls.return_value = []
        mock_turn.primary_model.return_value = "claude-3"

        output, _, _ = SessionProcessor.build_turn_output(mock_turn, interrupted=True)

        assert output["interrupted"] is True
        assert output["stop_reason"] == "user_interrupt"


class TestFinishSessionCall:
    """Test SessionProcessor.finish_session_call()."""

    def test_finish_session_call_builds_summary(self):
        """Verify finish_session_call builds correct summary structure."""
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        mock_session_call = MagicMock()
        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.turns = []
        mock_session.total_tool_calls.return_value = 5
        mock_session.tool_call_counts.return_value = {"Read": 3, "Edit": 2}
        mock_session.duration_ms.return_value = 10000
        mock_session.primary_model.return_value = "claude-3"
        mock_session.total_usage.return_value = None
        mock_session.cwd = None
        mock_session.get_all_changed_files.return_value = []

        with tempfile.TemporaryDirectory() as tmpdir:
            sessions_dir = Path(tmpdir)

            processor.finish_session_call(
                session_call=mock_session_call,
                session=mock_session,
                sessions_dir=sessions_dir,
            )

        # Verify summary was set
        assert mock_session_call.summary is not None
        summary = mock_session_call.summary
        assert summary["turn_count"] == 0
        assert summary["tool_call_count"] == 5
        assert summary["tool_call_breakdown"] == {"Read": 3, "Edit": 2}

        # Verify finish_call was called
        mock_client.finish_call.assert_called_once()

    def test_finish_session_call_with_extra_summary(self):
        """Verify extra_summary fields are merged."""
        from weave.integrations.claude_plugin.session.session_processor import (
            SessionProcessor,
        )

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        mock_session_call = MagicMock()
        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.turns = []
        mock_session.total_tool_calls.return_value = 0
        mock_session.tool_call_counts.return_value = {}
        mock_session.duration_ms.return_value = 1000
        mock_session.primary_model.return_value = "claude-3"
        mock_session.total_usage.return_value = None
        mock_session.cwd = None
        mock_session.get_all_changed_files.return_value = []

        with tempfile.TemporaryDirectory() as tmpdir:
            sessions_dir = Path(tmpdir)

            processor.finish_session_call(
                session_call=mock_session_call,
                session=mock_session,
                sessions_dir=sessions_dir,
                extra_summary={"compaction_count": 2, "redacted_secrets": 5},
            )

        summary = mock_session_call.summary
        assert summary["compaction_count"] == 2
        assert summary["redacted_secrets"] == 5
