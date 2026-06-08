"""Tests for the agent visibility (hide/unhide) feature.

Requires ClickHouse (auto-skips on SQLite via the `ch_server` fixture).
"""

import datetime
import uuid

from tests.trace_server.helpers import make_project_id as _make_project_id
from weave.trace_server.agents.helpers import genai_span_to_row
from weave.trace_server.agents.schema import (
    ALL_SPAN_INSERT_COLUMNS,
    AgentSpanCHInsertable,
)
from weave.trace_server.agents.types import (
    AgentsQueryFilters,
    AgentsQueryReq,
    AgentVisibilityReq,
)


def _current_hidden(ch_client, project_id: str, agent_name: str):
    """Resolve current is_hidden via the argMax read pattern.

    Mirrors how the read filter resolves state from the `hidden_agents`
    ReplacingMergeTree without `FINAL`: the latest row by `updated_at` wins.
    Returns None if the agent has no visibility row.
    """
    rows = ch_client.query(
        "SELECT argMax(is_hidden, updated_at) "
        "FROM hidden_agents "
        "WHERE project_id = {pid:String} AND agent_name = {an:String} "
        "GROUP BY agent_name",
        parameters={"pid": project_id, "an": agent_name},
    ).result_rows
    return rows[0][0] if rows else None


def test_set_visibility_persists_state(ch_server) -> None:
    """agent_set_visibility writes is_hidden and echoes the applied state."""
    project_id = _make_project_id("vis-write")

    res = ch_server.agent_set_visibility(
        AgentVisibilityReq(project_id=project_id, agent_name="a", hidden=True)
    )
    assert res.hidden is True

    # Correct column mapping: hidden -> is_hidden=true.
    assert _current_hidden(ch_server.ch_client, project_id, "a") is True


def test_set_visibility_toggle_latest_write_wins(ch_server) -> None:
    """Unhiding after hiding wins via updated_at (ReplacingMergeTree semantics)."""
    project_id = _make_project_id("vis-write-toggle")

    ch_server.agent_set_visibility(
        AgentVisibilityReq(project_id=project_id, agent_name="a", hidden=True)
    )
    res = ch_server.agent_set_visibility(
        AgentVisibilityReq(project_id=project_id, agent_name="a", hidden=False)
    )
    assert res.hidden is False

    assert _current_hidden(ch_server.ch_client, project_id, "a") is False


# ---------------------------------------------------------------------------
# Read-filter behaviour (end-to-end: write path + agent_agents_query)
# ---------------------------------------------------------------------------


def _make_span(project_id: str, **overrides: object) -> AgentSpanCHInsertable:
    """Build a span with sensible defaults; override any field via kwargs."""
    defaults: dict[str, object] = {
        "project_id": project_id,
        "trace_id": uuid.uuid4().hex,
        "span_id": uuid.uuid4().hex,
        "span_name": "test-span",
        "started_at": datetime.datetime.now(tz=datetime.timezone.utc),
        "ended_at": datetime.datetime.now(tz=datetime.timezone.utc),
        "status_code": "OK",
        "operation_name": "chat",
        "agent_name": "test-agent",
        "input_tokens": 100,
        "output_tokens": 50,
    }
    defaults.update(overrides)
    return AgentSpanCHInsertable(**defaults)


def _insert_spans(ch_client, spans: list[AgentSpanCHInsertable]) -> None:
    ch_client.insert(
        "spans",
        data=[genai_span_to_row(s) for s in spans],
        column_names=ALL_SPAN_INSERT_COLUMNS,
    )


def test_hidden_agent_excluded_by_default(ch_server) -> None:
    """A hidden agent drops out of the default list and the total_count."""
    project_id = _make_project_id("vis-excl")
    _insert_spans(
        ch_server.ch_client,
        [
            _make_span(project_id, agent_name="visible"),
            _make_span(project_id, agent_name="secret"),
        ],
    )

    res = ch_server.agent_agents_query(AgentsQueryReq(project_id=project_id))
    assert {a.agent_name for a in res.agents} == {"visible", "secret"}
    assert res.total_count == 2

    ch_server.agent_set_visibility(
        AgentVisibilityReq(project_id=project_id, agent_name="secret", hidden=True)
    )

    res = ch_server.agent_agents_query(AgentsQueryReq(project_id=project_id))
    assert [a.agent_name for a in res.agents] == ["visible"]
    assert res.total_count == 1
    assert res.agents[0].hidden is False


def test_include_hidden_returns_with_flag_and_unchanged_counts(ch_server) -> None:
    """include_hidden surfaces hidden agents with hidden=True; counts are intact.

    The hidden_agents tombstone never touches the agents AMT, so aggregated
    counts for a hidden agent are exactly what they were before hiding.
    """
    project_id = _make_project_id("vis-incl")
    _insert_spans(
        ch_server.ch_client,
        [
            _make_span(
                project_id,
                agent_name="secret",
                operation_name="invoke_agent",
                input_tokens=100,
                output_tokens=50,
            ),
            _make_span(
                project_id,
                agent_name="secret",
                operation_name="chat",
                input_tokens=10,
                output_tokens=5,
            ),
        ],
    )
    ch_server.agent_set_visibility(
        AgentVisibilityReq(project_id=project_id, agent_name="secret", hidden=True)
    )

    res = ch_server.agent_agents_query(
        AgentsQueryReq(
            project_id=project_id,
            filters=AgentsQueryFilters(include_hidden=True),
        )
    )
    by_name = {a.agent_name: a for a in res.agents}
    assert by_name["secret"].hidden is True
    assert by_name["secret"].span_count == 2
    assert by_name["secret"].total_input_tokens == 110
    assert by_name["secret"].invocation_count == 1


def test_hide_unhide_round_trip(ch_server) -> None:
    """Unhiding restores the agent to the default list (reversible toggle)."""
    project_id = _make_project_id("vis-rt")
    _insert_spans(ch_server.ch_client, [_make_span(project_id, agent_name="a")])

    ch_server.agent_set_visibility(
        AgentVisibilityReq(project_id=project_id, agent_name="a", hidden=True)
    )
    assert (
        ch_server.agent_agents_query(AgentsQueryReq(project_id=project_id)).agents == []
    )

    ch_server.agent_set_visibility(
        AgentVisibilityReq(project_id=project_id, agent_name="a", hidden=False)
    )
    res = ch_server.agent_agents_query(AgentsQueryReq(project_id=project_id))
    assert [a.agent_name for a in res.agents] == ["a"]
    assert res.agents[0].hidden is False


def test_hiding_one_agent_leaves_others_visible(ch_server) -> None:
    """Visibility is per (project, agent): hiding one does not affect another."""
    project_id = _make_project_id("vis-iso")
    _insert_spans(
        ch_server.ch_client,
        [
            _make_span(project_id, agent_name="a"),
            _make_span(project_id, agent_name="b"),
        ],
    )

    ch_server.agent_set_visibility(
        AgentVisibilityReq(project_id=project_id, agent_name="a", hidden=True)
    )

    res = ch_server.agent_agents_query(AgentsQueryReq(project_id=project_id))
    assert {a.agent_name for a in res.agents} == {"b"}
