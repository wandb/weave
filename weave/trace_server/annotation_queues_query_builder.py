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

VALID_SORT_DIRECTIONS = {"asc", "desc"}


def _make_sort_clause(sort_by: list[tsi.SortBy] | None) -> str:
    """Build ORDER BY clause from sort_by list.

    Args:
        sort_by: List of SortBy objects

    Returns:
        ORDER BY clause string, or default "ORDER BY created_at DESC" if no valid sorts
    """
    if not sort_by:
        return "ORDER BY created_at DESC"

    sort_clauses = []
    for sort in sort_by:
        if (
            sort.field in VALID_QUEUE_SORT_FIELDS
            and sort.direction in VALID_SORT_DIRECTIONS
        ):
            sort_clause = f"{sort.field} {sort.direction.upper()}"
            sort_clauses.append(sort_clause)

    if not sort_clauses:
        return "ORDER BY created_at DESC"

    return "ORDER BY " + ", ".join(sort_clauses)


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
    sort_clause = _make_sort_clause(sort_by)

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
    {sort_clause}
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
