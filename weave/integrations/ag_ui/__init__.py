"""AG-UI Protocol Integration for Weave

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
    # Union type
    AgentEvent,
    FileSnapshotEvent,
    RunErrorEvent,
    RunFinishedEvent,
    # Lifecycle events
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    # Message events
    TextMessageStartEvent,
    ThinkingContentEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    # Tool events
    ToolCallStartEvent,
    # Tracing extensions
    UsageRecordedEvent,
)
from weave.integrations.ag_ui.parser import AgentEventParser
from weave.integrations.ag_ui.secret_scanner import SecretScanner

__all__ = [
    "AgentEvent",
    "AgentEventParser",
    "FileSnapshotEvent",
    "RunErrorEvent",
    "RunFinishedEvent",
    "RunStartedEvent",
    "SecretScanner",
    "StepFinishedEvent",
    "StepStartedEvent",
    "TextMessageContentEvent",
    "TextMessageEndEvent",
    "TextMessageStartEvent",
    "ThinkingContentEvent",
    "ToolCallArgsEvent",
    "ToolCallEndEvent",
    "ToolCallResultEvent",
    "ToolCallStartEvent",
    "UsageRecordedEvent",
]
