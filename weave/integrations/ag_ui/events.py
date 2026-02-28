"""AG-UI Protocol Event Types for Weave

Event types inspired by the AG-UI protocol for standardizing agentic tool communication.
Extended with tracing-specific events for observability.

Copied from: https://github.com/ag-ui-protocol/ag-ui
Reference commit: (initial implementation based on spec as of 2025-01-20)

These types are copied rather than imported to avoid an external dependency.
If AG-UI gains wider adoption, consider switching to the official SDK.

References:
- AG-UI Protocol: https://docs.ag-ui.com/
- AG-UI Events: https://docs.ag-ui.com/concepts/events
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

# ─────────────────────────────────────────────────────────────────────────────
# Base Event
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class BaseEvent:
    """Base class for all AG-UI events."""

    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict, kw_only=True)


# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle Events
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RunStartedEvent:
    """Marks the start of an agent run (session).

    Maps to: Session start in claude_plugin
    """

    run_id: str
    timestamp: datetime
    thread_id: str | None = None  # For grouping related runs
    parent_run_id: str | None = None  # For subagent/nested runs
    input: str | None = None  # Initial prompt
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunFinishedEvent:
    """Marks successful completion of an agent run.

    Maps to: Session end in claude_plugin
    """

    run_id: str
    timestamp: datetime
    result: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunErrorEvent:
    """Signals an error during agent execution.

    Maps to: Session error/crash in claude_plugin
    """

    run_id: str
    message: str
    timestamp: datetime
    code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Step Events (Turns, Q&A flows, etc.)
# ─────────────────────────────────────────────────────────────────────────────

StepType = Literal["turn", "qa_flow", "plan_mode", "skill", "other"]


@dataclass
class StepStartedEvent:
    """Marks the start of a step within a run.

    Steps can represent:
    - turn: A conversation turn (user prompt → assistant response)
    - qa_flow: An interactive Q&A sequence
    - plan_mode: Planning/design phase
    - skill: Skill execution
    - other: Custom step type

    Maps to: Turn start in claude_plugin
    """

    step_id: str
    run_id: str
    timestamp: datetime
    step_type: StepType = "turn"
    step_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepFinishedEvent:
    """Marks completion of a step.

    Maps to: Turn end in claude_plugin
    """

    step_id: str
    timestamp: datetime
    pending_question: str | None = None  # If step ends with a question to user
    metadata: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Message Events
# ─────────────────────────────────────────────────────────────────────────────

MessageRole = Literal["user", "assistant", "system"]


@dataclass
class TextMessageStartEvent:
    """Initializes a new text message.

    Maps to: Message start in claude_plugin
    """

    message_id: str
    role: MessageRole
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TextMessageContentEvent:
    """Delivers a chunk of message content (for streaming).

    Maps to: Message content in claude_plugin
    """

    message_id: str
    delta: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TextMessageEndEvent:
    """Marks completion of a message.

    Maps to: Message end in claude_plugin
    """

    message_id: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Tool Call Events
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ToolCallStartEvent:
    """Marks the start of a tool invocation.

    Maps to: tool_use in claude_plugin
    """

    tool_call_id: str
    tool_name: str
    timestamp: datetime
    parent_message_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallArgsEvent:
    """Provides tool call arguments.

    For streaming, this may be called multiple times with partial args.
    For batch, this is called once with complete args.

    Maps to: tool_use input in claude_plugin
    """

    tool_call_id: str
    args: dict[str, Any]
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallEndEvent:
    """Marks that tool arguments are complete (tool is executing).

    Maps to: tool execution start in claude_plugin
    """

    tool_call_id: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallResultEvent:
    """Delivers tool execution result.

    Maps to: tool_result in claude_plugin
    """

    tool_call_id: str
    timestamp: datetime
    content: str | None = None
    is_error: bool = False
    duration_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Tracing Extensions (not in AG-UI spec)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class UsageRecordedEvent:
    """Records token usage for a message.

    This is a Weave tracing extension, not part of the AG-UI spec.
    """

    message_id: str
    timestamp: datetime
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_input_tokens(self) -> int:
        """Total input tokens including cache."""
        return self.input_tokens + self.cache_read_tokens + self.cache_creation_tokens

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)."""
        return self.total_input_tokens + self.output_tokens


@dataclass
class FileSnapshotEvent(BaseEvent):
    """Records a file snapshot for tracing.

    This is a Weave tracing extension, not part of the AG-UI spec.
    Used for file backup tracking in Edit operations.
    """

    file_path: str
    content: str | bytes | None = None
    mimetype: str = "text/plain"
    is_backup: bool = False
    linked_message_id: str | None = None


@dataclass
class ThinkingContentEvent:
    """Records extended thinking/reasoning content.

    This is a Weave tracing extension, not part of the AG-UI spec.
    Used for Claude's extended thinking blocks.
    """

    message_id: str
    content: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Event Union Type
# ─────────────────────────────────────────────────────────────────────────────

AgentEvent = (
    # Lifecycle
    RunStartedEvent
    | RunFinishedEvent
    | RunErrorEvent
    # Steps
    | StepStartedEvent
    | StepFinishedEvent
    # Messages
    | TextMessageStartEvent
    | TextMessageContentEvent
    | TextMessageEndEvent
    # Tool calls
    | ToolCallStartEvent
    | ToolCallArgsEvent
    | ToolCallEndEvent
    | ToolCallResultEvent
    # Tracing extensions
    | UsageRecordedEvent
    | FileSnapshotEvent
    | ThinkingContentEvent
)
