import datetime
from typing import Optional, Union

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.orm import ParamBuilder


def make_threads_query(
    project_id: str,
    pb: ParamBuilder,
    *,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    sort_by: Optional[list[tsi.SortBy]] = None,
    sortable_datetime_after: Optional[datetime.datetime] = None,
    sortable_datetime_before: Optional[datetime.datetime] = None,
) -> str:
    """
    Generate a query to fetch threads with aggregated statistics from turn calls only.

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

    # Two-level aggregation to handle ClickHouse materialized view partial merges
    query = f"""
    SELECT
        thread_id,
        COUNT(*) as turn_count,
        min(call_start_time) as start_time,          -- Earliest start time across all calls in thread
        max(call_end_time) as last_updated,          -- Latest end time across all calls in thread
        argMin(id, call_start_time) as first_turn_id,     -- Turn ID with earliest start_time
        argMax(id, call_end_time) as last_turn_id,   -- Turn ID with latest last_updated
        quantile(0.5)(call_duration) as p50_turn_duration_ms,  -- P50 of turn durations in milliseconds
        quantile(0.99)(call_duration) as p99_turn_duration_ms  -- P99 of turn durations in milliseconds
    FROM (
        -- INNER QUERY: Consolidate each individual call before thread-level aggregation
        -- This handles cases where calls_merged has multiple partial rows per call_id
        -- due to ClickHouse materialized view background merge behavior
        SELECT
            id,                              -- Call identifier
            any(thread_id) as thread_id,     -- Get any non-null thread_id for this call
                                            -- (all non-null values should be identical)
            min(started_at) as call_start_time,   -- Earliest start time for this call
            max(ended_at) as call_end_time,   -- Latest end time for this call
            -- Calculate call duration in milliseconds
            CASE
                WHEN call_end_time IS NOT NULL AND call_start_time IS NOT NULL
                THEN dateDiff('millisecond', call_start_time, call_end_time)
                ELSE NULL
            END as call_duration
        FROM calls_merged
        WHERE project_id = {{{project_id_param}: String}}
            {sortable_datetime_filter_clause}
        GROUP BY id                         -- Group by call id to merge partial rows
        HAVING thread_id IS NOT NULL AND thread_id != '' AND id = any(turn_id)  -- Filter to turn calls only
    ) as properly_merged_calls
    -- OUTER QUERY: Now aggregate at thread level with properly consolidated calls
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
        limit_param = pb.add_param(limit)
        query += f" LIMIT {{{limit_param}: Int64}}"

    if offset is not None:
        offset_param = pb.add_param(offset)
        query += f" OFFSET {{{offset_param}: Int64}}"

    return query


def make_threads_query_sqlite(
    project_id: str,
    *,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    sort_by: Optional[list[tsi.SortBy]] = None,
    sortable_datetime_after: Optional[datetime.datetime] = None,
    sortable_datetime_before: Optional[datetime.datetime] = None,
) -> tuple[str, list]:
    """
    Generate a SQLite query to fetch threads with aggregated statistics from turn calls only.

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

    Returns:
        Tuple of (SQL query string, parameters list) for SQLite
    """
    parameters: list[Union[str, int]] = [project_id]

    # Build optional timestamp filter clauses (SQLite uses started_at instead of sortable_datetime)
    timestamp_filter_clauses = []

    if sortable_datetime_after is not None:
        timestamp_filter_clauses.append("AND started_at > ?")
        parameters.append(sortable_datetime_after.isoformat())

    if sortable_datetime_before is not None:
        timestamp_filter_clauses.append("AND started_at < ?")
        parameters.append(sortable_datetime_before.isoformat())

    timestamp_filter_clause = " ".join(timestamp_filter_clauses)

    # Base query - group by thread_id and collect statistics from turn calls only
    query = f"""
    SELECT
        thread_id,
        COUNT(*) as turn_count,
        MIN(started_at) as start_time,
        MAX(ended_at) as last_updated,
        -- Get turn ID with earliest start time for this thread
        (SELECT id FROM calls c2
         WHERE c2.thread_id = c1.thread_id
         AND c2.project_id = c1.project_id
         AND c2.id = c2.turn_id
         ORDER BY c2.started_at ASC
         LIMIT 1) as first_turn_id,
        -- Get turn ID with latest end time for this thread
        (SELECT id FROM calls c2
         WHERE c2.thread_id = c1.thread_id
         AND c2.project_id = c1.project_id
         AND c2.id = c2.turn_id
         ORDER BY c2.ended_at DESC
         LIMIT 1) as last_turn_id,
        -- P50 calculation placeholder - might be implemented properly later
        -1 as p50_turn_duration_ms,
        -- P99 calculation placeholder - might be implemented properly later
        -1 as p99_turn_duration_ms
    FROM calls c1
    WHERE project_id = ?
        AND thread_id IS NOT NULL
        AND thread_id != ''
        AND id = turn_id                 -- Only include turn calls for meaningful thread stats
        {timestamp_filter_clause}
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
    """
    Validate and map sort field names to their SQL equivalents.

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
