"""Tests for the v3 Session SDK API surface."""

from __future__ import annotations

from weave.trace.session import (
    ChatSpan,
    LogResult,
    Message,
    Reasoning,
    ToolSpan,
    Usage,
)


class TestMessage:
    def test_defaults(self) -> None:
        msg = Message(role="user")
        assert msg.role == "user"
        assert msg.content == ""
        assert msg.tool_call_id == ""
        assert msg.tool_name == ""

    def test_all_fields(self) -> None:
        msg = Message(
            role="tool",
            content="result",
            tool_call_id="tc_1",
            tool_name="get_weather",
        )
        assert msg.role == "tool"
        assert msg.content == "result"
        assert msg.tool_call_id == "tc_1"
        assert msg.tool_name == "get_weather"


class TestUsage:
    def test_defaults(self) -> None:
        u = Usage()
        assert u.input_tokens == 0
        assert u.output_tokens == 0
        assert u.reasoning_tokens == 0

    def test_set_fields(self) -> None:
        u = Usage(input_tokens=100, output_tokens=50, reasoning_tokens=20)
        assert u.input_tokens == 100
        assert u.output_tokens == 50
        assert u.reasoning_tokens == 20


class TestReasoning:
    def test_defaults(self) -> None:
        r = Reasoning()
        assert r.content == ""

    def test_set_content(self) -> None:
        r = Reasoning(content="thinking...")
        assert r.content == "thinking..."


class TestLogResult:
    def test_defaults(self) -> None:
        lr = LogResult()
        assert lr.session_id == ""
        assert lr.trace_ids == []
        assert lr.root_span_ids == []
        assert lr.span_count == 0


class TestChatSpan:
    def test_defaults(self) -> None:
        cs = ChatSpan()
        assert cs.model == ""
        assert cs.input_tokens == 0
        assert cs.output_tokens == 0

    def test_all_fields(self) -> None:
        cs = ChatSpan(
            model="gpt-4o",
            provider_name="openai",
            input_messages=[{"role": "user", "content": "hi"}],
            output_messages=[{"role": "assistant", "content": "hello"}],
            system_instructions=["Be helpful"],
            input_tokens=100,
            output_tokens=50,
            reasoning_tokens=20,
            reasoning_content="let me think",
            finish_reasons=["stop"],
        )
        assert cs.model == "gpt-4o"
        assert cs.provider_name == "openai"
        assert len(cs.input_messages) == 1
        assert cs.finish_reasons == ["stop"]


class TestToolSpan:
    def test_defaults(self) -> None:
        ts = ToolSpan()
        assert ts.name == ""
        assert ts.arguments == ""
        assert ts.result == ""
        assert ts.tool_call_id == ""

    def test_all_fields(self) -> None:
        ts = ToolSpan(
            name="get_weather",
            arguments='{"city":"Tokyo"}',
            result="75F",
            tool_call_id="tc_1",
        )
        assert ts.name == "get_weather"
        assert ts.tool_call_id == "tc_1"
