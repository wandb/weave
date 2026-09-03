"""The async agent reads issue the same SQL as their sync twins.

`aagent_spans_query` and `aagent_search` exist so the agent scoring worker can
await a socket instead of a thread. They share the sync path's SQL builders and
row transforms, so what these assert is that the split did not change what runs
or what comes back -- not that the transport is faster.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from weave.trace_server.agents.clickhouse import (
    AgentQueryHandler,
    search_res_from_rows,
)
from weave.trace_server.agents.types import (
    AgentGroupByRef,
    AgentSearchReq,
    AgentSpansQueryReq,
)
from weave.trace_server.async_clickhouse_trace_server import AsyncClickHouseTraceServer
from weave.trace_server.errors import GroupedQueryNotSupportedAsync
from weave.trace_server.query_builder.agent_query_builder import (
    make_spans_count_query,
    make_spans_list_query,
)

PROJECT = "entity/project"


def result(rows, columns):
    return SimpleNamespace(result_rows=rows, column_names=columns)


@pytest.mark.asyncio
async def test_arun_paginated_issues_the_sync_pair_with_one_param_builder():
    """Count then page, built by the same builders and bound to one ParamBuilder."""
    req = AgentSpansQueryReq(project_id=PROJECT, limit=5)
    seen: list[tuple[str, dict]] = []

    async def aquery(sql, params):
        seen.append((sql, params))
        return result([[0]], ["c"]) if len(seen) == 1 else result([], [])

    handler = AgentQueryHandler(MagicMock(), MagicMock())
    total, rows = await handler.arun_paginated(
        make_spans_count_query, make_spans_list_query, req, aquery
    )

    assert (total, rows) == (0, [])
    assert len(seen) == 2
    (count_sql, count_params), (list_sql, list_params) = seen
    assert "count" in count_sql.lower()
    assert count_sql != list_sql
    # One builder: both statements bind the same parameters, not two sets.
    assert count_params == list_params
    assert any(PROJECT in str(v) for v in count_params.values())


@pytest.mark.asyncio
async def test_aagent_spans_query_refuses_group_by():
    """Grouped queries hydrate with further reads and stay on the sync path."""
    server = AsyncClickHouseTraceServer(host="test")
    req = AgentSpansQueryReq(
        project_id=PROJECT,
        group_by=[AgentGroupByRef(source="field", key="agent_name")],
        limit=1,
    )

    with pytest.raises(GroupedQueryNotSupportedAsync):
        await server.aagent_spans_query(req)


@pytest.mark.asyncio
async def test_aagent_search_returns_the_shared_transform_output():
    """`aagent_search` must go through `search_res_from_rows`, not its own mapping.

    The previous version of this test called the transform directly, so it
    proved nothing about the async endpoint it was named for.
    """
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
    server = AsyncClickHouseTraceServer(host="test")
    with patch.object(
        AgentQueryHandler, "arun_message_search_query", AsyncMock(return_value=rows)
    ):
        res = await server.aagent_search(AgentSearchReq(project_id=PROJECT))

    assert res == search_res_from_rows(rows)
    assert res.results[0].matched_messages[0].span_id == "s-1"


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
