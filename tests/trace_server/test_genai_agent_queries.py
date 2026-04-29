"""Integration tests for GenAI agent tables and query layer.

Requires ClickHouse backend (auto-skips on SQLite via ch_server fixture).
Migration 030 creates the genai tables automatically.
"""

import base64
import datetime
import uuid

from weave.trace_server.agents.helpers import genai_span_to_row
from weave.trace_server.agents.schema import (
    ALL_SPAN_INSERT_COLUMNS,
    AgentSpanCHInsertable,
    NormalizedMessage,
)
from weave.trace_server.agents.types import (
    AgentConversationChatReq,
    AgentGroupByRef,
    AgentSearchReq,
    AgentSpansQueryReq,
    AgentsQueryReq,
)
from weave.trace_server.interface.query import Query


def _make_project_id(prefix: str) -> str:
    raw = f"test/{prefix}_{uuid.uuid4().hex[:8]}"
    return base64.b64encode(raw.encode()).decode()


def _make_span(project_id: str, **overrides: object) -> AgentSpanCHInsertable:
    """Create a span with sensible defaults. Override any field via kwargs."""
    defaults = {
        "project_id": project_id,
        "trace_id": uuid.uuid4().hex,
        "span_id": uuid.uuid4().hex,
        "span_name": "test-span",
        "started_at": datetime.datetime.now(tz=datetime.timezone.utc),
        "ended_at": datetime.datetime.now(tz=datetime.timezone.utc),
        "status_code": "OK",
        "operation_name": "chat",
        "agent_name": "test-agent",
        "provider_name": "openai",
        "request_model": "gpt-4o",
        "input_tokens": 100,
        "output_tokens": 50,
    }
    defaults.update(overrides)
    return AgentSpanCHInsertable(**defaults)


def _insert_spans(ch_client, spans: list[AgentSpanCHInsertable]) -> None:
    """Insert spans. The `messages` MV populates the search index as a
    side effect of this insert.
    """
    rows = [genai_span_to_row(s) for s in spans]
    ch_client.insert(
        "spans",
        data=rows,
        column_names=ALL_SPAN_INSERT_COLUMNS,
    )


# ---------------------------------------------------------------------------
# Test: ungrouped spans query
# ---------------------------------------------------------------------------


def test_spans_insert_and_query(ch_server):
    """Insert spans and query with filters (ungrouped mode)."""
    project_id = _make_project_id("spans")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(project_id, agent_name="agent-A", started_at=now),
        _make_span(
            project_id,
            agent_name="agent-A",
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            agent_name="agent-B",
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    # Query all
    res = ch_server.agent_spans_query(AgentSpansQueryReq(project_id=project_id))
    assert res.total_count == 3
    assert len(res.spans) == 3
    assert res.groups == []

    # Filter by agent_name
    res_filtered = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            query=Query.model_validate(
                {
                    "$expr": {
                        "$eq": [
                            {"$getField": "agent.name"},
                            {"$literal": "agent-A"},
                        ]
                    }
                }
            ),
        )
    )
    assert res_filtered.total_count == 2
    assert all(s.agent_name == "agent-A" for s in res_filtered.spans)


# ---------------------------------------------------------------------------
# Test: group by trace_id (replaces old traces_query)
# ---------------------------------------------------------------------------


def test_group_by_trace_id(ch_server):
    """Grouping spans by trace_id returns per-trace aggregates."""
    project_id = _make_project_id("traces")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    trace_a = uuid.uuid4().hex
    trace_b = uuid.uuid4().hex

    spans = [
        # Trace A: 2 spans, 300 input tokens total
        _make_span(
            project_id,
            trace_id=trace_a,
            input_tokens=100,
            output_tokens=20,
            agent_name="alpha",
            started_at=now,
        ),
        _make_span(
            project_id,
            trace_id=trace_a,
            input_tokens=200,
            output_tokens=30,
            agent_name="alpha",
            started_at=now + datetime.timedelta(seconds=1),
        ),
        # Trace B: 1 span
        _make_span(
            project_id,
            trace_id=trace_b,
            input_tokens=50,
            output_tokens=10,
            agent_name="beta",
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            group_by=[AgentGroupByRef(source="column", key="trace_id")],
        )
    )
    assert res.total_count == 2
    assert res.spans == []

    by_trace = {g.group_keys["trace_id"]: g for g in res.groups}
    assert by_trace[trace_a].span_count == 2
    assert by_trace[trace_a].total_input_tokens == 300
    assert by_trace[trace_a].total_output_tokens == 50
    assert "alpha" in by_trace[trace_a].agent_names

    assert by_trace[trace_b].span_count == 1
    assert by_trace[trace_b].total_input_tokens == 50


# ---------------------------------------------------------------------------
# Test: group by conversation_id (replaces old conversations_query)
# ---------------------------------------------------------------------------


def test_group_by_conversation_id(ch_server):
    """Grouping spans by conversation_id returns per-conversation aggregates."""
    project_id = _make_project_id("convs")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    conv_a = f"conv-{uuid.uuid4().hex[:8]}"
    conv_b = f"conv-{uuid.uuid4().hex[:8]}"

    spans = [
        _make_span(
            project_id,
            conversation_id=conv_a,
            conversation_name="Alpha Chat",
            operation_name="invoke_agent",
            agent_name="agent-x",
            started_at=now,
        ),
        _make_span(
            project_id,
            conversation_id=conv_a,
            conversation_name="Alpha Chat",
            operation_name="chat",
            agent_name="agent-x",
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            conversation_id=conv_b,
            conversation_name="Beta Chat",
            operation_name="invoke_agent",
            agent_name="agent-y",
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            group_by=[AgentGroupByRef(source="column", key="conversation_id")],
        )
    )
    # Only inserted rows have our conversation_ids, but project may include
    # a row with the default empty conversation_id from other tests; guard
    # by filtering to the conversation_ids we actually created.
    by_conv = {g.group_keys["conversation_id"]: g for g in res.groups}
    assert conv_a in by_conv
    assert conv_b in by_conv

    assert by_conv[conv_a].span_count == 2
    assert by_conv[conv_a].invocation_count == 1  # one invoke_agent span
    assert "agent-x" in by_conv[conv_a].agent_names
    assert "Alpha Chat" in by_conv[conv_a].conversation_names

    assert by_conv[conv_b].span_count == 1
    assert by_conv[conv_b].invocation_count == 1
    assert "agent-y" in by_conv[conv_b].agent_names
    assert "Beta Chat" in by_conv[conv_b].conversation_names


# ---------------------------------------------------------------------------
# Test: group by a custom_attrs_string map key (the new capability)
# ---------------------------------------------------------------------------


def test_group_by_custom_attrs(ch_server):
    """Grouping on a custom_attrs_string key buckets spans by the user-supplied label."""
    project_id = _make_project_id("cattr")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            agent_name="a1",
            custom_attrs_string={"env": "prod"},
            input_tokens=100,
            started_at=now,
        ),
        _make_span(
            project_id,
            agent_name="a1",
            custom_attrs_string={"env": "prod"},
            input_tokens=200,
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            agent_name="a1",
            custom_attrs_string={"env": "staging"},
            input_tokens=50,
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            group_by=[
                AgentGroupByRef(source="custom_attrs_string", key="env"),
            ],
        )
    )
    by_env = {g.group_keys["env"]: g for g in res.groups}
    assert by_env["prod"].span_count == 2
    assert by_env["prod"].total_input_tokens == 300
    assert by_env["staging"].span_count == 1
    assert by_env["staging"].total_input_tokens == 50


# ---------------------------------------------------------------------------
# Test: Agents MV aggregation
# ---------------------------------------------------------------------------


def test_agents_mv_aggregation(ch_server):
    """AggregatingMergeTree MV populates agents on insert."""
    project_id = _make_project_id("agents")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            agent_name="mv-agent",
            operation_name="invoke_agent",
            input_tokens=100,
            output_tokens=50,
            started_at=now,
        ),
        _make_span(
            project_id,
            agent_name="mv-agent",
            operation_name="chat",
            input_tokens=200,
            output_tokens=80,
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            agent_name="mv-agent",
            operation_name="invoke_agent",
            input_tokens=150,
            output_tokens=60,
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_agents_query(AgentsQueryReq(project_id=project_id))
    assert len(res.agents) == 1

    agent = res.agents[0]
    assert agent.agent_name == "mv-agent"
    # 2 invoke_agent spans
    assert agent.invocation_count == 2
    # 3 total spans
    assert agent.span_count == 3
    assert agent.total_input_tokens == 450
    assert agent.total_output_tokens == 190


def test_agents_mv_zero_duration_when_ended_at_unset(ch_server):
    """A span inserted without ended_at (defaults to epoch) must contribute
    0 to total_duration_ms rather than wrapping via UInt64 cast to ~2^64.

    Before the fix, `toUInt64(toUnixTimestamp64Milli(ended_at) -
    toUnixTimestamp64Milli(started_at))` on an epoch ended_at produced
    18446742296979951616 and permanently poisoned the aggregate.
    """
    project_id = _make_project_id("dur_guard")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    # ended_at omitted — schema default is epoch. started_at is real.
    unset = AgentSpanCHInsertable(
        project_id=project_id,
        trace_id=uuid.uuid4().hex,
        span_id=uuid.uuid4().hex,
        span_name="unset-end",
        started_at=now,
        status_code="OK",
        operation_name="invoke_agent",
        agent_name="dur-guard-agent",
        input_tokens=10,
        output_tokens=5,
    )
    # A well-formed span that should contribute real duration to the rollup.
    finished = _make_span(
        project_id,
        agent_name="dur-guard-agent",
        operation_name="invoke_agent",
        input_tokens=20,
        output_tokens=10,
        started_at=now,
        ended_at=now + datetime.timedelta(milliseconds=150),
    )
    _insert_spans(ch_server.ch_client, [unset, finished])

    res = ch_server.agent_agents_query(AgentsQueryReq(project_id=project_id))
    assert len(res.agents) == 1
    agent = res.agents[0]
    # Only the well-formed span contributes; unset span contributes 0.
    # The exact ms depends on clock granularity, but must be within a
    # human-reasonable range — crucially NOT the 2^64 wrap value.
    assert 0 < agent.total_duration_ms < 10_000
    # Tokens are still summed across both spans (30 + 0-token unset span had 10
    # inputs / 5 outputs).
    assert agent.total_input_tokens == 30
    assert agent.total_output_tokens == 15


# ---------------------------------------------------------------------------
# Test: Conversation chat pagination
# ---------------------------------------------------------------------------


def test_conversation_chat_paginates_turns(ch_server):
    """Conversation chat returns the latest turn page plus pagination metadata."""
    project_id = _make_project_id("conv_chat")
    conversation_id = f"conv-{uuid.uuid4().hex[:8]}"
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    trace_ids = [uuid.uuid4().hex for _ in range(3)]

    spans = []
    for i, trace_id in enumerate(trace_ids):
        started_at = now + datetime.timedelta(minutes=i)
        spans.append(
            _make_span(
                project_id,
                trace_id=trace_id,
                conversation_id=conversation_id,
                operation_name="invoke_agent",
                agent_name="chat-agent",
                input_messages=[NormalizedMessage(role="user", content=f"turn {i}")],
                started_at=started_at,
                ended_at=started_at + datetime.timedelta(seconds=1),
            )
        )
    _insert_spans(ch_server.ch_client, spans)

    first_page = ch_server.agent_conversation_chat(
        AgentConversationChatReq(
            project_id=project_id,
            conversation_id=conversation_id,
            limit=2,
        )
    )
    assert first_page.total_turns == 3
    assert first_page.has_more is True
    assert first_page.limit == 2
    assert first_page.offset == 0
    # Page zero preserves the old default: latest turns, returned
    # chronologically within the selected page.
    assert [turn.trace_id for turn in first_page.turns] == trace_ids[1:]

    second_page = ch_server.agent_conversation_chat(
        AgentConversationChatReq(
            project_id=project_id,
            conversation_id=conversation_id,
            limit=2,
            offset=2,
        )
    )
    assert second_page.total_turns == 3
    assert second_page.has_more is False
    assert second_page.limit == 2
    assert second_page.offset == 2
    assert [turn.trace_id for turn in second_page.turns] == [trace_ids[0]]


def test_conversation_chat_includes_child_spans_without_conversation_id(ch_server):
    """Conversation membership is trace-scoped after selecting conversation turns.

    Some producers attach ``conversation_id`` only to the root/invoke span. The
    chat projection still needs child LLM/tool spans in that trace, because
    those children usually carry the assistant text and tool bodies.
    """
    project_id = _make_project_id("conv_chat_children")
    conversation_id = f"conv-{uuid.uuid4().hex[:8]}"
    trace_id = uuid.uuid4().hex
    root_span_id = uuid.uuid4().hex
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            trace_id=trace_id,
            span_id=root_span_id,
            conversation_id=conversation_id,
            operation_name="invoke_agent",
            agent_name="chat-agent",
            input_messages=[NormalizedMessage(role="user", content="hello")],
            input_tokens=0,
            output_tokens=0,
            started_at=now,
            ended_at=now + datetime.timedelta(seconds=3),
        ),
        _make_span(
            project_id,
            trace_id=trace_id,
            parent_span_id=root_span_id,
            operation_name="chat",
            output_messages=[
                NormalizedMessage(role="assistant", content="hello from child")
            ],
            input_tokens=12,
            output_tokens=7,
            started_at=now + datetime.timedelta(seconds=1),
            ended_at=now + datetime.timedelta(seconds=2),
        ),
        _make_span(
            project_id,
            trace_id=trace_id,
            parent_span_id=root_span_id,
            operation_name="execute_tool",
            tool_name="lookup",
            tool_call_arguments='{"query":"hello"}',
            tool_call_result='{"ok":true}',
            input_tokens=0,
            output_tokens=0,
            started_at=now + datetime.timedelta(seconds=2),
            ended_at=now + datetime.timedelta(seconds=3),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_conversation_chat(
        AgentConversationChatReq(
            project_id=project_id,
            conversation_id=conversation_id,
        )
    )

    assert res.total_turns == 1
    assert len(res.turns) == 1
    messages = res.turns[0].messages
    assistant = next(msg for msg in messages if msg.type == "assistant_message")
    tool = next(msg for msg in messages if msg.type == "tool_call")

    assert assistant.assistant_message is not None
    assert assistant.assistant_message.text == "hello from child"
    assert assistant.assistant_message.input_tokens == 12
    assert assistant.assistant_message.output_tokens == 7
    assert tool.tool_call is not None
    assert tool.tool_call.tool_name == "lookup"
    assert tool.tool_call.tool_arguments == '{"query":"hello"}'
    assert tool.tool_call.tool_result == '{"ok":true}'


# ---------------------------------------------------------------------------
# Test: Message search
# ---------------------------------------------------------------------------


def test_message_search(ch_server):
    """End-to-end search against the `messages` table.

    Spans are inserted and the ClickHouse MV populates the search index
    automatically; no Python-side extraction runs. Verifies that content
    LIKE + span-level filters return the expected hits.
    """
    project_id = _make_project_id("search")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            conversation_id="search-conv-1",
            conversation_name="Search Test",
            output_messages=[
                NormalizedMessage(
                    role="assistant",
                    content="The quantum entanglement hypothesis is fascinating.",
                ),
            ],
            started_at=now,
        ),
        _make_span(
            project_id,
            conversation_id="search-conv-1",
            conversation_name="Search Test",
            output_messages=[
                NormalizedMessage(
                    role="assistant",
                    content="Classical mechanics still has many applications.",
                ),
            ],
            started_at=now + datetime.timedelta(seconds=1),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    # Search for "quantum" — should match 1 message
    res = ch_server.agent_search(AgentSearchReq(project_id=project_id, query="quantum"))
    assert len(res.results) >= 1
    matched = res.results[0]
    assert "quantum" in matched.matched_messages[0].content_preview.lower()

    # Search for "xyznonexistent" — should match nothing
    res_empty = ch_server.agent_search(
        AgentSearchReq(project_id=project_id, query="xyznonexistent")
    )
    assert res_empty.results == []


def test_message_search_shared_digest_across_spans(ch_server):
    """Two spans carrying identical output message content should produce
    two rows in `messages` that share a single content_digest — enabling
    read-side dedup via GROUP BY content_digest when desired.
    """
    project_id = _make_project_id("search_dedup")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    repeated = "Identical assistant response across two different spans."
    spans = [
        _make_span(
            project_id,
            conversation_id="dedup-conv-1",
            output_messages=[NormalizedMessage(role="assistant", content=repeated)],
            started_at=now,
        ),
        _make_span(
            project_id,
            conversation_id="dedup-conv-2",
            output_messages=[NormalizedMessage(role="assistant", content=repeated)],
            started_at=now + datetime.timedelta(seconds=1),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_search(
        AgentSearchReq(project_id=project_id, query="Identical assistant")
    )
    # One row per occurrence across two conversations
    total_matches = sum(len(r.matched_messages) for r in res.results)
    assert total_matches == 2
    # Both occurrences share a single content_digest
    digests = {m.content_digest for r in res.results for m in r.matched_messages}
    assert len(digests) == 1


def test_message_search_indexes_tool_calls(ch_server):
    """tool_call_arguments and tool_call_result should each produce a
    searchable occurrence with role 'tool_call' / 'tool_result'.
    """
    project_id = _make_project_id("search_tools")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            conversation_id="tool-conv-1",
            operation_name="execute_tool",
            tool_call_arguments='{"city":"Reykjavík"}',
            tool_call_result='{"temperature":5,"condition":"snowy"}',
            started_at=now,
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    # Hit on the arguments side
    res_args = ch_server.agent_search(
        AgentSearchReq(project_id=project_id, query="Reykjavík")
    )
    assert len(res_args.results) == 1
    assert res_args.results[0].matched_messages[0].role == "tool_call"

    # Hit on the result side
    res_result = ch_server.agent_search(
        AgentSearchReq(project_id=project_id, query="snowy")
    )
    assert len(res_result.results) == 1
    assert res_result.results[0].matched_messages[0].role == "tool_result"

    # UI/back-compat alias: "tool" should include both persisted tool roles.
    res_tool_alias = ch_server.agent_search(
        AgentSearchReq(project_id=project_id, query="Reykjavík", roles=["tool"])
    )
    assert len(res_tool_alias.results) == 1
    assert res_tool_alias.results[0].matched_messages[0].role == "tool_call"


# ---------------------------------------------------------------------------
# Test: Query DSL end-to-end
# ---------------------------------------------------------------------------


def test_query_dsl_combines_semconv_column_and_custom_attr(ch_server):
    """Compile and execute a Mongo-style query mixing a semconv-mapped column
    and an unprefixed custom_attrs_string key dispatched via sibling-literal type.
    """
    project_id = _make_project_id("dsl")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        # alpha / prod — matches
        _make_span(
            project_id,
            agent_name="alpha",
            custom_attrs_string={"env": "prod"},
            started_at=now,
        ),
        # alpha / staging — agent matches but env doesn't
        _make_span(
            project_id,
            agent_name="alpha",
            custom_attrs_string={"env": "staging"},
            started_at=now + datetime.timedelta(seconds=1),
        ),
        # beta / prod — env matches but agent doesn't
        _make_span(
            project_id,
            agent_name="beta",
            custom_attrs_string={"env": "prod"},
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    q = Query.model_validate(
        {
            "$expr": {
                "$and": [
                    {
                        "$eq": [
                            {"$getField": "agent.name"},
                            {"$literal": "alpha"},
                        ]
                    },
                    # `env` is unknown -> falls through to custom_attrs_string
                    # (sibling literal is a str, so the String map).
                    {"$eq": [{"$getField": "env"}, {"$literal": "prod"}]},
                ]
            }
        }
    )
    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, query=q)
    )
    assert res.total_count == 1
    assert len(res.spans) == 1
    assert res.spans[0].agent_name == "alpha"


def test_query_dsl_typed_custom_attr_comparison(ch_server):
    """Int-typed custom attributes route to `custom_attrs_int` via the
    sibling-literal type and compare numerically.
    """
    project_id = _make_project_id("dsl_int")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        # retries=5 — matches > 3
        _make_span(
            project_id,
            custom_attrs_int={"retries": 5},
            started_at=now,
        ),
        # retries=1 — doesn't match
        _make_span(
            project_id,
            custom_attrs_int={"retries": 1},
            started_at=now + datetime.timedelta(seconds=1),
        ),
        # no retries attr — doesn't match
        _make_span(
            project_id,
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    q = Query.model_validate(
        {"$expr": {"$gt": [{"$getField": "retries"}, {"$literal": 3}]}}
    )
    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(project_id=project_id, query=q)
    )
    assert res.total_count == 1
    assert len(res.spans) == 1
