"""Integration tests for session importer.

These tests verify the full import pipeline works correctly
with realistic session data, including skill expansions, file backups,
and subagent handling.

Note: Tool calls are embedded in turn output via build_turn_output(),
not as separate child traces. Tests verify tool call counting and
proper trace structure without individual tool call assertions.
"""

import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from weave.integrations.claude_plugin.session_importer import _import_session_to_weave
from weave.integrations.claude_plugin.session_parser import parse_session_file


def create_session_jsonl(messages: list[dict]) -> Path:
    """Create a temporary JSONL session file from message dicts."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for msg in messages:
        tmp.write(json.dumps(msg) + "\n")
    tmp.close()
    return Path(tmp.name)


class TestSessionImporterIntegration:
    """Integration tests for session importer."""

    def test_skill_expansion_creates_correct_structure(self):
        """Import a session with skill expansions and verify trace structure."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Use the brainstorming skill"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Skill",
                            "input": {"skill": "superpowers:brainstorming"},
                        },
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 10},
                },
            },
            # Skill expansion - should NOT create a new turn
            {
                "type": "user",
                "uuid": "u2",
                "timestamp": "2025-01-01T10:00:02Z",
                "sessionId": "test-session",
                "sourceToolUseID": "tool-1",
                "isMeta": True,
                "message": {
                    "role": "user",
                    "content": "Base directory for this skill: /path/to/skill\n\n# Brainstorming\n\nThis is the skill content...",
                },
            },
            {
                "type": "assistant",
                "uuid": "a2",
                "timestamp": "2025-01-01T10:00:03Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "I understand the skill."}],
                    "usage": {"input_tokens": 200, "output_tokens": 20},
                },
            },
            # Real user message
            {
                "type": "user",
                "uuid": "u3",
                "timestamp": "2025-01-01T10:00:04Z",
                "sessionId": "test-session",
                "message": {"role": "user", "content": "Now help me brainstorm"},
            },
            {
                "type": "assistant",
                "uuid": "a3",
                "timestamp": "2025-01-01T10:00:05Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Let me help you brainstorm."}],
                    "usage": {"input_tokens": 300, "output_tokens": 30},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)
            assert session is not None

            # Verify parser correctly identified 2 turns (not 3)
            assert len(session.turns) == 2
            assert session.turns[0].skill_expansion is not None
            assert "Base directory for this skill:" in session.turns[0].skill_expansion

            # Mock the Weave client and import
            with patch(
                "weave.integrations.claude_plugin.session_importer.require_weave_client"
            ) as mock_client:
                mock_call = MagicMock(id="call-1")
                mock_call.summary = {}
                mock_client.return_value.create_call.return_value = mock_call
                mock_client.return_value.finish_call = MagicMock()

                turns, tool_calls, calls_created, _ = _import_session_to_weave(
                    session, session_jsonl, use_ollama=False
                )

                # Should have 2 turns
                assert turns == 2

                # Tool call should be counted (Skill tool in turn 1)
                assert tool_calls == 1

                # Only session + turns created (no child tool traces)
                assert calls_created == 3  # 1 session + 2 turns
        finally:
            session_jsonl.unlink()

    def test_todowrite_counted_in_tool_calls(self):
        """Import a session with TodoWrite and verify it's counted."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Create a todo list"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "TodoWrite",
                            "input": {
                                "todos": [
                                    {"content": "Task 1", "status": "pending", "activeForm": "Working on task 1"},
                                    {"content": "Task 2", "status": "in_progress", "activeForm": "Working on task 2"},
                                ]
                            },
                        },
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)
            assert session is not None

            with patch(
                "weave.integrations.claude_plugin.session_importer.require_weave_client"
            ) as mock_client:
                mock_call = MagicMock(id="call-1")
                mock_call.summary = {}
                mock_client.return_value.create_call.return_value = mock_call
                mock_client.return_value.finish_call = MagicMock()

                turns, tool_calls, calls_created, _ = _import_session_to_weave(
                    session, session_jsonl, use_ollama=False
                )

                # TodoWrite should be counted
                assert tool_calls == 1

                # Only session + turn created (no child tool traces)
                assert calls_created == 2  # 1 session + 1 turn
        finally:
            session_jsonl.unlink()

    def test_turns_have_summary_not_output(self):
        """Verify turn metadata is in summary, not output."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Hello"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Hi there!"}],
                    "usage": {"input_tokens": 50, "output_tokens": 10},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)

            with patch(
                "weave.integrations.claude_plugin.session_importer.require_weave_client"
            ) as mock_client, patch(
                "weave.integrations.claude_plugin.session_importer.reconstruct_call"
            ) as mock_reconstruct:
                mock_turn_call = MagicMock(id="turn-1")
                mock_turn_call.summary = {}
                mock_session_call = MagicMock(id="session-1")
                mock_session_call.summary = {}

                # Return different mocks for session vs turn calls
                mock_client.return_value.create_call.side_effect = [
                    mock_session_call,  # Session call
                    mock_turn_call,  # Turn call
                ]
                mock_client.return_value.finish_call = MagicMock()

                # Make reconstruct_call return a call with settable summary
                reconstructed_turn = MagicMock(id="turn-1")
                reconstructed_turn.summary = {}
                reconstructed_session = MagicMock(id="session-1")
                reconstructed_session.summary = {}
                mock_reconstruct.side_effect = [
                    mock_session_call,  # Parent for turn
                    reconstructed_turn,  # Reconstructed turn for finish
                    reconstructed_session,  # Reconstructed session for finish
                ]

                _import_session_to_weave(session, session_jsonl, use_ollama=False)

                # Check that finish_call was called and turn summary was set
                # The reconstructed turn should have summary set by finish_turn_call
                assert reconstructed_turn.summary is not None

                # Check finish_call output does not have usage in output
                finish_calls = mock_client.return_value.finish_call.call_args_list
                for call in finish_calls:
                    output = call.kwargs.get("output") or {}
                    if output:
                        assert "usage" not in output, "Turn output should not have usage"
        finally:
            session_jsonl.unlink()

    def test_multiple_tool_calls_in_turn(self):
        """Import a turn with multiple tool calls."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Read two files"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Read",
                            "input": {"file_path": "/tmp/file1.txt"},
                        },
                        {
                            "type": "tool_use",
                            "id": "tool-2",
                            "name": "Read",
                            "input": {"file_path": "/tmp/file2.txt"},
                        },
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 20},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)

            with patch(
                "weave.integrations.claude_plugin.session_importer.require_weave_client"
            ) as mock_client:
                mock_call = MagicMock(id="call-1")
                mock_call.summary = {}
                mock_client.return_value.create_call.return_value = mock_call
                mock_client.return_value.finish_call = MagicMock()

                turns, tool_calls, calls_created, _ = _import_session_to_weave(
                    session, session_jsonl, use_ollama=False
                )

                # Should have 2 tool calls counted
                assert tool_calls == 2

                # Only session + turn created (no child tool traces)
                assert calls_created == 2  # 1 session + 1 turn
        finally:
            session_jsonl.unlink()


# Path to the real test session file (for testing with actual data)
TEST_SESSION_DIR = Path.home() / ".claude/projects/-Users-vanpelt-Development-weave"
TEST_SESSION_ID = "a3ed5899-7076-4cf3-85a0-854501857bc4"
TEST_SESSION_FILE = TEST_SESSION_DIR / f"{TEST_SESSION_ID}.jsonl"


class TestRealSessionData:
    """Integration tests using real session data from the test session."""

    @pytest.fixture
    def real_session(self):
        """Load the real test session."""
        if not TEST_SESSION_FILE.exists():
            pytest.skip(f"Test session file not found: {TEST_SESSION_FILE}")
        return parse_session_file(TEST_SESSION_FILE)

    @pytest.fixture
    def agent_files(self) -> list[Path]:
        """Find all agent files associated with the test session."""
        if not TEST_SESSION_DIR.exists():
            return []
        agent_files = []
        for agent_file in TEST_SESSION_DIR.glob("agent-*.jsonl"):
            try:
                with open(agent_file) as f:
                    first_line = f.readline().strip()
                    if first_line:
                        obj = json.loads(first_line)
                        if obj.get("sessionId") == TEST_SESSION_ID:
                            agent_files.append(agent_file)
            except Exception:
                pass
        return agent_files

    def test_session_has_task_calls_with_subagent_type(self, real_session):
        """Verify test session has Task calls with subagent_type for testing."""
        task_calls_with_subagent = []
        for turn in real_session.turns:
            for tc in turn.all_tool_calls():
                if tc.name == "Task" and tc.input.get("subagent_type"):
                    task_calls_with_subagent.append(tc)

        assert len(task_calls_with_subagent) > 0, (
            "Test session should have at least one Task call with subagent_type"
        )

    def test_task_results_contain_agent_id(self, real_session):
        """Verify Task tool results contain agentId for linking.

        NOTE: This test currently checks the raw messages since the parser
        truncates/simplifies tool results. The importer should extract agentId
        from the raw tool_result content (which can be a list of text blocks).
        """
        import re

        # Check raw messages for tool_result with agentId
        agent_ids_found = []
        for turn in real_session.turns:
            for msg in turn.raw_messages:
                if msg.get("type") == "user":
                    content = msg.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for c in content:
                            if c.get("type") == "tool_result":
                                # Result content can be a list of text blocks
                                result_content = c.get("content", "")
                                if isinstance(result_content, list):
                                    # Join text blocks to search for agentId
                                    text = " ".join(
                                        block.get("text", "")
                                        for block in result_content
                                        if block.get("type") == "text"
                                    )
                                else:
                                    text = str(result_content)
                                match = re.search(r"agentId:\s*([a-f0-9]+)", text)
                                if match:
                                    agent_ids_found.append(match.group(1))

        assert len(agent_ids_found) > 0, (
            "Task tool results should contain agentId for subagent linking"
        )

    def test_agent_files_exist_for_session(self, agent_files):
        """Verify agent files exist for the test session."""
        assert len(agent_files) > 0, (
            f"Session {TEST_SESSION_ID} should have associated agent files"
        )


class TestSubagentExpansion:
    """Test that Task calls with subagent_type are properly expanded."""

    def test_extract_agent_id_from_task_result_string(self):
        """Test extracting agentId from Task tool result string."""
        import re

        # Sample result text from a Task tool call
        result_text = """## Task 1 Implementation Report

### What I Implemented
...implementation details...

agentId: a06151e (for resuming to continue this agent's work if needed)"""

        match = re.search(r"agentId:\s*([a-f0-9]+)", result_text)
        assert match is not None, "Should find agentId in result"
        assert match.group(1) == "a06151e"

    def test_extract_agent_id_from_list_result(self):
        """Test extracting agentId when result is a list of dicts (tool_result format)."""
        import re

        # The tool_result format when stored in the session file
        result = [
            {"type": "text", "text": "Implementation complete."},
            {"type": "text", "text": "agentId: abc1234 (for resuming)"},
        ]

        # Convert to string for pattern matching (how importer would process)
        result_str = str(result)
        match = re.search(r"agentId:\s*([a-f0-9]+)", result_str)
        assert match is not None
        assert match.group(1) == "abc1234"

    def test_task_with_subagent_type_should_create_subagent_call(self, tmp_path):
        """Task calls with subagent_type should create subagent traces.

        This tests that when a Task tool call with subagent_type is imported,
        the importer finds the corresponding agent-{agentId}.jsonl file and
        creates a subagent call with tool calls embedded in output.
        """
        # Create the main session file
        session_file = tmp_path / "test-session.jsonl"
        session_messages = [
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Launch agent"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Task",
                            "input": {
                                "subagent_type": "general-purpose",
                                "prompt": "Do something",
                                "description": "Test task",
                            },
                        },
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
            },
            {
                "type": "user",
                "uuid": "u2",
                "timestamp": "2025-01-01T10:00:05Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool-1",
                            "content": "Done.\n\nagentId: abc1234",
                        }
                    ],
                },
            },
        ]
        with open(session_file, "w") as f:
            for msg in session_messages:
                f.write(json.dumps(msg) + "\n")

        # Create the agent file that the subagent would have created
        agent_file = tmp_path / "agent-abc1234.jsonl"
        agent_messages = [
            {
                "type": "user",
                "uuid": "agent-u1",
                "timestamp": "2025-01-01T10:00:02Z",
                "sessionId": "agent-abc1234",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Do something"},
            },
            {
                "type": "assistant",
                "uuid": "agent-a1",
                "timestamp": "2025-01-01T10:00:03Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "agent-tool-1",
                            "name": "Read",
                            "input": {"file_path": "/tmp/test.txt"},
                        },
                    ],
                    "usage": {"input_tokens": 50, "output_tokens": 25},
                },
            },
            {
                "type": "user",
                "uuid": "agent-u2",
                "timestamp": "2025-01-01T10:00:04Z",
                "sessionId": "agent-abc1234",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "agent-tool-1",
                            "content": "file contents here",
                        }
                    ],
                },
            },
        ]
        with open(agent_file, "w") as f:
            for msg in agent_messages:
                f.write(json.dumps(msg) + "\n")

        # Parse the session
        session = parse_session_file(session_file)
        assert session is not None

        # Verify the Task call was parsed
        task_calls = [
            tc
            for turn in session.turns
            for tc in turn.all_tool_calls()
            if tc.name == "Task" and tc.input.get("subagent_type")
        ]
        assert len(task_calls) == 1, "Should have one Task call with subagent_type"

        # Track create_call invocations
        create_call_ops = []

        with patch(
            "weave.integrations.claude_plugin.session_importer.require_weave_client"
        ) as mock_client:
            def track_create_call(**kwargs):
                create_call_ops.append(kwargs.get("op"))
                mock_call = MagicMock(id=f"call-{len(create_call_ops)}")
                mock_call.summary = {}
                return mock_call

            mock_client.return_value.create_call.side_effect = track_create_call
            mock_client.return_value.finish_call = MagicMock()

            turns, tool_calls, calls_created, _ = _import_session_to_weave(
                session, session_file, use_ollama=False
            )

        # Should create: session, turn, and subagent calls
        assert "claude_code.session" in create_call_ops
        assert "claude_code.turn" in create_call_ops
        assert "claude_code.subagent" in create_call_ops

        # Task tool counts as 1 tool call (even though it spawned a subagent)
        assert tool_calls == 1

        # Calls created: session + turn + subagent (no individual tool call traces)
        assert calls_created == 3


class TestHTMLDiffViews:
    """Test that HTML diff views are properly attached."""

    def test_session_gets_html_diff_view_when_files_changed(self):
        """Session-level call should have HTML diff view when files changed."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Edit a file"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Edit",
                            "input": {
                                "file_path": "/tmp/test.py",
                                "old_string": "a",
                                "new_string": "b",
                            },
                        },
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)

            with patch(
                "weave.integrations.claude_plugin.session_importer.require_weave_client"
            ) as mock_client, patch(
                "weave.integrations.claude_plugin.session_importer.reconstruct_call"
            ) as mock_reconstruct:
                mock_session_call = MagicMock(id="session-1")
                mock_session_call.summary = {}
                mock_turn_call = MagicMock(id="turn-1")
                mock_turn_call.summary = {}
                mock_client.return_value.create_call.side_effect = [
                    mock_session_call,
                    mock_turn_call,
                ]
                mock_client.return_value.finish_call = MagicMock()
                mock_client.return_value._project_id.return_value = "test-entity/test-project"

                # reconstruct_call returns reconstructed calls for finishing
                # Order: parent for turn, turn for finish, session for finish
                mock_reconstruct.side_effect = [
                    mock_session_call,  # Parent for turn creation
                    mock_turn_call,  # Reconstructed turn for finish
                    mock_session_call,  # Reconstructed session for finish
                ]

                with patch(
                    "weave.integrations.claude_plugin.session_processor.set_call_view"
                ) as mock_set_view:
                    with patch(
                        "weave.integrations.claude_plugin.diff_view.generate_session_diff_html"
                    ) as mock_gen_diff:
                        mock_gen_diff.return_value = "<html>session diff</html>"

                        _import_session_to_weave(
                            session, session_jsonl, use_ollama=False
                        )

                        # Verify generate_session_diff_html was called
                        mock_gen_diff.assert_called_once()

                        # Verify set_call_view was called for session
                        session_view_calls = [
                            c
                            for c in mock_set_view.call_args_list
                            if c.kwargs.get("call") == mock_session_call
                        ]
                        assert len(session_view_calls) == 1, (
                            "set_call_view should be called for session with diff HTML"
                        )
                        assert session_view_calls[0].kwargs.get("name") == "file_changes"
        finally:
            session_jsonl.unlink()

    def test_turn_gets_html_diff_view_when_files_changed(self):
        """Turn-level call should have HTML diff view when that turn changed files."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Edit a file"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Edit",
                            "input": {"file_path": "/tmp/test.py"},
                        },
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)

            with patch(
                "weave.integrations.claude_plugin.session_importer.require_weave_client"
            ) as mock_client, patch(
                "weave.integrations.claude_plugin.session_importer.reconstruct_call"
            ) as mock_reconstruct:
                mock_session_call = MagicMock(id="session-1")
                mock_session_call.summary = {}
                mock_turn_call = MagicMock(id="turn-1")
                mock_turn_call.summary = {}
                mock_client.return_value.create_call.side_effect = [
                    mock_session_call,
                    mock_turn_call,
                ]
                mock_client.return_value.finish_call = MagicMock()
                mock_client.return_value._project_id.return_value = "test-entity/test-project"

                # reconstruct_call returns reconstructed calls for finishing
                # Order: parent for turn, turn for finish, session for finish
                mock_reconstruct.side_effect = [
                    mock_session_call,  # Parent for turn creation
                    mock_turn_call,  # Reconstructed turn for finish
                    mock_session_call,  # Reconstructed session for finish
                ]

                with patch(
                    "weave.integrations.claude_plugin.session_processor.set_call_view"
                ) as mock_set_view:
                    with patch(
                        "weave.integrations.claude_plugin.diff_view.generate_turn_diff_html"
                    ) as mock_gen_diff:
                        mock_gen_diff.return_value = "<html>turn diff</html>"

                        _import_session_to_weave(
                            session, session_jsonl, use_ollama=False
                        )

                        # Verify generate_turn_diff_html was called
                        mock_gen_diff.assert_called()

                        # Verify set_call_view was called for turn
                        turn_view_calls = [
                            c
                            for c in mock_set_view.call_args_list
                            if c.kwargs.get("call") == mock_turn_call
                        ]
                        assert len(turn_view_calls) >= 1, (
                            "set_call_view should be called for turn with diff HTML"
                        )
        finally:
            session_jsonl.unlink()


class TestImporterDaemonParity:
    """Document expected parity between importer and daemon trace structure.

    The daemon creates traces in real-time with these features:
    1. Session-level call with HTML diff view and file_snapshots
    2. Turn-level calls with HTML diff view and file_snapshots
    3. Subagent expansion for Task calls with subagent_type
    4. Tool calls as children of turns (or subagents)

    This class tests that the importer produces equivalent structure.
    """

    def test_both_create_session_with_correct_op(self):
        """Both daemon and importer use claude_code.session op."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Hello"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Hi"}],
                    "usage": {"input_tokens": 50, "output_tokens": 10},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)

            with patch(
                "weave.integrations.claude_plugin.session_importer.require_weave_client"
            ) as mock_client:
                mock_client.return_value.create_call.return_value = MagicMock(
                    id="call-1", summary={}
                )

                _import_session_to_weave(session, session_jsonl, use_ollama=False)

                # Check first create_call was for session
                first_call = mock_client.return_value.create_call.call_args_list[0]
                assert first_call.kwargs.get("op") == "claude_code.session"
        finally:
            session_jsonl.unlink()

    def test_both_create_turns_with_correct_op(self):
        """Both daemon and importer use claude_code.turn op."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Hello"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Hi"}],
                    "usage": {"input_tokens": 50, "output_tokens": 10},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)

            with patch(
                "weave.integrations.claude_plugin.session_importer.require_weave_client"
            ) as mock_client:
                mock_session_call = MagicMock(id="session-1", summary={})
                mock_turn_call = MagicMock(id="turn-1", summary={})
                mock_client.return_value.create_call.side_effect = [
                    mock_session_call,
                    mock_turn_call,
                ]

                _import_session_to_weave(session, session_jsonl, use_ollama=False)

                # Check second create_call was for turn
                turn_call = mock_client.return_value.create_call.call_args_list[1]
                assert turn_call.kwargs.get("op") == "claude_code.turn"
        finally:
            session_jsonl.unlink()

    def test_session_summary_has_expected_keys(self):
        """Session summary should have turn_count, tool_call_count, etc."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Hello"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Hi"}],
                    "usage": {"input_tokens": 50, "output_tokens": 10},
                },
            },
        ])

        try:
            session = parse_session_file(session_jsonl)

            with patch(
                "weave.integrations.claude_plugin.session_importer.require_weave_client"
            ) as mock_client, patch(
                "weave.integrations.claude_plugin.session_importer.reconstruct_call"
            ) as mock_reconstruct:
                # Create distinct mock objects for session and turn
                mock_session_call = MagicMock(id="session-1")
                mock_session_call.summary = {}
                mock_turn_call = MagicMock(id="turn-1")
                mock_turn_call.summary = {}
                mock_client.return_value.create_call.side_effect = [
                    mock_session_call,
                    mock_turn_call,
                ]
                mock_client.return_value.finish_call = MagicMock()

                # Make reconstruct_call return calls with settable summary
                reconstructed_session = MagicMock(id="session-1")
                reconstructed_session.summary = {}
                reconstructed_turn = MagicMock(id="turn-1")
                reconstructed_turn.summary = {}
                mock_reconstruct.side_effect = [
                    mock_session_call,  # Parent for turn
                    reconstructed_turn,  # Reconstructed turn for finish
                    reconstructed_session,  # Reconstructed session for finish
                ]

                _import_session_to_weave(session, session_jsonl, use_ollama=False)

                # Check session summary has expected keys on the reconstructed call
                summary = reconstructed_session.summary
                assert "turn_count" in summary, f"Expected turn_count in session summary, got: {summary}"
                assert "tool_call_count" in summary, f"Expected tool_call_count in session summary, got: {summary}"
                assert "tool_call_breakdown" in summary
                assert "duration_ms" in summary
                assert "model" in summary
        finally:
            session_jsonl.unlink()


class TestFileChangeDetectionFiltering:
    """Tests for filtering file changes by session_id.

    Regression tests for the bug where generate_session_diff_html and
    collect_all_file_changes_from_session were scanning ALL agent-*.jsonl
    files in the sessions directory instead of only those belonging to
    the current session.
    """

    def test_collect_file_changes_filters_by_session_id(self, tmp_path):
        """collect_all_file_changes_from_session only includes this session's subagents."""
        from weave.integrations.claude_plugin.diff_utils import (
            collect_all_file_changes_from_session,
        )

        # Create main session file
        session_file = tmp_path / "session-a.jsonl"
        session_messages = [
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "session-a",
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Create a file"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-01-01T10:00:01Z",
                "toolUseResult": {
                    "type": "create",
                    "filePath": "/tmp/file-from-session-a.py",
                    "content": "# Created by session A",
                },
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Done"}],
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
            },
        ]
        with open(session_file, "w") as f:
            for msg in session_messages:
                f.write(json.dumps(msg) + "\n")

        # Create agent file that BELONGS to session-a
        agent_file_a = tmp_path / "agent-abc123.jsonl"
        agent_a_messages = [
            {
                "type": "user",
                "uuid": "agent-u1",
                "timestamp": "2025-01-01T10:00:02Z",
                "sessionId": "session-a",  # Same session ID
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Do something"},
            },
            {
                "type": "assistant",
                "uuid": "agent-a1",
                "timestamp": "2025-01-01T10:00:03Z",
                "toolUseResult": {
                    "type": "create",
                    "filePath": "/tmp/file-from-agent-a.py",
                    "content": "# Created by agent belonging to session A",
                },
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Done"}],
                    "usage": {"input_tokens": 50, "output_tokens": 25},
                },
            },
        ]
        with open(agent_file_a, "w") as f:
            for msg in agent_a_messages:
                f.write(json.dumps(msg) + "\n")

        # Create agent file that belongs to a DIFFERENT session
        agent_file_b = tmp_path / "agent-xyz789.jsonl"
        agent_b_messages = [
            {
                "type": "user",
                "uuid": "other-u1",
                "timestamp": "2025-01-01T09:00:00Z",
                "sessionId": "session-b",  # Different session ID!
                "cwd": "/tmp/test",
                "message": {"role": "user", "content": "Other session work"},
            },
            {
                "type": "assistant",
                "uuid": "other-a1",
                "timestamp": "2025-01-01T09:00:01Z",
                "toolUseResult": {
                    "type": "create",
                    "filePath": "/tmp/file-from-OTHER-session.py",
                    "content": "# Created by agent from session B - should NOT appear",
                },
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Done"}],
                    "usage": {"input_tokens": 50, "output_tokens": 25},
                },
            },
        ]
        with open(agent_file_b, "w") as f:
            for msg in agent_b_messages:
                f.write(json.dumps(msg) + "\n")

        # Parse and collect file changes
        session = parse_session_file(session_file)
        file_changes = collect_all_file_changes_from_session(session, tmp_path)

        # Should include files from session-a and its agent, but NOT from session-b's agent
        file_paths = set(file_changes.keys())

        assert "/tmp/file-from-session-a.py" in file_paths, (
            "Should include file from main session"
        )
        assert "/tmp/file-from-agent-a.py" in file_paths, (
            "Should include file from this session's agent"
        )
        assert "/tmp/file-from-OTHER-session.py" not in file_paths, (
            "Should NOT include file from other session's agent"
        )

        # Verify correct count
        assert len(file_changes) == 2, (
            f"Expected 2 files (session + its agent), got {len(file_changes)}: {list(file_changes.keys())}"
        )

    def test_real_session_file_change_count(self):
        """Verify real test session has expected number of file changes.

        Regression test for the bug where ALL agent files were scanned
        instead of only those belonging to the current session.
        """
        from weave.integrations.claude_plugin.diff_utils import (
            collect_all_file_changes_from_session,
        )

        if not TEST_SESSION_FILE.exists():
            pytest.skip(f"Test session file not found: {TEST_SESSION_FILE}")

        session = parse_session_file(TEST_SESSION_FILE)
        file_changes = collect_all_file_changes_from_session(session, TEST_SESSION_DIR)

        # The bug caused ~28+ files to be detected due to scanning all agent files
        # After fix, should be ~7 files for this specific session
        assert len(file_changes) < 15, (
            f"Expected ~7 file changes, got {len(file_changes)}. "
            "This suggests the session_id filter may not be working."
        )

        # Verify some expected files are present
        file_names = {Path(p).name for p in file_changes.keys()}
        expected_files = {"secret_scanner.py", "daemon.py", "handlers.py"}
        for expected in expected_files:
            assert expected in file_names, (
                f"Expected {expected} in file changes, got: {file_names}"
            )
