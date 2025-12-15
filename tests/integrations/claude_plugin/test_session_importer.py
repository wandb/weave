"""Tests for session importer.

Tool calls are embedded in turn/subagent output using build_turn_output(),
not as separate child traces. This enables ChatView rendering.
"""

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


class TestToolCallsInOutput:
    """Test that tool calls are embedded in turn output, not as child traces."""

    def test_tool_calls_counted_in_return_value(self):
        """Tool calls should be counted in the return value."""
        # Create minimal session with tool calls
        turn = make_turn_with_tool_call(
            user_content="Add todos",
            tool_name="TodoWrite",
            tool_input={
                "todos": [{"content": "Test", "status": "pending", "activeForm": "Testing"}]
            },
        )
        session = make_minimal_session(turns=[turn])

        with patch(
            "weave.integrations.claude_plugin.session_importer.require_weave_client"
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
        turn = Turn(user_message=UserMessage(uuid="u1", content="Do stuff", timestamp=now))
        turn.assistant_messages.append(
            AssistantMessage(
                uuid="a1",
                model="claude-sonnet-4-20250514",
                text_content=["Done"],
                tool_calls=[
                    ToolCall(id="t1", name="Read", input={"file_path": "/a.txt"}, timestamp=now, result="a"),
                    ToolCall(id="t2", name="Grep", input={"pattern": "foo"}, timestamp=now, result="b"),
                    ToolCall(id="t3", name="Edit", input={"file_path": "/a.txt"}, timestamp=now, result="c"),
                ],
                usage=TokenUsage(),
                timestamp=now,
            )
        )
        session = make_minimal_session(turns=[turn])

        with patch(
            "weave.integrations.claude_plugin.session_importer.require_weave_client"
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
        # Note: skill_expansion is stored on the turn but not used for child traces
        # The expansion becomes part of conversation context, not tool output
        turn.skill_expansion = "Base directory for this skill: /path\n\n# Skill Content"
        session = make_minimal_session(turns=[turn])

        with patch(
            "weave.integrations.claude_plugin.session_importer.require_weave_client"
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
        ) as mock_client, patch(
            "weave.integrations.claude_plugin.session_importer.reconstruct_call"
        ) as mock_reconstruct:
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
            assert reconstructed_call.summary is not None, "Turn should have summary set"
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
            "weave.integrations.claude_plugin.session_importer.require_weave_client"
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
