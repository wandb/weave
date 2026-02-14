"""Tests for session importer.

Tool calls are embedded in turn/subagent output using build_turn_output(),
not as separate child traces. This enables ChatView rendering.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from weave.integrations.claude_plugin.session.session_importer import (
    _import_session_to_weave,
    discover_session_files,
    extract_agent_id,
    is_uuid_filename,
)
from weave.integrations.claude_plugin.session.session_parser import (
    AssistantMessage,
    Session,
    TokenUsage,
    ToolCall,
    Turn,
    UserMessage,
)


def make_minimal_session(
    session_id: str = "test-session",
    turns: list[Turn] | None = None,
) -> Session:
    """Create a minimal Session for testing."""
    session = Session(
        session_id=session_id,
        filename="test.jsonl",
        git_branch="main",
        cwd="/tmp/test",
        version="1.0.0",
    )
    if turns:
        session.turns.extend(turns)
    return session


def make_turn_with_tool_call(
    user_content: str,
    tool_name: str,
    tool_input: dict,
    tool_result: str = "OK",
) -> Turn:
    """Create a Turn with a single tool call."""
    now = datetime.now(timezone.utc)
    turn = Turn(
        user_message=UserMessage(uuid="u1", content=user_content, timestamp=now)
    )
    turn.assistant_messages.append(
        AssistantMessage(
            uuid="a1",
            model="claude-sonnet-4-20250514",
            text_content=["Done"],
            tool_calls=[
                ToolCall(
                    id="tool-1",
                    name=tool_name,
                    input=tool_input,
                    timestamp=now,
                    result=tool_result,
                    result_timestamp=now,
                )
            ],
            usage=TokenUsage(),
            timestamp=now,
        )
    )
    return turn


class TestToolCallsInOutput:
    """Test that tool calls are embedded in turn output, not as child traces."""

    def test_tool_calls_counted_in_return_value(self):
        """Tool calls should be counted in the return value."""
        # Create minimal session with tool calls
        turn = make_turn_with_tool_call(
            user_content="Add todos",
            tool_name="TodoWrite",
            tool_input={
                "todos": [
                    {"content": "Test", "status": "pending", "activeForm": "Testing"}
                ]
            },
        )
        session = make_minimal_session(turns=[turn])

        with patch(
            "weave.integrations.claude_plugin.session.session_importer.require_weave_client"
        ) as mock_client:
            mock_call = MagicMock(id="call-1")
            mock_call.summary = {}
            mock_client.return_value.create_call.return_value = mock_call
            mock_client.return_value.finish_call = MagicMock()

            turns, tool_calls, calls_created, _ = _import_session_to_weave(
                session, Path("/tmp/test.jsonl"), use_ollama=False
            )

            # Tool calls should be counted
            assert tool_calls == 1, "Should count 1 tool call"
            # Only session + turn calls created (no child tool traces)
            assert calls_created == 2, "Should only create session + turn calls"

    def test_multiple_tool_calls_counted(self):
        """Multiple tool calls should all be counted."""
        now = datetime.now(timezone.utc)
        turn = Turn(
            user_message=UserMessage(uuid="u1", content="Do stuff", timestamp=now)
        )
        turn.assistant_messages.append(
            AssistantMessage(
                uuid="a1",
                model="claude-sonnet-4-20250514",
                text_content=["Done"],
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name="Read",
                        input={"file_path": "/a.txt"},
                        timestamp=now,
                        result="a",
                    ),
                    ToolCall(
                        id="t2",
                        name="Grep",
                        input={"pattern": "foo"},
                        timestamp=now,
                        result="b",
                    ),
                    ToolCall(
                        id="t3",
                        name="Edit",
                        input={"file_path": "/a.txt"},
                        timestamp=now,
                        result="c",
                    ),
                ],
                usage=TokenUsage(),
                timestamp=now,
            )
        )
        session = make_minimal_session(turns=[turn])

        with patch(
            "weave.integrations.claude_plugin.session.session_importer.require_weave_client"
        ) as mock_client:
            mock_call = MagicMock(id="call-1")
            mock_call.summary = {}
            mock_client.return_value.create_call.return_value = mock_call
            mock_client.return_value.finish_call = MagicMock()

            turns, tool_calls, calls_created, _ = _import_session_to_weave(
                session, Path("/tmp/test.jsonl"), use_ollama=False
            )

            # All tool calls should be counted
            assert tool_calls == 3, "Should count 3 tool calls"
            # Only session + turn calls created (no child tool traces)
            assert calls_created == 2, "Should only create session + turn calls"


class TestSkillToolCalls:
    """Test that skill tool calls are properly handled."""

    def test_skill_tool_counted(self):
        """Skill tool calls should be counted like other tool calls."""
        now = datetime.now(timezone.utc)

        # Create session with skill call
        turn = Turn(
            user_message=UserMessage(uuid="u1", content="Use skill", timestamp=now)
        )
        turn.assistant_messages.append(
            AssistantMessage(
                uuid="a1",
                model="claude-sonnet-4-20250514",
                text_content=["Using the skill"],
                tool_calls=[
                    ToolCall(
                        id="tool-1",
                        name="Skill",
                        input={"skill": "test:skill"},
                        timestamp=now,
                        result="Launching skill",
                        result_timestamp=now,
                    )
                ],
                usage=TokenUsage(),
                timestamp=now,
            )
        )
        # Note: skill_expansion is stored on the turn but not used for child traces
        # The expansion becomes part of conversation context, not tool output
        turn.skill_expansion = "Base directory for this skill: /path\n\n# Skill Content"
        session = make_minimal_session(turns=[turn])

        with patch(
            "weave.integrations.claude_plugin.session.session_importer.require_weave_client"
        ) as mock_client:
            mock_call = MagicMock(id="call-1")
            mock_call.summary = {}
            mock_client.return_value.create_call.return_value = mock_call
            mock_client.return_value.finish_call = MagicMock()

            turns, tool_calls, calls_created, _ = _import_session_to_weave(
                session, Path("/tmp/test.jsonl"), use_ollama=False
            )

            # Skill tool should be counted
            assert tool_calls == 1, "Should count 1 tool call (Skill)"
            # Only session + turn calls created (Skill embedded in turn output)
            assert calls_created == 2, "Should only create session + turn calls"


class TestQAContextTracking:
    """Test that Q&A context is tracked across turns."""

    def test_question_from_turn1_appears_in_turn2_input(self):
        """When Turn 1 ends with a question, Turn 2 should have in_response_to."""
        now = datetime.now(timezone.utc)

        # Create Turn 1 with assistant ending with a question
        turn1 = Turn(
            user_message=UserMessage(uuid="u1", content="Help me", timestamp=now)
        )
        turn1.assistant_messages.append(
            AssistantMessage(
                uuid="a1",
                model="claude-sonnet-4-20250514",
                text_content=["I can help. What file would you like me to look at?"],
                tool_calls=[],
                usage=TokenUsage(),
                timestamp=now,
            )
        )

        # Create Turn 2 with user response to the question
        turn2 = Turn(
            user_message=UserMessage(uuid="u2", content="Look at foo.py", timestamp=now)
        )
        turn2.assistant_messages.append(
            AssistantMessage(
                uuid="a2",
                model="claude-sonnet-4-20250514",
                text_content=["Let me check foo.py"],
                tool_calls=[],
                usage=TokenUsage(),
                timestamp=now,
            )
        )

        session = make_minimal_session(turns=[turn1, turn2])

        with patch(
            "weave.integrations.claude_plugin.session.session_importer.require_weave_client"
        ) as mock_client:
            mock_call = MagicMock(id="turn-1")
            mock_call.summary = {}
            mock_client.return_value.create_call.return_value = mock_call
            mock_client.return_value.finish_call = MagicMock()

            _import_session_to_weave(session, Path("/tmp/test.jsonl"), use_ollama=False)

            # Find the second turn's create_call
            create_calls = mock_client.return_value.create_call.call_args_list

            # Find turn calls (op="claude_code.turn")
            turn_calls = [
                c for c in create_calls if c.kwargs.get("op") == "claude_code.turn"
            ]
            assert len(turn_calls) >= 2, "Should have at least 2 turn calls"

            # Second turn should have in_response_to in inputs
            turn2_inputs = turn_calls[1].kwargs.get("inputs", {})
            assert "in_response_to" in turn2_inputs, "Turn 2 should have in_response_to"
            assert "?" in turn2_inputs["in_response_to"], (
                "in_response_to should be a question"
            )

    def test_no_question_means_no_in_response_to(self):
        """When Turn 1 doesn't end with a question, Turn 2 should NOT have in_response_to."""
        now = datetime.now(timezone.utc)

        # Create Turn 1 WITHOUT a question
        turn1 = Turn(
            user_message=UserMessage(uuid="u1", content="Help me", timestamp=now)
        )
        turn1.assistant_messages.append(
            AssistantMessage(
                uuid="a1",
                model="claude-sonnet-4-20250514",
                text_content=["Done! I've completed the task."],
                tool_calls=[],
                usage=TokenUsage(),
                timestamp=now,
            )
        )

        # Create Turn 2
        turn2 = Turn(
            user_message=UserMessage(uuid="u2", content="Thanks", timestamp=now)
        )
        turn2.assistant_messages.append(
            AssistantMessage(
                uuid="a2",
                model="claude-sonnet-4-20250514",
                text_content=["You're welcome!"],
                tool_calls=[],
                usage=TokenUsage(),
                timestamp=now,
            )
        )

        session = make_minimal_session(turns=[turn1, turn2])

        with patch(
            "weave.integrations.claude_plugin.session.session_importer.require_weave_client"
        ) as mock_client:
            mock_call = MagicMock(id="turn-1")
            mock_call.summary = {}
            mock_client.return_value.create_call.return_value = mock_call
            mock_client.return_value.finish_call = MagicMock()

            _import_session_to_weave(session, Path("/tmp/test.jsonl"), use_ollama=False)

            # Find the second turn's create_call
            create_calls = mock_client.return_value.create_call.call_args_list

            # Find turn calls (op="claude_code.turn")
            turn_calls = [
                c for c in create_calls if c.kwargs.get("op") == "claude_code.turn"
            ]
            assert len(turn_calls) >= 2, "Should have at least 2 turn calls"

            # Second turn should NOT have in_response_to
            turn2_inputs = turn_calls[1].kwargs.get("inputs", {})
            assert "in_response_to" not in turn2_inputs, (
                "Turn 2 should NOT have in_response_to when Turn 1 has no question"
            )


class TestTurnSummary:
    """Test that turns have proper summary/output separation."""

    def test_turn_has_summary_with_metadata(self):
        """Turn metadata (model, usage, duration) should be in summary."""
        now = datetime.now(timezone.utc)
        turn = Turn(user_message=UserMessage(uuid="u1", content="Hello", timestamp=now))
        turn.assistant_messages.append(
            AssistantMessage(
                uuid="a1",
                model="claude-sonnet-4-20250514",
                text_content=["Hi there"],
                tool_calls=[],
                usage=TokenUsage(input_tokens=100, output_tokens=50),
                timestamp=now,
            )
        )
        session = make_minimal_session(turns=[turn])

        with (
            patch(
                "weave.integrations.claude_plugin.session.session_importer.require_weave_client"
            ) as mock_client,
            patch(
                "weave.integrations.claude_plugin.session.session_importer.reconstruct_call"
            ) as mock_reconstruct,
        ):
            mock_call = MagicMock(id="turn-1")
            mock_call.summary = {}
            mock_client.return_value.create_call.return_value = mock_call
            mock_client.return_value.finish_call = MagicMock()
            # Make reconstruct_call return a call with settable summary
            reconstructed_call = MagicMock(id="turn-1")
            reconstructed_call.summary = {}
            mock_reconstruct.return_value = reconstructed_call

            _import_session_to_weave(session, Path("/tmp/test.jsonl"), use_ollama=False)

            # Turn summary should have been set with model info on the reconstructed call
            # Check that summary was assigned before finish_call
            assert reconstructed_call.summary is not None, (
                "Turn should have summary set"
            )
            assert "model" in reconstructed_call.summary, "Summary should have model"
            assert "usage" in reconstructed_call.summary, "Summary should have usage"

    def test_turn_output_uses_message_format(self):
        """Turn output uses Message format for chat view detection."""
        now = datetime.now(timezone.utc)
        turn = Turn(user_message=UserMessage(uuid="u1", content="Hello", timestamp=now))
        turn.assistant_messages.append(
            AssistantMessage(
                uuid="a1",
                model="claude-sonnet-4-20250514",
                text_content=["Hi there"],
                tool_calls=[],
                usage=TokenUsage(input_tokens=100, output_tokens=50),
                timestamp=now,
            )
        )
        session = make_minimal_session(turns=[turn])

        with patch(
            "weave.integrations.claude_plugin.session.session_importer.require_weave_client"
        ) as mock_client:
            mock_call = MagicMock(id="turn-1")
            mock_call.summary = {}
            mock_client.return_value.create_call.return_value = mock_call
            mock_client.return_value.finish_call = MagicMock()

            _import_session_to_weave(session, Path("/tmp/test.jsonl"), use_ollama=False)

            # Check finish_call was called and output has Message format
            finish_calls = mock_client.return_value.finish_call.call_args_list
            # Find the turn finish call (not session)
            for call in finish_calls:
                output = call.kwargs.get("output", {}) or {}
                if output and "role" in output:
                    # Turn output uses Message format (no "type" field)
                    # This is OpenAI-compatible, not Anthropic's native format
                    assert output["role"] == "assistant"
                    assert "model" in output  # Model in output for chat view
                    assert "content" in output
                    # Usage should still NOT be in output (only in summary)
                    assert "usage" not in output, "Usage goes in summary, not output"


class TestIsUuidFilename:
    """Test is_uuid_filename helper function."""

    def test_valid_uuid_filename(self):
        """Should return True for valid UUID filenames."""
        assert is_uuid_filename("12345678-1234-5678-1234-567812345678.jsonl") is True
        assert is_uuid_filename("abcdefab-abcd-abcd-abcd-abcdefabcdef.jsonl") is True
        assert is_uuid_filename("ABCDEFAB-ABCD-ABCD-ABCD-ABCDEFABCDEF.jsonl") is True

    def test_invalid_uuid_filename(self):
        """Should return False for non-UUID filenames."""
        assert is_uuid_filename("agent-abc123.jsonl") is False
        assert is_uuid_filename("session.jsonl") is False
        assert is_uuid_filename("12345678.jsonl") is False
        assert is_uuid_filename("not-a-uuid.jsonl") is False

    def test_wrong_extension(self):
        """Should return False for wrong file extensions."""
        assert is_uuid_filename("12345678-1234-5678-1234-567812345678.json") is False


class TestExtractAgentId:
    """Test extract_agent_id helper function."""

    def test_extracts_agent_id_from_result(self):
        """Should extract agent ID from Task tool result."""
        result = "Task started successfully.\nagentId: abc123\nOther info"
        assert extract_agent_id(result) == "abc123"

    def test_extracts_first_agent_id(self):
        """Should extract the first agentId if multiple present."""
        result = "agentId: first123\nagentId: second456"
        assert extract_agent_id(result) == "first123"

    def test_returns_none_for_no_agent_id(self):
        """Should return None when no agentId present."""
        result = "Task completed without agent ID"
        assert extract_agent_id(result) is None

    def test_returns_none_for_none_input(self):
        """Should return None for None input."""
        assert extract_agent_id(None) is None

    def test_returns_none_for_empty_string(self):
        """Should return None for empty string."""
        assert extract_agent_id("") is None


class TestDiscoverSessionFiles:
    """Test discover_session_files function."""

    def test_finds_uuid_files(self, tmp_path):
        """Should find UUID-style session files."""
        # Create some files
        (tmp_path / "12345678-1234-5678-1234-567812345678.jsonl").write_text("{}")
        (tmp_path / "agent-abc123.jsonl").write_text("{}")
        (tmp_path / "session.jsonl").write_text("{}")

        files = discover_session_files(tmp_path, most_recent_only=False)

        assert len(files) == 1
        assert "12345678-1234-5678-1234-567812345678.jsonl" in files[0].name

    def test_returns_most_recent_only(self, tmp_path):
        """Should return only most recent file when most_recent_only=True."""
        import time

        # Create files with different modification times
        file1 = tmp_path / "12345678-1234-5678-1234-567812345678.jsonl"
        file1.write_text("{}")
        time.sleep(0.01)  # Ensure different mtime
        file2 = tmp_path / "87654321-4321-8765-4321-876543218765.jsonl"
        file2.write_text("{}")

        files = discover_session_files(tmp_path, most_recent_only=True)

        assert len(files) == 1
        # Should be the newer file
        assert files[0].name == "87654321-4321-8765-4321-876543218765.jsonl"

    def test_returns_empty_list_for_no_files(self, tmp_path):
        """Should return empty list when no session files found."""
        files = discover_session_files(tmp_path, most_recent_only=False)
        assert files == []

    def test_sorts_by_modification_time(self, tmp_path):
        """Should sort files by modification time (newest first)."""
        import time

        # Create files with different modification times
        file1 = tmp_path / "11111111-1111-1111-1111-111111111111.jsonl"
        file1.write_text("{}")
        time.sleep(0.01)

        file2 = tmp_path / "22222222-2222-2222-2222-222222222222.jsonl"
        file2.write_text("{}")
        time.sleep(0.01)

        file3 = tmp_path / "33333333-3333-3333-3333-333333333333.jsonl"
        file3.write_text("{}")

        files = discover_session_files(tmp_path, most_recent_only=False)

        assert len(files) == 3
        # Newest first
        assert files[0].name == "33333333-3333-3333-3333-333333333333.jsonl"
        assert files[1].name == "22222222-2222-2222-2222-222222222222.jsonl"
        assert files[2].name == "11111111-1111-1111-1111-111111111111.jsonl"


class TestImportSessionWithResult:
    """Test import_session_with_result error handling."""

    def test_returns_error_for_unparseable_file(self, tmp_path):
        """Should return error result when file can't be parsed."""
        from weave.integrations.claude_plugin.session.session_importer import (
            import_session_with_result,
        )

        # Create invalid session file
        session_file = tmp_path / "invalid.jsonl"
        session_file.write_text("not valid json at all")

        result = import_session_with_result(session_file)

        assert result.success is False
        assert "parse" in result.error.lower() or "Failed" in result.error

    def test_returns_error_for_empty_session(self, tmp_path):
        """Should return error result when session has no turns."""
        import json

        from weave.integrations.claude_plugin.session.session_importer import (
            import_session_with_result,
        )

        # Create session file with no turns (just metadata)
        session_file = tmp_path / "12345678-1234-5678-1234-567812345678.jsonl"
        session_file.write_text(
            json.dumps(
                {
                    "type": "system",
                    "sessionId": "12345678-1234-5678-1234-567812345678",
                }
            )
            + "\n"
        )

        result = import_session_with_result(session_file)

        assert result.success is False
        assert "no turns" in result.error.lower()

    def test_returns_error_for_active_session(self, tmp_path):
        """Should return error result when session is currently active."""
        import json

        from weave.integrations.claude_plugin.core.state import StateManager
        from weave.integrations.claude_plugin.session.session_importer import (
            import_session_with_result,
        )

        session_id = "active-session-12345678"

        # Create session file with one turn
        session_file = tmp_path / f"{session_id}.jsonl"
        session_file.write_text(
            json.dumps(
                {
                    "type": "user",
                    "sessionId": session_id,
                    "uuid": "msg-1",
                    "timestamp": "2025-01-01T10:00:00Z",
                    "message": {"role": "user", "content": "Hello"},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "type": "assistant",
                    "sessionId": session_id,
                    "uuid": "msg-2",
                    "timestamp": "2025-01-01T10:00:01Z",
                    "message": {
                        "role": "assistant",
                        "model": "claude-sonnet-4-20250514",
                        "content": [{"type": "text", "text": "Hi!"}],
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    },
                }
            )
            + "\n"
        )

        # Mark session as active in state
        with StateManager() as state:
            state.save_session(
                session_id,
                {
                    "project": "test/project",
                    "session_ended": False,
                },
            )

        try:
            result = import_session_with_result(session_file)

            assert result.success is False
            assert "active" in result.error.lower()
        finally:
            # Cleanup
            with StateManager() as state:
                state.delete_session(session_id)

    def test_dry_run_does_not_create_traces(self, tmp_path):
        """Should not create traces when dry_run=True."""
        import json

        from weave.integrations.claude_plugin.session.session_importer import (
            import_session_with_result,
        )

        session_id = "dry-run-session-123"
        session_file = tmp_path / f"{session_id}.jsonl"
        session_file.write_text(
            json.dumps(
                {
                    "type": "user",
                    "sessionId": session_id,
                    "uuid": "msg-1",
                    "timestamp": "2025-01-01T10:00:00Z",
                    "message": {"role": "user", "content": "Hello"},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "type": "assistant",
                    "sessionId": session_id,
                    "uuid": "msg-2",
                    "timestamp": "2025-01-01T10:00:01Z",
                    "message": {
                        "role": "assistant",
                        "model": "claude-sonnet-4-20250514",
                        "content": [{"type": "text", "text": "Hi!"}],
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    },
                }
            )
            + "\n"
        )

        with patch(
            "weave.integrations.claude_plugin.session.session_importer.require_weave_client"
        ) as mock_client:
            result = import_session_with_result(session_file, dry_run=True)

            # Should succeed - dry_run returns counts that would be created
            assert result.success is True
            # weave_calls shows what WOULD be created, not what WAS created
            assert result.weave_calls > 0  # Would create session + turn calls
            # But no actual weave client calls were made
            mock_client.assert_not_called()


class TestImportSessions:
    """Test import_sessions batch import function."""

    def test_raises_error_for_nonexistent_path(self, tmp_path):
        """Should raise ValueError for non-existent path."""
        import pytest

        from weave.integrations.claude_plugin.session.session_importer import (
            import_sessions,
        )

        with pytest.raises(ValueError, match="does not exist"):
            import_sessions(
                path=tmp_path / "nonexistent",
                project="test/project",
            )

    def test_raises_error_for_empty_directory(self, tmp_path):
        """Should raise ValueError when no session files found."""
        import pytest

        from weave.integrations.claude_plugin.session.session_importer import (
            import_sessions,
        )

        with pytest.raises(ValueError, match="No session files found"):
            import_sessions(
                path=tmp_path,
                project="test/project",
            )

    def test_dry_run_does_not_initialize_weave(self, tmp_path):
        """Should not initialize weave in dry_run mode."""
        import json

        from weave.integrations.claude_plugin.session.session_importer import (
            import_sessions,
        )

        # Create a valid session file
        session_id = "12345678-1234-5678-1234-567812345678"
        session_file = tmp_path / f"{session_id}.jsonl"
        session_file.write_text(
            json.dumps(
                {
                    "type": "user",
                    "sessionId": session_id,
                    "uuid": "msg-1",
                    "timestamp": "2025-01-01T10:00:00Z",
                    "message": {"role": "user", "content": "Hello"},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "type": "assistant",
                    "sessionId": session_id,
                    "uuid": "msg-2",
                    "timestamp": "2025-01-01T10:00:01Z",
                    "message": {
                        "role": "assistant",
                        "model": "claude-sonnet-4-20250514",
                        "content": [{"type": "text", "text": "Hi!"}],
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    },
                }
            )
            + "\n"
        )

        with patch(
            "weave.integrations.claude_plugin.session.session_importer.weave"
        ) as mock_weave:
            summary = import_sessions(
                path=tmp_path,
                project="test/project",
                dry_run=True,
            )

            # weave.init should not be called in dry_run
            mock_weave.init.assert_not_called()
            # Should still return a summary
            assert "sessions_imported" in summary

    def test_imports_single_file(self, tmp_path):
        """Should import a single file when path is a file."""
        import json

        from weave.integrations.claude_plugin.session.session_importer import (
            import_sessions,
        )

        session_id = "12345678-1234-5678-1234-567812345678"
        session_file = tmp_path / f"{session_id}.jsonl"
        session_file.write_text(
            json.dumps(
                {
                    "type": "user",
                    "sessionId": session_id,
                    "uuid": "msg-1",
                    "timestamp": "2025-01-01T10:00:00Z",
                    "message": {"role": "user", "content": "Hello"},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "type": "assistant",
                    "sessionId": session_id,
                    "uuid": "msg-2",
                    "timestamp": "2025-01-01T10:00:01Z",
                    "message": {
                        "role": "assistant",
                        "model": "claude-sonnet-4-20250514",
                        "content": [{"type": "text", "text": "Hi!"}],
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    },
                }
            )
            + "\n"
        )

        with patch(
            "weave.integrations.claude_plugin.session.session_importer.weave"
        ) as mock_weave:
            summary = import_sessions(
                path=session_file,  # Pass file directly
                project="test/project",
                dry_run=True,
            )

            # Should recognize 1 turn
            assert summary["total_turns"] == 1

    def test_full_mode_processes_all_files(self, tmp_path):
        """Should process all files in full mode."""
        import json

        from weave.integrations.claude_plugin.session.session_importer import (
            import_sessions,
        )

        # Create two session files
        for i in range(2):
            session_id = f"1234567{i}-1234-5678-1234-567812345678"
            session_file = tmp_path / f"{session_id}.jsonl"
            session_file.write_text(
                json.dumps(
                    {
                        "type": "user",
                        "sessionId": session_id,
                        "uuid": "msg-1",
                        "timestamp": "2025-01-01T10:00:00Z",
                        "message": {"role": "user", "content": "Hello"},
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "type": "assistant",
                        "sessionId": session_id,
                        "uuid": "msg-2",
                        "timestamp": "2025-01-01T10:00:01Z",
                        "message": {
                            "role": "assistant",
                            "model": "claude-sonnet-4-20250514",
                            "content": [{"type": "text", "text": "Hi!"}],
                            "usage": {"input_tokens": 10, "output_tokens": 5},
                        },
                    }
                )
                + "\n"
            )

        with patch("weave.integrations.claude_plugin.session.session_importer.weave"):
            summary = import_sessions(
                path=tmp_path,
                project="test/project",
                dry_run=True,
                full=True,  # Process all files
            )

            # Should process both sessions (2 turns total)
            assert summary["total_turns"] == 2

    def test_most_recent_only_by_default(self, tmp_path):
        """Should only import most recent file by default."""
        import json
        import time

        from weave.integrations.claude_plugin.session.session_importer import (
            import_sessions,
        )

        # Create two session files with different mtimes
        session1 = tmp_path / "11111111-1111-1111-1111-111111111111.jsonl"
        session1.write_text(
            json.dumps(
                {
                    "type": "user",
                    "sessionId": "11111111-1111-1111-1111-111111111111",
                    "uuid": "msg-1",
                    "timestamp": "2025-01-01T10:00:00Z",
                    "message": {"role": "user", "content": "First"},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "type": "assistant",
                    "sessionId": "11111111-1111-1111-1111-111111111111",
                    "uuid": "msg-2",
                    "timestamp": "2025-01-01T10:00:01Z",
                    "message": {
                        "role": "assistant",
                        "model": "claude-sonnet-4-20250514",
                        "content": [{"type": "text", "text": "Response 1"}],
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    },
                }
            )
            + "\n"
        )

        time.sleep(0.01)  # Ensure different mtime

        session2 = tmp_path / "22222222-2222-2222-2222-222222222222.jsonl"
        session2.write_text(
            json.dumps(
                {
                    "type": "user",
                    "sessionId": "22222222-2222-2222-2222-222222222222",
                    "uuid": "msg-1",
                    "timestamp": "2025-01-01T11:00:00Z",
                    "message": {"role": "user", "content": "Second"},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "type": "assistant",
                    "sessionId": "22222222-2222-2222-2222-222222222222",
                    "uuid": "msg-2",
                    "timestamp": "2025-01-01T11:00:01Z",
                    "message": {
                        "role": "assistant",
                        "model": "claude-sonnet-4-20250514",
                        "content": [{"type": "text", "text": "Response 2"}],
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    },
                }
            )
            + "\n"
        )

        with patch("weave.integrations.claude_plugin.session.session_importer.weave"):
            summary = import_sessions(
                path=tmp_path,
                project="test/project",
                dry_run=True,
                full=False,  # Only most recent (default)
            )

            # Should only process 1 session (the most recent)
            assert summary["total_turns"] == 1
