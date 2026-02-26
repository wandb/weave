from __future__ import annotations

import datetime
from typing import Any, Protocol

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.call_stats_helpers import rows_to_bucket_dicts
from weave.trace_server.feedback_payload_schema import (
    build_feedback_payload_sample_query,
    discover_payload_schema,
)
from weave.trace_server.feedback_stats_query_builder import (
    build_feedback_stats_query,
    build_feedback_stats_window_query,
)
from weave.trace_server.orm import ParamBuilder

# Ordered longest-first so count_true/count_false win before count.
_WINDOW_STAT_AGG_PREFIXES = (
    "count_true",
    "count_false",
    "avg",
    "sum",
    "min",
    "max",
    "count",
)


class _ClickHouseFeedbackStatsServer(Protocol):
    def _query(self, sql: str, parameters: dict[str, Any]) -> Any: ...


def _parse_window_stat_col(col: str) -> tuple[str, str] | None:
    """Parse a window-stat alias into an aggregation key and metric slug.

    Args:
        col: Column alias produced by the feedback stats query builder.

    Returns:
        A tuple of `(aggregation_key, metric_slug)` when the alias matches a
        known pattern, otherwise `None`.

    Examples:
        >>> _parse_window_stat_col("avg_output_score")
        ('avg', 'output_score')
        >>> _parse_window_stat_col("p95_output_score")
        ('p95', 'output_score')
        >>> _parse_window_stat_col("unknown")
        None
    """
    for prefix in _WINDOW_STAT_AGG_PREFIXES:
        if col.startswith(prefix + "_"):
            return prefix, col[len(prefix) + 1 :]
    if (
        "_" in col
        and col[0] == "p"
        and col[1 : col.index("_")].replace(".", "").isdigit()
    ):
        idx = col.index("_")
        return col[:idx], col[idx + 1 :]
    return None


def _extract_window_stats(
    columns: list[str], row: tuple[Any, ...]
) -> dict[str, dict[str, float | None]]:
    """Convert a single window-stats row into the response shape.

    Args:
        columns: Column aliases returned by the window query.
        row: The single ClickHouse result row.

    Returns:
        A mapping of metric slug to aggregation name to float value.

    Examples:
        >>> _extract_window_stats(["avg_output_score"], (0.5,))
        {'output_score': {'avg': 0.5}}
        >>> _extract_window_stats(["ignored"], (1.0,))
        {}
    """
    raw_stats: dict[str, dict[str, float | None]] = {}
    for idx, col in enumerate(columns):
        if idx >= len(row):
            break
        parsed = _parse_window_stat_col(col)
        if parsed is None:
            continue
        key, slug = parsed
        val = row[idx]
        raw_stats.setdefault(slug, {})[key] = float(val) if val is not None else None
    return raw_stats


def feedback_stats(
    server: _ClickHouseFeedbackStatsServer, req: tsi.FeedbackStatsReq
) -> tsi.FeedbackStatsRes:
    """Run ClickHouse-backed feedback stats queries for a request.

    Args:
        server: ClickHouse trace server instance that can execute `_query`.
        req: Feedback stats request describing time range and metrics.

    Returns:
        The resolved feedback stats response, including bucketed data and
        optional full-window aggregations.

    Examples:
        >>> class _Server:
        ...     def _query(self, sql: str, parameters: dict[str, Any]) -> Any:  # doctest: +SKIP
        ...         raise NotImplementedError
        >>> feedback_stats(_Server(), tsi.FeedbackStatsReq(  # doctest: +SKIP
        ...     project_id="proj",
        ...     start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        ... ))
    """
    end = req.end or datetime.datetime.now(datetime.timezone.utc)
    if not req.metrics:
        return tsi.FeedbackStatsRes(
            start=req.start,
            end=end,
            granularity=3600,
            timezone=req.timezone or "UTC",
            buckets=[],
        )

    pb = ParamBuilder()
    query_result = build_feedback_stats_query(req, pb)
    result = server._query(query_result.sql, query_result.parameters)
    buckets = rows_to_bucket_dicts(query_result.columns, result.result_rows)

    window_stats: dict[str, dict[str, float | None]] | None = None
    pb_window = ParamBuilder()
    window_query = build_feedback_stats_window_query(req, pb_window)
    if window_query is not None:
        window_result = server._query(window_query.sql, window_query.parameters)
        if window_result.result_rows:
            window_stats = _extract_window_stats(
                window_query.columns, window_result.result_rows[0]
            )

    return tsi.FeedbackStatsRes(
        start=query_result.start,
        end=query_result.end,
        granularity=query_result.granularity_seconds,
        timezone=req.timezone or "UTC",
        buckets=buckets,
        window_stats=window_stats,
    )


def feedback_payload_schema(
    server: _ClickHouseFeedbackStatsServer, req: tsi.FeedbackPayloadSchemaReq
) -> tsi.FeedbackPayloadSchemaRes:
    """Discover feedback payload paths from ClickHouse samples.

    Args:
        server: ClickHouse trace server instance that can execute `_query`.
        req: Payload schema discovery request with filters and sample limit.

    Returns:
        A payload-schema response containing inferred paths and value types.

    Examples:
        >>> class _Server:
        ...     def _query(self, sql: str, parameters: dict[str, Any]) -> Any:  # doctest: +SKIP
        ...         raise NotImplementedError
        >>> feedback_payload_schema(_Server(), tsi.FeedbackPayloadSchemaReq(  # doctest: +SKIP
        ...     project_id="proj",
        ...     start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        ... ))
    """
    pb = ParamBuilder()
    sql, params = build_feedback_payload_sample_query(req, pb)
    result = server._query(sql, params)
    payload_strs = [row[0] for row in result.result_rows if row and row[0]]
    paths = discover_payload_schema(payload_strs)
    return tsi.FeedbackPayloadSchemaRes(paths=paths)
