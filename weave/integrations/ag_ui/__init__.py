"""
AG-UI Protocol Integration for Weave

Provides shared abstractions for tracing agentic coding tools:
- Event types based on AG-UI protocol
- Parser protocol for agent-specific implementations
- Trace builder for converting events to Weave traces

Supported agents:
- Claude Code (claude_plugin)
- Google Gemini CLI (future)
- OpenAI Codex CLI (future)

References:
- AG-UI Protocol: https://docs.ag-ui.com/
"""

from weave.integrations.ag_ui.events import (
    # Lifecycle events
    RunStartedEvent,
    RunFinishedEvent,
    RunErrorEvent,
    StepStartedEvent,
    StepFinishedEvent,
    # Message events
    TextMessageStartEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    # Tool events
    ToolCallStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    # Tracing extensions
    UsageRecordedEvent,
    FileSnapshotEvent,
    ThinkingContentEvent,
    # Union type
    AgentEvent,
)

__all__ = [
    # Events
    "RunStartedEvent",
    "RunFinishedEvent",
    "RunErrorEvent",
    "StepStartedEvent",
    "StepFinishedEvent",
    "TextMessageStartEvent",
    "TextMessageContentEvent",
    "TextMessageEndEvent",
    "ToolCallStartEvent",
    "ToolCallArgsEvent",
    "ToolCallEndEvent",
    "ToolCallResultEvent",
    "UsageRecordedEvent",
    "FileSnapshotEvent",
    "ThinkingContentEvent",
    "AgentEvent",
]
