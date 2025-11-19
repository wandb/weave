import datetime

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.orm import ParamBuilder


def make_threads_query(
    project_id: str,
    pb: ParamBuilder,
    *,
    limit: int | None = None,
    offset: int | None = None,
    sort_by: list[tsi.SortBy] | None = None,
    sortable_datetime_after: datetime.datetime | None = None,
    sortable_datetime_before: datetime.datetime | None = None,
    thread_ids: list[str] | None = None,
) -> str:
    """Generate a query to fetch threads with aggregated statistics from turn calls only.

    IMPORTANT: This filters to only include turn calls (where id = turn_id) to provide
    meaningful thread statistics based on conversation turns rather than all nested calls.

    This uses two-level aggregation to handle ClickHouse materialized view behavior.

    ClickHouse Background:
    - calls_merged is populated by a materialized view from call_parts
    - ClickHouse initially creates partial inserts, then background processes merge them
    - Before merging, we may have multiple rows per call_id with different field combinations:
      * Row 1: id=call-123, thread_id=NULL, started_at=T1, ended_at=NULL
      * Row 2: id=call-123, thread_id="thread-abc", started_at=NULL, ended_at=T2
    - SimpleAggregateFunction columns store values to be merged later

    Problem:
    - Direct GROUP BY thread_id would count partial rows incorrectly
    - Some calls might be missing thread_id in certain rows
    - Timing data might be split across multiple rows

    Solution:
    - Inner query: GROUP BY (id, trace_id) to properly aggregate each call first
    - Outer query: GROUP BY thread_id for final thread-level statistics

    Args:
        project_id: The project ID to filter by
        pb: Parameter builder for safe SQL parameter injection
        limit: Maximum number of threads to return
        offset: Number of threads to skip
        sort_by: List of sort criteria
        sortable_datetime_after: Only include calls with sortable_datetime after this timestamp.
                                Uses sortable_datetime column for efficient granule filtering.
        sortable_datetime_before: Only include calls with sortable_datetime before this timestamp.
                                 Uses sortable_datetime column for efficient granule filtering.
        thread_ids: Only include threads with thread_ids in this list

    Returns:
        SQL query string for threads aggregation
    """
    project_id_param = pb.add_param(project_id)

    # Build optional sortable_datetime filter clauses for ClickHouse granule optimization
    sortable_datetime_filter_clauses = []

    if sortable_datetime_after is not None:
        # Convert to datetime string format expected by ClickHouse
        datetime_str = sortable_datetime_after.strftime("%Y-%m-%d %H:%M:%S.%f")
        sortable_datetime_param = pb.add_param(datetime_str)
        sortable_datetime_filter_clauses.append(
            f"AND sortable_datetime > {{{sortable_datetime_param}: String}}"
        )

    if sortable_datetime_before is not None:
        # Convert to datetime string format expected by ClickHouse
        datetime_str = sortable_datetime_before.strftime("%Y-%m-%d %H:%M:%S.%f")
        sortable_datetime_param = pb.add_param(datetime_str)
        sortable_datetime_filter_clauses.append(
            f"AND sortable_datetime < {{{sortable_datetime_param}: String}}"
        )

    sortable_datetime_filter_clause = " ".join(sortable_datetime_filter_clauses)

    # Build thread filtering clauses for WHERE and HAVING
    # When thread_ids are specified:
    #   - WHERE: Include NULL rows (partial data) + rows matching thread_ids (optimization)
    #   - HAVING: Filter final aggregated thread_id to only specified thread_ids
    # When thread_ids are not specified:
    #   - WHERE: No additional filtering needed
    #   - HAVING: Filter out NULL/empty thread_ids
    where_thread_filter_clause = ""
    having_thread_filter_clause = ""

    if thread_ids is not None and len(thread_ids) > 0:
        # Create parameterized IN clause for multiple thread IDs
        thread_id_params = []
        for thread_id in thread_ids:
            thread_id_param = pb.add_param(thread_id)
            thread_id_params.append(f"{{{thread_id_param}: String}}")

        thread_ids_in_clause = f"({', '.join(thread_id_params)})"

        # WHERE: Include NULL (incomplete rows) OR matching thread_ids (optimization)
        where_thread_filter_clause = (
            f"AND (thread_id IS NULL OR thread_id IN {thread_ids_in_clause})"
        )

        # HAVING: Filter final aggregated thread_id to specified thread_ids only
        having_thread_filter_clause = (
            f"AND aggregated_thread_id IN {thread_ids_in_clause}"
        )
    else:
        # Filter out NULL and empty thread_ids when no specific thread_ids are requested
        having_thread_filter_clause = (
            "AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''"
        )

    # Two-level aggregation to handle ClickHouse materialized view partial merges
    #
    # OUTER QUERY: Aggregates at thread level with properly consolidated calls
    # - thread_id: The thread identifier
    # - turn_count: Count of turn calls in thread
    # - start_time: Earliest start time across all calls in thread
    # - last_updated: Latest end time across all calls in thread
    # - first_turn_id: Turn ID with earliest start_time
    # - last_turn_id: Turn ID with latest last_updated
    # - p50_turn_duration_ms: P50 of turn durations in milliseconds
    # - p99_turn_duration_ms: P99 of turn durations in milliseconds
    #
    # INNER QUERY: Consolidates each individual call before thread-level aggregation
    # This handles cases where calls_merged has multiple partial rows per call_id
    # due to ClickHouse materialized view background merge behavior
    # - id: Call identifier
    # - thread_id: Get any non-null thread_id for this call (all non-null values should be identical)
    # - call_start_time: Earliest start time for this call
    # - call_end_time: Latest end time for this call
    # - call_duration: Calculate call duration in milliseconds
    # - Group by call id to merge partial rows
    # - Filter to turn calls only
    query = f"""
    SELECT
        aggregated_thread_id AS thread_id,
        COUNT(*) AS turn_count,
        min(call_start_time) AS start_time,
        max(call_end_time) AS last_updated,
        argMin(id, call_start_time) AS first_turn_id,
        argMax(id, call_end_time) AS last_turn_id,
        quantile(0.5)(call_duration) AS p50_turn_duration_ms,
        quantile(0.99)(call_duration) AS p99_turn_duration_ms
    FROM (
        SELECT
            id,
            any(thread_id) AS aggregated_thread_id,
            min(started_at) AS call_start_time,
            max(ended_at) AS call_end_time,
            CASE
                WHEN call_end_time IS NOT NULL AND call_start_time IS NOT NULL
                THEN dateDiff('millisecond', call_start_time, call_end_time)
                ELSE NULL
            END AS call_duration
        FROM calls_merged
        WHERE project_id = {{{project_id_param}: String}}
            {sortable_datetime_filter_clause}
            {where_thread_filter_clause}
        GROUP BY (project_id, id)
        HAVING id = any(turn_id) {having_thread_filter_clause}
    ) AS properly_merged_calls
    GROUP BY aggregated_thread_id
    """

    # Add sorting
    if sort_by:
        order_clauses = []
        for sort in sort_by:
            field = _validate_and_map_sort_field(sort.field)
            direction = sort.direction.upper()
            order_clauses.append(f"{field} {direction}")
        query += f" ORDER BY {', '.join(order_clauses)}"
    else:
        # Default sorting by last_updated descending
        query += " ORDER BY last_updated DESC"

    # Add pagination
    if limit is not None:
        limit_param = pb.add_param(limit)
        query += f" LIMIT {{{limit_param}: Int64}}"

    if offset is not None:
        offset_param = pb.add_param(offset)
        query += f" OFFSET {{{offset_param}: Int64}}"

    return query


def make_threads_query_sqlite(
    project_id: str,
    *,
    limit: int | None = None,
    offset: int | None = None,
    sort_by: list[tsi.SortBy] | None = None,
    sortable_datetime_after: datetime.datetime | None = None,
    sortable_datetime_before: datetime.datetime | None = None,
    thread_ids: list[str] | None = None,
) -> tuple[str, list]:
    """Generate a SQLite query to fetch threads with aggregated statistics from turn calls only.

    This filters to only include turn calls (where id = turn_id) to provide meaningful
    thread statistics based on conversation turns rather than all nested calls.

    Args:
        project_id: The project ID to filter by
        limit: Maximum number of threads to return
        offset: Number of threads to skip
        sort_by: List of sort criteria
        sortable_datetime_after: Only include calls that started after this timestamp.
                                SQLite uses started_at since it doesn't have sortable_datetime column.
        sortable_datetime_before: Only include calls that started before this timestamp.
                                 SQLite uses started_at since it doesn't have sortable_datetime column.
        thread_ids: Only include threads with thread_ids in this list

    Returns:
        Tuple of (SQL query string, parameters list) for SQLite
    """
    parameters: list[str | int] = [project_id]

    # Build optional timestamp filter clauses (SQLite uses started_at instead of sortable_datetime)
    timestamp_filter_clauses = []

    if sortable_datetime_after is not None:
        timestamp_filter_clauses.append("AND started_at > ?")
        parameters.append(sortable_datetime_after.isoformat())

    if sortable_datetime_before is not None:
        timestamp_filter_clauses.append("AND started_at < ?")
        parameters.append(sortable_datetime_before.isoformat())

    timestamp_filter_clause = " ".join(timestamp_filter_clauses)

    # Build thread filtering clause
    # When thread_ids are specified, use IN clause (which already filters out NULL/empty)
    # When thread_ids are not specified, filter out NULL/empty thread_ids
    thread_filter_clause = ""
    if thread_ids is not None and len(thread_ids) > 0:
        # Create a parameterized IN clause for multiple thread IDs
        placeholders = ",".join("?" * len(thread_ids))
        thread_filter_clause = f"AND thread_id IN ({placeholders})"
        parameters.extend(thread_ids)
    else:
        # Filter out NULL and empty thread_ids when no specific thread_ids are requested
        thread_filter_clause = "AND thread_id IS NOT NULL AND thread_id != ''"

    # Base query - group by thread_id and collect statistics from turn calls only
    # - thread_id: The thread identifier
    # - turn_count: Count of turn calls in thread
    # - start_time: Minimum started_at timestamp in thread
    # - last_updated: Maximum ended_at timestamp in thread
    # - first_turn_id: Get turn ID with earliest start time for this thread
    # - last_turn_id: Get turn ID with latest end time for this thread
    # - p50_turn_duration_ms: P50 calculation placeholder - might be implemented properly later
    # - p99_turn_duration_ms: P99 calculation placeholder - might be implemented properly later
    # Only include turn calls for meaningful thread stats
    query = f"""
    SELECT
        thread_id,
        COUNT(*) AS turn_count,
        MIN(started_at) AS start_time,
        MAX(ended_at) AS last_updated,
        (SELECT id FROM calls c2
         WHERE c2.thread_id = c1.thread_id
         AND c2.project_id = c1.project_id
         AND c2.id = c2.turn_id
         ORDER BY c2.started_at ASC
         LIMIT 1) AS first_turn_id,
        (SELECT id FROM calls c2
         WHERE c2.thread_id = c1.thread_id
         AND c2.project_id = c1.project_id
         AND c2.id = c2.turn_id
         ORDER BY c2.ended_at DESC
         LIMIT 1) AS last_turn_id,
        -1 AS p50_turn_duration_ms,
        -1 AS p99_turn_duration_ms
    FROM calls c1
    WHERE project_id = ?
        AND id = turn_id
        {timestamp_filter_clause}
        {thread_filter_clause}
    GROUP BY thread_id
    """

    # Add sorting
    if sort_by:
        order_clauses = []
        for sort in sort_by:
            field = _validate_and_map_sort_field(sort.field)
            direction = sort.direction.upper()
            order_clauses.append(f"{field} {direction}")
        query += f" ORDER BY {', '.join(order_clauses)}"
    else:
        # Default sorting by last_updated descending
        query += " ORDER BY last_updated DESC"

    # Add pagination
    if limit is not None:
        query += " LIMIT ?"
        parameters.append(limit)

    if offset is not None:
        query += " OFFSET ?"
        parameters.append(offset)

    return query, parameters


def _validate_and_map_sort_field(field: str) -> str:
    """Validate and map sort field names to their SQL equivalents.

    Args:
        field: The field name from the API request

    Returns:
        The SQL column name to use in the query

    Raises:
        ValueError: If the field is not supported for sorting
    """
    # Map of API field names to SQL column names
    valid_fields = {
        "thread_id": "thread_id",
        "turn_count": "turn_count",
        "start_time": "start_time",
        "last_updated": "last_updated",
        "p50_turn_duration_ms": "p50_turn_duration_ms",
        "p99_turn_duration_ms": "p99_turn_duration_ms",
    }

    if field not in valid_fields:
        raise ValueError(
            f"Unsupported sort field: {field}. Supported fields: {list(valid_fields.keys())}"
        )

    return valid_fields[field]
