"""Unit tests for agent_chat_view.py — span tree to chat trajectory.

Integration tests in test_genai_agent_queries.py cover realistic trace shapes
end-to-end against ClickHouse; these tests pin the pure projection rules.
"""

import datetime
import json
import sys

import pytest

from weave.trace_server.agents.chat_view import (
    _MAX_REF_SEARCH_DEPTH,
    _iter_internal_refs,
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


def _parts(*parts: dict) -> str:
    """Serialize message parts the way ingestion stores multimodal content.

    `genai_extraction._normalize_single_message` JSON-dumps a message's parts
    array into the `content` field, so a multimodal message arrives here as a
    JSON string starting with "[".
    """
    return json.dumps(list(parts))


def _text_part(text: str) -> dict:
    return {"type": "text", "content": text}


def _uri_part(
    uri: str, *, mime_type: str = "audio/wav", modality: str = "audio"
) -> dict:
    return {"type": "uri", "mime_type": mime_type, "modality": modality, "uri": uri}


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


def test_chat_view_aggregates_cost() -> None:
    """Per-message cost sums across the agent subtree; trace cost sums all spans."""

    def at(seconds: int) -> datetime.datetime:
        return datetime.datetime(
            2026, 1, 1, 0, 0, seconds, tzinfo=datetime.timezone.utc
        )

    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            agent_name="my-bot",
            output_messages=[{"role": "assistant", "content": "done"}],
            input_cost_usd=0.001,
            output_cost_usd=0.002,
            total_cost_usd=0.003,
            started_at=at(0),
        ),
        _span(
            span_id="tool",
            parent_span_id="agent",
            operation_name="execute_tool",
            tool_name="get_weather",
            started_at=at(1),
        ),
        _span(
            span_id="llm",
            parent_span_id="agent",
            operation_name="chat",
            input_cost_usd=0.02,
            output_cost_usd=0.01,
            total_cost_usd=0.03,
            started_at=at(2),
        ),
    ]

    res = build_trace_chat(spans, "trace-cost")

    assistant = _assistant_payload(
        next(m for m in res.messages if m.type == "assistant_message")
    )
    # Aggregated across root + llm (tool contributes no cost).
    assert assistant.input_cost_usd == pytest.approx(0.021)
    assert assistant.output_cost_usd == pytest.approx(0.012)
    assert assistant.total_cost_usd == pytest.approx(0.033)
    # Trace total sums every span's cost.
    assert res.total_cost_usd == pytest.approx(0.033)


def test_chat_view_cost_none_when_unpriced() -> None:
    """With no priced spans, costs stay None (unknown), not 0."""
    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            agent_name="my-bot",
            output_messages=[{"role": "assistant", "content": "done"}],
        ),
    ]
    res = build_trace_chat(spans, "trace-unpriced")
    assistant = _assistant_payload(
        next(m for m in res.messages if m.type == "assistant_message")
    )
    assert assistant.total_cost_usd is None
    assert res.total_cost_usd is None


def test_chat_view_exposes_agent_metadata_for_reactions() -> None:
    """The chat view surfaces agent_version + status_code so reaction feedback
    can carry them: per-message from the message's span, and the trace root's
    metadata on AgentTraceChatRes (used for turn-level reactions).
    """
    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            agent_name="my-bot",
            agent_version="1.2.0",  # `_span` hardcodes status_code="OK"
            output_messages=[{"role": "assistant", "content": "done"}],
        ),
    ]

    res = build_trace_chat(spans, "trace-1")

    # Root span metadata on the trace — turn-level reactions read these.
    assert res.agent_name == "my-bot"
    assert res.agent_version == "1.2.0"
    assert res.status_code == "OK"

    # Each message built from the span carries the same metadata.
    span_messages = [m for m in res.messages if m.span_id == "agent"]
    assert span_messages
    for m in span_messages:
        assert m.agent_version == "1.2.0"
        assert m.status_code == "OK"


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


def test_content_span_system_instructions_surface_as_agent_start() -> None:
    """System instructions logged on a bare chat span (no invoke_agent) still
    reach the chat view via a synthesized agent_start card.
    """
    messages = build_chat_messages(
        [
            _span(
                span_id="chat",
                operation_name="chat",
                request_model="gpt-4o",
                system_instructions=["You are helpful."],
                output_messages=[{"role": "assistant", "content": "hello"}],
            )
        ]
    )

    assert [m.type for m in messages] == ["agent_start", "assistant_message"]
    agent_start = _agent_start_payload(messages[0])
    assert agent_start.system_instructions == "You are helpful."
    assert agent_start.model == "gpt-4o"


def test_content_span_system_instructions_deduped_across_turns() -> None:
    """The same system prompt replayed on every turn's chat span renders once."""
    spans = [
        _span(
            span_id=f"chat{i}",
            operation_name="chat",
            system_instructions=["You are helpful."],
            input_messages=[{"role": "user", "content": f"q{i}"}],
            output_messages=[{"role": "assistant", "content": f"a{i}"}],
            started_at=datetime.datetime(
                2026, 1, 1, 0, 0, i, tzinfo=datetime.timezone.utc
            ),
        )
        for i in range(3)
    ]

    messages = build_chat_messages(spans)

    assert [m.type for m in messages].count("agent_start") == 1


def test_content_span_system_instructions_change_emits_new_card() -> None:
    """A genuinely changed system prompt mid-conversation emits a fresh card."""
    spans = [
        _span(
            span_id="chat0",
            operation_name="chat",
            system_instructions=["You are helpful."],
            output_messages=[{"role": "assistant", "content": "a0"}],
            started_at=datetime.datetime(
                2026, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
            ),
        ),
        _span(
            span_id="chat1",
            operation_name="chat",
            system_instructions=["You are terse."],
            output_messages=[{"role": "assistant", "content": "a1"}],
            started_at=datetime.datetime(
                2026, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc
            ),
        ),
    ]

    messages = build_chat_messages(spans)

    starts = [m for m in messages if m.type == "agent_start"]
    assert [_agent_start_payload(m).system_instructions for m in starts] == [
        "You are helpful.",
        "You are terse.",
    ]


def test_invoke_agent_system_instructions_suppress_descendant_duplicate() -> None:
    """An invoke_agent's system instructions are not re-emitted by a descendant
    chat span that replays the same prompt.
    """
    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            span_name="invoke_agent",
            system_instructions=["You are helpful."],
        ),
        _span(
            span_id="chat",
            parent_span_id="agent",
            operation_name="chat",
            system_instructions=["You are helpful."],
            output_messages=[{"role": "assistant", "content": "hello"}],
        ),
    ]

    messages = build_chat_messages(spans)

    assert [m.type for m in messages].count("agent_start") == 1


def test_invoke_agent_without_prompt_absorbs_descendant_system_instructions() -> None:
    """A bare invoke_agent agent_start (identity, no prompt) absorbs a child
    chat span's system instructions instead of emitting a second card.

    Mirrors the prod WB Agent shape: invoke_agent carries the agent name but no
    instructions, and the prompt is recorded on the child chat span.
    """
    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            span_name="invoke_agent WB Agent",
            agent_name="WB Agent",
        ),
        _span(
            span_id="chat",
            parent_span_id="agent",
            operation_name="chat",
            agent_name="WB Agent",
            request_model="gpt-5.5",
            system_instructions=["You are ARIA."],
            output_messages=[{"role": "assistant", "content": "hello"}],
        ),
    ]

    messages = build_chat_messages(spans)

    starts = [m for m in messages if m.type == "agent_start"]
    assert len(starts) == 1
    payload = _agent_start_payload(starts[0])
    assert payload.system_instructions == "You are ARIA."
    # Model is folded in from the chat span when the invoke_agent lacked one.
    assert payload.model == "gpt-5.5"


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
    # Must not raise. The chat (LLM) span's own user input drives the turn, so
    # its prompt is what renders; the null-start invoke_agent prompt is only a
    # fallback for when no LLM span carries user input. The important thing is
    # that the sort doesn't crash on the mixed (None / datetime) key.
    res = build_trace_chat(spans, "trace-with-null")
    assert res.trace_id == "trace-with-null"
    user_msgs = [m for m in res.messages if m.type == "user_message"]
    assert len(user_msgs) == 1
    assert _user_payload(user_msgs[0]).text == "hello from now"
    # Sourced from the chat span (which has a real start), not the null one.
    assert user_msgs[0].started_at is not None


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


def test_chat_span_mirrors_assistant_text_child() -> None:
    """Claude Code emits assistant text on both the model chat span and a
    direct assistant_text transcript child. The child keeps its timeline
    position and inherits the parent model's richer metadata.
    """

    def at(milliseconds: int) -> datetime.datetime:
        return datetime.datetime(
            2026,
            1,
            1,
            0,
            0,
            0,
            milliseconds * 1000,
            tzinfo=datetime.timezone.utc,
        )

    final_text = [
        {
            "role": "assistant",
            "content": _parts(_text_part("I'll inspect the trace.")),
        }
    ]
    spans = [
        _span(
            span_id="chat",
            operation_name="chat",
            agent_name="claude-code",
            request_model="claude-opus-4-8",
            agent_version="1.2.3",
            output_messages=final_text,
            reasoning_content="Check the trace structure first.",
            reasoning_tokens=12,
            input_tokens=200,
            output_tokens=40,
            total_cost_usd=0.03,
            started_at=at(100),
            ended_at=at(900),
        ),
        _span(
            span_id="assistant-text",
            parent_span_id="chat",
            operation_name="assistant_text",
            agent_name="claude-code",
            output_messages=final_text,
            started_at=at(500),
            ended_at=at(500),
        ),
    ]

    assistant_messages = [
        message
        for message in build_chat_messages(spans)
        if message.type == "assistant_message"
    ]

    assert len(assistant_messages) == 1
    message = assistant_messages[0]
    payload = _assistant_payload(message)
    assert message.span_id == "assistant-text"
    assert message.started_at == at(500)
    assert message.agent_version == "1.2.3"
    assert payload.text == "I'll inspect the trace."
    assert payload.model == "claude-opus-4-8"
    assert payload.reasoning_content == "Check the trace structure first."
    assert payload.reasoning_tokens == 12
    assert payload.input_tokens == 200
    assert payload.output_tokens == 40
    assert payload.total_cost_usd == 0.03
    assert payload.duration_ms == 800


def test_chat_span_keeps_distinct_child_assistant_text() -> None:
    """Only exact mirrored text coalesces; distinct parent/child replies stay
    separate.
    """
    spans = [
        _span(
            span_id="chat",
            operation_name="chat",
            output_messages=[{"role": "assistant", "content": "Final answer"}],
        ),
        _span(
            span_id="assistant-text",
            parent_span_id="chat",
            operation_name="assistant_text",
            output_messages=[{"role": "assistant", "content": "Progress update"}],
        ),
    ]

    assistant_texts = [
        _assistant_payload(message).text
        for message in build_chat_messages(spans)
        if message.type == "assistant_message"
    ]

    assert assistant_texts == ["Progress update", "Final answer"]


def test_chat_spans_use_assistant_text_children_for_sibling_order() -> None:
    """Claude Code chat siblings can share a coarse start timestamp while
    their transcript children retain the true assistant-message order.
    """

    def at(milliseconds: int) -> datetime.datetime:
        return datetime.datetime(
            2026,
            1,
            1,
            0,
            0,
            0,
            milliseconds * 1000,
            tzinfo=datetime.timezone.utc,
        )

    first = [{"role": "assistant", "content": "First update"}]
    second = [{"role": "assistant", "content": "Second update"}]
    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            started_at=at(0),
            ended_at=at(400),
        ),
        # The later response has the longer parent span, which is the normal
        # equal-start tiebreaker. Its transcript child must override that.
        _span(
            span_id="chat-second",
            parent_span_id="agent",
            operation_name="chat",
            output_messages=second,
            started_at=at(100),
            ended_at=at(300),
        ),
        _span(
            span_id="text-second",
            parent_span_id="chat-second",
            operation_name="assistant_text",
            output_messages=second,
            started_at=at(250),
            ended_at=at(250),
        ),
        _span(
            span_id="chat-first",
            parent_span_id="agent",
            operation_name="chat",
            output_messages=first,
            started_at=at(100),
            ended_at=at(200),
        ),
        _span(
            span_id="text-first",
            parent_span_id="chat-first",
            operation_name="assistant_text",
            output_messages=first,
            started_at=at(150),
            ended_at=at(150),
        ),
    ]

    assistants = [
        message
        for message in build_chat_messages(spans)
        if message.type == "assistant_message"
    ]

    assert [message.span_id for message in assistants] == [
        "text-first",
        "text-second",
    ]
    assert [_assistant_payload(message).text for message in assistants] == [
        "First update",
        "Second update",
    ]


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


def test_claude_async_agent_launch_renders_as_tool_activity() -> None:
    """Claude Code's async launch envelope is execution state, not a reply."""
    launch = json.dumps(
        {
            "isAsync": True,
            "status": "async_launched",
            "agentId": "worker-1",
            "description": "Inspect the frontend cost card",
        }
    )
    messages = build_chat_messages(
        [
            _span(
                span_id="explore-agent",
                operation_name="invoke_agent",
                agent_name="Explore",
                output_messages=[{"role": "assistant", "content": launch}],
            )
        ]
    )

    assert [message.type for message in messages] == ["agent_start", "tool_call"]
    tool = _tool_payload(messages[1])
    assert tool.tool_name == "Start Explore"
    assert tool.tool_arguments == "Inspect the frontend cost card"
    assert tool.tool_result == launch


def test_reasoning_part_not_duplicated_in_assistant_text() -> None:
    """A reasoning part in output_messages surfaces only as `reasoning_content`,
    never concatenated into the assistant body text.

    `_serialize_output_messages` folds reasoning into the assistant message's
    parts as a ReasoningPart (so downstream extraction can populate
    `reasoning_content`). The chat view must render that reasoning solely in the
    Reasoning block — otherwise the same text renders twice: once in the
    collapsible and again as body text.
    """
    reasoning = "Investigating scenario counts"
    answer = "There are 17 scenarios, not 16."
    span = _span(
        operation_name="chat",
        output_messages=[
            {
                "role": "assistant",
                "content": _parts(
                    {"type": "reasoning", "content": reasoning},
                    _text_part(answer),
                ),
            }
        ],
        reasoning_content=reasoning,
    )

    messages = build_chat_messages([span])
    assistant = next(m for m in messages if m.type == "assistant_message")
    payload = _assistant_payload(assistant)

    assert payload.text == answer
    assert reasoning not in payload.text
    assert payload.reasoning_content == reasoning


def _tool_call_part(name: str, arguments: str) -> dict:
    return {"type": "tool_call", "id": "tc1", "name": name, "arguments": arguments}


def test_interleaved_reasoning_before_tool_call_is_surfaced() -> None:
    """Reasoning that precedes a tool call (an LLM step whose only output is a
    tool call, no assistant text) must still surface as a reasoning-only
    message, in order before the tool call — not be dropped because the step
    produced no final text.
    """

    def at(seconds: int) -> datetime.datetime:
        return datetime.datetime(
            2026, 1, 1, 0, 0, seconds, tzinfo=datetime.timezone.utc
        )

    step_reasoning = "Deciding to inspect the workspace"
    final_reasoning = "Summarizing what I found"
    answer = "The eval suite has 17 scenarios."

    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            agent_name="wb-agent",
            input_messages=[{"role": "user", "content": "How many scenarios?"}],
            started_at=at(0),
        ),
        # LLM step that reasons then calls a tool: reasoning + tool_call parts,
        # no text part.
        _span(
            span_id="llm1",
            parent_span_id="agent",
            operation_name="chat",
            output_messages=[
                {
                    "role": "assistant",
                    "content": _parts(
                        {"type": "reasoning", "content": step_reasoning},
                        _tool_call_part("shell", '{"command": "ls"}'),
                    ),
                }
            ],
            reasoning_content=step_reasoning,
            started_at=at(1),
        ),
        _span(
            span_id="tool1",
            parent_span_id="agent",
            operation_name="execute_tool",
            span_name="execute_tool shell",
            tool_name="shell",
            tool_call_arguments='{"command": "ls"}',
            tool_call_result="17 files",
            started_at=at(2),
        ),
        # Final LLM step: reasoning + the answer text.
        _span(
            span_id="llm2",
            parent_span_id="agent",
            operation_name="chat",
            output_messages=[
                {
                    "role": "assistant",
                    "content": _parts(
                        {"type": "reasoning", "content": final_reasoning},
                        _text_part(answer),
                    ),
                }
            ],
            reasoning_content=final_reasoning,
            started_at=at(3),
        ),
    ]

    messages = build_chat_messages(spans)
    types = [m.type for m in messages]

    # The interleaved reasoning step is emitted before its tool call, and the
    # final answer (with its own reasoning) comes last.
    assert types == [
        "user_message",
        "agent_start",
        "assistant_message",  # reasoning-only step
        "tool_call",
        "assistant_message",  # final answer
    ]

    step = _assistant_payload(messages[2])
    assert step.text == ""
    assert step.reasoning_content == step_reasoning

    final = _assistant_payload(messages[4])
    assert final.text == answer
    assert final.reasoning_content == final_reasoning


def test_tool_call_step_without_reasoning_emits_no_assistant_message() -> None:
    """A tool-calling LLM step that carries neither assistant text nor
    reasoning must not produce an empty assistant bubble.
    """

    def at(seconds: int) -> datetime.datetime:
        return datetime.datetime(
            2026, 1, 1, 0, 0, seconds, tzinfo=datetime.timezone.utc
        )

    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            agent_name="wb-agent",
            input_messages=[{"role": "user", "content": "run it"}],
            started_at=at(0),
        ),
        _span(
            span_id="llm1",
            parent_span_id="agent",
            operation_name="chat",
            output_messages=[
                {
                    "role": "assistant",
                    "content": _parts(_tool_call_part("shell", "{}")),
                }
            ],
            started_at=at(1),
        ),
        _span(
            span_id="tool1",
            parent_span_id="agent",
            operation_name="execute_tool",
            span_name="execute_tool shell",
            tool_name="shell",
            tool_call_result="done",
            started_at=at(2),
        ),
    ]

    messages = build_chat_messages(spans)
    assert [m.type for m in messages if m.type == "assistant_message"] == []


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


def test_claude_task_notification_renders_as_tool_activity() -> None:
    """Claude Code sends async subagent completions to the model as role=user,
    but the chat trajectory must not present them as a human prompt.
    """
    notification = (
        "<task-notification>\n"
        "<task-id>worker-1</task-id>\n"
        "<output-file>/tmp/worker-1.txt</output-file>\n"
        "<status>completed</status>\n"
        "</task-notification>"
    )
    messages = build_chat_messages(
        [
            _span(
                span_id="claude-chat",
                operation_name="chat",
                agent_name="claude-code",
                input_messages=[{"role": "user", "content": notification}],
                output_messages=[
                    {"role": "assistant", "content": "Worker result received."}
                ],
            )
        ]
    )

    assert [message.type for message in messages] == [
        "tool_call",
        "assistant_message",
    ]
    tool_message = messages[0]
    tool = _tool_payload(tool_message)
    assert tool_message.span_id == "claude-chat"
    assert tool_message.agent_name == "claude-code"
    assert tool.tool_name == "Task notification"
    assert tool.tool_result == notification
    assert all(message.type != "user_message" for message in messages)


def test_claude_task_notification_falls_back_from_invoke_agent() -> None:
    """Claude session turns can record the notification only on the enclosing
    invoke_agent span rather than the child chat span.
    """
    notification = (
        "<task-notification>\n"
        "<task-id>worker-1</task-id>\n"
        "<status>completed</status>\n"
        "</task-notification>"
    )
    messages = build_chat_messages(
        [
            _span(
                span_id="agent",
                operation_name="invoke_agent",
                agent_name="claude-code",
                input_messages=[{"role": "user", "content": notification}],
            ),
            _span(
                span_id="chat",
                parent_span_id="agent",
                operation_name="chat",
                output_messages=[
                    {"role": "assistant", "content": "Worker result received."}
                ],
            ),
        ]
    )

    assert [message.type for message in messages] == [
        "tool_call",
        "agent_start",
        "assistant_message",
    ]
    tool_message = messages[0]
    assert tool_message.span_id == "agent"
    assert _tool_payload(tool_message).tool_result == notification


def test_input_media_attaches_to_user_message_not_assistant() -> None:
    """Regression: media supplied with the user prompt renders on the user
    bubble, not the assistant.

    Mirrors the session SDK shape — `attach_media` records media on the
    LLM/chat span as a `uri` part on the user input message (external form)
    and, separately, in the span-level `content_refs` (internal,
    int<->ext-convertible form). The user text comes from the enclosing
    invoke_agent span. The ref *value* surfaced is the internal `content_refs`
    one (so the response's int->ext adapter can round-trip it); its *direction*
    comes from the input part, matched by digest. So the audio lands on the
    user message and the assistant stays clean.
    """
    audio_internal = "weave-trace-internal:///PID/object/Content:AUDIODIGEST"
    audio_external = "weave:///e/p/object/Content:AUDIODIGEST"
    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            agent_name="audio-agent",
            input_messages=[
                {"role": "user", "content": _parts(_text_part("Describe the audio."))}
            ],
        ),
        _span(
            span_id="chat",
            parent_span_id="agent",
            operation_name="chat",
            input_messages=[
                {
                    "role": "user",
                    "content": _parts(
                        _text_part("Describe the audio."), _uri_part(audio_external)
                    ),
                }
            ],
            output_messages=[
                {"role": "assistant", "content": _parts(_text_part("Chiptune music."))}
            ],
            # Round-trippable internal-form ref; same object digest as the part.
            content_refs=[audio_internal],
        ),
    ]

    messages = build_chat_messages(spans)
    user = next(m for m in messages if m.type == "user_message")
    assistant = next(m for m in messages if m.type == "assistant_message")

    # Value is the internal (convertible) ref; direction is from the input part.
    assert _user_payload(user).content_refs == [audio_internal]
    assert _assistant_payload(assistant).content_refs == []


def test_inline_internal_ref_surfaces_without_span_content_refs() -> None:
    """Server-side content conversion embeds an internal weave ref directly in
    the message part (e.g. an OpenAI ``image_url``) with no span-level
    ``content_refs``. The recursive inline-ref sweep surfaces it so the image
    still renders on the user bubble.
    """
    image_internal = "weave-trace-internal:///PID/object/image-abcd.png:IMGDIGEST"
    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            agent_name="image-describer",
            input_messages=[
                {
                    "role": "user",
                    "content": _parts(_text_part("What is in this image?")),
                }
            ],
        ),
        _span(
            span_id="chat",
            parent_span_id="agent",
            operation_name="chat",
            input_messages=[
                {
                    "role": "user",
                    "content": _parts(
                        _text_part("What is in this image?"),
                        {"type": "image_url", "image_url": {"url": image_internal}},
                    ),
                }
            ],
            output_messages=[
                {"role": "assistant", "content": _parts(_text_part("A gift basket."))}
            ],
            # No span-level content_refs — the ref lives only inline in the part.
        ),
    ]

    messages = build_chat_messages(spans)
    user = next(m for m in messages if m.type == "user_message")
    assistant = next(m for m in messages if m.type == "assistant_message")

    assert _user_payload(user).content_refs == [image_internal]
    assert _assistant_payload(assistant).content_refs == []


@pytest.mark.xfail(
    reason=(
        "Known limitation (PR #7489 discussion): the inline-ref sweep "
        "(_iter_internal_refs) surfaces ANY internal weave ref, not only "
        "Content/media refs. A message that legitimately carries a ref to a "
        "non-media object (prompt/model/dataset) in a structured field leaks "
        "into content_refs and renders as broken media. A media ref is "
        "indistinguishable from a prompt ref at the string level and the part "
        "shapes are not normalized, so scoping the sweep is deferred to a "
        "follow-up (e.g. record converted media refs authoritatively at "
        "ingest, or scope the sweep to media part positions)."
    ),
    strict=False,
)
def test_inline_sweep_excludes_non_media_internal_refs() -> None:
    """The inline-ref sweep must surface only Content/media refs. A message that
    legitimately carries a ref to a non-media object (a prompt, model, dataset)
    in a structured field must NOT land in ``content_refs``, or the UI renders
    it as broken media. Content objects are stored under a sanitized-filename
    object_id, so a media ref is indistinguishable at the string level from a
    prompt ref — the walker needs to scope the match.
    """
    image_ref = "weave-trace-internal:///PID/object/gift_basket_png:IMGDIGEST"
    prompt_ref = "weave-trace-internal:///PID/object/describe_image_prompt:PROMPTDIGEST"
    spans = [
        _span(
            span_id="chat",
            operation_name="chat",
            input_messages=[
                {
                    "role": "user",
                    "content": _parts(
                        _text_part("What is in this image?"),
                        {"type": "image_url", "image_url": {"url": image_ref}},
                        # Agent quoting the prompt object it ran under — not media.
                        {"type": "tool_use", "input": {"prompt_ref": prompt_ref}},
                    ),
                }
            ],
            output_messages=[
                {"role": "assistant", "content": _parts(_text_part("A gift basket."))}
            ],
        ),
    ]

    messages = build_chat_messages(spans)
    user = next(m for m in messages if m.type == "user_message")

    # Only the media ref should render; the prompt ref is a false positive today.
    assert _user_payload(user).content_refs == [image_ref]


def test_output_media_attaches_to_assistant_message() -> None:
    """Model-generated media is a part on the output message and renders on
    the assistant bubble (mirror image of the input case).
    """
    image_internal = "weave-trace-internal:///PID/object/Content:GENIMG"
    image_external = "weave:///e/p/object/Content:GENIMG"
    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            agent_name="image-gen",
            input_messages=[
                {"role": "user", "content": _parts(_text_part("Draw a cat."))}
            ],
        ),
        _span(
            span_id="chat",
            parent_span_id="agent",
            operation_name="chat",
            input_messages=[
                {"role": "user", "content": _parts(_text_part("Draw a cat."))}
            ],
            output_messages=[
                {
                    "role": "assistant",
                    "content": _parts(
                        _text_part("Here you go."),
                        _uri_part(
                            image_external, mime_type="image/png", modality="image"
                        ),
                    ),
                }
            ],
            content_refs=[image_internal],
        ),
    ]

    messages = build_chat_messages(spans)
    user = next(m for m in messages if m.type == "user_message")
    assistant = next(m for m in messages if m.type == "assistant_message")

    assert _user_payload(user).content_refs == []
    assert _assistant_payload(assistant).content_refs == [image_internal]


def test_prior_assistant_media_in_input_history_not_attached_to_user() -> None:
    """Regression: a multi-turn turn replays the prior assistant turn — audio
    and all — into its ``input_messages`` as an assistant-role message. That
    echoed model-generated media must NOT surface as the user's attachment.

    Direction is the message *role*, not its input/output position: both the
    echoed assistant audio and the user's own audio live in this span's
    ``input_messages``, but only the user-role one belongs to the user. This is
    the OpenAI Realtime conversations bug — turn 2's user bubble showed turn 1's
    assistant audio clip.
    """
    user_audio_internal = "weave-trace-internal:///PID/object/Content:USERAUDIO"
    user_audio_external = "weave:///e/p/object/Content:USERAUDIO"
    asst_audio_internal = "weave-trace-internal:///PID/object/Content:ASSTAUDIO"
    asst_audio_external = "weave:///e/p/object/Content:ASSTAUDIO"
    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            agent_name="voice-agent",
            input_messages=[
                {"role": "user", "content": _parts(_text_part("And after that?"))}
            ],
        ),
        _span(
            span_id="chat",
            parent_span_id="agent",
            operation_name="chat",
            # The prior assistant turn is replayed as history (assistant role),
            # followed by the current user turn (user role) with its own audio.
            input_messages=[
                {
                    "role": "assistant",
                    "content": _parts(
                        _text_part("It's foggy."), _uri_part(asst_audio_external)
                    ),
                },
                {
                    "role": "user",
                    "content": _parts(
                        _text_part("And after that?"),
                        _uri_part(user_audio_external),
                    ),
                },
            ],
            output_messages=[
                {"role": "assistant", "content": _parts(_text_part("Clearing up."))}
            ],
            content_refs=[asst_audio_internal, user_audio_internal],
        ),
    ]

    messages = build_chat_messages(spans)
    user = next(m for m in messages if m.type == "user_message")

    # Only the user's own audio attaches; the echoed assistant audio does not.
    assert _user_payload(user).content_refs == [user_audio_internal]
    assert asst_audio_internal not in _user_payload(user).content_refs


def test_content_ref_without_inline_part_is_not_attached() -> None:
    """A `content_refs` entry with no matching inline message part has no
    direction signal, so it attaches to neither bubble — only refs anchored to
    an input/output part are surfaced (documents the deliberate pre-GA break
    away from the undirected flat list).
    """
    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            agent_name="bot",
            input_messages=[{"role": "user", "content": "hello"}],
            output_messages=[{"role": "assistant", "content": "hi"}],
            content_refs=["weave-trace-internal:///PID/object/Content:ORPHAN"],
        ),
    ]

    messages = build_chat_messages(spans)
    user = next(m for m in messages if m.type == "user_message")
    assistant = next(m for m in messages if m.type == "assistant_message")
    assert _user_payload(user).content_refs == []
    assert _assistant_payload(assistant).content_refs == []


def test_realtime_multi_turn_in_one_trace_renders_each_user_turn() -> None:
    """Regression (OpenAI Realtime): a whole voice session is ONE trace with
    one chat span per turn. Each turn's user message must render with its OWN
    audio — not collapse to a single leading bubble holding every turn's audio.

    Each chat span's input replays the prior thread and ends with that turn's
    new user message; output is that turn's assistant reply. Media is matched
    per message from the inline part digest to the span's internal content_refs.
    """

    def at(sec: int) -> datetime.datetime:
        return datetime.datetime(2026, 1, 1, 0, 0, sec, tzinfo=datetime.timezone.utc)

    def ext(d: str) -> str:
        return f"weave:///e/p/object/Content:{d}"

    def intl(d: str) -> str:
        return f"weave-trace-internal:///PID/object/Content:{d}"

    def u(text: str, d: str) -> dict:
        return {"role": "user", "content": _parts(_text_part(text), _uri_part(ext(d)))}

    def a(text: str, d: str) -> dict:
        return {
            "role": "assistant",
            "content": _parts(_text_part(text), _uri_part(ext(d))),
        }

    spans = [
        _span(
            span_id="agent",
            operation_name="invoke_agent",
            agent_name="openai_realtime",
            started_at=at(0),
        ),
        _span(
            span_id="c1",
            parent_span_id="agent",
            operation_name="chat",
            started_at=at(1),
            input_messages=[u("Hello", "U1")],
            output_messages=[a("Hi there!", "A1")],
            content_refs=[intl("U1"), intl("A1")],
        ),
        _span(
            span_id="c2",
            parent_span_id="agent",
            operation_name="chat",
            started_at=at(3),
            input_messages=[
                u("Hello", "U1"),
                a("Hi there!", "A1"),
                u("Tell me a fact.", "U2"),
            ],
            output_messages=[a("Oceans cover 70%.", "A2")],
            content_refs=[intl("U1"), intl("A1"), intl("U2"), intl("A2")],
        ),
        _span(
            span_id="c3",
            parent_span_id="agent",
            operation_name="chat",
            started_at=at(5),
            input_messages=[
                u("Hello", "U1"),
                a("Hi there!", "A1"),
                u("Tell me a fact.", "U2"),
                a("Oceans cover 70%.", "A2"),
                u("Thanks!", "U3"),
            ],
            output_messages=[a("Anytime!", "A3")],
            content_refs=[
                intl("U1"),
                intl("A1"),
                intl("U2"),
                intl("A2"),
                intl("U3"),
                intl("A3"),
            ],
        ),
    ]

    messages = build_chat_messages(spans)
    users = [m for m in messages if m.type == "user_message"]
    assistants = [m for m in messages if m.type == "assistant_message"]

    # All three user turns render, each with only its own audio.
    assert [_user_payload(m).text for m in users] == [
        "Hello",
        "Tell me a fact.",
        "Thanks!",
    ]
    assert [_user_payload(m).content_refs for m in users] == [
        [intl("U1")],
        [intl("U2")],
        [intl("U3")],
    ]
    # Assistants keep their own audio (already per-span correct).
    assert [_assistant_payload(m).content_refs for m in assistants] == [
        [intl("A1")],
        [intl("A2")],
        [intl("A3")],
    ]
    # User/assistant alternate in order across the single trace.
    chat_types = {"user_message", "assistant_message"}
    assert [m.type for m in messages if m.type in chat_types] == [
        "user_message",
        "assistant_message",
        "user_message",
        "assistant_message",
        "user_message",
        "assistant_message",
    ]


def test_consecutive_user_messages_each_render_with_own_media() -> None:
    """A turn can be several user messages in a row (no alternation). The
    trailing run is all of them, and each renders as its own bubble keeping its
    own media — not a single collapsed bubble that re-groups the audio.
    """

    def ext(d: str) -> str:
        return f"weave:///e/p/object/Content:{d}"

    def intl(d: str) -> str:
        return f"weave-trace-internal:///PID/object/Content:{d}"

    spans = [
        _span(
            span_id="chat",
            operation_name="chat",
            input_messages=[
                {
                    "role": "user",
                    "content": _parts(_text_part("first"), _uri_part(ext("M1"))),
                },
                {"role": "assistant", "content": _parts(_text_part("ok"))},
                # Two user messages in a row before the response.
                {
                    "role": "user",
                    "content": _parts(_text_part("second"), _uri_part(ext("M2"))),
                },
                {
                    "role": "user",
                    "content": _parts(_text_part("third"), _uri_part(ext("M3"))),
                },
            ],
            output_messages=[
                {"role": "assistant", "content": _parts(_text_part("reply"))}
            ],
            content_refs=[intl("M1"), intl("M2"), intl("M3")],
        ),
    ]

    users = [m for m in build_chat_messages(spans) if m.type == "user_message"]
    # Only the trailing run ("second", "third") is this span's new turn; the
    # earlier "first" (before the assistant) is history and is not re-emitted.
    assert [_user_payload(m).text for m in users] == ["second", "third"]
    assert [_user_payload(m).content_refs for m in users] == [
        [intl("M2")],
        [intl("M3")],
    ]


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


def _nest_in_lists(value: object, levels: int) -> object:
    """Wrap ``value`` in ``levels`` nested single-element lists.

    Each list level costs one ``_iter_internal_refs`` recursive descent, so the
    ref sits exactly ``levels`` deep — a deterministic knob for the depth cap.
    """
    nested = value
    for _ in range(levels):
        nested = [nested]
    return nested


def test_iter_internal_refs_finds_refs_at_normal_depth() -> None:
    """A realistically nested inline part (message dict -> content JSON ->
    parts list -> image_url dict -> url string) is well within the cap, so the
    internal ref is still surfaced exactly as before.
    """
    image_internal = "weave-trace-internal:///PID/object/image-abcd.png:IMGDIGEST"
    message = {
        "role": "user",
        "content": _parts(
            _text_part("What is in this image?"),
            {"type": "image_url", "image_url": {"url": image_internal}},
        ),
        "finish_reason": "",
    }
    assert list(_iter_internal_refs(message)) == [image_internal]


def test_iter_internal_refs_caps_recursion_on_deeply_nested_payload() -> None:
    """A pathologically deep payload terminates without ``RecursionError``.

    The recursion limit is dwarfed by the nesting depth, so an uncapped walk
    would blow the interpreter stack. With the cap in place the walk returns
    cleanly; refs at the cap boundary are surfaced and deeper refs are dropped.
    """
    ref = "weave-trace-internal:///PID/object/deep:DIGEST"

    # A ref sitting exactly at the cap is still found; one level deeper is not.
    assert list(_iter_internal_refs(_nest_in_lists(ref, _MAX_REF_SEARCH_DEPTH))) == [
        ref
    ]
    assert (
        list(_iter_internal_refs(_nest_in_lists(ref, _MAX_REF_SEARCH_DEPTH + 1))) == []
    )

    # Far beyond sys.getrecursionlimit(): must not raise, must yield nothing.
    pathological = _nest_in_lists(ref, sys.getrecursionlimit() * 2)
    assert list(_iter_internal_refs(pathological)) == []
