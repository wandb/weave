"""
Trace Builder for Converting AG-UI Events to Weave Traces

Consumes AG-UI events and produces Weave traces with proper
parent-child relationships and metadata.
"""

from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

from weave.integrations.ag_ui.events import (
    AgentEvent,
    FileSnapshotEvent,
    RunErrorEvent,
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
from weave.integrations.ag_ui.tools import get_tool_registry


class AgentTraceBuilder:
    """Converts AG-UI events into Weave traces.

    Shared across all agent integrations. Handles:
    - Run → Session call hierarchy
    - Step → Turn calls (nested under session)
    - ToolCall → Tool calls (nested under turn)
    - Usage aggregation
    - Parallel tool grouping

    Example:
        builder = AgentTraceBuilder(
            weave_client=weave.init("entity/project"),
            agent_name="Claude Code",
            on_tool_call=lambda event, call: generate_diff_view(event, call),
        )

        for event in parser.parse(session_path):
            builder.handle(event)
    """

    def __init__(
        self,
        weave_client: Any,  # weave.WeaveClient
        agent_name: str,
        on_tool_call: Callable[[ToolCallResultEvent, Any], None] | None = None,
    ):
        """Initialize the trace builder.

        Args:
            weave_client: Initialized Weave client
            agent_name: Agent name for tool registry lookup
            on_tool_call: Optional hook called after each tool result.
                         Use for integration-specific views (diffs, etc.)
        """
        self.client = weave_client
        self.agent_name = agent_name
        self.tool_registry = get_tool_registry(agent_name)
        self.on_tool_call = on_tool_call

        # State tracking
        self._run_calls: dict[str, Any] = {}  # run_id → Call
        self._step_calls: dict[str, Any] = {}  # step_id → Call
        self._tool_calls: dict[str, Any] = {}  # tool_call_id → Call
        self._pending_tools: dict[str, ToolCallStartEvent] = {}
        self._tool_args: dict[str, dict[str, Any]] = {}  # tool_call_id → args
        self._current_step_id: str | None = None

        # Usage tracking: message_id → usage event
        self._message_usage: dict[str, UsageRecordedEvent] = {}

        # Accumulated text content: message_id → content
        self._message_text: dict[str, str] = {}
        self._message_thinking: dict[str, str] = {}

        # Message to step mapping: message_id → step_id
        self._message_to_step: dict[str, str] = {}

    def handle(self, event: AgentEvent) -> None:
        """Process a single event, updating trace state.

        Args:
            event: AG-UI event to process
        """
        match event:
            # Lifecycle
            case RunStartedEvent():
                self._handle_run_started(event)
            case RunFinishedEvent():
                self._handle_run_finished(event)
            case RunErrorEvent():
                self._handle_run_error(event)
            # Steps
            case StepStartedEvent():
                self._handle_step_started(event)
            case StepFinishedEvent():
                self._handle_step_finished(event)
            # Messages
            case TextMessageStartEvent():
                self._handle_message_start(event)
            case TextMessageContentEvent():
                self._handle_text_content(event)
            case TextMessageEndEvent():
                pass  # Message end, content already accumulated
            # Tool calls
            case ToolCallStartEvent():
                self._handle_tool_start(event)
            case ToolCallArgsEvent():
                self._handle_tool_args(event)
            case ToolCallEndEvent():
                pass  # Execution started, wait for result
            case ToolCallResultEvent():
                self._handle_tool_result(event)
            # Tracing extensions
            case UsageRecordedEvent():
                self._handle_usage(event)
            case FileSnapshotEvent():
                self._handle_file_snapshot(event)
            case ThinkingContentEvent():
                self._handle_thinking(event)

    def process_events(self, events: Iterator[AgentEvent]) -> None:
        """Process a stream of events.

        Convenience method for processing multiple events in sequence.

        Args:
            events: Iterator of AG-UI events to process
        """
        for event in events:
            self.handle(event)

    def _handle_run_started(self, event: RunStartedEvent) -> None:
        """Create session call for run start."""
        parent = (
            self._run_calls.get(event.parent_run_id)
            if event.parent_run_id
            else None
        )

        call = self.client.create_call(
            op=f"{self.agent_name.lower().replace(' ', '_')}_session",
            inputs={"prompt": event.input} if event.input else {},
            parent=parent,
        )
        self._run_calls[event.run_id] = call

    def _handle_run_finished(self, event: RunFinishedEvent) -> None:
        """Finish session call."""
        call = self._run_calls.get(event.run_id)
        if call:
            self.client.finish_call(
                call,
                output={"result": event.result} if event.result else {},
            )

    def _handle_run_error(self, event: RunErrorEvent) -> None:
        """Finish session call with error."""
        call = self._run_calls.get(event.run_id)
        if call:
            self.client.finish_call(
                call,
                exception=Exception(event.message),
            )

    def _handle_step_started(self, event: StepStartedEvent) -> None:
        """Create turn call for step start."""
        parent = self._run_calls.get(event.run_id)
        if not parent:
            return

        call = self.client.create_call(
            op=f"{event.step_type}",
            inputs={"step_name": event.step_name} if event.step_name else {},
            parent=parent,
        )
        self._step_calls[event.step_id] = call
        self._current_step_id = event.step_id

    def _handle_step_finished(self, event: StepFinishedEvent) -> None:
        """Finish turn call with aggregated output and usage."""
        call = self._step_calls.get(event.step_id)
        if not call:
            if self._current_step_id == event.step_id:
                self._current_step_id = None
            return

        # Build output with aggregated content from all messages in this step
        output: dict[str, Any] = {}

        # Aggregate text and thinking from all messages in this step
        assistant_text_parts = []
        thinking_text_parts = []
        usage_by_model: dict[str, dict[str, int]] = {}

        for message_id, step_id in list(self._message_to_step.items()):
            if step_id != event.step_id:
                continue

            # Collect text content
            text = self._message_text.get(message_id, "")
            if text:
                assistant_text_parts.append(text)

            # Collect thinking content
            thinking = self._message_thinking.get(message_id, "")
            if thinking:
                thinking_text_parts.append(thinking)

            # Collect usage
            usage = self._message_usage.get(message_id)
            if usage and usage.model:
                if usage.model not in usage_by_model:
                    usage_by_model[usage.model] = {"input_tokens": 0, "output_tokens": 0}
                usage_by_model[usage.model]["input_tokens"] += usage.input_tokens or 0
                usage_by_model[usage.model]["output_tokens"] += usage.output_tokens or 0

        # Add aggregated content to output
        if assistant_text_parts:
            output["content"] = "".join(assistant_text_parts).strip()

        if thinking_text_parts:
            output["reasoning_content"] = "".join(thinking_text_parts).strip()

        # Add pending question if present
        if event.pending_question:
            output["pending_question"] = event.pending_question

        # Set usage summary
        if usage_by_model:
            call.summary = {"usage": usage_by_model}

        self.client.finish_call(call, output=output if output else None)

        # Clean up state for this step's messages
        for message_id, step_id in list(self._message_to_step.items()):
            if step_id == event.step_id:
                self._message_text.pop(message_id, None)
                self._message_thinking.pop(message_id, None)
                self._message_usage.pop(message_id, None)
                del self._message_to_step[message_id]

        if self._current_step_id == event.step_id:
            self._current_step_id = None

    def _handle_tool_start(self, event: ToolCallStartEvent) -> None:
        """Record pending tool call."""
        self._pending_tools[event.tool_call_id] = event

    def _handle_tool_args(self, event: ToolCallArgsEvent) -> None:
        """Store tool arguments for use when creating the call."""
        if event.args:
            self._tool_args[event.tool_call_id] = event.args

    def _handle_tool_result(self, event: ToolCallResultEvent) -> None:
        """Create tool call using log_tool_call and invoke hook."""
        start_event = self._pending_tools.pop(event.tool_call_id, None)
        if not start_event:
            return

        # Find parent (current step or run)
        parent = None
        if self._current_step_id:
            parent = self._step_calls.get(self._current_step_id)
        if not parent:
            # Fallback to finding any active run
            for run_call in self._run_calls.values():
                parent = run_call
                break

        if not parent:
            return

        # Get tool arguments
        tool_input = self._tool_args.pop(event.tool_call_id, {})

        # Calculate duration if we have timestamps
        duration_ms = None
        if hasattr(event, "timestamp") and hasattr(start_event, "timestamp"):
            duration = (event.timestamp - start_event.timestamp).total_seconds() * 1000
            duration_ms = int(duration)

        # Check if tool has diff view capability
        tool_config = self.tool_registry.get(start_event.tool_name, {})
        has_diff_view = tool_config.get("has_diff_view", False)

        # For Edit tool, check if we can generate diff view
        original_file = None
        structured_patch = None
        if has_diff_view and start_event.tool_name == "Edit":
            # Diff view generation will be handled by on_tool_call hook
            # which has access to the full event context
            pass

        # Import log_tool_call from claude_plugin/utils
        from weave.integrations.claude_plugin.utils import log_tool_call

        # Create and log the tool call
        call = log_tool_call(
            tool_name=start_event.tool_name,
            tool_input=tool_input,
            tool_output=event.content,
            tool_use_id=event.tool_call_id,
            duration_ms=duration_ms,
            parent=parent,
            started_at=start_event.timestamp if hasattr(start_event, "timestamp") else None,
            ended_at=event.timestamp if hasattr(event, "timestamp") else None,
            is_error=event.is_error,
            original_file=original_file,
            structured_patch=structured_patch,
        )

        self._tool_calls[event.tool_call_id] = call

        # Invoke hook for integration-specific behavior (e.g., diff view generation)
        if self.on_tool_call:
            self.on_tool_call(event, call)

    def _handle_message_start(self, event: TextMessageStartEvent) -> None:
        """Track message to step mapping."""
        if self._current_step_id:
            self._message_to_step[event.message_id] = self._current_step_id

    def _handle_text_content(self, event: TextMessageContentEvent) -> None:
        """Accumulate text content for a message."""
        # Accumulate content using delta field (streaming)
        if event.delta:
            current = self._message_text.get(event.message_id, "")
            self._message_text[event.message_id] = current + event.delta

    def _handle_usage(self, event: UsageRecordedEvent) -> None:
        """Record token usage for a message."""
        # Store usage by message_id
        self._message_usage[event.message_id] = event

    def _handle_file_snapshot(self, event: FileSnapshotEvent) -> None:
        """Record file snapshot.

        File snapshots are typically handled by the on_tool_call hook
        for generating diff views. This is a placeholder for future
        direct file snapshot handling.
        """
        # File snapshots are event-specific and may be used by hooks
        pass

    def _handle_thinking(self, event: ThinkingContentEvent) -> None:
        """Accumulate thinking/reasoning content for a message."""
        # Accumulate thinking content
        if event.content:
            current = self._message_thinking.get(event.message_id, "")
            self._message_thinking[event.message_id] = current + event.content
