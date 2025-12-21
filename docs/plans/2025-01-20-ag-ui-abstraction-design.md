# AG-UI Abstraction Layer Design

**Date:** 2025-01-20
**Status:** Draft
**Author:** Claude + vanpelt

## Overview

Extract generic interfaces from `weave/integrations/claude_plugin/` to support future integrations with other agentic coding tools (Google Gemini CLI, OpenAI Codex CLI), using the [AG-UI protocol](https://docs.ag-ui.com/) as a common vocabulary.

## Goals

1. Define a shared event vocabulary inspired by AG-UI for representing agent sessions
2. Create a parser protocol that each agent integration implements
3. Build a shared trace builder that converts events → Weave traces
4. Minimize disruption to existing `claude_plugin` functionality
5. Enable future integrations with minimal boilerplate

## Non-Goals

- Full AG-UI frontend integration (real-time streaming UI, generative UI)
- Breaking changes to existing `claude_plugin` public API
- Supporting non-CLI agent tools (e.g., API-based agents)

## Design Decisions

### 1. Hybrid AG-UI Approach

Use AG-UI's event vocabulary where it maps naturally, extend with tracing-specific events.

**AG-UI aligned:**
- `RunStarted` / `RunFinished` / `RunError` (session lifecycle)
- `StepStarted` / `StepFinished` (turn lifecycle)
- `TextMessageStart` / `TextMessageContent` / `TextMessageEnd`
- `ToolCallStart` / `ToolCallArgs` / `ToolCallEnd` / `ToolCallResult`

**Tracing extensions:**
- `UsageRecordedEvent` - token usage data
- `FileSnapshotEvent` - file backup/state capture
- `ThinkingContentEvent` - extended thinking blocks

### 2. Turn as Step Subtype

Conversation turns are modeled as Steps with `step_type: "turn"`. This preserves the semantic meaning of "conversation round-trip" while fitting into AG-UI's more general model.

Other step types: `"qa_flow"`, `"plan_mode"`, `"skill"`

### 3. Metadata over New Event Types

Instead of creating event types for every scenario, use metadata on existing events:

```python
StepStartedEvent(step_type="turn", metadata={"qa_flow": True})
StepFinishedEvent(pending_question="Which approach do you prefer?")
ToolCallStartEvent(tool_name="Skill", metadata={"skill_name": "commit"})
ToolCallResultEvent(metadata={"compaction_detected": True})
```

### 4. Event Stream Architecture

Parsers emit an ordered stream of events. A shared trace builder consumes events and produces Weave traces.

```
Claude JSONL ─► ClaudeParser ─┐
Gemini logs  ─► GeminiParser ─┼─► Event Stream ─► AgentTraceBuilder ─► Weave
Codex logs   ─► CodexParser  ─┘
```

### 5. Copy AG-UI Types (No Dependency)

Copy event types from the `ag-ui-protocol` Python SDK rather than taking a dependency. Include provenance in docstring.

Benefits:
- No external dependency to manage
- Full control over extensions
- Can swap in real SDK later if AG-UI gains traction

### 6. Iterator-Based Parser Interface

```python
class AgentEventParser(Protocol):
    def parse(self, source: Path) -> Iterator[AgentEvent]:
        """Batch: parse complete file."""

    async def parse_stream(self, source: Path, from_line: int = 0) -> AsyncIterator[AgentEvent]:
        """Real-time: tail file for new events."""
```

## File Structure

```
weave/integrations/
├── ag_ui/                          # Shared AG-UI abstractions
│   ├── __init__.py                 # Public exports
│   ├── events.py                   # Event types (from ag-ui-protocol)
│   ├── parser.py                   # AgentEventParser protocol
│   ├── trace_builder.py            # Events → Weave traces
│   ├── secret_scanner.py           # Moved from claude_plugin
│   ├── tools/                      # Agent-specific tool registries
│   │   ├── __init__.py
│   │   ├── claude.py               # Claude Code special tools
│   │   ├── gemini.py               # Gemini CLI special tools (future)
│   │   └── codex.py                # Codex CLI special tools (future)
│   └── views/                      # Shared view generation
│       ├── __init__.py
│       ├── diff_view.py            # Moved from claude_plugin
│       └── diff_utils.py           # Moved from claude_plugin
│
├── claude_plugin/                  # Claude Code specific
│   ├── parser.py                   # ClaudeParser(AgentEventParser)
│   ├── core/                       # Daemon/hook infrastructure
│   ├── session/                    # JSONL parsing (session_parser.py)
│   └── ...                         # teleport, credentials, etc.
│
├── gemini_plugin/                  # Future: Gemini CLI
│   └── parser.py                   # GeminiParser(AgentEventParser)
│
└── codex_plugin/                   # Future: Codex CLI
    └── parser.py                   # CodexParser(AgentEventParser)
```

## Component Details

### ag_ui/events.py

Event types copied from [ag-ui-protocol](https://github.com/ag-ui-protocol/ag-ui) Python SDK.

```python
"""
AG-UI Protocol Event Types

Copied from: https://github.com/ag-ui-protocol/ag-ui
Version: [commit hash]
Date: 2025-01-20

These types are copied rather than imported to avoid an external dependency.
If AG-UI gains wider adoption, consider switching to the official SDK.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

# ... event definitions
```

### ag_ui/parser.py

Protocol that each agent integration implements:

```python
class AgentEventParser(Protocol):
    @property
    def agent_name(self) -> str:
        """Human-readable name, e.g. 'Claude Code'"""
        ...

    def parse(self, source: Path) -> Iterator[AgentEvent]:
        """Parse complete session file for batch import."""
        ...

    async def parse_stream(
        self, source: Path, from_line: int = 0
    ) -> AsyncIterator[AgentEvent]:
        """Parse incrementally for real-time tailing."""
        ...
```

### ag_ui/trace_builder.py

Stateful consumer that builds Weave traces from events:

```python
class AgentTraceBuilder:
    def __init__(
        self,
        weave_client: weave.WeaveClient,
        on_tool_call: Callable[[ToolCallResultEvent, Call], None] | None = None,
    ):
        ...

    def handle(self, event: AgentEvent) -> None:
        """Process single event, updating trace state."""
        match event:
            case RunStartedEvent(): ...
            case ToolCallResultEvent(): ...
            # ...
```

Hook system (`on_tool_call`) allows integration-specific behavior (e.g., Claude's diff views).

## Shared vs. Integration-Specific

| Component | Shared (ag_ui/) | Claude-specific |
|-----------|-----------------|-----------------|
| Event types | ✓ | |
| Parser protocol | ✓ | |
| Trace builder | ✓ | |
| Diff views / HTML | ✓ | |
| Secret scanning | ✓ | |
| Tool registries | ✓ (per-agent files) | |
| JSONL parsing logic | | ✓ |
| Daemon/hook infrastructure | | ✓ |
| State management | | ✓ |
| Teleport | | ✓ |
| OAuth/credentials | | ✓ |

## Migration Plan

1. **Create `ag_ui/` module**
   - Copy AG-UI event types with provenance docstring
   - Define `AgentEventParser` protocol
   - Implement `AgentTraceBuilder`

2. **Move shared views**
   - Move `diff_view.py`, `diff_utils.py` to `ag_ui/views/`
   - Update imports in `claude_plugin`

3. **Create `ClaudeParser`**
   - Wrap existing `session_parser.py`
   - Emit AG-UI events from parsed `Session` objects

4. **Refactor `daemon.py`**
   - Replace direct `SessionProcessor` usage with `AgentTraceBuilder`
   - Feed events from `ClaudeParser.parse_stream()`

5. **Refactor `session_importer.py`**
   - Use `ClaudeParser.parse()` + `AgentTraceBuilder`

6. **Deprecate `session_processor.py`**
   - Remove once migration complete

## Future Work

- **Gemini CLI integration**: Implement `GeminiParser` once format is understood
- **Codex CLI integration**: Implement `CodexParser` once format is understood
- **Full AG-UI SDK**: Consider switching to official `ag-ui-protocol` package if widely adopted
- **AG-UI frontend**: Separate project to expose Weave traces as AG-UI events for frontend consumption

## Resolved Questions

### Secret Scanner Integration

The secret scanner should be integrated at the `AgentEventParser` level, conditionally applied:

```python
class AgentEventParser(Protocol):
    def parse(
        self,
        source: Path,
        redact_secrets: bool = True,  # Conditional secret scanning
    ) -> Iterator[AgentEvent]:
        ...
```

Each parser implementation calls the shared secret scanner on event content before emitting. This keeps the scanner in `ag_ui/` as shared infrastructure.

### Agent-Specific Tool Detection

Agent-specific tools are detected in `ag_ui/` but organized clearly by agent:

```python
# ag_ui/tools/__init__.py
from .claude import CLAUDE_SPECIAL_TOOLS
from .gemini import GEMINI_SPECIAL_TOOLS  # Future
from .codex import CODEX_SPECIAL_TOOLS    # Future

# ag_ui/tools/claude.py
CLAUDE_SPECIAL_TOOLS = {
    "Task": {"spawns_subagent": True, "subagent_id_field": "metadata.agentId"},
    "Skill": {"metadata_fields": ["skill_name"]},
    "AskUserQuestion": {"is_qa_flow": True},
    "TodoWrite": {"has_custom_view": True},
    "Edit": {"has_diff_view": True},
    # ...
}

# ag_ui/tools/gemini.py  (future)
GEMINI_SPECIAL_TOOLS = {
    # Gemini-specific tool handling
}
```

The `AgentTraceBuilder` uses these registries to apply agent-specific behavior:

```python
class AgentTraceBuilder:
    def __init__(self, agent_name: str, ...):
        self.tool_registry = get_tool_registry(agent_name)

    def _handle_tool_result(self, event: ToolCallResultEvent):
        tool_config = self.tool_registry.get(event.tool_name, {})
        if tool_config.get("has_diff_view"):
            # Generate diff view
        if tool_config.get("spawns_subagent"):
            # Track subagent
```

## Open Questions

1. Should we version the copied AG-UI types and track upstream changes?

## References

- [AG-UI Protocol Documentation](https://docs.ag-ui.com/)
- [AG-UI Python SDK](https://github.com/ag-ui-protocol/ag-ui)
- [Current claude_plugin architecture](../weave/integrations/claude_plugin/README.md)
