"""Tests for AgentTraceBuilder."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from weave.integrations.ag_ui.events import (
    RunFinishedEvent,
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    ThinkingContentEvent,
    ToolCallArgsEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
    UsageRecordedEvent,
)
from weave.integrations.ag_ui.trace_builder import AgentTraceBuilder


class TestTraceBuilderLifecycle:
    def test_run_started_creates_session_call(self):
        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock(id="call-123")

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        event = RunStartedEvent(
            run_id="run-1",
            timestamp=datetime.now(timezone.utc),
            input="Help me with code",
        )
        builder.handle(event)

        mock_client.create_call.assert_called_once()
        assert "run-1" in builder._run_calls

    def test_run_finished_finishes_session_call(self):
        mock_client = MagicMock()
        mock_call = MagicMock(id="call-123")
        mock_client.create_call.return_value = mock_call

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Start then finish
        builder.handle(
            RunStartedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )
        builder.handle(
            RunFinishedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )

        mock_client.finish_call.assert_called_once()


class TestTraceBuilderSteps:
    def test_step_creates_child_call(self):
        mock_client = MagicMock()
        mock_session_call = MagicMock(id="session-call")
        mock_step_call = MagicMock(id="step-call")
        mock_client.create_call.side_effect = [mock_session_call, mock_step_call]

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        builder.handle(
            RunStartedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )
        builder.handle(
            StepStartedEvent(
                step_id="step-1",
                run_id="run-1",
                step_type="turn",
                timestamp=datetime.now(timezone.utc),
            )
        )

        assert mock_client.create_call.call_count == 2
        assert "step-1" in builder._step_calls


class TestTraceBuilderToolHook:
    @patch("weave.integrations.claude_plugin.utils.log_tool_call")
    def test_on_tool_call_hook_invoked(self, mock_log_tool_call):
        mock_client = MagicMock()
        mock_tool_call = MagicMock(id="tool-call")
        mock_log_tool_call.return_value = mock_tool_call

        hook_called = []

        def on_tool(event, call):
            hook_called.append((event.tool_call_id, call.id))

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
            on_tool_call=on_tool,
        )

        # Setup run and step
        builder.handle(
            RunStartedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )
        builder.handle(
            StepStartedEvent(
                step_id="step-1",
                run_id="run-1",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Tool call
        builder.handle(
            ToolCallStartEvent(
                tool_call_id="tool-1",
                tool_name="Read",
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            ToolCallResultEvent(
                tool_call_id="tool-1",
                content="file content",
                timestamp=datetime.now(timezone.utc),
            )
        )

        assert len(hook_called) == 1
        assert hook_called[0][0] == "tool-1"


class TestTraceBuilderToolArgs:
    """Test ToolCallArgsEvent handling."""

    @patch("weave.integrations.claude_plugin.utils.log_tool_call")
    def test_tool_args_stored_and_used(self, mock_log_tool_call):
        mock_client = MagicMock()
        mock_tool_call = MagicMock(id="tool-call")
        mock_log_tool_call.return_value = mock_tool_call

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Setup run and step
        builder.handle(
            RunStartedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )
        builder.handle(
            StepStartedEvent(
                step_id="step-1",
                run_id="run-1",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Tool call with args
        builder.handle(
            ToolCallStartEvent(
                tool_call_id="tool-1",
                tool_name="Read",
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            ToolCallArgsEvent(
                tool_call_id="tool-1",
                args={"file_path": "/path/to/file.py"},
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            ToolCallResultEvent(
                tool_call_id="tool-1",
                content="file content",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Verify log_tool_call was called with the args
        mock_log_tool_call.assert_called_once()
        call_kwargs = mock_log_tool_call.call_args[1]
        assert call_kwargs["tool_input"] == {"file_path": "/path/to/file.py"}
        assert call_kwargs["tool_name"] == "Read"


class TestTraceBuilderUsage:
    """Test UsageRecordedEvent handling."""

    def test_usage_aggregated_to_step(self):
        mock_client = MagicMock()
        mock_step_call = MagicMock(id="step-call")
        mock_client.create_call.side_effect = [
            MagicMock(id="run-call"),
            mock_step_call,
        ]

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Setup run and step
        builder.handle(
            RunStartedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )
        builder.handle(
            StepStartedEvent(
                step_id="step-1",
                run_id="run-1",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Start messages and track usage
        from weave.integrations.ag_ui.events import TextMessageStartEvent

        builder.handle(
            TextMessageStartEvent(
                message_id="msg-1",
                role="assistant",
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            UsageRecordedEvent(
                message_id="msg-1",
                model="claude-sonnet-4",
                input_tokens=100,
                output_tokens=50,
                timestamp=datetime.now(timezone.utc),
            )
        )

        builder.handle(
            TextMessageStartEvent(
                message_id="msg-2",
                role="assistant",
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            UsageRecordedEvent(
                message_id="msg-2",
                model="claude-sonnet-4",
                input_tokens=75,
                output_tokens=25,
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Check that summary was set with aggregated usage
        assert mock_step_call.summary is not None
        assert "usage" in mock_step_call.summary
        assert "claude-sonnet-4" in mock_step_call.summary["usage"]
        usage = mock_step_call.summary["usage"]["claude-sonnet-4"]
        assert usage["input_tokens"] == 175  # 100 + 75
        assert usage["output_tokens"] == 75  # 50 + 25


class TestTraceBuilderTextContent:
    """Test text content accumulation."""

    def test_text_content_accumulated_in_output(self):
        mock_client = MagicMock()
        mock_step_call = MagicMock(id="step-call")
        mock_client.create_call.side_effect = [
            MagicMock(id="run-call"),
            mock_step_call,
        ]

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Setup run and step
        builder.handle(
            RunStartedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )
        builder.handle(
            StepStartedEvent(
                step_id="step-1",
                run_id="run-1",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Start message and add content
        from weave.integrations.ag_ui.events import TextMessageStartEvent

        builder.handle(
            TextMessageStartEvent(
                message_id="msg-1",
                role="assistant",
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            TextMessageContentEvent(
                message_id="msg-1",
                delta="Hello, ",
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            TextMessageContentEvent(
                message_id="msg-1",
                delta="world!",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Check that finish_call was called with accumulated content
        mock_client.finish_call.assert_called_once()
        call_args = mock_client.finish_call.call_args
        output = call_args[1]["output"]
        assert output["content"] == "Hello, world!"


class TestTraceBuilderThinking:
    """Test thinking content accumulation."""

    def test_thinking_content_accumulated_as_reasoning(self):
        mock_client = MagicMock()
        mock_step_call = MagicMock(id="step-call")
        mock_client.create_call.side_effect = [
            MagicMock(id="run-call"),
            mock_step_call,
        ]

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Setup run and step
        builder.handle(
            RunStartedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )
        builder.handle(
            StepStartedEvent(
                step_id="step-1",
                run_id="run-1",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Start message and add thinking content
        from weave.integrations.ag_ui.events import TextMessageStartEvent

        builder.handle(
            TextMessageStartEvent(
                message_id="msg-1",
                role="assistant",
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            ThinkingContentEvent(
                message_id="msg-1",
                content="Let me think about this... ",
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            ThinkingContentEvent(
                message_id="msg-1",
                content="I should check the file first.",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Check that finish_call was called with reasoning content
        mock_client.finish_call.assert_called_once()
        call_args = mock_client.finish_call.call_args
        output = call_args[1]["output"]
        assert (
            output["reasoning_content"]
            == "Let me think about this... I should check the file first."
        )


class TestTraceBuilderProcessEvents:
    """Test the process_events convenience method."""

    def test_process_events_handles_all_events(self):
        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock(id="call")

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Create a list of events
        events = [
            RunStartedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc)),
            StepStartedEvent(
                step_id="step-1",
                run_id="run-1",
                timestamp=datetime.now(timezone.utc),
            ),
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc)),
            RunFinishedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc)),
        ]

        # Process all events
        builder.process_events(iter(events))

        # Verify calls were created and finished
        assert mock_client.create_call.call_count == 2  # run + step
        assert mock_client.finish_call.call_count == 2  # run + step
