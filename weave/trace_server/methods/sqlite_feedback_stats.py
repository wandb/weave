"""SQLite implementation of feedback_stats and feedback_payload_schema.

Queries raw feedback rows via SQL, then aggregates in Python to match the
ClickHouse implementation's response shape.
"""

from __future__ import annotations

import datetime
import json
import math
import statistics
from typing import TYPE_CHECKING, Any

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.stats_query_base import (
    auto_select_granularity_seconds,
    ensure_max_buckets,
)
from weave.trace_server.feedback_payload_schema import discover_payload_schema

if TYPE_CHECKING:
    from weave.trace_server.sqlite_trace_server import SqliteTraceServer


def _fetch_feedback_rows(
    server: SqliteTraceServer,
    project_id: str,
    start: datetime.datetime,
    end: datetime.datetime,
    feedback_type: str | None = None,
    trigger_ref: str | None = None,
) -> list[tuple[str, str]]:
    """Fetch (created_at, payload_dump) tuples from the feedback table."""
    # Avoid circular import at module level
    from weave.trace_server.sqlite_trace_server import get_conn_cursor

    _, cursor = get_conn_cursor(server.db_path)
    clauses = ["project_id = ?", "created_at >= ?", "created_at < ?"]
    params: list[Any] = [
        project_id,
        start.strftime("%Y-%m-%d %H:%M:%S"),
        end.strftime("%Y-%m-%d %H:%M:%S"),
    ]
    if feedback_type is not None:
        clauses.append("feedback_type = ?")
        params.append(feedback_type)
    if trigger_ref is not None:
        if trigger_ref.endswith(":*"):
            clauses.append("trigger_ref LIKE ?")
            params.append(trigger_ref[:-2] + "%")
        else:
            clauses.append("trigger_ref = ?")
            params.append(trigger_ref)
    where = " AND ".join(clauses)
    sql = f"SELECT created_at, payload_dump FROM feedback WHERE {where}"
    r = cursor.execute(sql, params)
    return r.fetchall()


def _extract_value(payload_str: str, json_path: str, value_type: str) -> Any:
    """Extract a value from a JSON payload string at a dot path."""
    try:
        obj = json.loads(payload_str)
    except (json.JSONDecodeError, TypeError):
        return None
    for part in json_path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
        if obj is None:
            return None
    if value_type == "numeric":
        try:
            return float(obj)
        except (TypeError, ValueError):
            return None
    if value_type == "boolean":
        if isinstance(obj, bool):
            return obj
        if isinstance(obj, str):
            if obj.lower() == "true":
                return True
            if obj.lower() == "false":
                return False
        return None
    return obj


def _parse_row_ts(created_at_str: str) -> datetime.datetime:
    """Parse SQLite created_at into a UTC datetime."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.datetime.strptime(created_at_str, fmt).replace(
                tzinfo=datetime.timezone.utc
            )
        except ValueError:
            continue
    return datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))


def _bucket_key(
    ts: datetime.datetime, start: datetime.datetime, granularity: int
) -> datetime.datetime:
    """Round a timestamp down to its bucket start."""
    offset = int((ts - start).total_seconds())
    bucket_offset = (offset // granularity) * granularity
    return start + datetime.timedelta(seconds=bucket_offset)


def _compute_agg(
    values: list[float],
    agg: str,
) -> float | None:
    """Compute a single aggregation over a list of numeric values."""
    if not values:
        return None
    if agg == "avg":
        return statistics.mean(values)
    if agg == "sum":
        return math.fsum(values)
    if agg == "min":
        return min(values)
    if agg == "max":
        return max(values)
    if agg == "count":
        return float(len(values))
    return None


def _compute_percentile(values: list[float], pct: float) -> float | None:
    """Compute a percentile (0-100) using linear interpolation."""
    if not values:
        return None
    s = sorted(values)
    k = (pct / 100.0) * (len(s) - 1)
    f = int(k)
    c = f + 1
    if c >= len(s):
        return s[-1]
    return s[f] + (k - f) * (s[c] - s[f])


def sqlite_feedback_stats(
    server: SqliteTraceServer, req: tsi.FeedbackStatsReq
) -> tsi.FeedbackStatsRes:
    """Compute feedback stats by querying SQLite and aggregating in Python."""
    end = req.end or datetime.datetime.now(datetime.timezone.utc)
    if not req.metrics:
        return tsi.FeedbackStatsRes(
            start=req.start,
            end=end,
            granularity=3600,
            timezone=req.timezone or "UTC",
            buckets=[],
        )

    start = req.start
    if start.tzinfo is None:
        start = start.replace(tzinfo=datetime.timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=datetime.timezone.utc)

    time_range = end - start
    granularity = req.granularity or auto_select_granularity_seconds(time_range)
    granularity = ensure_max_buckets(granularity, time_range.total_seconds())

    rows = _fetch_feedback_rows(
        server,
        req.project_id,
        start,
        end,
        req.feedback_type,
        req.trigger_ref,
    )

    metrics = [m for m in req.metrics if m.aggregations or m.percentiles]

    bucket_data: dict[datetime.datetime, dict[str, list[Any]]] = {}
    all_values: dict[str, list[Any]] = {m.json_path: [] for m in metrics}

    for created_at_str, payload_str in rows:
        ts = _parse_row_ts(created_at_str)
        bk = _bucket_key(ts, start, granularity)
        if bk not in bucket_data:
            bucket_data[bk] = {m.json_path: [] for m in metrics}
        for m in metrics:
            val = _extract_value(payload_str or "", m.json_path, m.value_type)
            if val is not None:
                bucket_data[bk][m.json_path].append(val)
                all_values[m.json_path].append(val)

    all_bucket_starts = []
    t = start
    while t < end:
        all_bucket_starts.append(t)
        t += datetime.timedelta(seconds=granularity)

    buckets: list[dict[str, Any]] = []
    for bk in all_bucket_starts:
        row_dict: dict[str, Any] = {"timestamp": bk}
        count = 0
        for m in metrics:
            slug = m.json_path.replace(".", "_")
            vals = bucket_data.get(bk, {}).get(m.json_path, [])
            if m.value_type == "boolean":
                bool_vals = vals
                for agg in m.aggregations or []:
                    if agg.value == "count_true":
                        row_dict[f"count_true_{slug}"] = sum(
                            1 for v in bool_vals if v is True
                        )
                    elif agg.value == "count_false":
                        row_dict[f"count_false_{slug}"] = sum(
                            1 for v in bool_vals if v is False
                        )
            else:
                numeric_vals = [float(v) for v in vals if v is not None]
                for agg in m.aggregations or []:
                    row_dict[f"{agg.value}_{slug}"] = _compute_agg(
                        numeric_vals, agg.value
                    )
                for pct in m.percentiles or []:
                    key = f"p{pct:g}"
                    row_dict[f"{key}_{slug}"] = _compute_percentile(numeric_vals, pct)
            count = max(count, len(vals))
        row_dict["count"] = count
        buckets.append(row_dict)

    window_stats: dict[str, dict[str, float | None]] | None = None
    has_window_aggs = any(m.aggregations or m.percentiles for m in metrics)
    if has_window_aggs:
        window_stats = {}
        for m in metrics:
            slug = m.json_path.replace(".", "_")
            vals = all_values[m.json_path]
            stat: dict[str, float | None] = {}
            if m.value_type == "boolean":
                for agg in m.aggregations or []:
                    if agg.value == "count_true":
                        stat["count_true"] = float(sum(1 for v in vals if v is True))
                    elif agg.value == "count_false":
                        stat["count_false"] = float(sum(1 for v in vals if v is False))
            else:
                numeric_vals = [float(v) for v in vals if v is not None]
                for agg in m.aggregations or []:
                    stat[agg.value] = _compute_agg(numeric_vals, agg.value)
                for pct in m.percentiles or []:
                    key = f"p{pct:g}"
                    stat[key] = _compute_percentile(numeric_vals, pct)
            window_stats[slug] = stat

    return tsi.FeedbackStatsRes(
        start=start,
        end=end,
        granularity=granularity,
        timezone=req.timezone or "UTC",
        buckets=buckets,
        window_stats=window_stats,
    )


def sqlite_feedback_payload_schema(
    server: SqliteTraceServer, req: tsi.FeedbackPayloadSchemaReq
) -> tsi.FeedbackPayloadSchemaRes:
    """Discover feedback payload schema from SQLite samples."""
    end = req.end or datetime.datetime.now(datetime.timezone.utc)
    start = req.start
    if start.tzinfo is None:
        start = start.replace(tzinfo=datetime.timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=datetime.timezone.utc)

    rows = _fetch_feedback_rows(
        server,
        req.project_id,
        start,
        end,
        req.feedback_type,
        req.trigger_ref,
    )
    payload_strs = [row[1] for row in rows if row[1]]
    if req.sample_limit and len(payload_strs) > req.sample_limit:
        payload_strs = payload_strs[: req.sample_limit]

    paths = discover_payload_schema(payload_strs)
    return tsi.FeedbackPayloadSchemaRes(paths=paths)
