"""Unit tests for agent_chat_view.py — span tree to chat trajectory.

Integration tests in test_genai_agent_queries.py cover realistic trace shapes
end-to-end against ClickHouse; these tests pin the pure projection rules.
"""

import datetime

import pytest

from weave.trace_server.agents.chat_view import (
    build_chat_messages,
    build_span_tree,
    build_trace_chat,
)
from weave.trace_server.agents.types import (
    AgentChatAgentStart,
    AgentChatAssistantMessage,
    AgentChatContextCompacted,
    AgentChatMessage,
    AgentChatToolCall,
    AgentChatUserMessage,
    AgentSpanSchema,
)


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
    ended_at: datetime.datetime | None = None,
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
        ended_at=ended_at
        or datetime.datetime(2026, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc),
        **kwargs,
    )


def _user_payload(message: AgentChatMessage) -> AgentChatUserMessage:
    assert message.user_message is not None
    return message.user_message


def _assistant_payload(message: AgentChatMessage) -> AgentChatAssistantMessage:
    assert message.assistant_message is not None
    return message.assistant_message


def _tool_payload(message: AgentChatMessage) -> AgentChatToolCall:
    assert message.tool_call is not None
    return message.tool_call


def _agent_start_payload(message: AgentChatMessage) -> AgentChatAgentStart:
    assert message.agent_start is not None
    return message.agent_start


def _context_compacted_payload(
    message: AgentChatMessage,
) -> AgentChatContextCompacted:
    assert message.context_compacted is not None
    return message.context_compacted


def test_empty() -> None:
    assert build_chat_messages([]) == []
    res = build_trace_chat([], "trace-empty")
    assert res.trace_id == "trace-empty"
    assert res.messages == []


def test_agent_chat_message_requires_matching_payload() -> None:
    msg = AgentChatMessage(
        type="assistant_message",
        assistant_message=AgentChatAssistantMessage(text="hello"),
    )

    assert msg.assistant_message is not None
    assert msg.assistant_message.text == "hello"

    with pytest.raises(ValueError, match="must set only"):
        AgentChatMessage(type="assistant_message")

    with pytest.raises(ValueError, match="must set only"):
        AgentChatMessage(
            type="assistant_message",
            assistant_message=AgentChatAssistantMessage(text="hello"),
            tool_call=AgentChatToolCall(tool_name="search"),
        )


def test_full_agent_turn() -> None:
    """A realistic agent trace exercising every message type the projection
    emits (user_message, agent_start, tool_call, context_compacted,
    assistant_message), plus token aggregation from child spans and
    build_trace_chat wrapper metadata.
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
            span_id="llm",
            parent_span_id="agent",
            operation_name="chat",
            input_tokens=200,
            output_tokens=100,
            started_at=at(2),
        ),
    ]

    res = build_trace_chat(spans, "trace-123")

    # Wrapper metadata
    assert res.trace_id == "trace-123"
    assert res.root_span_name == "my-bot"
    assert res.provider == "openai"
    assert res.total_duration_ms > 0

    # Every expected message type is emitted exactly once.
    by_type: dict[str, AgentChatMessage] = {}
    for m in res.messages:
        assert m.type not in by_type, f"duplicate {m.type}"
        by_type[m.type] = m
    assert set(by_type) == {
        "user_message",
        "agent_start",
        "tool_call",
        "context_compacted",
        "assistant_message",
    }

    # Per-message content
    assert _user_payload(by_type["user_message"]).text == "What's the weather?"
    assert by_type["agent_start"].agent_name == "my-bot"
    assert _tool_payload(by_type["tool_call"]).tool_name == "get_weather"
    assert _tool_payload(by_type["tool_call"]).tool_arguments == '{"city":"NYC"}'
    assert _tool_payload(by_type["tool_call"]).tool_result == '{"temp":72}'
    assert by_type["tool_call"].started_at == at(1)
    context_compacted = _context_compacted_payload(by_type["context_compacted"])
    assert context_compacted.compaction_summary == "Summarized 10 messages"
    assert context_compacted.compaction_items_before == 10
    assert context_compacted.compaction_items_after == 3
    assert _assistant_payload(by_type["assistant_message"]).text == "It's 72°F."

    # Token aggregation: root 10 + llm 200 = 210 in, 5 + 100 = 105 out.
    # Tool spans don't contribute tokens.
    assert _assistant_payload(by_type["assistant_message"]).input_tokens == 210
    assert _assistant_payload(by_type["assistant_message"]).output_tokens == 105


def test_agent_start_uses_agent_id_when_name_missing() -> None:
    messages = build_chat_messages(
        [
            _span(
                span_id="agent",
                operation_name="invoke_agent",
                agent_id="agent-123",
                output_messages=[{"role": "assistant", "content": "hello"}],
            )
        ]
    )

    agent_start = next(m for m in messages if m.type == "agent_start")
    assistant = next(m for m in messages if m.type == "assistant_message")
    assert agent_start.agent_name == "agent-123"
    assert assistant.agent_name == "agent-123"


def test_agent_start_emits_useful_metadata_without_agent_identity() -> None:
    messages = build_chat_messages(
        [
            _span(
                span_id="agent",
                operation_name="invoke_agent",
                span_name="invoke_agent",
                request_model="gpt-4o",
                system_instructions=["You are helpful."],
                tool_definitions='[{"name":"search"}]',
            )
        ]
    )

    assert [m.type for m in messages] == ["agent_start"]
    assert messages[0].agent_name is None
    agent_start = _agent_start_payload(messages[0])
    assert agent_start.model == "gpt-4o"
    assert agent_start.system_instructions == "You are helpful."
    assert agent_start.tool_definitions == '[{"name":"search"}]'


def test_anonymous_invoke_without_metadata_skips_empty_agent_start() -> None:
    messages = build_chat_messages(
        [
            _span(
                span_id="agent",
                operation_name="invoke_agent",
                span_name="invoke_agent",
                output_messages=[{"role": "assistant", "content": "hello"}],
            )
        ]
    )

    assert [m.type for m in messages] == ["assistant_message"]
    assert messages[0].agent_name is None


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


def test_build_trace_chat_handles_null_started_at() -> None:
    """build_trace_chat must not crash when a span has started_at=None.

    _find_user_prompt previously sorted by `s.started_at or ""` which
    mixed datetime with str and raised TypeError for any span missing
    started_at. The fix uses a tuple key with a None-last sentinel.
    """
    spans = [
        AgentSpanSchema(
            project_id="p1",
            trace_id="t1",
            span_id="null-start",
            span_name="invoke_agent",
            operation_name="invoke_agent",
            status_code="OK",
            started_at=None,
            ended_at=None,
            input_messages=[{"role": "user", "content": "hello from the void"}],
        ),
        AgentSpanSchema(
            project_id="p1",
            trace_id="t1",
            span_id="real-start",
            span_name="chat",
            operation_name="chat",
            status_code="OK",
            started_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            ended_at=datetime.datetime(
                2026, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc
            ),
            input_messages=[{"role": "user", "content": "hello from now"}],
        ),
    ]
    # Must not raise. _find_user_prompt prefers invoke_agent spans, so the
    # null-start invoke_agent's prompt wins over the chat span's prompt.
    # The important thing is that the sort doesn't crash on the mixed key.
    res = build_trace_chat(spans, "trace-with-null")
    assert res.trace_id == "trace-with-null"
    user_msgs = [m for m in res.messages if m.type == "user_message"]
    assert len(user_msgs) == 1
    assert _user_payload(user_msgs[0]).text == "hello from the void"
    assert user_msgs[0].started_at is None


def test_build_trace_chat_uses_latest_ended_span_when_root_missing() -> None:
    def at(seconds: int) -> datetime.datetime:
        return datetime.datetime(
            2026, 1, 1, 0, 0, seconds, tzinfo=datetime.timezone.utc
        )

    spans = [
        _span(
            span_id="early",
            parent_span_id="missing",
            span_name="early span",
            started_at=at(0),
            ended_at=at(1),
        ),
        _span(
            span_id="late",
            parent_span_id="missing",
            span_name="late span",
            provider_name="openai",
            started_at=at(0),
            ended_at=at(2),
        ),
    ]

    res = build_trace_chat(spans, "trace-without-root")
    assert res.root_span_name == "late span"
    assert res.provider == "openai"


def test_invoke_agent_mirrors_child_llm_output_messages() -> None:
    """When an invoke_agent span and its inner LLM span both carry the same
    final `output_messages` (OpenAI Agents SDK / Google ADK single-call
    turn), we should emit exactly one `assistant_message`, not two.

    The inner LLM span is the canonical content source; the parent
    invoke_agent only emits if no descendant did.
    """

    def at(seconds: int) -> datetime.datetime:
        return datetime.datetime(
            2026, 1, 1, 0, 0, seconds, tzinfo=datetime.timezone.utc
        )

    final_text = [{"role": "assistant", "content": "It's 72°F."}]

    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            agent_name="my-bot",
            input_messages=[{"role": "user", "content": "What's the weather?"}],
            output_messages=final_text,  # mirrored onto the parent
            input_tokens=10,
            output_tokens=5,
            started_at=at(0),
        ),
        _span(
            span_id="llm",
            parent_span_id="agent",
            operation_name="chat",
            output_messages=final_text,  # same text on the inner LLM call
            input_tokens=200,
            output_tokens=100,
            started_at=at(1),
        ),
    ]

    messages = build_chat_messages(spans)
    agent_messages = [m for m in messages if m.type == "assistant_message"]

    # Exactly one assistant_message, sourced from the child chat span (not
    # duplicated from the parent invoke_agent).
    assert len(agent_messages) == 1
    assert _assistant_payload(agent_messages[0]).text == "It's 72°F."


def test_invoke_agent_emits_when_no_descendant_llm_span() -> None:
    """If an invoke_agent has output_messages but no descendant LLM span
    carries them, the parent still emits — the guard is "child emitted
    already?", not a blanket "never emit from invoke_agent".
    """

    def at(seconds: int) -> datetime.datetime:
        return datetime.datetime(
            2026, 1, 1, 0, 0, seconds, tzinfo=datetime.timezone.utc
        )

    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            agent_name="solo-bot",
            output_messages=[{"role": "assistant", "content": "hi there"}],
            started_at=at(0),
        ),
    ]

    messages = build_chat_messages(spans)
    agent_messages = [m for m in messages if m.type == "assistant_message"]
    assert len(agent_messages) == 1
    assert _assistant_payload(agent_messages[0]).text == "hi there"


def test_subagent_spans_render_inline_with_agent_label_inheritance() -> None:
    def at(seconds: int) -> datetime.datetime:
        return datetime.datetime(
            2026, 1, 1, 0, 0, seconds, tzinfo=datetime.timezone.utc
        )

    messages = build_chat_messages(
        [
            _span(
                span_id="root-agent",
                operation_name="invoke_agent",
                agent_name="root",
                started_at=at(0),
            ),
            _span(
                span_id="root-chat",
                parent_span_id="root-agent",
                operation_name="chat",
                output_messages=[{"role": "assistant", "content": "root reply"}],
                started_at=at(1),
            ),
            _span(
                span_id="sub-agent",
                parent_span_id="root-agent",
                operation_name="invoke_agent",
                agent_name="sub",
                output_messages=[{"role": "assistant", "content": "sub reply"}],
                started_at=at(2),
            ),
        ]
    )

    assert [
        (
            m.type,
            m.agent_name,
            _assistant_payload(m).text if m.assistant_message else None,
        )
        for m in messages
    ] == [
        ("agent_start", "root", None),
        ("assistant_message", "root", "root reply"),
        ("agent_start", "sub", None),
        ("assistant_message", "sub", "sub reply"),
    ]


def test_system_message_not_used_as_user_prompt_fallback() -> None:
    messages = build_chat_messages(
        [
            _span(
                span_id="s1",
                input_messages=[{"role": "system", "content": "You are helpful."}],
                output_messages=[{"role": "assistant", "content": "hello"}],
            )
        ]
    )

    assert [m.type for m in messages] == ["assistant_message"]


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


def test_build_span_tree_sorts_equal_starts_by_latest_end_first() -> None:
    """Enclosing spans often share child start times and should sort first."""
    t0 = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    t1 = datetime.datetime(2026, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)
    t2 = datetime.datetime(2026, 1, 1, 0, 0, 2, tzinfo=datetime.timezone.utc)
    spans = [
        AgentSpanSchema(
            project_id="p1",
            trace_id="t1",
            span_id="a-short",
            span_name="short",
            status_code="OK",
            started_at=t0,
            ended_at=t1,
        ),
        AgentSpanSchema(
            project_id="p1",
            trace_id="t1",
            span_id="z-long",
            span_name="long",
            status_code="OK",
            started_at=t0,
            ended_at=t2,
        ),
        AgentSpanSchema(
            project_id="p1",
            trace_id="t1",
            span_id="b-short",
            span_name="also short",
            status_code="OK",
            started_at=t0,
            ended_at=t1,
        ),
    ]
    roots = build_span_tree(spans)
    assert [r.span.span_id for r in roots] == ["z-long", "a-short", "b-short"]
