"""Integration tests for GenAI agent tables and query layer.

Requires ClickHouse backend (auto-skips on SQLite via ch_server fixture).
Migration 030 creates the genai tables automatically.
"""

import base64
import datetime
import uuid

from weave.trace_server.agents.helpers import (
    extract_search_rows,
    genai_search_row_to_row,
    genai_span_to_row,
)
from weave.trace_server.agents.schema import (
    ALL_SEARCH_INSERT_COLUMNS,
    ALL_SPAN_INSERT_COLUMNS,
    AgentSpanCHInsertable,
    NormalizedMessage,
)
from weave.trace_server.agents.types import (
    AgentGroupByRef,
    AgentSearchReq,
    AgentSpansQueryFilters,
    AgentSpansQueryReq,
    AgentsQueryReq,
)


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
    """Insert spans directly into spans."""
    rows = [genai_span_to_row(s) for s in spans]
    ch_client.insert(
        "spans",
        data=rows,
        column_names=ALL_SPAN_INSERT_COLUMNS,
    )


def _insert_search_rows(ch_client, spans: list[AgentSpanCHInsertable]) -> None:
    """Extract and insert message search rows from spans."""
    all_rows = []
    for s in spans:
        all_rows.extend(genai_search_row_to_row(sr) for sr in extract_search_rows(s))
    if all_rows:
        ch_client.insert(
            "message_search",
            data=all_rows,
            column_names=ALL_SEARCH_INSERT_COLUMNS,
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
            filters=AgentSpansQueryFilters(agent_name="agent-A"),
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
            filters=AgentSpansQueryFilters(),
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
    assert "agent-x" in by_conv[conv_a].agent_names

    assert by_conv[conv_b].span_count == 1
    assert "agent-y" in by_conv[conv_b].agent_names


# ---------------------------------------------------------------------------
# Test: group by a custom_attrs map key (the new capability)
# ---------------------------------------------------------------------------


def test_group_by_custom_attrs(ch_server):
    """Grouping on a custom_attrs key buckets spans by the user-supplied label."""
    project_id = _make_project_id("cattr")
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    spans = [
        _make_span(
            project_id,
            agent_name="a1",
            custom_attrs={"env": "prod"},
            input_tokens=100,
            started_at=now,
        ),
        _make_span(
            project_id,
            agent_name="a1",
            custom_attrs={"env": "prod"},
            input_tokens=200,
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            agent_name="a1",
            custom_attrs={"env": "staging"},
            input_tokens=50,
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    res = ch_server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=project_id,
            group_by=[
                AgentGroupByRef(source="custom_attrs", key="env"),
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


# ---------------------------------------------------------------------------
# Test: Message search
# ---------------------------------------------------------------------------


def test_message_search(ch_server):
    """End-to-end LIKE search on the message_search table returns expected rows.

    Note: this does not assert the tokenbf_v1 skip index is actually used —
    verifying index selection would require EXPLAIN output or query metrics.
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
    _insert_search_rows(ch_server.ch_client, spans)

    # Search for "quantum" — should match 1 message
    res = ch_server.agent_search(AgentSearchReq(project_id=project_id, query="quantum"))
    assert res.total_conversations >= 1
    matched = res.results[0]
    assert "quantum" in matched.matched_messages[0].content_preview.lower()

    # Search for "xyznonexistent" — should match nothing
    res_empty = ch_server.agent_search(
        AgentSearchReq(project_id=project_id, query="xyznonexistent")
    )
    assert res_empty.total_conversations == 0
