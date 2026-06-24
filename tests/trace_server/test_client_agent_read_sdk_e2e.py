"""End-to-end validation of the WeaveClient agent read SDK methods.

Unlike test_client_agent_read_sdk.py (which captures requests via a fake
server), this drives the real ClickHouse trace server: it inserts agent spans
and exercises every SDK method against the real query engine, proving the full
round-trip — including that the get_agent_spans `agent_name` shortcut actually
filters server-side.
"""

from __future__ import annotations

import datetime
import uuid

from tests.trace_server.test_genai_agent_queries import _insert_spans, _make_span
from weave.trace.weave_client import WeaveClient


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

    # get_agent_spans: all spans for the project.
    all_spans = client.get_agent_spans()
    assert all_spans.total_count == 3
    assert {s.agent_name for s in all_spans.spans} == {"planner", "researcher"}

    # get_agent_spans: the agent_name shortcut must filter server-side.
    planner_spans = client.get_agent_spans(agent_name="planner")
    assert planner_spans.total_count == 2
    assert all(s.agent_name == "planner" for s in planner_spans.spans)

    # get_agents: aggregated per-agent stats.
    agents = client.get_agents()
    assert {a.agent_name for a in agents.agents} == {"planner", "researcher"}
    planner = next(a for a in agents.agents if a.agent_name == "planner")
    assert planner.span_count == 2

    # get_agents: filtered by agent_name.
    researcher_only = client.get_agents(agent_name="researcher")
    assert {a.agent_name for a in researcher_only.agents} == {"researcher"}

    # get_agent_versions: per-version stats for one agent.
    versions = client.get_agent_versions(agent_name="planner")
    assert {v.agent_version for v in versions.versions} == {"v1", "v2"}

    # get_agent_turn: structured chat view for a single trace.
    turn = client.get_agent_turn(trace_id=planner_trace)
    assert turn.trace_id == planner_trace

    # get_agent_turns: multi-turn view for a conversation.
    turns = client.get_agent_turns(conversation_id=conversation)
    assert turns.conversation_id == conversation
    assert turns.total_turns >= 1
