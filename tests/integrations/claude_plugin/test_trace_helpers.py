"""Tests for trace helper functions (build_turn_output, build_subagent_inputs, build_subagent_output)."""

from unittest.mock import MagicMock


class TestBuildTurnOutput:
    """Test _build_turn_output() helper function."""

    def test_build_turn_output_returns_message_format(self):
        """Verify build_turn_output returns proper Message format for ChatView."""
        from weave.integrations.claude_plugin.session.session_importer import (
            _build_turn_output,
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

        output, assistant_text, thinking_text = _build_turn_output(mock_turn)

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
        from weave.integrations.claude_plugin.session.session_importer import (
            _build_turn_output,
        )

        mock_msg = MagicMock()
        mock_msg.get_text.return_value = "Response"
        mock_msg.thinking_content = None

        mock_turn = MagicMock()
        mock_turn.assistant_messages = [mock_msg]
        mock_turn.all_tool_calls.return_value = []
        mock_turn.primary_model.return_value = "claude-3"

        output, _, _ = _build_turn_output(mock_turn, interrupted=True)

        assert output["interrupted"] is True
        assert output["stop_reason"] == "user_interrupt"


class TestBuildSubagentInputs:
    """Test _build_subagent_inputs() helper function."""

    def test_build_subagent_inputs_basic(self):
        """Verify basic subagent inputs structure."""
        from weave.integrations.claude_plugin.session.session_importer import (
            _build_subagent_inputs,
        )

        inputs = _build_subagent_inputs(
            prompt="Review the implementation",
            agent_id="agent-123",
        )

        assert "messages" in inputs
        assert len(inputs["messages"]) == 1
        assert inputs["messages"][0]["role"] == "user"
        assert inputs["messages"][0]["content"] == "Review the implementation"
        assert inputs["agent_id"] == "agent-123"

    def test_build_subagent_inputs_with_subagent_type(self):
        """Verify subagent_type is included when provided."""
        from weave.integrations.claude_plugin.session.session_importer import (
            _build_subagent_inputs,
        )

        inputs = _build_subagent_inputs(
            prompt="Fix the bug",
            subagent_type="code-reviewer",
        )

        assert inputs["subagent_type"] == "code-reviewer"

    def test_build_subagent_inputs_truncates_long_prompt(self):
        """Verify long prompts are truncated."""
        from weave.integrations.claude_plugin.session.session_importer import (
            _build_subagent_inputs,
        )

        long_prompt = "x" * 10000
        inputs = _build_subagent_inputs(prompt=long_prompt)

        # Should be truncated to 5000 chars + "...[truncated]"
        content = inputs["messages"][0]["content"]
        assert len(content) <= 5014  # 5000 + "...[truncated]"
        assert content.endswith("...[truncated]")


class TestBuildSubagentOutput:
    """Test _build_subagent_output() helper function."""

    def test_build_subagent_output_basic(self):
        """Verify basic subagent output structure."""
        from weave.integrations.claude_plugin.session.session_importer import (
            _build_subagent_output,
        )

        # Create mock session with turns
        mock_msg = MagicMock()
        mock_msg.get_text.return_value = "Task completed successfully."

        mock_turn = MagicMock()
        mock_turn.assistant_messages = [mock_msg]
        mock_turn.all_tool_calls.return_value = []

        mock_session = MagicMock()
        mock_session.turns = [mock_turn]
        mock_session.primary_model.return_value = "claude-3"

        output = _build_subagent_output(mock_session)

        assert output["role"] == "assistant"
        assert "Task completed successfully" in output["content"]
        assert output["model"] == "claude-3"

    def test_build_subagent_output_aggregates_tool_calls(self):
        """Verify tool calls from all turns are aggregated."""
        from weave.integrations.claude_plugin.session.session_importer import (
            _build_subagent_output,
        )

        # Create mock tool calls
        mock_tc1 = MagicMock()
        mock_tc1.id = "toolu_1"
        mock_tc1.name = "Read"
        mock_tc1.input = {"file_path": "test.py"}
        mock_tc1.result = "content1"

        mock_tc2 = MagicMock()
        mock_tc2.id = "toolu_2"
        mock_tc2.name = "Edit"
        mock_tc2.input = {"file_path": "test.py"}
        mock_tc2.result = "content2"

        # Create mock turns
        mock_turn1 = MagicMock()
        mock_turn1.assistant_messages = []
        mock_turn1.all_tool_calls.return_value = [mock_tc1]

        mock_turn2 = MagicMock()
        mock_msg = MagicMock()
        mock_msg.get_text.return_value = "Done."
        mock_turn2.assistant_messages = [mock_msg]
        mock_turn2.all_tool_calls.return_value = [mock_tc2]

        mock_session = MagicMock()
        mock_session.turns = [mock_turn1, mock_turn2]
        mock_session.primary_model.return_value = "claude-3"

        output = _build_subagent_output(mock_session)

        # Should have both tool calls
        assert "tool_calls" in output
        assert len(output["tool_calls"]) == 2
        assert output["tool_calls"][0]["id"] == "toolu_1"
        assert output["tool_calls"][1]["id"] == "toolu_2"
        # Final output should be from last turn
        assert "Done" in output["content"]

    def test_build_subagent_output_empty_session(self):
        """Verify empty session returns default output."""
        from weave.integrations.claude_plugin.session.session_importer import (
            _build_subagent_output,
        )

        mock_session = MagicMock()
        mock_session.turns = []

        output = _build_subagent_output(mock_session)

        assert output["role"] == "assistant"
        assert output["content"] == ""
        assert output["model"] == "unknown"

    def test_build_subagent_output_none_session(self):
        """Verify None session returns default output."""
        from weave.integrations.claude_plugin.session.session_importer import (
            _build_subagent_output,
        )

        output = _build_subagent_output(None)

        assert output["role"] == "assistant"
        assert output["content"] == ""
        assert output["model"] == "unknown"
