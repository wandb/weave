"""Unit tests for agent_chat_view.py — span → chat trajectory.

Just two tests: one empty-input smoke check, one comprehensive
end-to-end scenario that exercises every message type the projection
emits. Integration tests in test_genai_agent_queries.py cover realistic
trace shapes end-to-end against ClickHouse.
"""

import datetime

from weave.trace_server.agents.chat_view import (
    build_chat_messages,
    build_span_tree,
    build_trace_chat,
)
from weave.trace_server.agents.types import AgentSpanSchema


def _span(
    span_id: str = "s1",
    parent_span_id: str = "",
    operation_name: str = "chat",
    agent_name: str = "",
    span_name: str = "test",
    input_messages: list | None = None,
    output_messages: list | None = None,
    tool_name: str = "",
    tool_call_arguments: str = "",
    tool_call_result: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    compaction_summary: str = "",
    compaction_items_before: int = 0,
    compaction_items_after: int = 0,
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
        tool_name=tool_name,
        tool_call_arguments=tool_call_arguments,
        tool_call_result=tool_call_result,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        compaction_summary=compaction_summary,
        compaction_items_before=compaction_items_before,
        compaction_items_after=compaction_items_after,
        status_code="OK",
        started_at=started_at
        or datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        ended_at=datetime.datetime(2026, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc),
        **kwargs,
    )


def test_empty() -> None:
    assert build_chat_messages([]) == []
    res = build_trace_chat([], "trace-empty")
    assert res.trace_id == "trace-empty"
    assert res.messages == []


def test_full_agent_turn() -> None:
    """A realistic agent trace exercising every message type the projection
    emits (user_message, agent_start, tool_call, agent_handoff,
    context_compacted, agent_message), plus token aggregation from child
    spans and build_trace_chat wrapper metadata.
    """

    def at(seconds: int) -> datetime.datetime:
        return datetime.datetime(
            2026, 1, 1, 0, 0, seconds, tzinfo=datetime.timezone.utc
        )

    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            agent_name="my-bot",
            provider_name="openai",
            input_messages=[{"role": "user", "content": "What's the weather?"}],
            output_messages=[{"role": "assistant", "content": "It's 72°F."}],
            input_tokens=10,
            output_tokens=5,
            compaction_summary="Summarized 10 messages",
            compaction_items_before=10,
            compaction_items_after=3,
            started_at=at(0),
        ),
        _span(
            span_id="tool",
            parent_span_id="agent",
            operation_name="execute_tool",
            tool_name="get_weather",
            tool_call_arguments='{"city":"NYC"}',
            tool_call_result='{"temp":72}',
            started_at=at(1),
        ),
        _span(
            span_id="handoff",
            parent_span_id="agent",
            operation_name="execute_tool",
            tool_name="transfer_to_sales_agent",
            started_at=at(2),
        ),
        _span(
            span_id="llm",
            parent_span_id="agent",
            operation_name="chat",
            input_tokens=200,
            output_tokens=100,
            started_at=at(3),
        ),
    ]

    res = build_trace_chat(spans, "trace-123")

    # Wrapper metadata
    assert res.trace_id == "trace-123"
    assert res.root_span_name == "my-bot"
    assert res.provider == "openai"
    assert res.total_duration_ms > 0

    # Every expected message type is emitted exactly once.
    by_type: dict[str, object] = {}
    for m in res.messages:
        assert m.type not in by_type, f"duplicate {m.type}"
        by_type[m.type] = m
    assert set(by_type) == {
        "user_message",
        "agent_start",
        "tool_call",
        "agent_handoff",
        "context_compacted",
        "agent_message",
    }

    # Per-message content
    assert by_type["user_message"].text == "What's the weather?"
    assert by_type["agent_start"].agent_name == "my-bot"
    assert by_type["tool_call"].tool_name == "get_weather"
    assert by_type["tool_call"].tool_arguments == '{"city":"NYC"}'
    assert by_type["tool_call"].tool_result == '{"temp":72}'
    assert "sales_agent" in by_type["agent_handoff"].text
    assert by_type["context_compacted"].compaction_summary == "Summarized 10 messages"
    assert by_type["context_compacted"].compaction_items_before == 10
    assert by_type["context_compacted"].compaction_items_after == 3
    assert by_type["agent_message"].text == "It's 72°F."

    # Token aggregation: root 10 + llm 200 = 210 in, 5 + 100 = 105 out.
    # Tool and handoff spans don't contribute tokens.
    assert by_type["agent_message"].input_tokens == 210
    assert by_type["agent_message"].output_tokens == 105


def test_build_span_tree_handles_null_started_at() -> None:
    """build_span_tree must not crash when a span has started_at=None.

    The ClickHouse column is non-null, but in-memory callers/tests can
    construct AgentSpanSchema with started_at=None. The sort key needs to
    stay type-homogeneous.
    """
    s1 = AgentSpanSchema(
        project_id="p1",
        trace_id="t1",
        span_id="s1",
        span_name="a",
        status_code="OK",
        started_at=None,
        ended_at=None,
    )
    s2 = AgentSpanSchema(
        project_id="p1",
        trace_id="t1",
        span_id="s2",
        span_name="b",
        status_code="OK",
        started_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        ended_at=None,
    )
    roots = build_span_tree([s1, s2])
    assert {r.span.span_id for r in roots} == {"s1", "s2"}
    # s1 (None) sorts AFTER s2 so null timestamps don't leak to the top
    # of the conversation view.
    assert roots[-1].span.span_id == "s1"


def test_build_span_tree_sort_is_stable_on_equal_timestamps() -> None:
    """Siblings with equal started_at must sort deterministically by span_id."""
    t0 = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    spans = [
        AgentSpanSchema(
            project_id="p1",
            trace_id="t1",
            span_id=sid,
            span_name="s",
            status_code="OK",
            started_at=t0,
            ended_at=t0,
        )
        # Intentionally out of order to exercise the tiebreaker.
        for sid in ("c", "a", "b")
    ]
    roots = build_span_tree(spans)
    assert [r.span.span_id for r in roots] == ["a", "b", "c"]
