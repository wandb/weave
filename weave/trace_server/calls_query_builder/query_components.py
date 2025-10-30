"""Shared query component builders for calls queries.

Pure functions that build reusable SQL fragments. These functions do NOT manage CTEs,
only return SQL strings that can be composed into queries.
"""

from typing import TYPE_CHECKING, Optional

from weave.trace_server.orm import ParamBuilder

if TYPE_CHECKING:
    from weave.trace_server.calls_query_builder.calls_query_builder import (
        Condition,
        HardCodedFilter,
        OrderField,
    )


def build_filter_conditions(
    pb: ParamBuilder,
    query_conditions: list["Condition"],  # type: ignore
    hardcoded_filter: Optional["HardCodedFilter"],  # type: ignore
    table_alias: Optional[str] = None,
    expand_columns: Optional[list[str]] = None,
    field_to_object_join_alias_map: Optional[dict[str, str]] = None,
) -> list[str]:
    """Build filter condition SQL strings.

    Returns a list of condition strings that can be combined with AND/OR.
    Does NOT manage CTEs - object ref CTEs must be built separately.

    Args:
        pb: Parameter builder for parameterized queries
        query_conditions: Dynamic query conditions from user
        hardcoded_filter: Hardcoded filter (op_names, trace_ids, etc.)
        table_alias: Table alias for field references
        expand_columns: Columns to expand for object references
        field_to_object_join_alias_map: Map of object ref fields to CTE aliases

    Returns:
        List of SQL condition strings
    """
    conditions = []

    # Process each query condition
    for condition in query_conditions:
        condition_sql = condition.as_sql(
            pb,
            table_alias,
            expand_columns=expand_columns,
            field_to_object_join_alias_map=field_to_object_join_alias_map,
        )
        conditions.append(condition_sql)

    # Add hardcoded filter if present
    if hardcoded_filter is not None:
        hardcoded_sql = hardcoded_filter.as_sql(pb, table_alias)
        if hardcoded_sql:
            conditions.append(hardcoded_sql)

    return conditions


def build_query_joins(
    pb: ParamBuilder,
    table_alias: Optional[str],
    project_id_param_slot: str,
    needs_feedback: bool,
    include_storage_size: bool,
    include_total_storage_size: bool,
    order_fields: list["OrderField"],  # type: ignore
    expand_columns: Optional[list[str]],
    field_to_object_join_alias_map: Optional[dict[str, str]],
) -> list[str]:
    """Build all JOIN clauses needed for the query.

    Returns list of JOIN SQL strings (each is a complete LEFT JOIN ... ON ...).

    Args:
        pb: Parameter builder
        table_alias: Main table alias (calls_merged or calls_complete)
        project_id_param_slot: Parameterized project_id for JOINs
        needs_feedback: Whether feedback join is needed
        include_storage_size: Whether to join storage size stats
        include_total_storage_size: Whether to join total storage size stats
        order_fields: Order fields (may require object ref joins)
        expand_columns: Columns to expand for object references
        field_to_object_join_alias_map: Map for object ref joins

    Returns:
        List of JOIN clause SQL strings
    """
    # Import here to avoid circular dependencies
    from weave.trace_server.calls_query_builder.calls_query_builder import (
        build_feedback_join_sql,
        build_object_ref_joins_sql,
        build_storage_size_join_sql,
        build_total_storage_size_join_sql,
    )

    joins = []

    if needs_feedback:
        joins.append(
            build_feedback_join_sql(needs_feedback, project_id_param_slot, table_alias)
        )

    if include_storage_size:
        joins.append(
            build_storage_size_join_sql(
                include_storage_size, project_id_param_slot, table_alias
            )
        )

    if include_total_storage_size:
        joins.append(
            build_total_storage_size_join_sql(
                include_total_storage_size, project_id_param_slot, table_alias
            )
        )

    # Object ref joins for ordering
    if expand_columns and field_to_object_join_alias_map:
        object_ref_join = build_object_ref_joins_sql(
            pb,
            order_fields,
            expand_columns,
            field_to_object_join_alias_map,
            table_alias,
        )
        if object_ref_join:
            joins.append(object_ref_join)

    return joins


def build_order_by_clause(
    pb: ParamBuilder,
    order_fields: list["OrderField"],  # type: ignore
    table_alias: Optional[str] = None,
    expand_columns: Optional[list[str]] = None,
    field_to_object_join_alias_map: Optional[dict[str, str]] = None,
) -> Optional[str]:
    """Build ORDER BY clause.

    Returns None if no ordering, otherwise complete ORDER BY clause.

    Args:
        pb: Parameter builder
        order_fields: Fields to order by with direction
        table_alias: Table alias for field references
        expand_columns: Columns to expand for object references
        field_to_object_join_alias_map: Map for object ref fields

    Returns:
        ORDER BY clause string or None
    """
    if not order_fields:
        return None

    order_by_parts = [
        order_field.as_sql(
            pb, table_alias, expand_columns, field_to_object_join_alias_map
        )
        for order_field in order_fields
    ]

    return "ORDER BY " + ", ".join(order_by_parts)


def build_limit_offset_clause(
    limit: Optional[int],
    offset: Optional[int],
) -> tuple[str, str]:
    """Build LIMIT and OFFSET clauses.

    Returns:
        Tuple of (limit_clause, offset_clause) - both may be empty strings
    """
    limit_clause = f"LIMIT {limit}" if limit is not None else ""
    offset_clause = f"OFFSET {offset}" if offset is not None else ""
    return limit_clause, offset_clause
