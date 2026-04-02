"""Stats query builders for the calls query builder.

Handles building optimized count/stats queries for calls, including
special-case optimizations for common hot-path patterns.
"""

import logging
from collections.abc import KeysView

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.fields import (
    ROLLED_UP_CALL_MERGED_STATS_TABLE_NAME,
    get_calls_table_name,
    get_field_by_name,
)
from weave.trace_server.calls_query_builder.hardcoded_filters import HardCodedFilter
from weave.trace_server.calls_query_builder.utils import (
    param_slot,
    safely_format_sql,
)
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable

logger = logging.getLogger(__name__)


def build_calls_stats_query(
    req: tsi.CallsQueryStatsReq,
    param_builder: ParamBuilder,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
) -> tuple[str, KeysView[str]]:
    """Build a stats query for calls, automatically using optimized queries when possible.

    This function handles both optimized special-case queries and the general case.
    Returns a tuple of (query_sql, column_names).

    Args:
        req: The stats query request
        param_builder: Parameter builder for query parameterization
        read_table: Which calls table to read from

    Returns:
        Tuple of (SQL query string, column names in the result)
    """
    # Import here to avoid circular dependency: stats -> query -> stats
    # stats.py uses CallsQuery which is defined in calls_query_builder.py
    from weave.trace_server.calls_query_builder.calls_query_builder import CallsQuery

    aggregated_columns = {"count": "count()"}

    # Try optimized special case queries first
    if opt_query := _try_optimized_stats_query(req, param_builder, read_table):
        return (opt_query, aggregated_columns.keys())

    if req.include_total_storage_size:
        aggregated_columns["total_storage_size_bytes"] = (
            "sum(coalesce(total_storage_size_bytes, 0))"
        )

    # For calls_complete, use a flat query (10x+ faster, avoids subquery materialization):
    #   Fast:  SELECT count() FROM calls_complete WHERE ...
    #   Slow:  SELECT count() FROM (SELECT id FROM calls_complete WHERE ...)
    if read_table == ReadTable.CALLS_COMPLETE:
        query = _build_calls_complete_stats_query(
            req, param_builder, aggregated_columns
        )
        return (query, aggregated_columns.keys())

    # For calls_merged, use subquery wrapping (GROUP BY requires materialization)
    cq = _build_stats_calls_query(req, read_table, CallsQuery)
    inner_query = cq.as_sql(param_builder)
    calls_query_sql = f"SELECT {', '.join(aggregated_columns[k] for k in aggregated_columns)} FROM ({inner_query})"

    return (calls_query_sql, aggregated_columns.keys())


def _build_stats_calls_query(
    req: tsi.CallsQueryStatsReq,
    read_table: ReadTable,
    calls_query_cls: type,
) -> "CallsQuery":  # noqa: F821
    """Build a CallsQuery populated with the stats request's filters and conditions."""
    cq = calls_query_cls(
        project_id=req.project_id,
        include_total_storage_size=req.include_total_storage_size or False,
        read_table=read_table,
    )
    cq.add_field("id")
    if req.filter is not None:
        cq.set_hardcoded_filter(HardCodedFilter(filter=req.filter))
    if req.query is not None:
        cq.add_condition(req.query.expr_)
    if req.limit is not None:
        cq.set_limit(req.limit)
    if req.expand_columns is not None:
        cq.set_expand_columns(req.expand_columns)
    if req.include_total_storage_size:
        cq.add_field("total_storage_size_bytes")
    return cq


def _build_calls_complete_stats_query(
    req: tsi.CallsQueryStatsReq,
    param_builder: ParamBuilder,
    aggregated_columns: dict[str, str],
) -> str:
    """Build a flat stats query for calls_complete without subquery wrapping.

    Produces SELECT count() FROM calls_complete WHERE ... directly,
    which is 10x+ faster than the subquery form because ClickHouse evaluates
    aggregates without materializing intermediate rows.

    Uses CallsQuery._build_query_body for filter/condition/JOIN building,
    then composes its own aggregate SELECT clause on top.
    """
    from weave.trace_server.calls_query_builder.calls_query_builder import CallsQuery

    table_name = get_calls_table_name(ReadTable.CALLS_COMPLETE)
    cq = _build_stats_calls_query(req, ReadTable.CALLS_COMPLETE, CallsQuery)

    # Inject deleted_at sentinel filter for calls_complete (epoch zero = not deleted).
    # This is needed because _build_query_body doesn't inject it automatically --
    # that happens in as_sql() which we bypass here.
    # Use None as the literal so process_operation applies the sentinel value with
    # proper DateTime64(3) typing (same pattern as as_sql()).
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "deleted_at"},
                    {"$literal": None},
                ]
            }
        )
    )

    # Build the query body (FROM, JOINs, WHERE, etc.) — reuses all existing
    # filter/condition/join abstractions without CTE optimization overhead
    body = cq._build_query_body(param_builder, table_name)

    # Build the aggregate SELECT clause
    stats_parts: list[str] = []
    for col_name, col_agg in aggregated_columns.items():
        if col_name == "total_storage_size_bytes":
            # Inline the total_storage_size expression for the flat query.
            # Mirrors AggregatedDataSizeField.as_select_sql(use_agg_fn=False),
            # wrapped in the aggregate function directly.
            parent_id_field = get_field_by_name("parent_id")
            parent_null = parent_id_field.null_check_sql(
                param_builder, table_name, ReadTable.CALLS_COMPLETE, use_agg_fn=False
            )
            total_storage_expr = (
                f"CASE WHEN {parent_null} "
                f"THEN {ROLLED_UP_CALL_MERGED_STATS_TABLE_NAME}.total_storage_size_bytes "
                f"ELSE NULL END"
            )
            stats_parts.append(f"sum(coalesce({total_storage_expr}, 0)) AS {col_name}")
        else:
            stats_parts.append(f"{col_agg} AS {col_name}")
    stats_select = ", ".join(stats_parts)

    raw_sql = f"""
    SELECT {stats_select}
    {body}
    """
    return safely_format_sql(raw_sql, logger)


def _try_optimized_stats_query(
    req: tsi.CallsQueryStatsReq,
    param_builder: ParamBuilder,
    read_table: ReadTable,
) -> str | None:
    """Try to match request to an optimized special-case query.

    Returns optimized query string if a pattern matches, None otherwise.
    Add new patterns here for common hot-path queries.
    """
    # Pattern 1: Simple existence check (limit=1, no filters)
    if (
        req.limit == 1
        and req.filter is None
        and req.query is None
        and not req.include_total_storage_size
    ):
        return _optimized_project_contains_call_query(
            req.project_id, param_builder, read_table
        )

    # Pattern 2: Query with wb_run_id check (limit=1, query present, minimal filter)
    # Covers common case: checking for runs with wb_run_id not null
    if (
        req.limit == 1
        and req.query is not None
        and not req.include_total_storage_size
        and _is_minimal_filter(req.filter)
    ):
        return _optimized_wb_run_id_not_null_query(
            req.project_id, param_builder, read_table
        )

    return None


def _optimized_project_contains_call_query(
    project_id: str,
    param_builder: ParamBuilder,
    read_table: ReadTable,
) -> str:
    """Returns a query that checks if the project contains any calls."""
    table_name = get_calls_table_name(read_table)
    return safely_format_sql(
        f"""SELECT
    toUInt8(count()) AS has_any
    FROM
    (
        SELECT 1
        FROM {table_name}
        WHERE project_id = {param_slot(param_builder.add_param(project_id), "String")}
        LIMIT 1
    )
    """,
        logger,
    )


def _optimized_wb_run_id_not_null_query(
    project_id: str,
    param_builder: ParamBuilder,
    read_table: ReadTable,
) -> str:
    """Optimized query for checking existence of calls with wb_run_id not null.

    Uses WHERE clause instead of HAVING to avoid expensive aggregation.
    """
    project_id_param = param_builder.add_param(project_id)
    table_name = get_calls_table_name(read_table)
    wb_run_id_field = get_field_by_name("wb_run_id")
    wb_run_id_check = wb_run_id_field.null_check_sql(
        param_builder, table_name, read_table, use_agg_fn=False, negate=True
    )
    deleted_at_field = get_field_by_name("deleted_at")
    deleted_at_check = deleted_at_field.null_check_sql(
        param_builder, table_name, read_table, use_agg_fn=False
    )
    return f"""
        SELECT count() FROM (
            SELECT {table_name}.id AS id
            FROM {table_name}
            WHERE {table_name}.project_id = {param_slot(project_id_param, "String")}
                AND {wb_run_id_check}
                AND {deleted_at_check}
            LIMIT 1
        )
    """


def _is_minimal_filter(filter: tsi.CallsFilter | None) -> bool:
    """Check if filter has no specific filtering criteria set."""
    if filter is None:
        return True
    return (
        filter.wb_run_ids is None
        and filter.wb_user_ids is None
        and filter.op_names is None
        and filter.call_ids is None
        and filter.trace_ids is None
        and filter.parent_ids is None
        and filter.trace_roots_only is None
        and filter.input_refs is None
        and filter.output_refs is None
        and filter.thread_ids is None
        and filter.turn_ids is None
    )
