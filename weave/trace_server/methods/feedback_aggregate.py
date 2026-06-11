from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse.utilities import ensure_datetimes_have_tz_strict
from weave.trace_server.feedback_agg_query_builder import (
    build_feedback_aggregate_query,
)
from weave.trace_server.orm import ParamBuilder

if TYPE_CHECKING:
    from weave.trace_server.clickhouse_trace_server_batched import (
        ClickHouseTraceServer,
    )


def feedback_aggregate(
    server: ClickHouseTraceServer, req: tsi.FeedbackAggregateReq
) -> tsi.FeedbackAggregateRes:
    """Run the ClickHouse-backed feedback aggregate query and shape the response.

    Builds one row per group and maps each to a FeedbackAggregateBucket.
    """
    pb = ParamBuilder()
    built = build_feedback_aggregate_query(req, pb)
    result = server._query(built.sql, built.parameters)
    rows = [dict(zip(built.columns, row, strict=True)) for row in result.result_rows]
    buckets = [_row_to_bucket(row, req.group_by) for row in rows]
    return tsi.FeedbackAggregateRes(
        time_bucket_seconds=req.time_bucket_seconds,
        after_ms=req.after_ms,
        before_ms=req.before_ms,
        buckets=buckets,
    )


def _row_to_bucket(
    row: dict[str, Any], group_by: Sequence[str]
) -> tsi.FeedbackAggregateBucket:
    """Map one labeled result row to a FeedbackAggregateBucket.

    The bucket comes back as a (UTC) datetime, converted to unix epoch ms;
    group-by dimension values are stringified for the response. sumMap columns
    come back as a `Tuple(Array(key), Array(value))` (see `_summap_to_dict`).
    """
    tag_counts = _summap_to_dict(row["tag_counts"])
    rating_sums = _summap_to_dict(row["rating_sums"])
    rating_counts = _summap_to_dict(row["rating_counts"])
    time_bucket_start_ms = None
    if "bucket" in row:
        time_bucket_start_ms = int(
            ensure_datetimes_have_tz_strict(row["bucket"]).timestamp() * 1000
        )
    return tsi.FeedbackAggregateBucket(
        time_bucket_start_ms=time_bucket_start_ms,
        group={dim: str(row[dim]) for dim in group_by},
        total_count=int(row["total_count"]),
        scored_count=int(row["scored_count"]),
        tag_counts={k: int(v) for k, v in tag_counts.items()},
        rating_counts={k: int(v) for k, v in rating_counts.items()},
        rating_sums={k: float(v) for k, v in rating_sums.items()},
    )


def _summap_to_dict(
    value: dict[str, Any] | tuple[list[str], list[float]],
) -> dict[str, Any]:
    """Coerce a ClickHouse sumMap result into a plain dict.

    sumMap returns a `Tuple(Array(key), Array(value))` (two parallel arrays),
    which clickhouse-connect surfaces as a 2-tuple. Tolerates a dict too, in
    case a driver/version returns a native Map.
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, tuple):
        keys, values = value
        return dict(zip(keys, values, strict=True))
    raise ValueError(f"Unexpected value type: {type(value).__name__}")
