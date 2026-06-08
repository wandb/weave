"""Tests for the agent visibility (hide/unhide) feature.

Requires ClickHouse (auto-skips on SQLite via the `ch_server` fixture).
"""

from tests.trace_server.helpers import make_project_id as _make_project_id
from weave.trace_server.agents.types import AgentVisibilityReq


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
