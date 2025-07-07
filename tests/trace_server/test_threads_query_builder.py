import datetime

import pytest
import sqlparse

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.threads_query_builder import (
    _validate_and_map_sort_field,
    make_threads_query,
    make_threads_query_sqlite,
)


def assert_clickhouse_sql(expected_query: str, expected_params: dict, **kwargs):
    """Helper to test ClickHouse query generation."""
    pb = ParamBuilder("pb")
    query = make_threads_query(pb=pb, **kwargs)
    params = pb.get_params()

    expected_formatted = sqlparse.format(expected_query, reindent=True)
    found_formatted = sqlparse.format(query, reindent=True)

    assert (
        expected_formatted == found_formatted
    ), f"Query mismatch:\nExpected:\n{expected_formatted}\n\nFound:\n{found_formatted}"
    assert (
        expected_params == params
    ), f"Params mismatch:\nExpected: {expected_params}\nFound: {params}"


def assert_sqlite_sql(expected_query: str, expected_params: list, **kwargs):
    """Helper to test SQLite query generation."""
    query, params = make_threads_query_sqlite(**kwargs)

    expected_formatted = sqlparse.format(expected_query, reindent=True)
    found_formatted = sqlparse.format(query, reindent=True)

    assert (
        expected_formatted == found_formatted
    ), f"Query mismatch:\nExpected:\n{expected_formatted}\n\nFound:\n{found_formatted}"
    assert (
        expected_params == params
    ), f"Params mismatch:\nExpected: {expected_params}\nFound: {params}"


# Basic Functionality Tests


def test_clickhouse_basic_query():
    """Test basic ClickHouse query with turn-only filtering."""
    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}

            GROUP BY id                         -- Group by call id to merge partial rows
            HAVING thread_id IS NOT NULL AND thread_id != '' AND id = any(turn_id)  -- Filter to turn calls only
        ) as properly_merged_calls
        -- OUTER QUERY: Now aggregate at thread level with properly consolidated calls
        GROUP BY thread_id
        ORDER BY last_updated DESC
        """,
        {"pb_0": "test_project"},
        project_id="test_project",
    )


def test_sqlite_basic_query():
    """Test basic SQLite query with turn-only filtering."""
    assert_sqlite_sql(
        """
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

            GROUP BY thread_id
            ORDER BY last_updated DESC
            """,
        ["test_project"],
        project_id="test_project",
    )


# Sorting Tests


def test_clickhouse_custom_sorting():
    """Test ClickHouse query with custom sorting."""
    sort_by = [
        tsi.SortBy(field="turn_count", direction="asc"),
        tsi.SortBy(field="start_time", direction="desc"),
    ]

    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}

            GROUP BY id                         -- Group by call id to merge partial rows
            HAVING thread_id IS NOT NULL AND thread_id != '' AND id = any(turn_id)  -- Filter to turn calls only
        ) as properly_merged_calls
        -- OUTER QUERY: Now aggregate at thread level with properly consolidated calls
        GROUP BY thread_id
        ORDER BY turn_count ASC, start_time DESC
        """,
        {"pb_0": "test_project"},
        project_id="test_project",
        sort_by=sort_by,
    )


def test_sqlite_custom_sorting():
    """Test SQLite query with custom sorting."""
    sort_by = [
        tsi.SortBy(field="thread_id", direction="asc"),
        tsi.SortBy(field="turn_count", direction="desc"),
    ]

    assert_sqlite_sql(
        """
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

        GROUP BY thread_id
        ORDER BY thread_id ASC, turn_count DESC
        """,
        ["test_project"],
        project_id="test_project",
        sort_by=sort_by,
    )


# Pagination Tests


def test_clickhouse_with_limit():
    """Test ClickHouse query with limit."""
    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}

            GROUP BY id                         -- Group by call id to merge partial rows
            HAVING thread_id IS NOT NULL AND thread_id != '' AND id = any(turn_id)  -- Filter to turn calls only
        ) as properly_merged_calls
        -- OUTER QUERY: Now aggregate at thread level with properly consolidated calls
        GROUP BY thread_id
        ORDER BY last_updated DESC
        LIMIT {pb_1: Int64}
        """,
        {"pb_0": "test_project", "pb_1": 50},
        project_id="test_project",
        limit=50,
    )


def test_clickhouse_with_limit_and_offset():
    """Test ClickHouse query with limit and offset."""
    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}

            GROUP BY id                         -- Group by call id to merge partial rows
            HAVING thread_id IS NOT NULL AND thread_id != '' AND id = any(turn_id)  -- Filter to turn calls only
        ) as properly_merged_calls
        -- OUTER QUERY: Now aggregate at thread level with properly consolidated calls
        GROUP BY thread_id
        ORDER BY last_updated DESC
        LIMIT {pb_1: Int64}
        OFFSET {pb_2: Int64}
        """,
        {"pb_0": "test_project", "pb_1": 25, "pb_2": 100},
        project_id="test_project",
        limit=25,
        offset=100,
    )


def test_sqlite_with_limit_and_offset():
    """Test SQLite query with limit and offset."""
    assert_sqlite_sql(
        """
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

        GROUP BY thread_id
        ORDER BY last_updated DESC
        LIMIT ?
        OFFSET ?
        """,
        ["test_project", 10, 20],
        project_id="test_project",
        limit=10,
        offset=20,
    )


# Date Filtering Tests


def test_clickhouse_with_date_filters():
    """Test ClickHouse query with sortable_datetime filters."""
    after_date = datetime.datetime(2024, 1, 1, 12, 0, 0)
    before_date = datetime.datetime(2024, 12, 31, 23, 59, 59)

    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}
                AND sortable_datetime > {pb_1: String} AND sortable_datetime < {pb_2: String}
            GROUP BY id                         -- Group by call id to merge partial rows
            HAVING thread_id IS NOT NULL AND thread_id != '' AND id = any(turn_id)  -- Filter to turn calls only
        ) as properly_merged_calls
        -- OUTER QUERY: Now aggregate at thread level with properly consolidated calls
        GROUP BY thread_id
        ORDER BY last_updated DESC
        """,
        {
            "pb_0": "test_project",
            "pb_1": "2024-01-01 12:00:00.000000",
            "pb_2": "2024-12-31 23:59:59.000000",
        },
        project_id="test_project",
        sortable_datetime_after=after_date,
        sortable_datetime_before=before_date,
    )


def test_sqlite_with_date_filters():
    """Test SQLite query with started_at filters."""
    after_date = datetime.datetime(2024, 6, 15, 10, 30, 0)
    before_date = datetime.datetime(2024, 6, 15, 18, 0, 0)

    assert_sqlite_sql(
        """
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
            AND started_at > ? AND started_at < ?
        GROUP BY thread_id
        ORDER BY last_updated DESC
        """,
        ["test_project", "2024-06-15T10:30:00", "2024-06-15T18:00:00"],
        project_id="test_project",
        sortable_datetime_after=after_date,
        sortable_datetime_before=before_date,
    )


# Complex Scenarios


def test_clickhouse_full_featured_query():
    """Test ClickHouse query with all features: custom sorting, pagination, and date filtering."""
    after_date = datetime.datetime(2024, 1, 1)
    before_date = datetime.datetime(2024, 12, 31)
    sort_by = [tsi.SortBy(field="turn_count", direction="desc")]

    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}
                AND sortable_datetime > {pb_1: String} AND sortable_datetime < {pb_2: String}
            GROUP BY id                         -- Group by call id to merge partial rows
            HAVING thread_id IS NOT NULL AND thread_id != '' AND id = any(turn_id)  -- Filter to turn calls only
        ) as properly_merged_calls
        -- OUTER QUERY: Now aggregate at thread level with properly consolidated calls
        GROUP BY thread_id
        ORDER BY turn_count DESC
        LIMIT {pb_3: Int64}
        OFFSET {pb_4: Int64}
        """,
        {
            "pb_0": "test_project",
            "pb_1": "2024-01-01 00:00:00.000000",
            "pb_2": "2024-12-31 00:00:00.000000",
            "pb_3": 15,
            "pb_4": 30,
        },
        project_id="test_project",
        sortable_datetime_after=after_date,
        sortable_datetime_before=before_date,
        sort_by=sort_by,
        limit=15,
        offset=30,
    )


def test_sqlite_full_featured_query():
    """Test SQLite query with all features: custom sorting, pagination, and date filtering."""
    after_date = datetime.datetime(2024, 3, 15)
    sort_by = [
        tsi.SortBy(field="last_updated", direction="asc"),
        tsi.SortBy(field="thread_id", direction="desc"),
    ]

    assert_sqlite_sql(
        """
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
            AND started_at > ?
        GROUP BY thread_id
        ORDER BY last_updated ASC, thread_id DESC
        LIMIT ?
        """,
        ["test_project", "2024-03-15T00:00:00", 5],
        project_id="test_project",
        sortable_datetime_after=after_date,
        sort_by=sort_by,
        limit=5,
    )


# Edge Cases


def test_clickhouse_only_after_date():
    """Test ClickHouse query with only after date filter."""
    after_date = datetime.datetime(2024, 1, 1, 0, 0, 0)

    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}
                AND sortable_datetime > {pb_1: String}
            GROUP BY id                         -- Group by call id to merge partial rows
            HAVING thread_id IS NOT NULL AND thread_id != '' AND id = any(turn_id)  -- Filter to turn calls only
        ) as properly_merged_calls
        -- OUTER QUERY: Now aggregate at thread level with properly consolidated calls
        GROUP BY thread_id
        ORDER BY last_updated DESC
        """,
        {"pb_0": "test_project", "pb_1": "2024-01-01 00:00:00.000000"},
        project_id="test_project",
        sortable_datetime_after=after_date,
    )


def test_sqlite_only_before_date():
    """Test SQLite query with only before date filter."""
    before_date = datetime.datetime(2024, 12, 31, 23, 59, 59)

    assert_sqlite_sql(
        """
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
            AND started_at < ?
        GROUP BY thread_id
        ORDER BY last_updated DESC
        """,
        ["test_project", "2024-12-31T23:59:59"],
        project_id="test_project",
        sortable_datetime_before=before_date,
    )


# Validation Tests


def test_validate_and_map_sort_field():
    """Test the sort field validation function."""
    # Test valid fields
    assert _validate_and_map_sort_field("thread_id") == "thread_id"
    assert _validate_and_map_sort_field("turn_count") == "turn_count"
    assert _validate_and_map_sort_field("start_time") == "start_time"
    assert _validate_and_map_sort_field("last_updated") == "last_updated"
    assert (
        _validate_and_map_sort_field("p50_turn_duration_ms") == "p50_turn_duration_ms"
    )
    assert (
        _validate_and_map_sort_field("p99_turn_duration_ms") == "p99_turn_duration_ms"
    )

    # Test invalid fields - call IDs should not be sortable since they're just identifiers
    with pytest.raises(ValueError) as exc_info:
        _validate_and_map_sort_field("first_turn_id")
    assert "Unsupported sort field: first_turn_id" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        _validate_and_map_sort_field("last_turn_id")
    assert "Unsupported sort field: last_turn_id" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        _validate_and_map_sort_field("invalid_field")
    assert "Unsupported sort field: invalid_field" in str(exc_info.value)
    assert (
        "Supported fields: ['thread_id', 'turn_count', 'start_time', 'last_updated', 'p50_turn_duration_ms', 'p99_turn_duration_ms']"
        in str(exc_info.value)
    )


def test_sort_field_validation_in_query():
    """Test that invalid sort fields raise errors in query generation."""
    with pytest.raises(ValueError):
        invalid_sort = [tsi.SortBy(field="nonexistent_field", direction="asc")]
        make_threads_query_sqlite(project_id="test_project", sort_by=invalid_sort)


# Turn-ID Filtering Behavior Tests


def test_turn_filtering_explanation():
    """
    Test that demonstrates the key behavior: only turn calls are included.

    This test is more about documenting the expected behavior than testing
    implementation details. It shows that the filtering `id = turn_id` ensures
    only turn calls are included in thread statistics, not their descendants.
    """
    # The key filtering conditions in both implementations:
    # ClickHouse: "id = any(turn_id)" in HAVING clause
    # SQLite: "id = turn_id" in WHERE clause

    # This means:
    # ✅ Turn calls (where call.id == call.turn_id) are included
    # ❌ Descendant calls (where call.id != call.turn_id) are excluded

    # Verify this is present in both query builders
    pb = ParamBuilder("pb")
    clickhouse_query = make_threads_query(project_id="test", pb=pb)
    sqlite_query, _ = make_threads_query_sqlite(project_id="test")

    # Check that turn filtering is present
    assert "id = any(turn_id)" in clickhouse_query
    assert "id = turn_id" in sqlite_query

    # Check that thread filtering is also present (non-null, non-empty)
    assert "thread_id IS NOT NULL AND thread_id != ''" in clickhouse_query
    assert "thread_id IS NOT NULL" in sqlite_query
    assert "thread_id != ''" in sqlite_query


def test_query_structure_documentation():
    """
    Test that documents the structure and purpose of the threads query.

    This test serves as living documentation of what the threads query does
    and why it's structured the way it is.
    """
    pb = ParamBuilder("pb")
    query = make_threads_query(project_id="test_project", pb=pb)

    # Should be a two-level aggregation for ClickHouse
    assert "SELECT" in query  # Outer query
    assert "FROM (" in query  # Inner subquery
    assert "GROUP BY thread_id" in query  # Outer aggregation by thread
    assert "GROUP BY id" in query  # Inner aggregation by call

    # Should include key aggregations
    assert "COUNT(*) as turn_count" in query
    assert "min(call_start_time) as start_time" in query
    assert "max(call_end_time) as last_updated" in query

    # Should include turn filtering
    assert "id = any(turn_id)" in query

    # Should have default ordering
    assert "ORDER BY last_updated DESC" in query
