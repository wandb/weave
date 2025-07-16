from datetime import datetime, timedelta
from typing import Optional

from weave.trace_server.orm import ParamBuilder


def make_extended_project_stats_query(
    project_id: str,
    pb: ParamBuilder,
    time_start: Optional[datetime],
    time_end: Optional[datetime],
    time_delta: timedelta,
) -> str:
    """
    Build a query to get extended project statistics binned by time intervals.

    Returns statistics for:
    - num_traces: Number of unique trace_ids
    - trace_storage_size: Total size of all call data
    - object_storage_size: Total size of all objects
    - table_storage_size: Total size of all table rows
    - file_storage_size: Total size of all files

    Grouped by:
    - Time bins based on time_delta
    - User (wb_user_id) where available
    """
    project_id_param = pb.add_param(project_id)

    # Convert timedelta to seconds for ClickHouse interval
    interval_seconds = int(time_delta.total_seconds())
    interval_param = pb.add_param(interval_seconds)

    # Build time filters
    time_filters = []
    if time_start:
        time_start_param = pb.add_param(time_start)
        time_filters.append(f"started_at >= {{{time_start_param}: DateTime64(3)}}")
    if time_end:
        time_end_param = pb.add_param(time_end)
        time_filters.append(f"started_at <= {{{time_end_param}: DateTime64(3)}}")

    time_where_clause = ""
    if time_filters:
        time_where_clause = " AND " + " AND ".join(time_filters)

    # For files and tables, we'll use created_at for time filtering since they don't have started_at
    file_table_time_filters = []
    if time_start:
        file_table_time_filters.append(
            f"created_at >= {{{time_start_param}: DateTime64(3)}}"
        )
    if time_end:
        file_table_time_filters.append(
            f"created_at <= {{{time_end_param}: DateTime64(3)}}"
        )

    file_table_time_where = ""
    if file_table_time_filters:
        file_table_time_where = " AND " + " AND ".join(file_table_time_filters)

    # Main query that combines all statistics
    query = f"""
    WITH time_bins AS (
        -- Generate time bins based on the interval
        SELECT 
            toStartOfInterval(started_at, INTERVAL {{{interval_param}: UInt32}} SECOND) as time_bin
        FROM calls_merged_stats
        WHERE project_id = {{{project_id_param}: String}}
            AND started_at IS NOT NULL
            {time_where_clause}
        GROUP BY time_bin
        
        UNION DISTINCT
        
        -- Include time bins from files and tables based on created_at
        SELECT 
            toStartOfInterval(created_at, INTERVAL {{{interval_param}: UInt32}} SECOND) as time_bin
        FROM files_stats
        WHERE project_id = {{{project_id_param}: String}}
            {file_table_time_where}
        GROUP BY time_bin
        
        UNION DISTINCT
        
        SELECT 
            toStartOfInterval(created_at, INTERVAL {{{interval_param}: UInt32}} SECOND) as time_bin
        FROM table_rows_stats
        WHERE project_id = {{{project_id_param}: String}}
            {file_table_time_where}
        GROUP BY time_bin
        
        UNION DISTINCT
        
        SELECT 
            toStartOfInterval(created_at, INTERVAL {{{interval_param}: UInt32}} SECOND) as time_bin
        FROM object_versions_stats
        WHERE project_id = {{{project_id_param}: String}}
            {file_table_time_where}
        GROUP BY time_bin
    ),
    
    -- Get trace stats by user and time bin
    trace_stats AS (
        SELECT 
            toStartOfInterval(started_at, INTERVAL {{{interval_param}: UInt32}} SECOND) as time_bin,
            wb_user_id,
            COUNT(DISTINCT trace_id) as num_traces,
            SUM(
                COALESCE(attributes_size_bytes, 0) +
                COALESCE(inputs_size_bytes, 0) +
                COALESCE(output_size_bytes, 0) +
                COALESCE(summary_size_bytes, 0)
            ) as trace_storage_size
        FROM calls_merged_stats
        WHERE project_id = {{{project_id_param}: String}}
            AND started_at IS NOT NULL
            {time_where_clause}
        GROUP BY time_bin, wb_user_id
    ),
    
    -- Get object stats by user and time bin
    object_stats AS (
        SELECT 
            toStartOfInterval(created_at, INTERVAL {{{interval_param}: UInt32}} SECOND) as time_bin,
            wb_user_id,
            SUM(size_bytes) as object_storage_size
        FROM object_versions_stats
        WHERE project_id = {{{project_id_param}: String}}
            {file_table_time_where}
        GROUP BY time_bin, wb_user_id
    ),
    
    -- Get file stats by time bin (no user info available)
    file_stats AS (
        SELECT 
            toStartOfInterval(created_at, INTERVAL {{{interval_param}: UInt32}} SECOND) as time_bin,
            SUM(size_bytes) as file_storage_size
        FROM files_stats
        WHERE project_id = {{{project_id_param}: String}}
            {file_table_time_where}
        GROUP BY time_bin
    ),
    
    -- Get table stats by time bin (no user info available)
    table_stats AS (
        SELECT 
            toStartOfInterval(created_at, INTERVAL {{{interval_param}: UInt32}} SECOND) as time_bin,
            SUM(size_bytes) as table_storage_size
        FROM table_rows_stats
        WHERE project_id = {{{project_id_param}: String}}
            {file_table_time_where}
        GROUP BY time_bin
    ),
    
    -- Combine all stats
    combined_stats AS (
        SELECT 
            tb.time_bin,
            COALESCE(ts.wb_user_id, os.wb_user_id, 'unknown') as wb_user_id,
            COALESCE(ts.num_traces, 0) as num_traces,
            COALESCE(ts.trace_storage_size, 0) as trace_storage_size,
            COALESCE(os.object_storage_size, 0) as object_storage_size,
            COALESCE(fs.file_storage_size, 0) as file_storage_size,
            COALESCE(tbs.table_storage_size, 0) as table_storage_size
        FROM time_bins tb
        LEFT JOIN trace_stats ts ON tb.time_bin = ts.time_bin
        LEFT JOIN object_stats os ON tb.time_bin = os.time_bin AND (ts.wb_user_id = os.wb_user_id OR (ts.wb_user_id IS NULL AND os.wb_user_id IS NULL))
        LEFT JOIN file_stats fs ON tb.time_bin = fs.time_bin
        LEFT JOIN table_stats tbs ON tb.time_bin = tbs.time_bin
    )
    
    -- Final result with user-level and total aggregations
    SELECT 
        time_bin as time_start,
        time_bin + INTERVAL {{{interval_param}: UInt32}} SECOND as time_end,
        wb_user_id,
        num_traces,
        trace_storage_size,
        object_storage_size,
        file_storage_size,
        table_storage_size,
        -- Also calculate totals for each time bin
        SUM(num_traces) OVER (PARTITION BY time_bin) as total_num_traces,
        SUM(trace_storage_size) OVER (PARTITION BY time_bin) as total_trace_storage_size,
        SUM(object_storage_size) OVER (PARTITION BY time_bin) as total_object_storage_size,
        MAX(file_storage_size) OVER (PARTITION BY time_bin) as total_file_storage_size,  -- MAX because files aren't user-specific
        MAX(table_storage_size) OVER (PARTITION BY time_bin) as total_table_storage_size  -- MAX because tables aren't user-specific
    FROM combined_stats
    ORDER BY time_bin, wb_user_id
    """

    return query
