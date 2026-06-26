"""End-to-end validation of the WeaveClient agent read SDK methods.

Unlike test_client_agent_read_sdk.py (which captures requests via a fake
server), this drives the real ClickHouse trace server: it inserts agent spans
and exercises every SDK method against the real query engine, proving the full
round-trip — including that the get_agent_spans `agent_name` shortcut and the
search_agents content match actually run server-side.
"""

from __future__ import annotations

import datetime
import uuid

from tests.trace_server.test_genai_agent_queries import _insert_spans, _make_span
from weave.trace.weave_client import WeaveClient
from weave.trace_server.agents.schema import NormalizedMessage
from weave.trace_server.agents.types import (
    AgentSpanStatsMetricSpec,
    AgentSpanValueRef,
)


def test_agent_read_sdk_end_to_end(ch_server):
    entity = "e2e"
    project = f"agentsdk_{uuid.uuid4().hex[:8]}"
    project_id = f"{entity}/{project}"
    client = WeaveClient(entity, project, ch_server, ensure_project_exists=False)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    planner_trace = uuid.uuid4().hex
    conversation = uuid.uuid4().hex
    spans = [
        _make_span(
            project_id,
            agent_name="planner",
            agent_version="v1",
            operation_name="invoke_agent",
            trace_id=planner_trace,
            conversation_id=conversation,
            input_tokens=100,
            output_tokens=50,
            # message content powers search_agents; custom attr powers the schema.
            output_messages=[
                NormalizedMessage(
                    role="assistant",
                    content="The quantum entanglement hypothesis is fascinating.",
                )
            ],
            custom_attrs_string={"env": "prod"},
            started_at=now,
        ),
        _make_span(
            project_id,
            agent_name="planner",
            agent_version="v2",
            operation_name="chat",
            conversation_id=conversation,
            input_tokens=200,
            output_tokens=80,
            started_at=now + datetime.timedelta(seconds=1),
        ),
        _make_span(
            project_id,
            agent_name="researcher",
            agent_version="v1",
            operation_name="invoke_agent",
            input_tokens=10,
            output_tokens=5,
            started_at=now + datetime.timedelta(seconds=2),
        ),
    ]
    _insert_spans(ch_server.ch_client, spans)

    # get_agent_spans: all spans for the project. (get_agents / get_agent_versions
    # / get_agent_spans return a PaginatedIterator; len() round-trips to the count.)
    all_spans = list(client.get_agent_spans())
    assert len(all_spans) == 3
    assert {s.agent_name for s in all_spans} == {"planner", "researcher"}

    # get_agent_spans: the agent_name shortcut must filter server-side.
    planner_spans = list(client.get_agent_spans(agent_name="planner"))
    assert len(planner_spans) == 2
    assert all(s.agent_name == "planner" for s in planner_spans)

    # get_agents: aggregated per-agent stats.
    agents = list(client.get_agents())
    assert {a.agent_name for a in agents} == {"planner", "researcher"}
    planner = next(a for a in agents if a.agent_name == "planner")
    assert planner.span_count == 2
    # len() reports the server-side total agent count.
    assert len(client.get_agents()) == 2

    # get_agents: filtered by agent_name.
    researcher_only = list(client.get_agents(agent_name="researcher"))
    assert {a.agent_name for a in researcher_only} == {"researcher"}

    # get_agent_versions: per-version stats for one agent.
    versions = list(client.get_agent_versions(agent_name="planner"))
    assert {v.agent_version for v in versions} == {"v1", "v2"}

    # get_agent_turn: structured chat view for a single trace.
    turn = client.get_agent_turn(trace_id=planner_trace)
    assert turn.trace_id == planner_trace

    # get_agent_turns: multi-turn view for a conversation.
    turns = client.get_agent_turns(conversation_id=conversation)
    assert turns.conversation_id == conversation
    assert turns.total_turns >= 1

    # get_agent_span_stats: metric aggregation summed across time buckets.
    stats = client.get_agent_span_stats(
        start=now - datetime.timedelta(hours=1),
        end=now + datetime.timedelta(hours=1),
        metrics=[
            AgentSpanStatsMetricSpec(
                alias="input_tokens",
                value_type="number",
                value=AgentSpanValueRef(source="field", key="usage.input_tokens"),
                aggregations=["sum"],
            )
        ],
    )
    metric_cols = [c.name for c in stats.columns if c.role == "metric"]
    assert metric_cols, stats.columns
    total_input_tokens = sum(row[metric_cols[0]] or 0 for row in stats.rows)
    assert total_input_tokens == 310  # 100 + 200 + 10

    # get_agent_custom_attributes: discovers the typed custom-attr keys.
    schema = client.get_agent_custom_attributes()
    assert ("custom_attrs_string", "env") in {
        (a.source, a.key) for a in schema.attributes
    }

    # search_agents: full-text search over message content, run server-side.
    found = client.search_agents(query="quantum")
    assert len(found.results) >= 1
    assert "quantum" in found.results[0].matched_messages[0].content_preview.lower()
    assert client.search_agents(query="xyznonexistent").results == []
