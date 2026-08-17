"""Query builder for feedback aggregates over the typed scorer columns."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeAlias

from weave.trace_server.calls_query_builder.utils import param_slot, safely_format_sql
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.trace_server_interface import FeedbackAggregateReq

if TYPE_CHECKING:
    from weave.trace_server.agents.types import AgentSignalsQueryReq

logger = logging.getLogger(__name__)

# A value bound into the parameterized query: the scalar param types plus the
# list params used for the IN / Array(String) filters (tags, span_agent_names).
QueryParamValue: TypeAlias = str | int | float | bool | list[str] | None


@dataclass
class FeedbackAggregateQuery:
    """A parameterized ClickHouse query plus the column order of its result rows."""

    sql: str
    columns: list[str]
    parameters: dict[str, QueryParamValue] = field(default_factory=dict)


# Agent-monitor scores land under this scorer_ratings key; the rating filter targets it.
_RATING_KEY = "_rating_"

# SQL to add up tags and ratings by name. Each returns Map(<key-name>, <count-or-sum>).
# Sum and count are separate for ratings so the client can calculate averages across buckets.
_TAG_COUNTS_SQL = "sumMap(scorer_tags, arrayMap(x -> toUInt64(1), scorer_tags))"
_RATING_SUMS_SQL = "sumMap(mapKeys(scorer_ratings), mapValues(scorer_ratings))"
_RATING_COUNTS_SQL = "sumMap(mapKeys(scorer_ratings), arrayMap(x -> toUInt64(1), mapValues(scorer_ratings)))"

# Count a row if it produced at least one tag or rating. Used to show the total volume of scores.
_SCORED_COUNT_SQL = "countIf(notEmpty(scorer_tags) OR notEmpty(scorer_ratings))"


def build_feedback_aggregate_query(
    req: FeedbackAggregateReq,
    pb: ParamBuilder,
) -> FeedbackAggregateQuery:
    """Generate parameterized ClickHouse SQL for feedback aggregates.

    Groups by a time bucket (optional) plus `req.group_by`, returning per-group total count,
    per-tag counts, and per-rating sum/count. Empty time buckets are skipped.
    """
    project_param = pb.add_param(req.project_id)
    after_param = pb.add_param(req.after_ms)
    before_param = pb.add_param(req.before_ms)

    # The time bucket is an optional leading group key. Without it we roll up the
    # whole range into one row per group_by combination (or a single global row).
    dimension_parts: list[str] = []
    group_keys: list[str] = []
    if req.time_bucket_seconds is not None:
        bin_param = pb.add_param(req.time_bucket_seconds)
        bucket_expr = f"toStartOfInterval(created_at, toIntervalSecond({param_slot(bin_param, 'Int64')}), 'UTC')"
        dimension_parts.append(f"{bucket_expr} AS bucket")
        group_keys.append("bucket")

    # Each dimension keys its result column on the client-facing name; `scorer_id`
    # is derived from runnable_ref (so the response exposes an id, never a ref).
    for dimension in req.group_by:
        expr = _group_by_sql(dimension)
        dimension_parts.append(
            dimension if expr == dimension else f"{expr} AS {dimension}"
        )
        group_keys.append(dimension)

    select_parts = [
        *dimension_parts,
        f"{_TAG_COUNTS_SQL} AS tag_counts",
        f"{_RATING_SUMS_SQL} AS rating_sums",
        f"{_RATING_COUNTS_SQL} AS rating_counts",
        "count() AS total_count",
        f"{_SCORED_COUNT_SQL} AS scored_count",
    ]
    select_sql = ",\n      ".join(select_parts)
    where_sql = build_feedback_filter_sql(
        req, project_param, after_param, before_param, pb
    )

    raw_sql = f"SELECT {select_sql} FROM feedback WHERE {where_sql}"
    if group_keys:
        raw_sql += f" GROUP BY {', '.join(group_keys)}"
        # Bucketed results read as a time series (order by bucket); otherwise order
        # by the group_by dimensions for a deterministic row order.
        order_keys = ["bucket"] if req.time_bucket_seconds is not None else req.group_by
        raw_sql += f" ORDER BY {', '.join(order_keys)}"

    columns = [
        *group_keys,
        "tag_counts",
        "rating_sums",
        "rating_counts",
        "total_count",
        "scored_count",
    ]

    return FeedbackAggregateQuery(
        sql=safely_format_sql(raw_sql, logger),
        columns=columns,
        parameters=pb.get_params(),
    )


def _ref_object_id_sql(column: str) -> str:
    """SQL for a ref's object id: the last path segment's name, before any ':digest'.

    e.g. `weave:///proj/object/my_scorer:abc123` -> `my_scorer`. This is the
    stable object identity; the digest is the (version-specific) tail.
    """
    last_segment = f"splitByChar('/', ifNull({column}, ''))[-1]"
    return f"splitByChar(':', {last_segment})[1]"


def _group_by_sql(dimension: str) -> str:
    """SQL expression for a client-facing group_by dimension.

    `scorer_id` is derived from runnable_ref (its object id) so a grouped response
    returns scorer ids, never refs. Every other dimension is a stored column used
    as-is.
    """
    if dimension == "scorer_id":
        return _ref_object_id_sql("runnable_ref")
    return dimension


def _any_prefix_clause(column_expr: str, values: list[str], pb: ParamBuilder) -> str:
    """Match if `column_expr` starts with ANY of `values` (OR'd together).

    Used for namespace columns like feedback_type where prefix matching is the
    point (e.g. `wandb.runnable.` matches every runnable scorer).
    """
    ors: list[str] = []
    for value in values:
        # Client may add a trailing '*' to signal this is a prefix match: strip it
        param = pb.add_param(value.rstrip("*"))
        ors.append(f"startsWith({column_expr}, {param_slot(param, 'String')})")
    return f"({' OR '.join(ors)})"


def _object_id_match_clause(column: str, values: list[str], pb: ParamBuilder) -> str:
    """Match a ref's object id against ANY of `values` (OR'd together).

    Exact match by default (so `mon` matches the monitor `mon`, not `monday`); a
    trailing `*` opts into prefix matching (`mon*` matches both).
    """
    object_id = _ref_object_id_sql(column)
    ors: list[str] = []
    for value in values:
        if value.endswith("*"):
            param = pb.add_param(value.rstrip("*"))
            ors.append(f"startsWith({object_id}, {param_slot(param, 'String')})")
        else:
            param = pb.add_param(value)
            ors.append(f"{object_id} = {param_slot(param, 'String')}")
    return f"({' OR '.join(ors)})"


def build_feedback_filter_sql(
    req: FeedbackAggregateReq | AgentSignalsQueryReq,
    project_param: str,
    after_param: str,
    before_param: str,
    pb: ParamBuilder,
) -> str:
    """Assemble the WHERE clause: project + time range + the typed structured filters."""
    clauses = [
        f"project_id = {param_slot(project_param, 'String')}",
        f"created_at >= fromUnixTimestamp64Milli({param_slot(after_param, 'Int64')})",
        f"created_at < fromUnixTimestamp64Milli({param_slot(before_param, 'Int64')})",
    ]
    if req.feedback_types:
        clauses.append(_any_prefix_clause("feedback_type", req.feedback_types, pb))
    if req.monitor_ids:
        # Monitors are always stored in the `trigger_ref` column
        clauses.append(_object_id_match_clause("trigger_ref", req.monitor_ids, pb))
    if req.scorer_ids:
        # Scorers are always stored in the `runnable_ref` column
        clauses.append(_object_id_match_clause("runnable_ref", req.scorer_ids, pb))
    if req.span_agent_names:
        names_param = pb.add_param(req.span_agent_names)
        clauses.append(f"span_agent_name IN {param_slot(names_param, 'Array(String)')}")
    if req.span_types:
        # weave_ref looks like `<weave-scheme>:///<project_id>/<span_type>/<id>`, so the
        # span type is the second-to-last path segment (robust whether project_id is one
        # segment or `entity/project`). Match it exactly, not as a substring of the ref.
        ors = [
            f"splitByChar('/', weave_ref)[-2] = {param_slot(pb.add_param(span_type), 'String')}"
            for span_type in req.span_types
        ]
        clauses.append(f"({' OR '.join(ors)})")
    if req.tags:
        tags_param = pb.add_param(req.tags)
        clauses.append(
            f"hasAny(scorer_tags, {param_slot(tags_param, 'Array(String)')})"
        )
    # Rating bounds default to the full [0, 1] range; only filter when narrowed. A row
    # must actually carry a _rating_ (mapContains) so tag-only rows drop out.
    if req.rating_min is not None or req.rating_max is not None:
        key_param = pb.add_param(_RATING_KEY)
        key_slot = param_slot(key_param, "String")
        clauses.append(f"mapContains(scorer_ratings, {key_slot})")
        if req.rating_min is not None:
            gte_slot = param_slot(pb.add_param(req.rating_min), "Float64")
            clauses.append(f"scorer_ratings[{key_slot}] >= {gte_slot}")
        if req.rating_max is not None:
            lte_slot = param_slot(pb.add_param(req.rating_max), "Float64")
            clauses.append(f"scorer_ratings[{key_slot}] <= {lte_slot}")
    return " AND ".join(clauses)
