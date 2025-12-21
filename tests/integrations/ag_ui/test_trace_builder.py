"""Tests for AgentTraceBuilder."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from weave.integrations.ag_ui.events import (
    FileSnapshotEvent,
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
    def test_on_tool_call_hook_invoked(self):
        mock_client = MagicMock()
        mock_tool_call = MagicMock(id="tool-call")
        mock_client.create_call.return_value = mock_tool_call

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


class TestTraceBuilderStepFinishedHook:
    def test_on_step_finished_hook_invoked(self):
        """Test that on_step_finished hook is called after step finishes."""
        mock_client = MagicMock()
        mock_step_call = MagicMock(id="step-call")
        mock_client.create_call.side_effect = [
            MagicMock(id="run-call"),
            mock_step_call,
        ]

        hook_called = []

        def on_step(event, call):
            hook_called.append((event.step_id, call.id))

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
            on_step_finished=on_step,
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

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        assert len(hook_called) == 1
        assert hook_called[0][0] == "step-1"
        assert hook_called[0][1] == "step-call"

    def test_on_step_finished_hook_receives_event_and_call(self):
        """Test that hook receives both the event and the call object."""
        mock_client = MagicMock()
        mock_step_call = MagicMock(id="step-call")
        mock_client.create_call.side_effect = [
            MagicMock(id="run-call"),
            mock_step_call,
        ]

        received_event = None
        received_call = None

        def on_step(event, call):
            nonlocal received_event, received_call
            received_event = event
            received_call = call

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
            on_step_finished=on_step,
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

        # Finish step
        finish_event = StepFinishedEvent(
            step_id="step-1", timestamp=datetime.now(timezone.utc)
        )
        builder.handle(finish_event)

        assert received_event is finish_event
        assert received_call is mock_step_call

    def test_on_step_finished_hook_optional(self):
        """Test that step finishes work without hook."""
        mock_client = MagicMock()
        mock_step_call = MagicMock(id="step-call")
        mock_client.create_call.side_effect = [
            MagicMock(id="run-call"),
            mock_step_call,
        ]

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
            # No on_step_finished hook provided
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

        # Finish step - should not crash
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Verify step was finished
        mock_client.finish_call.assert_called_once()

    def test_on_step_finished_hook_called_after_finish_call(self):
        """Test that hook is called after the step call is finished."""
        mock_client = MagicMock()
        mock_step_call = MagicMock(id="step-call")
        mock_client.create_call.side_effect = [
            MagicMock(id="run-call"),
            mock_step_call,
        ]

        call_order = []

        def track_finish_call(*args, **kwargs):
            call_order.append("finish_call")

        def on_step(event, call):
            call_order.append("hook")

        mock_client.finish_call.side_effect = track_finish_call

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
            on_step_finished=on_step,
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

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Verify hook was called after finish_call
        assert call_order == ["finish_call", "hook"]

    def test_on_step_finished_hook_with_pending_question(self):
        """Test that hook is called even when step has pending question."""
        mock_client = MagicMock()
        mock_step_call = MagicMock(id="step-call")
        mock_client.create_call.side_effect = [
            MagicMock(id="run-call"),
            mock_step_call,
        ]

        hook_called = []

        def on_step(event, call):
            hook_called.append(event.pending_question)

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
            on_step_finished=on_step,
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

        # Finish step with pending question
        builder.handle(
            StepFinishedEvent(
                step_id="step-1",
                timestamp=datetime.now(timezone.utc),
                pending_question="Should I proceed?",
            )
        )

        assert len(hook_called) == 1
        assert hook_called[0] == "Should I proceed?"


class TestTraceBuilderToolArgs:
    """Test ToolCallArgsEvent handling."""

    def test_tool_args_stored_and_used(self):
        mock_client = MagicMock()
        mock_tool_call = MagicMock(id="tool-call")
        mock_client.create_call.return_value = mock_tool_call

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

        # Verify create_call was called with the args
        # The second create_call is for the tool (first is for step)
        tool_create_calls = [
            call for call in mock_client.create_call.call_args_list
            if call[1].get("op") == "Read"
        ]
        assert len(tool_create_calls) == 1
        assert tool_create_calls[0][1]["inputs"] == {"file_path": "/path/to/file.py"}


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


class TestChatViewFormat:
    """Test ChatView-compatible output format."""

    def test_step_output_includes_role_and_model(self):
        """Test that step output includes role and model for ChatView."""
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

        # Add message with usage
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
            TextMessageContentEvent(
                message_id="msg-1",
                delta="Hello!",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Check that finish_call was called with ChatView format
        mock_client.finish_call.assert_called_once()
        call_args = mock_client.finish_call.call_args
        output = call_args[1]["output"]
        assert output["role"] == "assistant"
        assert output["model"] == "claude-sonnet-4"
        assert output["content"] == "Hello!"

    def test_tool_calls_in_openai_format(self):
        """Test that tool calls are included in OpenAI format with embedded results."""
        mock_client = MagicMock()
        mock_step_call = MagicMock(id="step-call")
        mock_tool_call = MagicMock(id="tool-call")
        mock_client.create_call.side_effect = [
            MagicMock(id="run-call"),
            mock_step_call,
            mock_tool_call,
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

        # Tool call with args
        start_time = datetime.now(timezone.utc)
        builder.handle(
            ToolCallStartEvent(
                tool_call_id="tool-1",
                tool_name="Read",
                timestamp=start_time,
            )
        )
        builder.handle(
            ToolCallArgsEvent(
                tool_call_id="tool-1",
                args={"file_path": "/path/to/file.py"},
                timestamp=start_time,
            )
        )
        end_time = start_time + timedelta(milliseconds=150)
        builder.handle(
            ToolCallResultEvent(
                tool_call_id="tool-1",
                content="file content here",
                timestamp=end_time,
            )
        )

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Check that finish_call was called with tool_calls in output
        finish_calls = [
            call for call in mock_client.finish_call.call_args_list if call[0][0] == mock_step_call
        ]
        assert len(finish_calls) == 1
        output = finish_calls[0][1]["output"]

        assert "tool_calls" in output
        assert len(output["tool_calls"]) == 1

        tool_call = output["tool_calls"][0]
        assert tool_call["id"] == "tool-1"
        assert tool_call["type"] == "function"
        assert tool_call["function"]["name"] == "Read"
        assert tool_call["function"]["arguments"] == '{"file_path": "/path/to/file.py"}'
        assert tool_call["response"]["role"] == "tool"
        assert tool_call["response"]["content"] == "file content here"
        assert tool_call["response"]["tool_call_id"] == "tool-1"
        assert tool_call["is_error"] is False
        assert "duration_ms" in tool_call

    def test_multiple_tool_calls_in_step(self):
        """Test that multiple tool calls are all included in the output."""
        mock_client = MagicMock()
        mock_step_call = MagicMock(id="step-call")
        mock_client.create_call.return_value = mock_step_call

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

        # First tool call
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
                args={"file_path": "/file1.py"},
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            ToolCallResultEvent(
                tool_call_id="tool-1",
                content="content1",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Second tool call
        builder.handle(
            ToolCallStartEvent(
                tool_call_id="tool-2",
                tool_name="Write",
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            ToolCallArgsEvent(
                tool_call_id="tool-2",
                args={"file_path": "/file2.py", "content": "new content"},
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            ToolCallResultEvent(
                tool_call_id="tool-2",
                content="File written",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Get the last finish_call for the step
        finish_calls = mock_client.finish_call.call_args_list
        step_finish = [c for c in finish_calls if c[0][0] == mock_step_call][-1]
        output = step_finish[1]["output"]

        assert "tool_calls" in output
        assert len(output["tool_calls"]) == 2
        assert output["tool_calls"][0]["function"]["name"] == "Read"
        assert output["tool_calls"][1]["function"]["name"] == "Write"

    def test_reasoning_content_in_output(self):
        """Test that reasoning_content is included in output for ChatView."""
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

        # Add message with thinking and content
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
                content="Let me think... ",
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            ThinkingContentEvent(
                message_id="msg-1",
                content="I should check this.",
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            TextMessageContentEvent(
                message_id="msg-1",
                delta="Here's the answer!",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Check output has both content and reasoning_content
        mock_client.finish_call.assert_called_once()
        call_args = mock_client.finish_call.call_args
        output = call_args[1]["output"]
        assert output["content"] == "Here's the answer!"
        assert output["reasoning_content"] == "Let me think... I should check this."
        assert output["role"] == "assistant"

    def test_tool_call_without_current_step(self):
        """Test that tool calls outside a step don't crash."""
        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock(id="call")

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Setup run but no step
        builder.handle(
            RunStartedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )

        # Tool call without a step (edge case)
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
                content="result",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Should not crash - tool call created but not tracked for ChatView
        assert len(builder._step_tool_calls) == 0


class TestFileSnapshots:
    """Test file snapshot tracking."""

    def test_file_snapshot_creates_content_object(self):
        """Test that FileSnapshotEvent creates Content object in output."""
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

        # Record file snapshot
        builder.handle(
            FileSnapshotEvent(
                file_path="/path/to/file.py",
                content="print('hello world')",
                mimetype="text/x-python",
                is_backup=False,
                timestamp=datetime.now(timezone.utc),
                metadata={"edit_type": "create"},
            )
        )

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Check that finish_call was called with file_snapshots
        mock_client.finish_call.assert_called_once()
        call_args = mock_client.finish_call.call_args
        output = call_args[1]["output"]
        assert "file_snapshots" in output
        assert len(output["file_snapshots"]) == 1

        # Verify Content object properties
        snapshot = output["file_snapshots"][0]
        assert snapshot.mimetype == "text/x-python"
        assert snapshot.as_string() == "print('hello world')"
        assert snapshot.metadata["file_path"] == "/path/to/file.py"
        assert snapshot.metadata["is_backup"] is False
        assert snapshot.metadata["edit_type"] == "create"

    def test_multiple_file_snapshots_in_step(self):
        """Test that multiple file snapshots are tracked."""
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

        # Record multiple file snapshots
        builder.handle(
            FileSnapshotEvent(
                file_path="/path/to/file1.py",
                content="# File 1 backup",
                is_backup=True,
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            FileSnapshotEvent(
                file_path="/path/to/file1.py",
                content="# File 1 edited",
                is_backup=False,
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            FileSnapshotEvent(
                file_path="/path/to/file2.py",
                content="# File 2 new",
                is_backup=False,
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Check that all snapshots are in output
        mock_client.finish_call.assert_called_once()
        call_args = mock_client.finish_call.call_args
        output = call_args[1]["output"]
        assert "file_snapshots" in output
        assert len(output["file_snapshots"]) == 3

        # Verify snapshots are in order
        assert output["file_snapshots"][0].as_string() == "# File 1 backup"
        assert output["file_snapshots"][0].metadata["is_backup"] is True
        assert output["file_snapshots"][1].as_string() == "# File 1 edited"
        assert output["file_snapshots"][1].metadata["is_backup"] is False
        assert output["file_snapshots"][2].as_string() == "# File 2 new"

    def test_file_snapshot_with_bytes_content(self):
        """Test that FileSnapshotEvent with bytes content works."""
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

        # Record file snapshot with bytes
        binary_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        builder.handle(
            FileSnapshotEvent(
                file_path="/path/to/image.png",
                content=binary_content,
                mimetype="image/png",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Check that snapshot was created
        mock_client.finish_call.assert_called_once()
        call_args = mock_client.finish_call.call_args
        output = call_args[1]["output"]
        assert "file_snapshots" in output
        assert len(output["file_snapshots"]) == 1

        # Verify Content object
        snapshot = output["file_snapshots"][0]
        assert snapshot.mimetype == "image/png"
        assert snapshot.data == binary_content

    def test_file_snapshot_without_step(self):
        """Test that file snapshot outside step doesn't crash."""
        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock(id="call")

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Setup run but no step
        builder.handle(
            RunStartedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )

        # File snapshot without a step (edge case)
        builder.handle(
            FileSnapshotEvent(
                file_path="/path/to/file.py",
                content="some content",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Should not crash - snapshot not tracked
        assert len(builder._step_file_snapshots) == 0

    def test_file_snapshot_without_content(self):
        """Test that file snapshot without content is ignored."""
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

        # Record file snapshot without content
        builder.handle(
            FileSnapshotEvent(
                file_path="/path/to/file.py",
                content=None,
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Check that no file_snapshots in output
        mock_client.finish_call.assert_called_once()
        call_args = mock_client.finish_call.call_args
        output = call_args[1]["output"]
        assert "file_snapshots" not in output

    def test_file_snapshots_cleaned_up_after_step(self):
        """Test that file snapshots are cleaned up after step finishes."""
        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock(id="call")

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

        # Record file snapshot
        builder.handle(
            FileSnapshotEvent(
                file_path="/path/to/file.py",
                content="content",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Verify snapshot is tracked
        assert "step-1" in builder._step_file_snapshots
        assert len(builder._step_file_snapshots["step-1"]) == 1

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Verify cleanup
        assert "step-1" not in builder._step_file_snapshots


class TestSessionSummary:
    """Test session-level summary generation."""

    def test_run_finished_sets_summary_with_turn_count(self):
        """Test that run summary includes turn count."""
        mock_client = MagicMock()
        mock_run_call = MagicMock(id="run-call")
        mock_client.create_call.return_value = mock_run_call

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Start run
        builder.handle(
            RunStartedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )

        # Add multiple steps
        for i in range(3):
            builder.handle(
                StepStartedEvent(
                    step_id=f"step-{i}",
                    run_id="run-1",
                    timestamp=datetime.now(timezone.utc),
                )
            )
            builder.handle(
                StepFinishedEvent(
                    step_id=f"step-{i}", timestamp=datetime.now(timezone.utc)
                )
            )

        # Finish run
        builder.handle(
            RunFinishedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )

        # Verify summary was set
        assert mock_run_call.summary is not None
        assert mock_run_call.summary["turn_count"] == 3

    def test_run_finished_sets_summary_with_tool_count(self):
        """Test that run summary includes tool call count."""
        mock_client = MagicMock()
        mock_run_call = MagicMock(id="run-call")
        mock_client.create_call.return_value = mock_run_call

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Start run and step
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

        # Add multiple tool calls
        for i in range(5):
            builder.handle(
                ToolCallStartEvent(
                    tool_call_id=f"tool-{i}",
                    tool_name="Read",
                    timestamp=datetime.now(timezone.utc),
                )
            )
            builder.handle(
                ToolCallResultEvent(
                    tool_call_id=f"tool-{i}",
                    content="result",
                    timestamp=datetime.now(timezone.utc),
                )
            )

        # Finish step and run
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )
        builder.handle(
            RunFinishedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )

        # Verify summary was set
        assert mock_run_call.summary is not None
        assert mock_run_call.summary["tool_call_count"] == 5

    def test_run_finished_sets_summary_with_model(self):
        """Test that run summary includes model from metadata."""
        mock_client = MagicMock()
        mock_run_call = MagicMock(id="run-call")
        mock_client.create_call.return_value = mock_run_call

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Start run with model in metadata
        builder.handle(
            RunStartedEvent(
                run_id="run-1",
                timestamp=datetime.now(timezone.utc),
                metadata={"model": "claude-sonnet-4-5"},
            )
        )

        # Finish run
        builder.handle(
            RunFinishedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )

        # Verify summary includes model
        assert mock_run_call.summary is not None
        assert mock_run_call.summary["model"] == "claude-sonnet-4-5"

    def test_run_finished_sets_summary_with_git_info(self):
        """Test that run summary includes git info when cwd is in metadata."""
        mock_client = MagicMock()
        mock_run_call = MagicMock(id="run-call")
        mock_client.create_call.return_value = mock_run_call

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Start run with cwd in metadata (use current directory)
        import os

        cwd = os.getcwd()
        builder.handle(
            RunStartedEvent(
                run_id="run-1",
                timestamp=datetime.now(timezone.utc),
                metadata={"cwd": cwd},
            )
        )

        # Finish run
        builder.handle(
            RunFinishedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )

        # Verify summary was set (git_info may or may not be present depending on whether cwd is a git repo)
        assert mock_run_call.summary is not None
        # If git_info is present, it should have the right structure
        if "git_info" in mock_run_call.summary:
            git_info = mock_run_call.summary["git_info"]
            assert isinstance(git_info, dict)

    def test_run_finished_comprehensive_summary(self):
        """Test that run summary includes all available fields."""
        mock_client = MagicMock()
        mock_run_call = MagicMock(id="run-call")
        mock_client.create_call.return_value = mock_run_call

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Start run with full metadata
        import os

        cwd = os.getcwd()
        builder.handle(
            RunStartedEvent(
                run_id="run-1",
                timestamp=datetime.now(timezone.utc),
                metadata={"model": "claude-opus-4-5", "cwd": cwd},
            )
        )

        # Add steps
        builder.handle(
            StepStartedEvent(
                step_id="step-1",
                run_id="run-1",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Add tool calls
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
                content="result",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Finish step and run
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )
        builder.handle(
            RunFinishedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )

        # Verify comprehensive summary
        assert mock_run_call.summary is not None
        assert mock_run_call.summary["turn_count"] == 1
        assert mock_run_call.summary["tool_call_count"] == 1
        assert mock_run_call.summary["model"] == "claude-opus-4-5"

    def test_run_metadata_cleanup(self):
        """Test that run metadata is cleaned up after run finishes."""
        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock(id="call")

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Start run
        builder.handle(
            RunStartedEvent(
                run_id="run-1",
                timestamp=datetime.now(timezone.utc),
                metadata={"model": "claude-sonnet-4"},
            )
        )

        # Verify metadata is stored
        assert "run-1" in builder._run_metadata
        assert "run-1" in builder._run_step_count
        assert "run-1" in builder._run_tool_count

        # Finish run
        builder.handle(
            RunFinishedEvent(run_id="run-1", timestamp=datetime.now(timezone.utc))
        )

        # Verify cleanup
        assert "run-1" not in builder._run_metadata
        assert "run-1" not in builder._run_step_count
        assert "run-1" not in builder._run_tool_count


class TestQAContextTracking:
    """Test Q&A context tracking for question/answer flows."""

    def test_pending_question_detected_from_text(self):
        """Test that pending question is detected from assistant text ending with '?'."""
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

        # Add assistant message that ends with a question
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
                delta="I found two approaches. Which one would you prefer?",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Finish step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Verify pending question was detected and stored
        assert builder._pending_question is not None
        assert "Which one would you prefer?" in builder._pending_question

        # Verify output includes pending_question
        mock_client.finish_call.assert_called_once()
        call_args = mock_client.finish_call.call_args
        output = call_args[1]["output"]
        assert "pending_question" in output

    def test_explicit_pending_question_from_event(self):
        """Test that explicit pending_question from StepFinishedEvent is used."""
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

        # Finish step with explicit pending question
        builder.handle(
            StepFinishedEvent(
                step_id="step-1",
                timestamp=datetime.now(timezone.utc),
                pending_question="Should I proceed with this approach?",
            )
        )

        # Verify pending question was stored
        assert builder._pending_question == "Should I proceed with this approach?"

    def test_qa_context_added_to_next_step(self):
        """Test that pending question is added as context to next step's inputs."""
        mock_client = MagicMock()
        mock_step1_call = MagicMock(id="step-1-call")
        mock_step2_call = MagicMock(id="step-2-call")
        mock_client.create_call.side_effect = [
            MagicMock(id="run-call"),
            mock_step1_call,
            mock_step2_call,
        ]

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Setup run and first step
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

        # Add assistant message with question
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
                delta="Which approach should I use?",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # Finish first step
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Start second step with user response
        builder.handle(
            StepStartedEvent(
                step_id="step-2",
                run_id="run-1",
                timestamp=datetime.now(timezone.utc),
                metadata={"user_message": "Use the first approach"},
            )
        )

        # Verify that step 2 was created with Q&A context
        # The third create_call should be step-2 (after run and step-1)
        assert len(mock_client.create_call.call_args_list) >= 3
        step2_create_call = mock_client.create_call.call_args_list[2]

        inputs = step2_create_call[1]["inputs"]
        assert "messages" in inputs
        assert len(inputs["messages"]) == 2
        assert inputs["messages"][0]["role"] == "assistant"
        assert "Which approach should I use?" in inputs["messages"][0]["content"]
        assert inputs["messages"][1]["role"] == "user"
        assert inputs["messages"][1]["content"] == "Use the first approach"
        assert "in_response_to" in inputs
        assert "Which approach should I use?" in inputs["in_response_to"]

    def test_pending_question_cleared_when_no_question(self):
        """Test that pending question is cleared when step doesn't end with question."""
        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock(id="call")

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Setup run and step with question
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
                delta="Should I proceed?",
                timestamp=datetime.now(timezone.utc),
            )
        )

        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        # Verify question was stored
        assert builder._pending_question is not None

        # Second step without question
        builder.handle(
            StepStartedEvent(
                step_id="step-2",
                run_id="run-1",
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
            TextMessageContentEvent(
                message_id="msg-2",
                delta="Task completed successfully.",
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            StepFinishedEvent(step_id="step-2", timestamp=datetime.now(timezone.utc))
        )

        # Verify pending question was cleared
        assert builder._pending_question is None

    def test_detect_question_method(self):
        """Test the _detect_question helper method."""
        mock_client = MagicMock()
        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        # Test question at end
        result = builder._detect_question("I analyzed the code. Should I proceed?")
        assert result == "Should I proceed?"

        # Test no question
        result = builder._detect_question("I completed the task successfully.")
        assert result is None

        # Test question in middle paragraph
        result = builder._detect_question(
            "I found two options.\n\nOption 1 is faster. Option 2 is safer. Which do you prefer?"
        )
        assert result == "Which do you prefer?"

        # Test multiple sentences in last paragraph
        result = builder._detect_question(
            "I analyzed the code. I found an issue. Should I fix it now?"
        )
        assert result == "Should I fix it now?"

        # Test empty text
        result = builder._detect_question("")
        assert result is None

        # Test None
        result = builder._detect_question(None)
        assert result is None

    def test_qa_flow_with_multiple_steps(self):
        """Test complete Q&A flow across multiple steps."""
        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock(id="call")

        builder = AgentTraceBuilder(
            weave_client=mock_client,
            agent_name="Claude Code",
        )

        from weave.integrations.ag_ui.events import TextMessageStartEvent

        # Step 1: Assistant asks a question
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
                delta="I found two bugs. Which should I fix first?",
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            StepFinishedEvent(step_id="step-1", timestamp=datetime.now(timezone.utc))
        )

        assert builder._pending_question is not None

        # Step 2: User responds, assistant continues
        builder.handle(
            StepStartedEvent(
                step_id="step-2",
                run_id="run-1",
                timestamp=datetime.now(timezone.utc),
                metadata={"user_message": "Fix the first bug"},
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
            TextMessageContentEvent(
                message_id="msg-2",
                delta="I'll fix the first bug now.",
                timestamp=datetime.now(timezone.utc),
            )
        )
        builder.handle(
            StepFinishedEvent(step_id="step-2", timestamp=datetime.now(timezone.utc))
        )

        # Pending question should be cleared after non-question response
        assert builder._pending_question is None

        # Verify step 2 had Q&A context
        step2_calls = [
            c
            for c in mock_client.create_call.call_args_list
            if c[1].get("inputs", {}).get("messages")
        ]
        assert len(step2_calls) >= 1
        step2_inputs = step2_calls[0][1]["inputs"]
        assert "messages" in step2_inputs
        assert step2_inputs["messages"][0]["role"] == "assistant"
        assert "Which should I fix first?" in step2_inputs["messages"][0]["content"]
