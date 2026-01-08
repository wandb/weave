"""Query builder utilities for annotation queues system.

This module provides query building functions for the queue-based call annotation system,
following the same patterns as threads_query_builder.py and other query builders in the codebase.
"""

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.orm import ParamBuilder

# Valid sort fields for annotation queues
VALID_QUEUE_SORT_FIELDS = {
    "id",
    "name",
    "created_at",
    "updated_at",
}

# Valid sort fields for annotation queue items
VALID_QUEUE_ITEM_SORT_FIELDS = {
    "call_started_at",
    "call_op_name",
    "created_at",
    "updated_at",
}

VALID_SORT_DIRECTIONS = {"asc", "desc"}


def _make_sort_clause(
    sort_by: list[tsi.SortBy] | None,
    valid_fields: set[str],
    default: str,
    table_prefix: str = "",
) -> str:
    """Build sort field list from sort_by list.

    Args:
        sort_by: List of SortBy objects
        valid_fields: Set of valid field names for sorting
        default: Default sort field list (without ORDER BY prefix)
        table_prefix: Optional table alias prefix (e.g., "qi." for joins)

    Returns:
        Sort field list string (e.g., "created_at ASC, id ASC"), or default if no valid sorts.
        Always appends 'id ASC' as final tiebreaker for stable, deterministic sorting.
    """
    if not sort_by:
        return default

    sort_clauses = []
    for sort in sort_by:
        if sort.field in valid_fields and sort.direction in VALID_SORT_DIRECTIONS:
            sort_clause = f"{table_prefix}{sort.field} {sort.direction.upper()}"
            sort_clauses.append(sort_clause)

    if not sort_clauses:
        return default

    # Always append id ASC as tiebreaker for stable sorting
    sort_clauses.append(f"{table_prefix}id ASC")
    return ", ".join(sort_clauses)


def make_queues_query(
    project_id: str,
    pb: ParamBuilder,
    *,
    name: str | None = None,
    sort_by: list[tsi.SortBy] | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> str:
    """Generate a query to fetch annotation queues for a project.

    Args:
        project_id: The project ID to filter by
        pb: Parameter builder for safe SQL parameter injection
        name: Optional filter by queue name (case-insensitive partial match using LIKE)
        sort_by: Optional list of sort specifications
        limit: Maximum number of queues to return
        offset: Number of queues to skip

    Returns:
        SQL query string for queues query
    """
    project_id_param = pb.add_param(project_id)

    # Build WHERE clause with optional name filter
    where_clauses = [
        f"project_id = {{{project_id_param}: String}}",
        "deleted_at IS NULL",
    ]

    if name is not None:
        # Use LIKE with wildcards for partial match, and lowerUTF8 for case-insensitive
        name_pattern = f"%{name}%"
        name_param = pb.add_param(name_pattern)
        where_clauses.append(
            f"lowerUTF8(name) LIKE lowerUTF8({{{name_param}: String}})"
        )

    where_clause = " AND ".join(where_clauses)

    # Build sort clause
    sort_fields = _make_sort_clause(
        sort_by, VALID_QUEUE_SORT_FIELDS, "created_at DESC, id ASC"
    )

    query = f"""
    SELECT
        id,
        project_id,
        name,
        description,
        scorer_refs,
        created_at,
        created_by,
        updated_at,
        deleted_at
    FROM annotation_queues
    WHERE {where_clause}
    ORDER BY {sort_fields}
    """

    if limit is not None:
        limit_param = pb.add_param(limit)
        query += f" LIMIT {{{limit_param}: Int64}}"

    if offset is not None:
        offset_param = pb.add_param(offset)
        query += f" OFFSET {{{offset_param}: Int64}}"

    return query


def make_queue_read_query(
    project_id: str,
    queue_id: str,
    pb: ParamBuilder,
) -> str:
    """Generate a query to fetch a specific annotation queue.

    Args:
        project_id: The project ID
        queue_id: The queue ID (UUID as string)
        pb: Parameter builder for safe SQL parameter injection

    Returns:
        SQL query string for reading a single queue
    """
    project_id_param = pb.add_param(project_id)
    queue_id_param = pb.add_param(queue_id)

    query = f"""
    SELECT
        id,
        project_id,
        name,
        description,
        scorer_refs,
        created_at,
        created_by,
        updated_at,
        deleted_at
    FROM annotation_queues
    WHERE project_id = {{{project_id_param}: String}}
        AND id = {{{queue_id_param}: String}}
        AND deleted_at IS NULL
    LIMIT 1
    """

    return query


def make_queue_create_query(
    project_id: str,
    queue_id: str,
    name: str,
    description: str | None,
    scorer_refs: list[str],
    created_by: str,
    pb: ParamBuilder,
) -> str:
    """Generate an INSERT query to create a new annotation queue.

    Args:
        project_id: The project ID
        queue_id: The queue ID (UUID as string)
        name: Queue name
        description: Optional queue description
        scorer_refs: Array of scorer weave refs
        created_by: W&B user ID of creator
        pb: Parameter builder for safe SQL parameter injection

    Returns:
        SQL query string for inserting a queue
    """
    project_id_param = pb.add_param(project_id)
    queue_id_param = pb.add_param(queue_id)
    name_param = pb.add_param(name)
    description_param = pb.add_param(description)
    scorer_refs_param = pb.add_param(scorer_refs)
    created_by_param = pb.add_param(created_by)

    query = f"""
    INSERT INTO annotation_queues (
        id,
        project_id,
        name,
        description,
        scorer_refs,
        created_by
    ) VALUES (
        {{{queue_id_param}: String}},
        {{{project_id_param}: String}},
        {{{name_param}: String}},
        {{{description_param}: Nullable(String)}},
        {{{scorer_refs_param}: Array(String)}},
        {{{created_by_param}: String}}
    )
    """

    return query


def make_queue_add_calls_check_duplicates_query(
    project_id: str,
    queue_id: str,
    call_ids: list[str],
    pb: ParamBuilder,
) -> str:
    """Generate a query to check for existing calls in a queue (duplicate prevention).

    Args:
        project_id: The project ID
        queue_id: The queue ID (UUID as string)
        call_ids: List of call IDs to check
        pb: Parameter builder for safe SQL parameter injection

    Returns:
        SQL query string to find existing call_ids in the queue
    """
    project_id_param = pb.add_param(project_id)
    queue_id_param = pb.add_param(queue_id)
    call_ids_param = pb.add_param(call_ids)

    query = f"""
    SELECT call_id
    FROM annotation_queue_items
    WHERE project_id = {{{project_id_param}: String}}
        AND queue_id = {{{queue_id_param}: String}}
        AND call_id IN {{{call_ids_param}: Array(String)}}
        AND deleted_at IS NULL
    """

    return query


def make_queue_add_calls_fetch_calls_query(
    project_id: str,
    call_ids: list[str],
    pb: ParamBuilder,
) -> str:
    """Generate a query to fetch call details for adding to queue.

    This fetches the fields we cache in annotation_queue_items for performance.

    Args:
        project_id: The project ID
        call_ids: List of call IDs to fetch
        pb: Parameter builder for safe SQL parameter injection

    Returns:
        SQL query string to fetch call details
    """
    project_id_param = pb.add_param(project_id)
    call_ids_param = pb.add_param(call_ids)

    # Query the calls_merged table, using any() to handle SimpleAggregateFunction columns
    query = f"""
    SELECT
        id,
        any(started_at) as started_at,
        any(ended_at) as ended_at,
        any(op_name) as op_name,
        any(trace_id) as trace_id
    FROM calls_merged
    WHERE project_id = {{{project_id_param}: String}}
        AND id IN {{{call_ids_param}: Array(String)}}
    GROUP BY (project_id, id)
    """

    return query


def make_queues_stats_query(
    project_id: str,
    queue_ids: list[str],
    pb: ParamBuilder,
) -> str:
    """Generate a query to fetch stats for multiple annotation queues.

    This query returns:
    - total_items: Count of items in annotation_queue_items per queue
    - completed_items: Count of items where annotation_state is 'completed' or 'skipped'

    Note: An item is considered "completed" when any annotator has finished working on it
    (annotation_state = 'completed' or 'skipped'). Items with state 'in_progress' or
    'unstarted' are not counted as completed.

    Args:
        project_id: The project ID
        queue_ids: List of queue IDs to get stats for
        pb: Parameter builder for safe SQL parameter injection

    Returns:
        SQL query string for fetching queue stats
    """
    project_id_param = pb.add_param(project_id)
    queue_ids_param = pb.add_param(queue_ids)

    # Using LEFT JOIN to get stats for queues even if they have no items or progress
    # Only count items where annotation_state is 'completed' or 'skipped', not 'in_progress' or 'unstarted'
    query = f"""
    WITH total_items_per_queue AS (
        SELECT
            queue_id,
            count(*) as total_items
        FROM annotation_queue_items
        WHERE project_id = {{{project_id_param}: String}}
            AND queue_id IN {{{queue_ids_param}: Array(String)}}
            AND deleted_at IS NULL
        GROUP BY queue_id
    ),
    completed_items_per_queue AS (
        SELECT
            queue_id,
            count(DISTINCT queue_item_id) as completed_items
        FROM annotator_queue_items_progress
        WHERE project_id = {{{project_id_param}: String}}
            AND queue_id IN {{{queue_ids_param}: Array(String)}}
            AND annotation_state IN ('completed', 'skipped')
            AND deleted_at IS NULL
        GROUP BY queue_id
    )
    SELECT
        q.queue_id,
        coalesce(t.total_items, 0) as total_items,
        coalesce(c.completed_items, 0) as completed_items
    FROM (
        SELECT arrayJoin({{{queue_ids_param}: Array(String)}}) as queue_id
    ) q
    LEFT JOIN total_items_per_queue t ON q.queue_id = t.queue_id
    LEFT JOIN completed_items_per_queue c ON q.queue_id = c.queue_id
    """

    return query


def make_queue_items_query(
    project_id: str,
    queue_id: str,
    pb: ParamBuilder,
    *,
    filter: tsi.AnnotationQueueItemsFilter | None = None,
    sort_by: list[tsi.SortBy] | None = None,
    limit: int | None = None,
    offset: int | None = None,
    include_position: bool = False,
) -> str:
    """Generate a query to fetch items in an annotation queue.

    Joins with annotator_queue_items_progress to include annotation state.
    If no progress record exists, the state is 'unstarted'.
    If progress records exist (possibly from multiple annotators), returns the most recent state.

    Args:
        project_id: The project ID to filter by
        queue_id: The queue ID to filter by
        pb: Parameter builder for safe SQL parameter injection
        filter: Optional filter object for filtering results
        sort_by: Optional list of sort specifications
        limit: Maximum number of items to return
        offset: Number of items to skip
        include_position: If True, include position_in_queue field (1-based index)

    Returns:
        SQL query string for queue items query
    """
    project_id_param = pb.add_param(project_id)
    queue_id_param = pb.add_param(queue_id)

    # Build base WHERE clause for project and queue filtering
    where_clauses = [
        f"qi.project_id = {{{project_id_param}: String}}",
        f"qi.queue_id = {{{queue_id_param}: String}}",
        "qi.deleted_at IS NULL",
    ]

    # Add filters that can be applied directly on queue_items table
    if filter is not None:
        if filter.call_id is not None:
            param = pb.add(filter.call_id, None, "String")
            where_clauses.append(f"qi.call_id = {param}")

        if filter.call_op_name is not None:
            param = pb.add(filter.call_op_name, None, "String")
            where_clauses.append(f"qi.call_op_name = {param}")

        if filter.call_trace_id is not None:
            param = pb.add(filter.call_trace_id, None, "String")
            where_clauses.append(f"qi.call_trace_id = {param}")

        if filter.added_by is not None:
            param = pb.add(filter.added_by, None, "String")
            where_clauses.append(f"qi.added_by = {param}")

    where_clause = " AND ".join(where_clauses)

    # Build sort field list (default to created_at ASC, id ASC for queue items)
    # _make_sort_clause always adds id ASC as tiebreaker for deterministic ordering
    sort_fields = _make_sort_clause(
        sort_by,
        VALID_QUEUE_ITEM_SORT_FIELDS,
        "created_at ASC, id ASC",
        table_prefix="",  # No prefix needed since we select from subquery
    )

    # LEFT JOIN with progress table to get annotation state
    # Using argMax to get the most recent annotation_state when multiple annotators have worked on the item
    # Using any() for qi fields since they're functionally dependent on qi.id (same for all rows with same id)
    # The annotation_state enum includes 'unstarted' as the lowest numeric value (0).
    # When no progress records exist in the LEFT JOIN, ClickHouse's argMax() returns the default
    # enum value (the one with the lowest numeric code), which is 'unstarted'. This naturally
    # handles the case where no annotator has worked on an item yet.
    # Cast annotation_state enum to String so it can be compared with string filters
    inner_query = f"""
    SELECT
        qi.id,
        any(qi.project_id) as project_id,
        any(qi.queue_id) as queue_id,
        any(qi.call_id) as call_id,
        any(qi.call_started_at) as call_started_at,
        any(qi.call_ended_at) as call_ended_at,
        any(qi.call_op_name) as call_op_name,
        any(qi.call_trace_id) as call_trace_id,
        any(qi.display_fields) as display_fields,
        any(qi.added_by) as added_by,
        any(qi.created_at) as created_at,
        any(qi.created_by) as created_by,
        any(qi.updated_at) as updated_at,
        any(qi.deleted_at) as deleted_at,
        toString(argMax(p.annotation_state, p.updated_at)) as annotation_state
    FROM annotation_queue_items qi
    LEFT JOIN annotator_queue_items_progress p
        ON p.queue_item_id = qi.id
        AND p.project_id = qi.project_id
        AND p.deleted_at IS NULL
    WHERE {where_clause}
    GROUP BY qi.id
    """

    # If include_position is requested, wrap the query with ROW_NUMBER()
    # to compute position in the full queue (1-based)
    # Note: We use the same ORDER BY for both ROW_NUMBER and the outer query to ensure
    # position numbers match the display order. While this may look like double sorting,
    # it's necessary because the SQL standard doesn't guarantee that window function
    # ordering is preserved in the final result. Modern query planners can often optimize
    # away the redundant sort when they detect the data is already ordered.
    if include_position:
        # Reuse sort_fields directly - no string manipulation needed!
        # This ensures position numbering matches the final display order
        inner_query = f"""
        SELECT
            *,
            ROW_NUMBER() OVER (ORDER BY {sort_fields}) as position_in_queue
        FROM (
            {inner_query}
        )
        """

    # If there's an annotation_states filter, we need to wrap in outer query
    # since annotation_state is computed by the aggregation
    if (
        filter is not None
        and filter.annotation_states is not None
        and len(filter.annotation_states) > 0
    ):
        param = pb.add(filter.annotation_states, None, "Array(String)")
        sql_query = f"""
        SELECT * FROM (
            {inner_query}
        )
        WHERE annotation_state IN {param}
        ORDER BY {sort_fields}
        """
    else:
        sql_query = f"{inner_query}\nORDER BY {sort_fields}"

    if limit is not None:
        limit_param = pb.add_param(limit)
        sql_query += f" LIMIT {{{limit_param}: Int64}}"

    if offset is not None:
        offset_param = pb.add_param(offset)
        sql_query += f" OFFSET {{{offset_param}: Int64}}"

    return sql_query
