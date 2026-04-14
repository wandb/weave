"""Unit tests for agent_chat_view.py — span → chat trajectory."""

import datetime

from weave.trace_server.agent_chat_view import (
    build_chat_messages,
    build_trace_chat,
)
from weave.trace_server.agent_types import AgentSpanSchema


def _span(
    span_id: str = "s1",
    parent_span_id: str = "",
    operation_name: str = "chat",
    agent_name: str = "",
    span_name: str = "test",
    input_messages: list | None = None,
    output_messages: list | None = None,
    system_instructions: list | None = None,
    tool_name: str = "",
    tool_call_arguments: str = "",
    tool_call_result: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
    reasoning_content: str = "",
    compaction_summary: str = "",
    compaction_items_before: int = 0,
    compaction_items_after: int = 0,
    status_code: str = "OK",
    started_at: datetime.datetime | None = None,
    **kwargs: object,
) -> AgentSpanSchema:
    return AgentSpanSchema(
        project_id="p1",
        trace_id="t1",
        span_id=span_id,
        parent_span_id=parent_span_id,
        operation_name=operation_name,
        agent_name=agent_name,
        span_name=span_name,
        input_messages=input_messages or [],
        output_messages=output_messages or [],
        system_instructions=system_instructions or [],
        tool_name=tool_name,
        tool_call_arguments=tool_call_arguments,
        tool_call_result=tool_call_result,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        reasoning_content=reasoning_content,
        compaction_summary=compaction_summary,
        compaction_items_before=compaction_items_before,
        compaction_items_after=compaction_items_after,
        status_code=status_code,
        started_at=started_at
        or datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        ended_at=datetime.datetime(2026, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc),
        **kwargs,
    )


# ============================================================================
# Empty / minimal
# ============================================================================


class TestEmpty:
    def test_empty_spans(self) -> None:
        assert build_chat_messages([]) == []

    def test_single_chat_span_no_messages(self) -> None:
        msgs = build_chat_messages([_span()])
        assert msgs == []


# ============================================================================
# User prompt extraction
# ============================================================================


class TestUserPrompt:
    def test_user_prompt_from_invoke_agent(self) -> None:
        spans = [
            _span(
                span_id="s1",
                operation_name="invoke_agent",
                agent_name="bot",
                input_messages=[{"role": "user", "content": "Hello"}],
            ),
        ]
        msgs = build_chat_messages(spans)
        assert msgs[0].type == "user_message"
        assert msgs[0].text == "Hello"

    def test_user_prompt_from_any_span(self) -> None:
        spans = [
            _span(
                span_id="s1",
                operation_name="chat",
                input_messages=[{"role": "user", "content": "Hi there"}],
            ),
        ]
        msgs = build_chat_messages(spans)
        assert msgs[0].type == "user_message"
        assert msgs[0].text == "Hi there"

    def test_prefers_invoke_agent(self) -> None:
        t1 = datetime.datetime(2026, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        t2 = datetime.datetime(2026, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)
        spans = [
            _span(
                span_id="s1",
                operation_name="chat",
                started_at=t1,
                input_messages=[{"role": "user", "content": "from chat"}],
            ),
            _span(
                span_id="s2",
                operation_name="invoke_agent",
                started_at=t2,
                input_messages=[{"role": "user", "content": "from agent"}],
            ),
        ]
        msgs = build_chat_messages(spans)
        assert msgs[0].text == "from agent"


# ============================================================================
# Agent message emission
# ============================================================================


class TestAgentMessage:
    def test_chat_leaf_emits_message(self) -> None:
        spans = [
            _span(
                operation_name="chat",
                output_messages=[{"role": "assistant", "content": "Hello!"}],
            ),
        ]
        msgs = build_chat_messages(spans)
        agent_msgs = [m for m in msgs if m.type == "agent_message"]
        assert len(agent_msgs) == 1
        assert agent_msgs[0].text == "Hello!"

    def test_invoke_agent_emits_start_and_message(self) -> None:
        spans = [
            _span(
                span_id="s1",
                operation_name="invoke_agent",
                agent_name="my-bot",
                output_messages=[{"role": "assistant", "content": "Done!"}],
                input_tokens=100,
                output_tokens=50,
            ),
        ]
        msgs = build_chat_messages(spans)
        types = [m.type for m in msgs]
        assert "agent_start" in types
        assert "agent_message" in types
        start = next(m for m in msgs if m.type == "agent_start")
        assert start.agent_name == "my-bot"

    def test_dedup_by_span_id(self) -> None:
        """Same span shouldn't emit agent_message twice."""
        spans = [
            _span(
                span_id="s1",
                operation_name="invoke_agent",
                agent_name="bot",
                output_messages=[{"role": "assistant", "content": "Hello"}],
            ),
        ]
        msgs = build_chat_messages(spans)
        agent_msgs = [m for m in msgs if m.type == "agent_message"]
        assert len(agent_msgs) == 1


# ============================================================================
# Tool calls
# ============================================================================


class TestToolCall:
    def test_execute_tool_emits_tool_call(self) -> None:
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                agent_name="bot",
            ),
            _span(
                span_id="tool1",
                parent_span_id="root",
                operation_name="execute_tool",
                tool_name="get_weather",
                tool_call_arguments='{"city": "Paris"}',
                tool_call_result='{"temp": 20}',
            ),
        ]
        msgs = build_chat_messages(spans)
        tool_msgs = [m for m in msgs if m.type == "tool_call"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_name == "get_weather"
        assert tool_msgs[0].tool_arguments == '{"city": "Paris"}'
        assert tool_msgs[0].tool_result == '{"temp": 20}'

    def test_noise_tools_filtered(self) -> None:
        spans = [
            _span(
                operation_name="execute_tool",
                tool_name="(merged tools)",
            ),
        ]
        msgs = build_chat_messages(spans)
        tool_msgs = [m for m in msgs if m.type == "tool_call"]
        assert len(tool_msgs) == 0


# ============================================================================
# Handoffs
# ============================================================================


class TestHandoff:
    def test_transfer_to_emits_handoff(self) -> None:
        spans = [
            _span(
                operation_name="execute_tool",
                tool_name="transfer_to_sales_agent",
            ),
        ]
        msgs = build_chat_messages(spans)
        handoffs = [m for m in msgs if m.type == "agent_handoff"]
        assert len(handoffs) == 1
        assert "sales_agent" in handoffs[0].text

    def test_handoff_operation(self) -> None:
        spans = [
            _span(
                operation_name="handoff",
                agent_name="router",
                span_name="agent_handoff sales",
            ),
        ]
        msgs = build_chat_messages(spans)
        handoffs = [m for m in msgs if m.type == "agent_handoff"]
        assert len(handoffs) == 1


# ============================================================================
# Context compaction
# ============================================================================


class TestCompaction:
    def test_compaction_emitted(self) -> None:
        spans = [
            _span(
                operation_name="invoke_agent",
                agent_name="bot",
                compaction_summary="Summarized 10 messages",
                compaction_items_before=10,
                compaction_items_after=3,
            ),
        ]
        msgs = build_chat_messages(spans)
        compact_msgs = [m for m in msgs if m.type == "context_compacted"]
        assert len(compact_msgs) == 1
        assert compact_msgs[0].compaction_summary == "Summarized 10 messages"
        assert compact_msgs[0].compaction_items_before == 10
        assert compact_msgs[0].compaction_items_after == 3


# ============================================================================
# Token aggregation across subtree
# ============================================================================


class TestTokenAggregation:
    def test_invoke_agent_aggregates_child_tokens(self) -> None:
        t1 = datetime.datetime(2026, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        t2 = datetime.datetime(2026, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)
        spans = [
            _span(
                span_id="agent",
                operation_name="invoke_agent",
                agent_name="bot",
                output_messages=[{"role": "assistant", "content": "Result"}],
                input_tokens=10,
                output_tokens=5,
                started_at=t1,
            ),
            _span(
                span_id="llm",
                parent_span_id="agent",
                operation_name="chat",
                input_tokens=100,
                output_tokens=50,
                started_at=t2,
            ),
        ]
        msgs = build_chat_messages(spans)
        agent_msg = next(m for m in msgs if m.type == "agent_message")
        # Should aggregate: 10+100=110 input, 5+50=55 output
        assert agent_msg.input_tokens == 110
        assert agent_msg.output_tokens == 55


# ============================================================================
# Tree structure
# ============================================================================


class TestTreeStructure:
    def test_nested_agent_tool_chat(self) -> None:
        """Full agent turn: invoke_agent → execute_tool + chat → response."""
        t = lambda s: datetime.datetime(
            2026, 1, 1, 0, 0, s, tzinfo=datetime.timezone.utc
        )
        spans = [
            _span(
                span_id="agent",
                operation_name="invoke_agent",
                agent_name="bot",
                output_messages=[
                    {"role": "assistant", "content": "The weather is sunny."}
                ],
                input_messages=[{"role": "user", "content": "What's the weather?"}],
                started_at=t(0),
            ),
            _span(
                span_id="tool",
                parent_span_id="agent",
                operation_name="execute_tool",
                tool_name="get_weather",
                tool_call_arguments='{"city":"NYC"}',
                tool_call_result='{"temp":72}',
                started_at=t(1),
            ),
            _span(
                span_id="llm",
                parent_span_id="agent",
                operation_name="chat",
                input_tokens=200,
                output_tokens=100,
                started_at=t(2),
            ),
        ]
        msgs = build_chat_messages(spans)
        types = [m.type for m in msgs]
        assert "user_message" in types
        assert "agent_start" in types
        assert "tool_call" in types
        assert "agent_message" in types

    def test_orphan_spans_become_roots(self) -> None:
        """Spans whose parent is missing are treated as roots."""
        spans = [
            _span(
                span_id="orphan",
                parent_span_id="missing-parent",
                operation_name="chat",
                output_messages=[{"role": "assistant", "content": "Hi"}],
            ),
        ]
        msgs = build_chat_messages(spans)
        agent_msgs = [m for m in msgs if m.type == "agent_message"]
        assert len(agent_msgs) == 1


# ============================================================================
# build_trace_chat wrapper
# ============================================================================


class TestBuildTraceChat:
    def test_metadata(self) -> None:
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                agent_name="my-bot",
                provider_name="openai",
                output_messages=[{"role": "assistant", "content": "Done"}],
            ),
        ]
        res = build_trace_chat(spans, "trace-123")
        assert res.trace_id == "trace-123"
        assert res.root_span_name == "my-bot"
        assert res.provider == "openai"
        assert res.total_duration_ms > 0
        assert len(res.messages) > 0

    def test_empty(self) -> None:
        res = build_trace_chat([], "trace-empty")
        assert res.trace_id == "trace-empty"
        assert res.messages == []
