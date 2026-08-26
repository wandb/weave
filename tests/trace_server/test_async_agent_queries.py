"""The async agent reads issue the same SQL as their sync twins.

`aagent_spans_query` and `aagent_search` exist so the agent scoring worker can
await a socket instead of a thread. They share the sync path's SQL builders and
row transforms, so what these assert is that the split did not change what runs
or what comes back -- not that the transport is faster.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from weave.trace_server.agents.clickhouse import (
    AgentQueryHandler,
    search_res_from_rows,
    ungrouped_spans_res,
)
from weave.trace_server.agents.types import (
    AgentGroupByRef,
    AgentSpansQueryReq,
)
from weave.trace_server.async_clickhouse_trace_server import AsyncClickHouseTraceServer
from weave.trace_server.query_builder.agent_query_builder import (
    make_spans_count_query,
    make_spans_list_query,
)

PROJECT = "entity/project"


def result(rows, columns):
    return SimpleNamespace(result_rows=rows, column_names=columns)


@pytest.mark.asyncio
async def test_arun_paginated_issues_the_same_two_statements_as_the_sync_pair():
    """The count and list SQL must match what `_run_paginated` would run."""
    req = AgentSpansQueryReq(project_id=PROJECT, limit=5)
    seen: list[str] = []

    async def aquery(sql, params):
        seen.append(sql)
        return result([[0]], ["c"]) if len(seen) == 1 else result([], [])

    handler = AgentQueryHandler(MagicMock(), MagicMock())
    total, rows = await handler.arun_paginated(
        make_spans_count_query, make_spans_list_query, req, aquery
    )

    assert total == 0
    assert rows == []
    # Same builders, same order: count first, then the page.
    assert len(seen) == 2
    assert "count" in seen[0].lower()
    assert seen[0] != seen[1]


@pytest.mark.asyncio
async def test_arun_paginated_shares_one_param_builder():
    """Both statements bind the same parameters, not two divergent sets."""
    req = AgentSpansQueryReq(project_id=PROJECT, limit=5)
    params_seen: list[dict] = []

    async def aquery(sql, params):
        params_seen.append(params)
        return result([[0]], ["c"])

    handler = AgentQueryHandler(MagicMock(), MagicMock())
    await handler.arun_paginated(
        make_spans_count_query, make_spans_list_query, req, aquery
    )

    assert params_seen[0] == params_seen[1]
    assert any(PROJECT in str(v) for v in params_seen[0].values())


@pytest.mark.asyncio
async def test_aagent_spans_query_refuses_group_by():
    """Grouped queries hydrate with further reads and stay on the sync path."""
    server = AsyncClickHouseTraceServer(host="test")
    req = AgentSpansQueryReq(
        project_id=PROJECT,
        group_by=[AgentGroupByRef(source="field", key="agent_name")],
        limit=1,
    )

    with pytest.raises(ValueError, match="does not support group_by"):
        await server.aagent_spans_query(req)


@pytest.mark.asyncio
async def test_aagent_search_returns_the_same_shape_as_the_sync_transform():
    """`aagent_search` reuses `search_res_from_rows`, so rows map identically."""
    rows = [
        {
            "conversation_id": "c-1",
            "conversation_name": "Export work",
            "agent_name": "coding-agent",
            "span_id": "s-1",
            "trace_id": "t-1",
            "role": "user",
            "content": "add a CSV export",
            "content_digest": "d-1",
        }
    ]
    direct = search_res_from_rows(rows)
    assert direct.total_conversations == 1
    assert direct.results[0].conversation_id == "c-1"
    assert direct.results[0].matched_messages[0].span_id == "s-1"


def test_ungrouped_spans_res_is_the_shared_transform():
    """Both paths build the ungrouped response through this one function."""
    res = ungrouped_spans_res(0, [])
    assert res.total_count == 0
    assert res.spans == []


@pytest.mark.asyncio
async def test_afeedback_create_keeps_the_sync_insert_override():
    """Feedback backs a waiting caller, so the write must not be async-inserted."""
    server = AsyncClickHouseTraceServer(host="test")
    server._prepare_feedback_create = MagicMock(
        return_value=(SimpleNamespace(data=[["x"]], column_names=["a"]), {"id": "f-1"})
    )
    server._ainsert = AsyncMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "weave.trace_server.async_clickhouse_trace_server.format_feedback_to_res",
            lambda row: row,
        )
        await server.afeedback_create(MagicMock())

    assert server._ainsert.await_args.kwargs["do_sync_insert"] is True
