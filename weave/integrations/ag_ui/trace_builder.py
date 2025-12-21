"""
Trace Builder for Converting AG-UI Events to Weave Traces

Consumes AG-UI events and produces Weave traces with proper
parent-child relationships and metadata.
"""

from collections.abc import Callable
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
        self._current_step_id: str | None = None

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
            # Messages (currently not creating separate calls)
            case TextMessageStartEvent() | TextMessageContentEvent() | TextMessageEndEvent():
                pass  # Message content aggregated at step level
            # Tool calls
            case ToolCallStartEvent():
                self._handle_tool_start(event)
            case ToolCallArgsEvent():
                pass  # Args stored in pending_tools
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
        """Finish turn call."""
        call = self._step_calls.get(event.step_id)
        if call:
            output = {}
            if event.pending_question:
                output["pending_question"] = event.pending_question
            self.client.finish_call(call, output=output)

        if self._current_step_id == event.step_id:
            self._current_step_id = None

    def _handle_tool_start(self, event: ToolCallStartEvent) -> None:
        """Record pending tool call."""
        self._pending_tools[event.tool_call_id] = event

    def _handle_tool_result(self, event: ToolCallResultEvent) -> None:
        """Create tool call and invoke hook."""
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

        # Create tool call
        call = self.client.create_call(
            op=start_event.tool_name,
            inputs={},  # Would need ToolCallArgsEvent data
            parent=parent,
        )

        # Finish with result
        if event.is_error:
            self.client.finish_call(call, exception=Exception(event.content or "Error"))
        else:
            self.client.finish_call(call, output={"result": event.content})

        self._tool_calls[event.tool_call_id] = call

        # Invoke hook for integration-specific behavior
        if self.on_tool_call:
            self.on_tool_call(event, call)

    def _handle_usage(self, event: UsageRecordedEvent) -> None:
        """Record token usage (attached to message's step)."""
        # TODO: Attach usage to appropriate call
        pass

    def _handle_file_snapshot(self, event: FileSnapshotEvent) -> None:
        """Record file snapshot."""
        # TODO: Attach to appropriate call
        pass

    def _handle_thinking(self, event: ThinkingContentEvent) -> None:
        """Record thinking content."""
        # TODO: Attach to appropriate call
        pass
