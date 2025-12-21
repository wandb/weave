"""Tests for ClaudeParser - AG-UI event parser for Claude Code sessions."""

import json
import tempfile
from pathlib import Path

import pytest

from weave.integrations.ag_ui.events import (
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
from weave.integrations.claude_plugin.parser import ClaudeParser


def create_session_jsonl(messages: list[dict]) -> Path:
    """Create a temporary JSONL session file from message dicts."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for msg in messages:
        tmp.write(json.dumps(msg) + "\n")
    tmp.close()
    return Path(tmp.name)


class TestClaudeParser:
    """Test suite for ClaudeParser."""

    def test_implements_parser_protocol(self):
        """ClaudeParser should implement the AgentEventParser protocol."""
        from weave.integrations.ag_ui.parser import AgentEventParser

        parser = ClaudeParser()
        assert isinstance(parser, AgentEventParser)

    def test_agent_name_returns_claude_code(self):
        """Agent name should be 'Claude Code'."""
        parser = ClaudeParser()
        assert parser.agent_name == "Claude Code"

    def test_parse_empty_session(self):
        """Parsing an empty session should yield no events."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": "[system]",  # System message that gets filtered
                },
            }
        ])

        try:
            parser = ClaudeParser()
            events = list(parser.parse(session_jsonl))
            # Should still get run started/finished even with no turns
            assert len(events) == 2
            assert isinstance(events[0], RunStartedEvent)
            assert isinstance(events[1], RunFinishedEvent)
        finally:
            session_jsonl.unlink()

    def test_parse_simple_session_event_order(self):
        """Parse a simple session and verify event order."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "gitBranch": "main",
                "cwd": "/test",
                "message": {
                    "role": "user",
                    "content": "Hello Claude",
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {"type": "text", "text": "Hello! How can I help you?"}
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 20},
                },
            },
        ])

        try:
            parser = ClaudeParser()
            events = list(parser.parse(session_jsonl))

            # Expected event sequence:
            # 1. RunStartedEvent
            # 2. StepStartedEvent
            # 3. TextMessageStartEvent (user)
            # 4. TextMessageContentEvent (user)
            # 5. TextMessageEndEvent (user)
            # 6. TextMessageStartEvent (assistant)
            # 7. TextMessageContentEvent (assistant)
            # 8. TextMessageEndEvent (assistant)
            # 9. UsageRecordedEvent
            # 10. StepFinishedEvent
            # 11. RunFinishedEvent

            assert len(events) == 11
            assert isinstance(events[0], RunStartedEvent)
            assert events[0].run_id == "test-session"
            assert events[0].input == "Hello Claude"

            assert isinstance(events[1], StepStartedEvent)
            assert events[1].step_type == "turn"

            assert isinstance(events[2], TextMessageStartEvent)
            assert events[2].role == "user"

            assert isinstance(events[3], TextMessageContentEvent)
            assert events[3].delta == "Hello Claude"

            assert isinstance(events[4], TextMessageEndEvent)

            assert isinstance(events[5], TextMessageStartEvent)
            assert events[5].role == "assistant"

            assert isinstance(events[6], TextMessageContentEvent)
            assert events[6].delta == "Hello! How can I help you?"

            assert isinstance(events[7], TextMessageEndEvent)

            assert isinstance(events[8], UsageRecordedEvent)
            assert events[8].input_tokens == 100
            assert events[8].output_tokens == 20

            assert isinstance(events[9], StepFinishedEvent)

            assert isinstance(events[10], RunFinishedEvent)
            assert events[10].run_id == "test-session"

        finally:
            session_jsonl.unlink()

    def test_parse_tool_calls(self):
        """Parse a session with tool calls."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": "List files",
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Bash",
                            "input": {"command": "ls -la"},
                        }
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
            },
            {
                "type": "user",
                "uuid": "msg-3",
                "timestamp": "2025-01-01T10:00:02Z",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool-1",
                            "content": "file1.txt\nfile2.txt",
                        }
                    ],
                },
                "toolUseResult": {
                    "durationMs": 150,
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-4",
                "timestamp": "2025-01-01T10:00:03Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {"type": "text", "text": "I found 2 files."}
                    ],
                    "usage": {"input_tokens": 120, "output_tokens": 10},
                },
            },
        ])

        try:
            parser = ClaudeParser()
            events = list(parser.parse(session_jsonl))

            # Find tool call events
            tool_start_events = [e for e in events if isinstance(e, ToolCallStartEvent)]
            tool_args_events = [e for e in events if isinstance(e, ToolCallArgsEvent)]
            tool_end_events = [e for e in events if isinstance(e, ToolCallEndEvent)]
            tool_result_events = [e for e in events if isinstance(e, ToolCallResultEvent)]

            assert len(tool_start_events) == 1
            assert tool_start_events[0].tool_name == "Bash"
            assert tool_start_events[0].tool_call_id == "tool-1"

            assert len(tool_args_events) == 1
            assert tool_args_events[0].args == {"command": "ls -la"}

            assert len(tool_end_events) == 1
            assert tool_end_events[0].tool_call_id == "tool-1"

            assert len(tool_result_events) == 1
            assert tool_result_events[0].content == "file1.txt\nfile2.txt"
            assert tool_result_events[0].duration_ms == 150

        finally:
            session_jsonl.unlink()

    def test_parse_with_thinking_content(self):
        """Parse a session with thinking content."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": "What is 2 + 2?",
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-opus-4-5-20251101",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "Simple arithmetic.",
                        },
                        {"type": "text", "text": "4"},
                    ],
                    "usage": {"input_tokens": 50, "output_tokens": 5},
                },
            },
        ])

        try:
            parser = ClaudeParser()
            events = list(parser.parse(session_jsonl))

            thinking_events = [e for e in events if isinstance(e, ThinkingContentEvent)]
            assert len(thinking_events) == 1
            assert thinking_events[0].content == "Simple arithmetic."

        finally:
            session_jsonl.unlink()

    def test_parse_with_secret_redaction(self):
        """Parse a session with secret redaction enabled."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": "My API key is sk-proj-abc123def456ghi789",
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {"type": "text", "text": "I understand."}
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 10},
                },
            },
        ])

        try:
            parser = ClaudeParser()
            events = list(parser.parse(session_jsonl, redact_secrets=True))

            # Find user message content event
            user_content_events = [
                e for e in events
                if isinstance(e, TextMessageContentEvent)
                and "API key" in e.delta
            ]

            assert len(user_content_events) == 1
            # Secret should be redacted
            assert "sk-proj-abc123def456ghi789" not in user_content_events[0].delta
            assert "[REDACTED:" in user_content_events[0].delta

        finally:
            session_jsonl.unlink()

    def test_parse_without_secret_redaction(self):
        """Parse a session with secret redaction disabled."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": "My API key is sk-proj-abc123def456ghi789",
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {"type": "text", "text": "I understand."}
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 10},
                },
            },
        ])

        try:
            parser = ClaudeParser()
            events = list(parser.parse(session_jsonl, redact_secrets=False))

            # Find user message content event
            user_content_events = [
                e for e in events
                if isinstance(e, TextMessageContentEvent)
                and "API key" in e.delta
            ]

            assert len(user_content_events) == 1
            # Secret should NOT be redacted
            assert "sk-proj-abc123def456ghi789" in user_content_events[0].delta

        finally:
            session_jsonl.unlink()

    @pytest.mark.anyio
    async def test_parse_stream_basic(self):
        """Test async parse_stream method."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": "Hello",
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {"type": "text", "text": "Hi"}
                    ],
                    "usage": {"input_tokens": 50, "output_tokens": 5},
                },
            },
        ])

        try:
            parser = ClaudeParser()
            events = []
            async for event in parser.parse_stream(session_jsonl):
                events.append(event)

            # Should have same events as sync parse
            assert len(events) > 0
            assert isinstance(events[0], RunStartedEvent)
            assert isinstance(events[-1], RunFinishedEvent)

        finally:
            session_jsonl.unlink()

    def test_parse_multiple_turns(self):
        """Parse a session with multiple turns."""
        session_jsonl = create_session_jsonl([
            # Turn 1
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {
                    "role": "user",
                    "content": "First question",
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {"type": "text", "text": "First answer"}
                    ],
                    "usage": {"input_tokens": 50, "output_tokens": 10},
                },
            },
            # Turn 2
            {
                "type": "user",
                "uuid": "msg-3",
                "timestamp": "2025-01-01T10:00:02Z",
                "message": {
                    "role": "user",
                    "content": "Second question",
                },
            },
            {
                "type": "assistant",
                "uuid": "msg-4",
                "timestamp": "2025-01-01T10:00:03Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {"type": "text", "text": "Second answer"}
                    ],
                    "usage": {"input_tokens": 60, "output_tokens": 10},
                },
            },
        ])

        try:
            parser = ClaudeParser()
            events = list(parser.parse(session_jsonl))

            # Should have 2 StepStartedEvents and 2 StepFinishedEvents
            step_start_events = [e for e in events if isinstance(e, StepStartedEvent)]
            step_finish_events = [e for e in events if isinstance(e, StepFinishedEvent)]

            assert len(step_start_events) == 2
            assert len(step_finish_events) == 2

        finally:
            session_jsonl.unlink()
