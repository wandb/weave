"""Parser Protocol for Agent Event Streams

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
