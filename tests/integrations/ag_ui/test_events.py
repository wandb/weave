"""Tests for AG-UI event types."""

from datetime import datetime, timezone

import pytest

from weave.integrations.ag_ui.events import (
    AgentEvent,
    FileSnapshotEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ThinkingContentEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
    UsageRecordedEvent,
)


class TestLifecycleEvents:
    def test_run_started_event(self):
        event = RunStartedEvent(
            run_id="run-123",
            thread_id="thread-456",
            timestamp=datetime(2025, 1, 20, 12, 0, 0, tzinfo=timezone.utc),
            input="Hello, help me with code",
        )
        assert event.run_id == "run-123"
        assert event.thread_id == "thread-456"
        assert event.parent_run_id is None
        assert event.input == "Hello, help me with code"

    def test_run_started_with_parent(self):
        event = RunStartedEvent(
            run_id="sub-run",
            parent_run_id="parent-run",
            timestamp=datetime.now(timezone.utc),
        )
        assert event.parent_run_id == "parent-run"

    def test_run_finished_event(self):
        event = RunFinishedEvent(
            run_id="run-123",
            timestamp=datetime.now(timezone.utc),
            result="Task completed successfully",
        )
        assert event.run_id == "run-123"
        assert event.result == "Task completed successfully"


class TestStepEvents:
    def test_step_started_turn(self):
        event = StepStartedEvent(
            step_id="step-1",
            run_id="run-123",
            step_type="turn",
            step_name="Turn 1: Implement feature",
            timestamp=datetime.now(timezone.utc),
        )
        assert event.step_type == "turn"
        assert event.step_name == "Turn 1: Implement feature"

    def test_step_started_qa_flow(self):
        event = StepStartedEvent(
            step_id="step-2",
            run_id="run-123",
            step_type="qa_flow",
            timestamp=datetime.now(timezone.utc),
            metadata={"question_tool_id": "tool-123"},
        )
        assert event.step_type == "qa_flow"
        assert event.metadata["question_tool_id"] == "tool-123"

    def test_step_finished_with_pending_question(self):
        event = StepFinishedEvent(
            step_id="step-1",
            timestamp=datetime.now(timezone.utc),
            pending_question="Which approach do you prefer?",
        )
        assert event.pending_question == "Which approach do you prefer?"


class TestToolEvents:
    def test_tool_call_lifecycle(self):
        start = ToolCallStartEvent(
            tool_call_id="tool-1",
            tool_name="Read",
            timestamp=datetime.now(timezone.utc),
            parent_message_id="msg-1",
        )
        args = ToolCallArgsEvent(
            tool_call_id="tool-1",
            args={"file_path": "/src/main.py"},
            timestamp=datetime.now(timezone.utc),
        )
        end = ToolCallEndEvent(
            tool_call_id="tool-1",
            timestamp=datetime.now(timezone.utc),
        )
        result = ToolCallResultEvent(
            tool_call_id="tool-1",
            content="def main(): pass",
            timestamp=datetime.now(timezone.utc),
            duration_ms=150,
        )

        assert start.tool_name == "Read"
        assert args.args["file_path"] == "/src/main.py"
        assert result.duration_ms == 150
        assert result.is_error is False

    def test_tool_call_error(self):
        result = ToolCallResultEvent(
            tool_call_id="tool-1",
            content="File not found",
            timestamp=datetime.now(timezone.utc),
            is_error=True,
        )
        assert result.is_error is True


class TestTracingExtensions:
    def test_usage_recorded(self):
        event = UsageRecordedEvent(
            message_id="msg-1",
            timestamp=datetime.now(timezone.utc),
            input_tokens=500,
            output_tokens=200,
            cache_read_tokens=100,
            cache_creation_tokens=50,
            model="claude-opus-4-20250514",
        )
        assert event.input_tokens == 500
        assert event.total_input_tokens == 650  # 500 + 100 + 50

    def test_file_snapshot(self):
        event = FileSnapshotEvent(
            file_path="/src/main.py",
            timestamp=datetime.now(timezone.utc),
            content="def main(): pass",
            linked_message_id="msg-1",
        )
        assert event.file_path == "/src/main.py"
        assert event.content == "def main(): pass"

    def test_thinking_content(self):
        event = ThinkingContentEvent(
            message_id="msg-1",
            timestamp=datetime.now(timezone.utc),
            content="Let me analyze this problem...",
        )
        assert "analyze" in event.content


class TestEventUnion:
    def test_agent_event_type_checking(self):
        """Verify AgentEvent union accepts all event types."""
        events: list[AgentEvent] = [
            RunStartedEvent(run_id="r1", timestamp=datetime.now(timezone.utc)),
            StepStartedEvent(
                step_id="s1", run_id="r1", timestamp=datetime.now(timezone.utc)
            ),
            ToolCallStartEvent(
                tool_call_id="t1", tool_name="Bash", timestamp=datetime.now(timezone.utc)
            ),
        ]
        assert len(events) == 3
