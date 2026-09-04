"""Guards for the two ways the async calls reads can silently diverge from sync.

Both are failure modes that produce wrong data or wrong threading rather than an
exception, so neither would show up in a smoke test.
"""

import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.async_clickhouse_trace_server import (
    AsyncClickHouseTraceServer,
)
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsMergedField,
    OrderField,
)
from weave.trace_server.errors import HydratedQueryNotSupportedAsync
from weave.trace_server.token_costs import get_cost_result_columns

PROJECT = "UHJvamVjdEludGVybmFsSWQ6MQ=="


def test_acalls_query_stats_never_touches_ch_client_on_the_event_loop():
    """`ch_client` is thread-local and minting one blocks.

    Passed as an argument to `to_thread` it would be evaluated on the loop:
    blocking it on first use, and then handing one thread's client to every
    other thread running this concurrently.
    """
    server = AsyncClickHouseTraceServer(host="test_host")
    loop_thread = threading.get_ident()
    touched_on_loop: list[bool] = []

    class Guard:
        def __get__(self, obj, owner=None):
            touched_on_loop.append(threading.get_ident() == loop_thread)
            return MagicMock()

    async def run():
        with (
            patch.object(type(server), "ch_client", Guard()),
            patch.object(type(server), "table_routing_resolver", MagicMock()),
            patch.object(server, "_aquery", return_value=MagicMock(result_rows=[[0]])),
            patch(
                "weave.trace_server.async_clickhouse_trace_server.build_calls_stats_query",
                return_value=("SELECT 1", ["count"], None),
            ),
            patch(
                "weave.trace_server.async_clickhouse_trace_server.calls_stats_res",
                return_value=tsi.CallsQueryStatsRes(count=0),
            ),
        ):
            await server.acalls_query_stats(tsi.CallsQueryStatsReq(project_id=PROJECT))

    asyncio.run(run())
    assert touched_on_loop, "ch_client was never resolved; the test proves nothing"
    assert not any(touched_on_loop), (
        "ch_client was resolved on the event loop thread; it must be resolved "
        "inside the executor callback"
    )


class _Captured(Exception):
    """Carries the zip keys out before any downstream validation runs."""

    def __init__(self, columns):
        self.columns = columns


@pytest.mark.parametrize("include_costs", [True, False])
def test_acalls_query_maps_columns_the_way_sync_does(include_costs: bool):
    """A cost query's SELECT carries sort-only columns ahead of `summary_dump`.

    Zipping row values against `select_fields` alone shifts every value after
    that point onto the wrong key, which is silent rather than an error.
    """
    server = AsyncClickHouseTraceServer(host="test_host")
    select = ["id", "project_id", "summary_dump"]
    order = [OrderField(field=CallsMergedField(field="started_at"), direction="ASC")]
    cq = MagicMock(
        select_fields=[MagicMock(field=f) for f in select], order_fields=order
    )
    cq.as_sql.return_value = "SELECT 1"

    expected = get_cost_result_columns(select, order) if include_costs else select

    def capture(d):
        raise _Captured(list(d))

    async def run():
        with (
            patch.object(server, "_build_calls_query", return_value=(cq, None)),
            patch.object(
                server,
                "_aquery",
                return_value=MagicMock(result_rows=[list(range(len(expected)))]),
            ),
            patch(
                "weave.trace_server.async_clickhouse_trace_server.ch_call_dict_to_call_schema_dict",
                side_effect=capture,
            ),
        ):
            await server.acalls_query(
                tsi.CallsQueryReq(project_id=PROJECT, include_costs=include_costs)
            )

    with pytest.raises(_Captured) as exc:
        asyncio.run(run())
    assert exc.value.columns == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [{"expand_columns": ["inputs.x"]}, {"include_feedback": True}],
)
async def test_acalls_query_refuses_hydration(kwargs):
    """Hydration issues further reads per batch and stays on the sync path."""
    server = AsyncClickHouseTraceServer(host="test")
    req = tsi.CallsQueryReq(project_id="entity/project", **kwargs)

    with pytest.raises(HydratedQueryNotSupportedAsync):
        await server.acalls_query(req)
