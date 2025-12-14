"""Tests for session importer."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from weave.integrations.claude_plugin.session_importer import _import_session_to_weave
from weave.integrations.claude_plugin.session_parser import (
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
    turn = Turn(user_message=UserMessage(uuid="u1", content=user_content, timestamp=now))
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


class TestToolCallLogging:
    """Test that tool calls use log_tool_call for consistency."""

    def test_todowrite_uses_log_tool_call(self):
        """TodoWrite tool calls should go through log_tool_call for HTML views."""
        # Create minimal session with TodoWrite call
        turn = make_turn_with_tool_call(
            user_content="Add todos",
            tool_name="TodoWrite",
            tool_input={
                "todos": [{"content": "Test", "status": "pending", "activeForm": "Testing"}]
            },
        )
        session = make_minimal_session(turns=[turn])

        with patch(
            "weave.integrations.claude_plugin.session_importer.log_tool_call"
        ) as mock_log:
            with patch(
                "weave.integrations.claude_plugin.session_importer.require_weave_client"
            ) as mock_client:
                mock_client.return_value = MagicMock()
                mock_client.return_value.create_call.return_value = MagicMock(
                    id="call-1", summary={}
                )

                # This should use log_tool_call for TodoWrite
                _import_session_to_weave(session, Path("/tmp/test.jsonl"), use_ollama=False)

                # Verify log_tool_call was called for TodoWrite
                calls = [
                    c
                    for c in mock_log.call_args_list
                    if c.kwargs.get("tool_name") == "TodoWrite"
                ]
                assert len(calls) == 1, "TodoWrite should use log_tool_call"

    def test_read_uses_log_tool_call(self):
        """Read tool calls should also go through log_tool_call."""
        turn = make_turn_with_tool_call(
            user_content="Read a file",
            tool_name="Read",
            tool_input={"file_path": "/tmp/test.txt"},
            tool_result="file content",
        )
        session = make_minimal_session(turns=[turn])

        with patch(
            "weave.integrations.claude_plugin.session_importer.log_tool_call"
        ) as mock_log:
            with patch(
                "weave.integrations.claude_plugin.session_importer.require_weave_client"
            ) as mock_client:
                mock_client.return_value = MagicMock()
                mock_client.return_value.create_call.return_value = MagicMock(
                    id="call-1", summary={}
                )

                _import_session_to_weave(session, Path("/tmp/test.jsonl"), use_ollama=False)

                # Verify log_tool_call was called for Read
                calls = [
                    c
                    for c in mock_log.call_args_list
                    if c.kwargs.get("tool_name") == "Read"
                ]
                assert len(calls) == 1, "Read should use log_tool_call"


class TestSkillExpansionAttachment:
    """Test that skill expansions are attached to Skill tool calls."""

    def test_skill_tool_gets_expansion_content(self):
        """Skill tool calls should have the expansion as their output."""
        now = datetime.now(timezone.utc)

        # Create session with skill call and expansion
        turn = Turn(user_message=UserMessage(uuid="u1", content="Use skill", timestamp=now))
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
        # Attach skill expansion to the turn
        turn.skill_expansion = "Base directory for this skill: /path\n\n# Skill Content\n\nDetails here..."
        session = make_minimal_session(turns=[turn])

        with patch(
            "weave.integrations.claude_plugin.session_importer.log_tool_call"
        ) as mock_log:
            with patch(
                "weave.integrations.claude_plugin.session_importer.require_weave_client"
            ) as mock_client:
                mock_client.return_value = MagicMock()
                mock_client.return_value.create_call.return_value = MagicMock(
                    id="call-1", summary={}
                )

                _import_session_to_weave(session, Path("/tmp/test.jsonl"), use_ollama=False)

                # Check Skill tool call got the expansion as output
                skill_calls = [
                    c
                    for c in mock_log.call_args_list
                    if c.kwargs.get("tool_name") == "Skill"
                ]
                assert len(skill_calls) == 1
                assert "Skill Content" in skill_calls[0].kwargs.get("tool_output", "")


class TestQAContextTracking:
    """Test that Q&A context is tracked across turns."""

    def test_question_from_turn1_appears_in_turn2_input(self):
        """When Turn 1 ends with a question, Turn 2 should have in_response_to."""
        now = datetime.now(timezone.utc)

        # Create Turn 1 with assistant ending with a question
        turn1 = Turn(user_message=UserMessage(uuid="u1", content="Help me", timestamp=now))
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
            "weave.integrations.claude_plugin.session_importer.require_weave_client"
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
            assert "?" in turn2_inputs["in_response_to"], "in_response_to should be a question"

    def test_no_question_means_no_in_response_to(self):
        """When Turn 1 doesn't end with a question, Turn 2 should NOT have in_response_to."""
        now = datetime.now(timezone.utc)

        # Create Turn 1 WITHOUT a question
        turn1 = Turn(user_message=UserMessage(uuid="u1", content="Help me", timestamp=now))
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
            "weave.integrations.claude_plugin.session_importer.require_weave_client"
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
            assert (
                "in_response_to" not in turn2_inputs
            ), "Turn 2 should NOT have in_response_to when Turn 1 has no question"


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

        with patch(
            "weave.integrations.claude_plugin.session_importer.require_weave_client"
        ) as mock_client:
            mock_call = MagicMock(id="turn-1")
            mock_call.summary = {}
            mock_client.return_value.create_call.return_value = mock_call
            mock_client.return_value.finish_call = MagicMock()

            _import_session_to_weave(session, Path("/tmp/test.jsonl"), use_ollama=False)

            # Turn summary should have been set with model info
            # Check that summary was assigned before finish_call
            assert mock_call.summary is not None, "Turn should have summary set"
            assert "model" in mock_call.summary, "Summary should have model"
            assert "usage" in mock_call.summary, "Summary should have usage"

    def test_turn_output_does_not_have_model_usage(self):
        """Turn output should NOT contain model/usage (those go in summary)."""
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
            "weave.integrations.claude_plugin.session_importer.require_weave_client"
        ) as mock_client:
            mock_call = MagicMock(id="turn-1")
            mock_call.summary = {}
            mock_client.return_value.create_call.return_value = mock_call
            mock_client.return_value.finish_call = MagicMock()

            _import_session_to_weave(session, Path("/tmp/test.jsonl"), use_ollama=False)

            # Check finish_call was called and output doesn't have model/usage
            finish_calls = mock_client.return_value.finish_call.call_args_list
            # Find the turn finish call (not session)
            for call in finish_calls:
                output = call.kwargs.get("output", {}) or {}
                if output:
                    # Turn output should not have model or usage keys
                    assert "model" not in output, "Output should not have model"
                    assert "usage" not in output, "Output should not have usage"
