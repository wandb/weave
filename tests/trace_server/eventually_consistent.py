"""Test-only proxy that retries a read once when it returns empty or not-found.

Masks rare read-your-write lag on CI ClickHouse (a just-written row not yet
visible to the immediately-following query) so trace_server tests don't flake.
It wraps the raw server *below* the externalize/caching layers, so both direct
`ch_server.*` calls and the `client` -> caching -> externalize -> server path
are covered. One 200ms retry is sufficient; see WB-35048.
"""

import time
from collections.abc import Callable
from typing import TypeVar

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents import types as agent_types
from weave.trace_server.errors import NotFoundError

RETRY_DELAY_SECONDS = 0.2
BUCKET_COUNT_KEY = "count"

T = TypeVar("T")


class EventuallyConsistentServer:
    """Wraps a ClickHouseTraceServer, retrying reads once on empty/not-found.

    Only read methods whose miss signature is unambiguous are wrapped; every
    other attribute (writes, `ch_client`, streams, internals) passes straight
    through to the inner server. `_inner` is also discoverable by
    `find_server_layer` (see its `_NEXT_SERVER_ATTRS`).
    """

    def __init__(self, inner: tsi.TraceServerInterface) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)

    # --- objects / tables / files ---
    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return retry_read(lambda: self._inner.obj_read(req))

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        return retry_read(lambda: self._inner.objs_query(req), lambda res: not res.objs)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return retry_read(
            lambda: self._inner.table_query(req), lambda res: not res.rows
        )

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return retry_read(
            lambda: self._inner.refs_read_batch(req), lambda res: not res.vals
        )

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        return retry_read(lambda: self._inner.file_content_read(req))

    # --- agents ---
    def agent_spans_query(
        self, req: agent_types.AgentSpansQueryReq
    ) -> agent_types.AgentSpansQueryRes:
        return retry_read(
            lambda: self._inner.agent_spans_query(req),
            lambda res: res.total_count == 0,
        )

    def agent_spans_stats(
        self, req: agent_types.AgentSpanStatsReq
    ) -> agent_types.AgentSpanStatsRes:
        metric_keys = stats_metric_keys(req)
        return retry_read(
            lambda: self._inner.agent_spans_stats(req),
            lambda res: stats_result_is_empty(res, metric_keys),
        )

    def agent_agents_query(
        self, req: agent_types.AgentsQueryReq
    ) -> agent_types.AgentsQueryRes:
        return retry_read(
            lambda: self._inner.agent_agents_query(req), lambda res: not res.agents
        )

    def agent_versions_query(
        self, req: agent_types.AgentVersionsQueryReq
    ) -> agent_types.AgentVersionsQueryRes:
        return retry_read(
            lambda: self._inner.agent_versions_query(req),
            lambda res: not res.versions,
        )

    def agent_search(
        self, req: agent_types.AgentSearchReq
    ) -> agent_types.AgentSearchRes:
        return retry_read(
            lambda: self._inner.agent_search(req), lambda res: not res.results
        )

    def agent_conversation_chat(
        self, req: agent_types.AgentConversationChatReq
    ) -> agent_types.AgentConversationChatRes:
        return retry_read(
            lambda: self._inner.agent_conversation_chat(req),
            lambda res: res.total_turns == 0,
        )

    def agent_custom_attrs_schema(
        self, req: agent_types.AgentCustomAttrsSchemaReq
    ) -> agent_types.AgentCustomAttrsSchemaRes:
        return retry_read(
            lambda: self._inner.agent_custom_attrs_schema(req),
            lambda res: not res.attributes,
        )


def retry_read(call: Callable[[], T], is_empty: Callable[[T], bool] | None = None) -> T:
    """Call once; on NotFoundError or an empty result, wait 200ms and retry once.

    A second NotFoundError (or empty result) propagates/returns as-is. The
    retry only masks a transient read-your-write miss, never a real absence.
    """
    try:
        result = call()
    except NotFoundError:
        time.sleep(RETRY_DELAY_SECONDS)
        return call()
    if is_empty is not None and is_empty(result):
        time.sleep(RETRY_DELAY_SECONDS)
        return call()
    return result


def stats_metric_keys(req: agent_types.AgentSpanStatsReq) -> list[str]:
    """Result-row keys the stats query produces for the requested metrics."""
    keys: list[str] = []
    for metric in req.metrics:
        for aggregation in metric.aggregations:
            keys.append(f"{aggregation}_{metric.alias}")
        for percentile in metric.percentiles or []:
            keys.append(f"p{percentile}_{metric.alias}")
    return keys


def stats_result_is_empty(
    res: agent_types.AgentSpanStatsRes, metric_keys: list[str]
) -> bool:
    """Empty when no rows, or every judged column is zero/None in every row.

    Judged columns are the requested metric aliases, or the bucket `count` column
    for bucket queries that request no metrics. A populated grid whose values are
    all zero is the visibility-lag signature. With no judgeable column, treat as
    non-empty so we never retry a query we cannot reason about.
    """
    if not res.rows:
        return True
    keys = [
        key
        for key in (metric_keys or [BUCKET_COUNT_KEY])
        if any(key in row for row in res.rows)
    ]
    if not keys:
        return False
    return all(not row.get(key) for row in res.rows for key in keys)
