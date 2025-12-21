"""ClaudeParser - AG-UI event parser for Claude Code sessions.

This module implements the AgentEventParser protocol for Claude Code JSONL
session files, converting them into standardized AG-UI events.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

from weave.integrations.ag_ui.events import (
    AgentEvent,
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
from weave.integrations.ag_ui.secret_scanner import SecretScanner
from weave.integrations.claude_plugin.session.session_parser import (
    Session,
    parse_session_file,
)

logger = logging.getLogger(__name__)


class ClaudeParser:
    """Parser for Claude Code JSONL sessions.

    Implements the AgentEventParser protocol, converting Claude Code session
    files into AG-UI events for standardized tracing and visualization.
    """

    @property
    def agent_name(self) -> str:
        """Return the agent name."""
        return "Claude Code"

    def parse(
        self,
        source: Path,
        *,
        redact_secrets: bool = True,
    ) -> Iterator[AgentEvent]:
        """Parse a complete session file, yielding events in order.

        Args:
            source: Path to the Claude Code JSONL session file
            redact_secrets: If True, redact detected secrets from event content

        Yields:
            AgentEvent instances in chronological order
        """
        # Parse the session file using existing parser
        session = parse_session_file(source)
        if session is None:
            logger.warning(f"Failed to parse session file: {source}")
            return

        # Initialize secret scanner if needed
        scanner: SecretScanner | None = None
        if redact_secrets:
            scanner = SecretScanner()

        # Yield events in order
        yield from self._generate_events(session, scanner)

    async def parse_stream(
        self,
        source: Path,
        from_line: int = 0,
        *,
        redact_secrets: bool = True,
    ) -> AsyncIterator[AgentEvent]:
        """Parse a session file incrementally, yielding new events.

        For now, this is a simple async wrapper around the sync parse method.
        In the future, this could be enhanced to support true incremental
        parsing and file watching.

        Args:
            source: Path to the session file
            from_line: Line number to resume from (0-indexed) - not yet implemented
            redact_secrets: If True, redact detected secrets from event content

        Yields:
            AgentEvent instances as they become available
        """
        # For now, just yield all events
        # TODO: Implement true incremental parsing with from_line support
        for event in self.parse(source, redact_secrets=redact_secrets):
            yield event

    def _generate_events(
        self,
        session: Session,
        scanner: SecretScanner | None,
    ) -> Iterator[AgentEvent]:
        """Generate AG-UI events from a parsed session.

        Args:
            session: Parsed Session object
            scanner: Optional SecretScanner for redacting secrets

        Yields:
            AgentEvent instances in chronological order
        """
        # Import here to get current time if needed
        from datetime import datetime, timezone

        # Generate RunStartedEvent
        started_at = session.started_at()
        if started_at is None:
            # For empty sessions, use current time
            started_at = datetime.now(timezone.utc)

        first_prompt = session.first_user_prompt()
        if scanner:
            first_prompt, _ = scanner.redact_text(first_prompt)

        yield RunStartedEvent(
            run_id=session.session_id,
            timestamp=started_at,
            thread_id=None,
            parent_run_id=None,
            input=first_prompt,
            metadata={
                "git_branch": session.git_branch,
                "cwd": session.cwd,
                "version": session.version,
                "filename": session.filename,
            },
        )

        # Generate events for each turn
        for turn_idx, turn in enumerate(session.turns):
            step_id = f"{session.session_id}-turn-{turn_idx}"

            # StepStartedEvent
            yield StepStartedEvent(
                step_id=step_id,
                run_id=session.session_id,
                timestamp=turn.started_at(),
                step_type="turn",
                step_name=f"Turn {turn_idx + 1}",
                metadata={},
            )

            # User message events
            user_message_id = turn.user_message.uuid or f"{step_id}-user"
            user_content = turn.user_message.content
            if scanner:
                user_content, _ = scanner.redact_text(user_content)

            yield TextMessageStartEvent(
                message_id=user_message_id,
                role="user",
                timestamp=turn.user_message.timestamp,
                metadata={},
            )

            yield TextMessageContentEvent(
                message_id=user_message_id,
                delta=user_content,
                timestamp=turn.user_message.timestamp,
                metadata={},
            )

            yield TextMessageEndEvent(
                message_id=user_message_id,
                timestamp=turn.user_message.timestamp,
                metadata={},
            )

            # Assistant messages and tool calls
            for assistant_msg in turn.assistant_messages:
                assistant_message_id = assistant_msg.uuid or f"{step_id}-assistant"

                # Tool calls (before assistant text response)
                for tool_call in assistant_msg.tool_calls:
                    # ToolCallStartEvent
                    yield ToolCallStartEvent(
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.name,
                        timestamp=tool_call.timestamp,
                        parent_message_id=assistant_message_id,
                        metadata={},
                    )

                    # ToolCallArgsEvent
                    tool_input = tool_call.input
                    if scanner:
                        # Redact secrets from tool input
                        tool_input_str = str(tool_input)
                        redacted_str, _ = scanner.redact_text(tool_input_str)
                        # Try to parse back to dict, but fall back to original if fails
                        try:
                            import json
                            tool_input = json.loads(redacted_str)
                        except (json.JSONDecodeError, ValueError):
                            # Keep original if redaction broke JSON structure
                            pass

                    yield ToolCallArgsEvent(
                        tool_call_id=tool_call.id,
                        args=tool_input,
                        timestamp=tool_call.timestamp,
                        metadata={},
                    )

                    # ToolCallEndEvent
                    yield ToolCallEndEvent(
                        tool_call_id=tool_call.id,
                        timestamp=tool_call.timestamp,
                        metadata={},
                    )

                    # ToolCallResultEvent
                    result_timestamp = tool_call.result_timestamp or tool_call.timestamp
                    result_content = tool_call.result or ""
                    if scanner:
                        result_content, _ = scanner.redact_text(result_content)

                    yield ToolCallResultEvent(
                        tool_call_id=tool_call.id,
                        timestamp=result_timestamp,
                        content=result_content,
                        is_error=tool_call.is_error,
                        duration_ms=tool_call.duration_ms(),
                        metadata={},
                    )

                # Assistant text message events
                assistant_text = assistant_msg.get_text()
                if scanner:
                    assistant_text, _ = scanner.redact_text(assistant_text)

                yield TextMessageStartEvent(
                    message_id=assistant_message_id,
                    role="assistant",
                    timestamp=assistant_msg.timestamp,
                    metadata={},
                )

                yield TextMessageContentEvent(
                    message_id=assistant_message_id,
                    delta=assistant_text,
                    timestamp=assistant_msg.timestamp,
                    metadata={},
                )

                yield TextMessageEndEvent(
                    message_id=assistant_message_id,
                    timestamp=assistant_msg.timestamp,
                    metadata={},
                )

                # UsageRecordedEvent
                if assistant_msg.usage:
                    yield UsageRecordedEvent(
                        message_id=assistant_message_id,
                        timestamp=assistant_msg.timestamp,
                        input_tokens=assistant_msg.usage.input_tokens,
                        output_tokens=assistant_msg.usage.output_tokens,
                        cache_read_tokens=assistant_msg.usage.cache_read_input_tokens,
                        cache_creation_tokens=assistant_msg.usage.cache_creation_input_tokens,
                        model=assistant_msg.model,
                        metadata={},
                    )

                # ThinkingContentEvent (if present)
                if assistant_msg.thinking_content:
                    thinking_content = assistant_msg.thinking_content
                    if scanner:
                        thinking_content, _ = scanner.redact_text(thinking_content)

                    yield ThinkingContentEvent(
                        message_id=assistant_message_id,
                        content=thinking_content,
                        timestamp=assistant_msg.timestamp,
                        metadata={},
                    )

            # StepFinishedEvent
            yield StepFinishedEvent(
                step_id=step_id,
                timestamp=turn.ended_at(),
                pending_question=None,
                metadata={},
            )

        # Generate RunFinishedEvent
        from datetime import datetime, timezone

        ended_at = session.ended_at()
        if ended_at is None:
            # For empty sessions, use current time
            ended_at = datetime.now(timezone.utc)

        yield RunFinishedEvent(
            run_id=session.session_id,
            timestamp=ended_at,
            result=None,
            metadata={
                "total_turns": len(session.turns),
                "total_tool_calls": session.total_tool_calls(),
                "primary_model": session.primary_model(),
            },
        )
