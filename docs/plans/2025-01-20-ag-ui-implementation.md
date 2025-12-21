# AG-UI Abstraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract generic interfaces from `claude_plugin` to support future agent integrations, organized as stacked branches.

**Architecture:** Three-layer stack: (1) `ag_ui/` shared abstractions, (2) `claude_plugin/` core integration, (3) CLI commands. Each layer builds on the previous.

**Tech Stack:** Python 3.10+, Pydantic-style dataclasses, Protocol classes, Weave SDK

---

## Branch Strategy

We'll create three stacked branches from master:

```
master
  └── feature/ag-ui-base           # Layer 1: Shared ag_ui/ abstractions
        └── feature/claude-plugin-core   # Layer 2: Claude plugin integration
              └── feature/claude-plugin-cli    # Layer 3: CLI commands
```

**Current state:** `feature/claude-plugin-cli` has all changes. We'll reorganize into the stack.

---

## Phase 1: Branch Setup

### Task 1.1: Create Fresh Branch from Master

**Step 1: Stash current work and create base branch**

```bash
git stash push -m "WIP: before ag-ui reorganization"
git checkout master
git pull origin master
git checkout -b feature/ag-ui-base
```

**Step 2: Verify clean state**

```bash
git status
# Expected: On branch feature/ag-ui-base, nothing to commit
```

---

## Phase 2: Create ag_ui/ Shared Module (Layer 1)

### Task 2.1: Create ag_ui Module Structure

**Files:**
- Create: `weave/integrations/ag_ui/__init__.py`
- Create: `weave/integrations/ag_ui/events.py`
- Create: `weave/integrations/ag_ui/parser.py`

**Step 1: Create directory and __init__.py**

```bash
mkdir -p weave/integrations/ag_ui
```

```python
# weave/integrations/ag_ui/__init__.py
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
from weave.integrations.ag_ui.parser import AgentEventParser

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
    # Parser
    "AgentEventParser",
]
```

**Step 2: Commit structure**

```bash
git add weave/integrations/ag_ui/__init__.py
git commit -m "feat(ag-ui): create ag_ui module structure"
```

---

### Task 2.2: Create Event Types

**Files:**
- Create: `weave/integrations/ag_ui/events.py`
- Test: `tests/integrations/ag_ui/test_events.py`

**Step 1: Write the failing test**

```bash
mkdir -p tests/integrations/ag_ui
```

```python
# tests/integrations/ag_ui/test_events.py
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/integrations/ag_ui/test_events.py -v
# Expected: ModuleNotFoundError - weave.integrations.ag_ui.events not found
```

**Step 3: Write the implementation**

```python
# weave/integrations/ag_ui/events.py
"""
AG-UI Protocol Event Types for Weave

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
from typing import Any, Literal, Union


@dataclass
class BaseEvent:
    """Base class for all AG-UI events."""

    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle Events
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RunStartedEvent(BaseEvent):
    """Marks the start of an agent run (session).

    Maps to: Session start in claude_plugin
    """

    run_id: str
    thread_id: str | None = None  # For grouping related runs
    parent_run_id: str | None = None  # For subagent/nested runs
    input: str | None = None  # Initial prompt


@dataclass
class RunFinishedEvent(BaseEvent):
    """Marks successful completion of an agent run.

    Maps to: Session end in claude_plugin
    """

    run_id: str
    result: str | None = None


@dataclass
class RunErrorEvent(BaseEvent):
    """Signals an error during agent execution.

    Maps to: Session error/crash in claude_plugin
    """

    run_id: str
    message: str
    code: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Step Events (Turns, Q&A flows, etc.)
# ─────────────────────────────────────────────────────────────────────────────

StepType = Literal["turn", "qa_flow", "plan_mode", "skill", "other"]


@dataclass
class StepStartedEvent(BaseEvent):
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
    step_type: StepType = "turn"
    step_name: str | None = None


@dataclass
class StepFinishedEvent(BaseEvent):
    """Marks completion of a step.

    Maps to: Turn end in claude_plugin
    """

    step_id: str
    pending_question: str | None = None  # If step ends with a question to user


# ─────────────────────────────────────────────────────────────────────────────
# Message Events
# ─────────────────────────────────────────────────────────────────────────────

MessageRole = Literal["user", "assistant", "system"]


@dataclass
class TextMessageStartEvent(BaseEvent):
    """Initializes a new text message.

    Maps to: Message start in claude_plugin
    """

    message_id: str
    role: MessageRole


@dataclass
class TextMessageContentEvent(BaseEvent):
    """Delivers a chunk of message content (for streaming).

    Maps to: Message content in claude_plugin
    """

    message_id: str
    delta: str


@dataclass
class TextMessageEndEvent(BaseEvent):
    """Marks completion of a message.

    Maps to: Message end in claude_plugin
    """

    message_id: str


# ─────────────────────────────────────────────────────────────────────────────
# Tool Call Events
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ToolCallStartEvent(BaseEvent):
    """Marks the start of a tool invocation.

    Maps to: tool_use in claude_plugin
    """

    tool_call_id: str
    tool_name: str
    parent_message_id: str | None = None


@dataclass
class ToolCallArgsEvent(BaseEvent):
    """Provides tool call arguments.

    For streaming, this may be called multiple times with partial args.
    For batch, this is called once with complete args.

    Maps to: tool_use input in claude_plugin
    """

    tool_call_id: str
    args: dict[str, Any]


@dataclass
class ToolCallEndEvent(BaseEvent):
    """Marks that tool arguments are complete (tool is executing).

    Maps to: tool execution start in claude_plugin
    """

    tool_call_id: str


@dataclass
class ToolCallResultEvent(BaseEvent):
    """Delivers tool execution result.

    Maps to: tool_result in claude_plugin
    """

    tool_call_id: str
    content: str | None = None
    is_error: bool = False
    duration_ms: int | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Tracing Extensions (not in AG-UI spec)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class UsageRecordedEvent(BaseEvent):
    """Records token usage for a message.

    This is a Weave tracing extension, not part of the AG-UI spec.
    """

    message_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    model: str | None = None

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
    content: str | None = None
    backup_path: str | None = None
    linked_message_id: str | None = None


@dataclass
class ThinkingContentEvent(BaseEvent):
    """Records extended thinking/reasoning content.

    This is a Weave tracing extension, not part of the AG-UI spec.
    Used for Claude's extended thinking blocks.
    """

    message_id: str
    content: str


# ─────────────────────────────────────────────────────────────────────────────
# Event Union Type
# ─────────────────────────────────────────────────────────────────────────────

AgentEvent = Union[
    # Lifecycle
    RunStartedEvent,
    RunFinishedEvent,
    RunErrorEvent,
    # Steps
    StepStartedEvent,
    StepFinishedEvent,
    # Messages
    TextMessageStartEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    # Tool calls
    ToolCallStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    # Tracing extensions
    UsageRecordedEvent,
    FileSnapshotEvent,
    ThinkingContentEvent,
]
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/integrations/ag_ui/test_events.py -v
# Expected: All tests pass
```

**Step 5: Commit**

```bash
git add weave/integrations/ag_ui/events.py tests/integrations/ag_ui/
git commit -m "feat(ag-ui): add event types based on AG-UI protocol"
```

---

### Task 2.3: Create Parser Protocol

**Files:**
- Create: `weave/integrations/ag_ui/parser.py`
- Test: `tests/integrations/ag_ui/test_parser.py`

**Step 1: Write the failing test**

```python
# tests/integrations/ag_ui/test_parser.py
"""Tests for AgentEventParser protocol."""

from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

import pytest

from weave.integrations.ag_ui.events import AgentEvent, RunStartedEvent
from weave.integrations.ag_ui.parser import AgentEventParser


class TestParserProtocol:
    def test_protocol_is_runtime_checkable(self):
        """Parser protocol should be runtime checkable."""
        assert hasattr(AgentEventParser, "__protocol_attrs__") or isinstance(
            AgentEventParser, type
        )

    def test_mock_parser_implements_protocol(self):
        """A mock parser should satisfy the protocol."""

        class MockParser:
            @property
            def agent_name(self) -> str:
                return "Mock Agent"

            def parse(
                self, source: Path, *, redact_secrets: bool = True
            ) -> Iterator[AgentEvent]:
                yield RunStartedEvent(
                    run_id="test", timestamp=datetime.now(timezone.utc)
                )

            async def parse_stream(
                self, source: Path, from_line: int = 0, *, redact_secrets: bool = True
            ) -> AsyncIterator[AgentEvent]:
                yield RunStartedEvent(
                    run_id="test", timestamp=datetime.now(timezone.utc)
                )

        parser = MockParser()
        assert parser.agent_name == "Mock Agent"

        # Test batch parsing
        events = list(parser.parse(Path("/fake/path")))
        assert len(events) == 1
        assert isinstance(events[0], RunStartedEvent)


class TestParserSecretRedaction:
    def test_redact_secrets_parameter_exists(self):
        """Parser should accept redact_secrets parameter."""

        class MockParser:
            @property
            def agent_name(self) -> str:
                return "Mock"

            def parse(
                self, source: Path, *, redact_secrets: bool = True
            ) -> Iterator[AgentEvent]:
                if redact_secrets:
                    yield RunStartedEvent(
                        run_id="redacted", timestamp=datetime.now(timezone.utc)
                    )
                else:
                    yield RunStartedEvent(
                        run_id="not-redacted", timestamp=datetime.now(timezone.utc)
                    )

            async def parse_stream(
                self, source: Path, from_line: int = 0, *, redact_secrets: bool = True
            ) -> AsyncIterator[AgentEvent]:
                yield RunStartedEvent(
                    run_id="test", timestamp=datetime.now(timezone.utc)
                )

        parser = MockParser()

        # With redaction (default)
        events = list(parser.parse(Path("/fake")))
        assert events[0].run_id == "redacted"

        # Without redaction
        events = list(parser.parse(Path("/fake"), redact_secrets=False))
        assert events[0].run_id == "not-redacted"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/integrations/ag_ui/test_parser.py -v
# Expected: ModuleNotFoundError - weave.integrations.ag_ui.parser not found
```

**Step 3: Write the implementation**

```python
# weave/integrations/ag_ui/parser.py
"""
Parser Protocol for Agent Event Streams

Defines the interface that agent-specific parsers must implement.
Each agentic tool (Claude Code, Gemini CLI, Codex CLI) provides
its own parser that converts native log formats to AG-UI events.
"""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Protocol, runtime_checkable

from weave.integrations.ag_ui.events import AgentEvent


@runtime_checkable
class AgentEventParser(Protocol):
    """Protocol for parsing agent session logs into AG-UI events.

    Implementations:
    - ClaudeParser: Claude Code JSONL files
    - GeminiParser: Google Gemini CLI logs (future)
    - CodexParser: OpenAI Codex CLI logs (future)

    Example usage:

        parser = ClaudeParser()

        # Batch import of historic session
        for event in parser.parse(session_path):
            trace_builder.handle(event)

        # Real-time tailing for live session
        async for event in parser.parse_stream(session_path, from_line=100):
            trace_builder.handle(event)
    """

    @property
    def agent_name(self) -> str:
        """Human-readable agent name.

        Examples: 'Claude Code', 'Gemini CLI', 'Codex CLI'
        """
        ...

    def parse(
        self,
        source: Path,
        *,
        redact_secrets: bool = True,
    ) -> Iterator[AgentEvent]:
        """Parse a complete session file, yielding events in order.

        Used for batch import of historical sessions.

        Args:
            source: Path to the session file (e.g., JSONL transcript)
            redact_secrets: If True, redact detected secrets from event content.
                           Defaults to True for safety.

        Yields:
            AgentEvent instances in chronological order
        """
        ...

    async def parse_stream(
        self,
        source: Path,
        from_line: int = 0,
        *,
        redact_secrets: bool = True,
    ) -> AsyncIterator[AgentEvent]:
        """Parse a session file incrementally, yielding new events.

        Used for real-time tailing during live sessions.
        Resumes from `from_line` for daemon restarts.

        Args:
            source: Path to the session file
            from_line: Line number to resume from (0-indexed)
            redact_secrets: If True, redact detected secrets from event content

        Yields:
            AgentEvent instances as they become available
        """
        ...
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/integrations/ag_ui/test_parser.py -v
# Expected: All tests pass
```

**Step 5: Commit**

```bash
git add weave/integrations/ag_ui/parser.py tests/integrations/ag_ui/test_parser.py
git commit -m "feat(ag-ui): add AgentEventParser protocol"
```

---

### Task 2.4: Create Tool Registry Structure

**Files:**
- Create: `weave/integrations/ag_ui/tools/__init__.py`
- Create: `weave/integrations/ag_ui/tools/base.py`
- Create: `weave/integrations/ag_ui/tools/claude.py`
- Test: `tests/integrations/ag_ui/test_tools.py`

**Step 1: Write the failing test**

```python
# tests/integrations/ag_ui/test_tools.py
"""Tests for agent-specific tool registries."""

import pytest

from weave.integrations.ag_ui.tools import get_tool_registry
from weave.integrations.ag_ui.tools.claude import CLAUDE_TOOL_REGISTRY


class TestToolRegistry:
    def test_get_claude_registry(self):
        registry = get_tool_registry("Claude Code")
        assert registry is not None
        assert "Task" in registry
        assert "Edit" in registry

    def test_get_unknown_registry(self):
        registry = get_tool_registry("Unknown Agent")
        assert registry == {}  # Empty registry for unknown agents

    def test_claude_task_spawns_subagent(self):
        registry = get_tool_registry("Claude Code")
        task_config = registry.get("Task", {})
        assert task_config.get("spawns_subagent") is True

    def test_claude_edit_has_diff_view(self):
        registry = get_tool_registry("Claude Code")
        edit_config = registry.get("Edit", {})
        assert edit_config.get("has_diff_view") is True

    def test_claude_ask_user_question_is_qa_flow(self):
        registry = get_tool_registry("Claude Code")
        ask_config = registry.get("AskUserQuestion", {})
        assert ask_config.get("is_qa_flow") is True


class TestClaudeToolRegistry:
    def test_registry_has_expected_tools(self):
        expected_tools = [
            "Task",
            "Edit",
            "Write",
            "Read",
            "Bash",
            "Glob",
            "Grep",
            "TodoWrite",
            "Skill",
            "AskUserQuestion",
            "WebFetch",
            "WebSearch",
        ]
        for tool in expected_tools:
            assert tool in CLAUDE_TOOL_REGISTRY, f"Missing tool: {tool}"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/integrations/ag_ui/test_tools.py -v
# Expected: ModuleNotFoundError
```

**Step 3: Write the implementation**

```python
# weave/integrations/ag_ui/tools/__init__.py
"""
Agent-Specific Tool Registries

Each agentic tool (Claude, Gemini, Codex) has its own set of tools
with specific behaviors. This module provides registries that map
tool names to their configuration.
"""

from typing import Any

from weave.integrations.ag_ui.tools.claude import CLAUDE_TOOL_REGISTRY

# Map agent names to their tool registries
_REGISTRIES: dict[str, dict[str, dict[str, Any]]] = {
    "Claude Code": CLAUDE_TOOL_REGISTRY,
    # Future:
    # "Gemini CLI": GEMINI_TOOL_REGISTRY,
    # "Codex CLI": CODEX_TOOL_REGISTRY,
}


def get_tool_registry(agent_name: str) -> dict[str, dict[str, Any]]:
    """Get the tool registry for a specific agent.

    Args:
        agent_name: The agent name (e.g., "Claude Code")

    Returns:
        Dict mapping tool names to their configuration.
        Returns empty dict for unknown agents.
    """
    return _REGISTRIES.get(agent_name, {})
```

```python
# weave/integrations/ag_ui/tools/base.py
"""
Base types for tool configuration.

Tool configurations describe special behaviors that tools exhibit,
which the trace builder uses to create appropriate traces and views.
"""

from typing import TypedDict


class ToolConfig(TypedDict, total=False):
    """Configuration for a tool's special behaviors.

    All fields are optional - only specify what applies to the tool.
    """

    # Subagent spawning
    spawns_subagent: bool  # Tool spawns a nested agent run
    subagent_id_field: str  # Path to agent ID in metadata (e.g., "metadata.agentId")

    # Views
    has_diff_view: bool  # Tool results should show file diffs
    has_custom_view: bool  # Tool has a custom HTML view

    # Flow control
    is_qa_flow: bool  # Tool initiates a Q&A flow with user

    # Metadata extraction
    metadata_fields: list[str]  # Fields to extract to event metadata
```

```python
# weave/integrations/ag_ui/tools/claude.py
"""
Claude Code Tool Registry

Defines special behaviors for Claude Code tools.
Used by the trace builder to create appropriate traces and views.
"""

from typing import Any

# Tool name → configuration
CLAUDE_TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    # Subagent tools
    "Task": {
        "spawns_subagent": True,
        "subagent_id_field": "metadata.agentId",
        "metadata_fields": ["subagent_type", "description"],
    },
    # File modification tools
    "Edit": {
        "has_diff_view": True,
    },
    "Write": {
        "has_diff_view": True,
    },
    "NotebookEdit": {
        "has_diff_view": True,
    },
    # File reading tools
    "Read": {},
    "Glob": {},
    "Grep": {},
    # Execution tools
    "Bash": {},
    # Planning/tracking tools
    "TodoWrite": {
        "has_custom_view": True,
    },
    "EnterPlanMode": {
        "metadata_fields": ["plan_type"],
    },
    "ExitPlanMode": {},
    # User interaction tools
    "AskUserQuestion": {
        "is_qa_flow": True,
        "metadata_fields": ["questions"],
    },
    # Skill tools
    "Skill": {
        "metadata_fields": ["skill_name", "args"],
    },
    # Web tools
    "WebFetch": {},
    "WebSearch": {},
    # LSP tools
    "LSP": {
        "metadata_fields": ["operation"],
    },
    # Background task tools
    "TaskOutput": {},
    "KillShell": {},
}
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/integrations/ag_ui/test_tools.py -v
# Expected: All tests pass
```

**Step 5: Commit**

```bash
git add weave/integrations/ag_ui/tools/ tests/integrations/ag_ui/test_tools.py
git commit -m "feat(ag-ui): add tool registries for agent-specific behaviors"
```

---

### Task 2.5: Move Shared Views to ag_ui

**Files:**
- Create: `weave/integrations/ag_ui/views/__init__.py`
- Move: `claude_plugin/views/diff_view.py` → `ag_ui/views/diff_view.py`
- Move: `claude_plugin/views/diff_utils.py` → `ag_ui/views/diff_utils.py`

**Step 1: Cherry-pick diff view files from feature/claude-plugin-cli**

```bash
# Get the diff view files from the old branch
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/views/diff_view.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/views/diff_utils.py
```

**Step 2: Create ag_ui/views structure and move files**

```bash
mkdir -p weave/integrations/ag_ui/views
mv weave/integrations/claude_plugin/views/diff_view.py weave/integrations/ag_ui/views/
mv weave/integrations/claude_plugin/views/diff_utils.py weave/integrations/ag_ui/views/
rm -rf weave/integrations/claude_plugin  # Clean up temp files
```

**Step 3: Create views __init__.py**

```python
# weave/integrations/ag_ui/views/__init__.py
"""
Shared visualization components for agent tracing.

Provides HTML generation for:
- File diffs (Edit tool)
- Todo lists (TodoWrite tool)
- Other tool-specific views
"""

from weave.integrations.ag_ui.views.diff_view import (
    generate_edit_diff_html,
    generate_todo_html,
    generate_turn_diff_html,
)
from weave.integrations.ag_ui.views.diff_utils import (
    apply_edit_operation,
    compute_unified_diff,
)

__all__ = [
    "generate_edit_diff_html",
    "generate_todo_html",
    "generate_turn_diff_html",
    "apply_edit_operation",
    "compute_unified_diff",
]
```

**Step 4: Update imports in diff_view.py and diff_utils.py**

Update any internal imports to use the new location.

**Step 5: Run existing tests**

```bash
pytest tests/integrations/ag_ui/ -v
# Expected: All tests pass
```

**Step 6: Commit**

```bash
git add weave/integrations/ag_ui/views/
git commit -m "feat(ag-ui): move shared diff views to ag_ui module"
```

---

### Task 2.6: Move Secret Scanner to ag_ui

**Files:**
- Move: `claude_plugin/secret_scanner.py` → `ag_ui/secret_scanner.py`

**Step 1: Cherry-pick secret scanner from feature/claude-plugin-cli**

```bash
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/secret_scanner.py
mv weave/integrations/claude_plugin/secret_scanner.py weave/integrations/ag_ui/
rm -rf weave/integrations/claude_plugin
```

**Step 2: Update __init__.py exports**

Add to `weave/integrations/ag_ui/__init__.py`:

```python
from weave.integrations.ag_ui.secret_scanner import SecretScanner

__all__ = [
    # ... existing exports ...
    "SecretScanner",
]
```

**Step 3: Cherry-pick and move tests**

```bash
git checkout feature/claude-plugin-cli -- tests/integrations/claude_plugin/test_secret_scanner.py
mv tests/integrations/claude_plugin/test_secret_scanner.py tests/integrations/ag_ui/
rm -rf tests/integrations/claude_plugin
```

**Step 4: Update test imports**

Update imports in `tests/integrations/ag_ui/test_secret_scanner.py` to use new path.

**Step 5: Run tests**

```bash
pytest tests/integrations/ag_ui/test_secret_scanner.py -v
# Expected: All tests pass
```

**Step 6: Commit**

```bash
git add weave/integrations/ag_ui/secret_scanner.py tests/integrations/ag_ui/test_secret_scanner.py
git commit -m "feat(ag-ui): move secret scanner to shared ag_ui module"
```

---

### Task 2.7: Create Trace Builder Skeleton

**Files:**
- Create: `weave/integrations/ag_ui/trace_builder.py`
- Test: `tests/integrations/ag_ui/test_trace_builder.py`

**Step 1: Write the failing test**

```python
# tests/integrations/ag_ui/test_trace_builder.py
"""Tests for AgentTraceBuilder."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from weave.integrations.ag_ui.events import (
    RunFinishedEvent,
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
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
        mock_client.create_call.return_value = MagicMock(id="call")

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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/integrations/ag_ui/test_trace_builder.py -v
# Expected: ModuleNotFoundError
```

**Step 3: Write the implementation**

```python
# weave/integrations/ag_ui/trace_builder.py
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
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/integrations/ag_ui/test_trace_builder.py -v
# Expected: All tests pass
```

**Step 5: Commit**

```bash
git add weave/integrations/ag_ui/trace_builder.py tests/integrations/ag_ui/test_trace_builder.py
git commit -m "feat(ag-ui): add trace builder skeleton"
```

---

### Task 2.8: Finalize Layer 1 and Create Stack Point

**Step 1: Run all ag_ui tests**

```bash
pytest tests/integrations/ag_ui/ -v
# Expected: All tests pass
```

**Step 2: Update __init__.py with all exports**

Ensure `weave/integrations/ag_ui/__init__.py` exports everything.

**Step 3: Final commit and tag**

```bash
git add -A
git commit -m "feat(ag-ui): complete ag_ui shared module (Layer 1)"
```

**Step 4: Push Layer 1 branch**

```bash
git push -u origin feature/ag-ui-base
```

---

## Phase 3: Claude Plugin Core (Layer 2)

### Task 3.1: Create Layer 2 Branch

**Step 1: Create branch from Layer 1**

```bash
git checkout -b feature/claude-plugin-core
```

---

### Task 3.2: Cherry-pick Core Claude Plugin Files

**Step 1: Cherry-pick core files from original branch**

```bash
# Core infrastructure
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/__init__.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/constants.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/utils.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/credentials.py

# Core runtime
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/core/__init__.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/core/daemon.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/core/hook.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/core/socket_client.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/core/state.py

# Session processing
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/session/__init__.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/session/session_parser.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/session/session_processor.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/session/session_importer.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/session/session_title.py

# Config (functions only, not CLI main)
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/config.py
```

**Step 2: Cherry-pick views that stay in claude_plugin**

```bash
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/views/__init__.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/views/cli_output.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/views/feedback.py
```

**Step 3: Commit core files**

```bash
git add weave/integrations/claude_plugin/
git commit -m "feat(claude-plugin): add core plugin infrastructure"
```

---

### Task 3.3: Update Imports to Use ag_ui

**Step 1: Update claude_plugin files to import from ag_ui**

Update files to use shared components:
- `from weave.integrations.ag_ui.views import generate_edit_diff_html`
- `from weave.integrations.ag_ui import SecretScanner`

**Step 2: Run tests**

```bash
pytest tests/integrations/claude_plugin/ -v
# Expected: Tests pass (after cherry-picking test files)
```

**Step 3: Commit import updates**

```bash
git add -A
git commit -m "refactor(claude-plugin): update imports to use ag_ui shared module"
```

---

### Task 3.4: Cherry-pick Tests

**Step 1: Cherry-pick test files**

```bash
git checkout feature/claude-plugin-cli -- tests/integrations/claude_plugin/
```

**Step 2: Update test imports**

**Step 3: Run tests**

```bash
pytest tests/integrations/claude_plugin/ -v
```

**Step 4: Commit**

```bash
git add tests/integrations/claude_plugin/
git commit -m "test(claude-plugin): add core plugin tests"
```

---

### Task 3.5: Finalize Layer 2

**Step 1: Run all tests**

```bash
pytest tests/integrations/ -v
```

**Step 2: Push Layer 2**

```bash
git push -u origin feature/claude-plugin-core
```

---

## Phase 4: CLI Commands (Layer 3)

### Task 4.1: Create Layer 3 Branch

**Step 1: Create branch from Layer 2**

```bash
git checkout -b feature/claude-plugin-cli-v2
```

---

### Task 4.2: Add CLI Components

**Step 1: Cherry-pick CLI files**

```bash
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/__main__.py
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/teleport.py
```

**Step 2: Commit**

```bash
git add weave/integrations/claude_plugin/__main__.py
git add weave/integrations/claude_plugin/teleport.py
git commit -m "feat(claude-plugin): add CLI commands (teleport, config)"
```

---

### Task 4.3: Add Documentation

**Step 1: Cherry-pick docs**

```bash
git checkout feature/claude-plugin-cli -- weave/integrations/claude_plugin/README.md
```

**Step 2: Commit**

```bash
git add weave/integrations/claude_plugin/README.md
git commit -m "docs(claude-plugin): add README documentation"
```

---

### Task 4.4: Finalize Layer 3

**Step 1: Run all tests**

```bash
pytest tests/integrations/ -v
```

**Step 2: Push Layer 3**

```bash
git push -u origin feature/claude-plugin-cli-v2
```

---

## Summary: Final Branch Structure

```
master
  └── feature/ag-ui-base              # ~200 lines: events, parser, tools, views, scanner
        └── feature/claude-plugin-core    # ~8000 lines: daemon, hook, session processing
              └── feature/claude-plugin-cli-v2   # ~800 lines: teleport, __main__, docs
```

**PR Strategy:**
1. PR `feature/ag-ui-base` → `master` (review shared abstractions)
2. PR `feature/claude-plugin-core` → `feature/ag-ui-base` (review core integration)
3. PR `feature/claude-plugin-cli-v2` → `feature/claude-plugin-core` (review CLI)

Or merge as single PR with clear commit history.
