"""Test-only proxy that retries an agent read once when it returns empty.

Masks rare read-your-write visibility lag on CI ClickHouse (a just-inserted
span not yet visible to the immediately-following query) so the genai agent
query tests don't flake. One 200ms retry is sufficient; see WB-35048.
"""

import time
from collections.abc import Callable
from typing import TypeVar

RETRY_DELAY_SECONDS = 0.2
BUCKET_COUNT_KEY = "count"

T = TypeVar("T")


class EventuallyConsistentAgentServer:
    """Wraps a ClickHouseTraceServer, retrying agent reads once on an empty result.

    Non-agent attributes (e.g. `ch_client`) pass straight through to the inner
    server, so tests insert exactly as before.
    """

    def __init__(self, inner: object) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)

    def agent_spans_query(self, req: object) -> object:
        return retry_until_found(
            lambda: self._inner.agent_spans_query(req),
            lambda res: res.total_count == 0,
        )

    def agent_spans_stats(self, req: object) -> object:
        metric_keys = stats_metric_keys(req)
        return retry_until_found(
            lambda: self._inner.agent_spans_stats(req),
            lambda res: stats_result_is_empty(res, metric_keys),
        )

    def agent_agents_query(self, req: object) -> object:
        return retry_until_found(
            lambda: self._inner.agent_agents_query(req),
            lambda res: not res.agents,
        )

    def agent_versions_query(self, req: object) -> object:
        return retry_until_found(
            lambda: self._inner.agent_versions_query(req),
            lambda res: not res.agent_versions,
        )

    def agent_search(self, req: object) -> object:
        return retry_until_found(
            lambda: self._inner.agent_search(req),
            lambda res: not res.results,
        )

    def agent_conversation_chat(self, req: object) -> object:
        return retry_until_found(
            lambda: self._inner.agent_conversation_chat(req),
            lambda res: res.total_turns == 0,
        )

    def agent_custom_attrs_schema(self, req: object) -> object:
        return retry_until_found(
            lambda: self._inner.agent_custom_attrs_schema(req),
            lambda res: not res.attributes,
        )


def retry_until_found(call: Callable[[], T], is_empty: Callable[[T], bool]) -> T:
    """Run `call`; if it returns empty, wait once and run it again."""
    result = call()
    if is_empty(result):
        time.sleep(RETRY_DELAY_SECONDS)
        result = call()
    return result


def stats_metric_keys(req: object) -> list[str]:
    """Result-row keys the stats query produces for the requested metrics."""
    keys: list[str] = []
    for metric in req.metrics:
        for aggregation in metric.aggregations:
            keys.append(f"{aggregation}_{metric.alias}")
        for percentile in metric.percentiles or []:
            keys.append(f"p{percentile}_{metric.alias}")
    return keys


def stats_result_is_empty(res: object, metric_keys: list[str]) -> bool:
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
