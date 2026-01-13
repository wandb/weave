import datetime

import pytest
import sqlparse

from weave.trace_server import trace_server_interface as tsi
from tests.trace_server.query_builder.utils import (
    assert_clickhouse_sql,
    assert_sqlite_sql,
)
from weave.trace_server.common_interface import SortBy
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable
from weave.trace_server.threads_query_builder import (
    _validate_and_map_sort_field,
    make_threads_query,
    make_threads_query_sqlite,
)


def assert_clickhouse_sql(
    expected_query: str,
    expected_params: dict,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
    **kwargs,
) -> None:
    """Helper to test ClickHouse query generation for threads.

    Args:
        expected_query: The expected SQL query string
        expected_params: The expected parameter dictionary
        read_table: The table to read from (defaults to CALLS_MERGED)
        **kwargs: Arguments to pass to make_threads_query
    """
    pb = ParamBuilder("pb")
    query = make_threads_query(pb=pb, read_table=read_table, **kwargs)
    params = pb.get_params()

    expected_formatted = sqlparse.format(expected_query, reindent=True)
    found_formatted = sqlparse.format(query, reindent=True)

    assert expected_formatted == found_formatted, (
        f"Query mismatch:\nExpected:\n{expected_formatted}\n\nFound:\n{found_formatted}"
    )
    assert expected_params == params, (
        f"Params mismatch:\nExpected: {expected_params}\nFound: {params}"
    )


def assert_sqlite_sql(expected_query: str, expected_params: list, **kwargs) -> None:
    """Helper to test SQLite query generation for threads.

    Args:
        expected_query: The expected SQL query string
        expected_params: The expected parameter list
        **kwargs: Arguments to pass to make_threads_query_sqlite
    """
    query, params = make_threads_query_sqlite(**kwargs)

    expected_formatted = sqlparse.format(expected_query, reindent=True)
    found_formatted = sqlparse.format(query, reindent=True)

    assert expected_formatted == found_formatted, (
        f"Query mismatch:\nExpected:\n{expected_formatted}\n\nFound:\n{found_formatted}"
    )
    assert expected_params == params, (
        f"Params mismatch:\nExpected: {expected_params}\nFound: {params}"
    )


# Basic Functionality Tests


@pytest.mark.parametrize(
    ("read_table", "table_name"),
    [
        (ReadTable.CALLS_MERGED, "calls_merged"),
        (ReadTable.CALLS_COMPLETE, "calls_complete"),
    ],
)
def test_clickhouse_basic_query(read_table: ReadTable, table_name: str):
    """Test basic ClickHouse query with turn-only filtering."""
    if read_table == ReadTable.CALLS_MERGED:
        # CALLS_MERGED uses two-level aggregation to handle partial merges
        expected_query = f"""
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
                FROM {table_name}
                WHERE project_id = {{pb_0: String}}

                GROUP BY (project_id, id)
                HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
            ) AS properly_merged_calls
            GROUP BY aggregated_thread_id
            ORDER BY last_updated DESC
            """
    else:
        # CALLS_COMPLETE uses single-level aggregation (no partial merges)
        expected_query = f"""
            SELECT
                thread_id AS thread_id,
                COUNT(*) AS turn_count,
                min(started_at) AS start_time,
                max(ended_at) AS last_updated,
                argMin(id, started_at) AS first_turn_id,
                argMax(id, ended_at) AS last_turn_id,
                quantile(0.5)(dateDiff('millisecond', started_at, ended_at)) AS p50_turn_duration_ms,
                quantile(0.99)(dateDiff('millisecond', started_at, ended_at)) AS p99_turn_duration_ms
            FROM
                {table_name}
            WHERE project_id = {{pb_0: String}}
                AND id = turn_id
            GROUP BY thread_id
            HAVING thread_id IS NOT NULL AND thread_id != ''
            ORDER BY last_updated DESC
            """

    assert_clickhouse_sql(
        expected_query,
        {"pb_0": "test_project"},
        read_table=read_table,
        project_id="test_project",
    )


def test_sqlite_basic_query():
    """Test basic SQLite query with turn-only filtering."""
    assert_sqlite_sql(
        """
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
                AND thread_id IS NOT NULL
                AND thread_id != ''
            GROUP BY thread_id
            ORDER BY last_updated DESC
            """,
        ["test_project"],
        project_id="test_project",
    )


# Sorting Tests


@pytest.mark.parametrize(
    ("read_table", "table_name"),
    [
        (ReadTable.CALLS_MERGED, "calls_merged"),
        (ReadTable.CALLS_COMPLETE, "calls_complete"),
    ],
)
def test_clickhouse_custom_sorting(read_table: ReadTable, table_name: str):
    """Test ClickHouse query with custom sorting."""
    sort_by = [
        SortBy(field="turn_count", direction="asc"),
        SortBy(field="start_time", direction="desc"),
    ]

    if read_table == ReadTable.CALLS_MERGED:
        expected_query = f"""
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
                FROM {table_name}
                WHERE project_id = {{pb_0: String}}

                GROUP BY (project_id, id)
                HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
            ) AS properly_merged_calls
            GROUP BY aggregated_thread_id
            ORDER BY turn_count ASC, start_time DESC
            """
    else:
        expected_query = f"""
            SELECT
                thread_id AS thread_id,
                COUNT(*) AS turn_count,
                min(started_at) AS start_time,
                max(ended_at) AS last_updated,
                argMin(id, started_at) AS first_turn_id,
                argMax(id, ended_at) AS last_turn_id,
                quantile(0.5)(dateDiff('millisecond', started_at, ended_at)) AS p50_turn_duration_ms,
                quantile(0.99)(dateDiff('millisecond', started_at, ended_at)) AS p99_turn_duration_ms
            FROM
                {table_name}
            WHERE project_id = {{pb_0: String}}
                AND id = turn_id
            GROUP BY thread_id
            HAVING thread_id IS NOT NULL AND thread_id != ''
            ORDER BY turn_count ASC, start_time DESC
            """

    assert_clickhouse_sql(
        expected_query,
        {"pb_0": "test_project"},
        read_table=read_table,
        project_id="test_project",
        sort_by=sort_by,
    )


def test_sqlite_custom_sorting():
    """Test SQLite query with custom sorting."""
    sort_by = [
        SortBy(field="thread_id", direction="asc"),
        SortBy(field="turn_count", direction="desc"),
    ]

    assert_sqlite_sql(
        """
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
            AND thread_id IS NOT NULL
            AND thread_id != ''
        GROUP BY thread_id
        ORDER BY thread_id ASC, turn_count DESC
        """,
        ["test_project"],
        project_id="test_project",
        sort_by=sort_by,
    )


# Pagination Tests


@pytest.mark.parametrize(
    ("read_table", "table_name"),
    [
        (ReadTable.CALLS_MERGED, "calls_merged"),
        (ReadTable.CALLS_COMPLETE, "calls_complete"),
    ],
)
def test_clickhouse_with_limit(read_table: ReadTable, table_name: str):
    """Test ClickHouse query with limit."""
    if read_table == ReadTable.CALLS_MERGED:
        expected_query = f"""
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
                FROM {table_name}
                WHERE project_id = {{pb_0: String}}

                GROUP BY (project_id, id)
                HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
            ) AS properly_merged_calls
            GROUP BY aggregated_thread_id
            ORDER BY last_updated DESC
            LIMIT {{pb_1: Int64}}
            """
    else:
        expected_query = f"""
            SELECT
                thread_id AS thread_id,
                COUNT(*) AS turn_count,
                min(started_at) AS start_time,
                max(ended_at) AS last_updated,
                argMin(id, started_at) AS first_turn_id,
                argMax(id, ended_at) AS last_turn_id,
                quantile(0.5)(dateDiff('millisecond', started_at, ended_at)) AS p50_turn_duration_ms,
                quantile(0.99)(dateDiff('millisecond', started_at, ended_at)) AS p99_turn_duration_ms
            FROM
                {table_name}
            WHERE project_id = {{pb_0: String}}
                AND id = turn_id
            GROUP BY thread_id
            HAVING thread_id IS NOT NULL AND thread_id != ''
            ORDER BY last_updated DESC
            LIMIT {{pb_1: Int64}}
            """

    assert_clickhouse_sql(
        expected_query,
        {"pb_0": "test_project", "pb_1": 50},
        read_table=read_table,
        project_id="test_project",
        limit=50,
    )


@pytest.mark.parametrize(
    ("read_table", "table_name"),
    [
        (ReadTable.CALLS_MERGED, "calls_merged"),
        (ReadTable.CALLS_COMPLETE, "calls_complete"),
    ],
)
def test_clickhouse_with_limit_and_offset(read_table: ReadTable, table_name: str):
    """Test ClickHouse query with limit and offset."""
    if read_table == ReadTable.CALLS_MERGED:
        expected_query = f"""
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
                FROM {table_name}
                WHERE project_id = {{pb_0: String}}

                GROUP BY (project_id, id)
                HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
            ) AS properly_merged_calls
            GROUP BY aggregated_thread_id
            ORDER BY last_updated DESC
            LIMIT {{pb_1: Int64}}
            OFFSET {{pb_2: Int64}}
            """
    else:
        expected_query = f"""
            SELECT
                thread_id AS thread_id,
                COUNT(*) AS turn_count,
                min(started_at) AS start_time,
                max(ended_at) AS last_updated,
                argMin(id, started_at) AS first_turn_id,
                argMax(id, ended_at) AS last_turn_id,
                quantile(0.5)(dateDiff('millisecond', started_at, ended_at)) AS p50_turn_duration_ms,
                quantile(0.99)(dateDiff('millisecond', started_at, ended_at)) AS p99_turn_duration_ms
            FROM
                {table_name}
            WHERE project_id = {{pb_0: String}}
                AND id = turn_id
            GROUP BY thread_id
            HAVING thread_id IS NOT NULL AND thread_id != ''
            ORDER BY last_updated DESC
            LIMIT {{pb_1: Int64}}
            OFFSET {{pb_2: Int64}}
            """

    assert_clickhouse_sql(
        expected_query,
        {"pb_0": "test_project", "pb_1": 25, "pb_2": 100},
        read_table=read_table,
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
            AND thread_id IS NOT NULL
            AND thread_id != ''
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


@pytest.mark.parametrize(
    ("read_table", "table_name"),
    [
        (ReadTable.CALLS_MERGED, "calls_merged"),
        (ReadTable.CALLS_COMPLETE, "calls_complete"),
    ],
)
def test_clickhouse_with_date_filters(read_table: ReadTable, table_name: str):
    """Test ClickHouse query with sortable_datetime filters."""
    after_date = datetime.datetime(2024, 1, 1, 12, 0, 0)
    before_date = datetime.datetime(2024, 12, 31, 23, 59, 59)

    if read_table == ReadTable.CALLS_MERGED:
        expected_query = f"""
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
                FROM {table_name}
                WHERE project_id = {{pb_0: String}}
                    AND sortable_datetime > {{pb_1: String}} AND sortable_datetime < {{pb_2: String}}
                GROUP BY (project_id, id)
                HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
            ) AS properly_merged_calls
            GROUP BY aggregated_thread_id
            ORDER BY last_updated DESC
            """
    else:
        expected_query = f"""
            SELECT
                thread_id AS thread_id,
                COUNT(*) AS turn_count,
                min(started_at) AS start_time,
                max(ended_at) AS last_updated,
                argMin(id, started_at) AS first_turn_id,
                argMax(id, ended_at) AS last_turn_id,
                quantile(0.5)(dateDiff('millisecond', started_at, ended_at)) AS p50_turn_duration_ms,
                quantile(0.99)(dateDiff('millisecond', started_at, ended_at)) AS p99_turn_duration_ms
            FROM
                {table_name}
            WHERE project_id = {{pb_0: String}}
                AND id = turn_id
                AND sortable_datetime > {{pb_1: String}} AND sortable_datetime < {{pb_2: String}}
            GROUP BY thread_id
            HAVING thread_id IS NOT NULL AND thread_id != ''
            ORDER BY last_updated DESC
            """

    assert_clickhouse_sql(
        expected_query,
        {
            "pb_0": "test_project",
            "pb_1": "2024-01-01 12:00:00.000000",
            "pb_2": "2024-12-31 23:59:59.000000",
        },
        read_table=read_table,
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
            AND started_at > ? AND started_at < ?
            AND thread_id IS NOT NULL
            AND thread_id != ''
        GROUP BY thread_id
        ORDER BY last_updated DESC
        """,
        ["test_project", "2024-06-15T10:30:00", "2024-06-15T18:00:00"],
        project_id="test_project",
        sortable_datetime_after=after_date,
        sortable_datetime_before=before_date,
    )


# Complex Scenarios


@pytest.mark.parametrize(
    ("read_table", "table_name"),
    [
        (ReadTable.CALLS_MERGED, "calls_merged"),
        (ReadTable.CALLS_COMPLETE, "calls_complete"),
    ],
)
def test_clickhouse_full_featured_query(read_table: ReadTable, table_name: str):
    """Test ClickHouse query with all features: custom sorting, pagination, and date filtering."""
    after_date = datetime.datetime(2024, 1, 1)
    before_date = datetime.datetime(2024, 12, 31)
    sort_by = [SortBy(field="turn_count", direction="desc")]

    if read_table == ReadTable.CALLS_MERGED:
        expected_query = f"""
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
                FROM {table_name}
                WHERE project_id = {{pb_0: String}}
                    AND sortable_datetime > {{pb_1: String}} AND sortable_datetime < {{pb_2: String}}
                GROUP BY (project_id, id)
                HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
            ) AS properly_merged_calls
            GROUP BY aggregated_thread_id
            ORDER BY turn_count DESC
            LIMIT {{pb_3: Int64}}
            OFFSET {{pb_4: Int64}}
            """
    else:
        expected_query = f"""
            SELECT
                thread_id AS thread_id,
                COUNT(*) AS turn_count,
                min(started_at) AS start_time,
                max(ended_at) AS last_updated,
                argMin(id, started_at) AS first_turn_id,
                argMax(id, ended_at) AS last_turn_id,
                quantile(0.5)(dateDiff('millisecond', started_at, ended_at)) AS p50_turn_duration_ms,
                quantile(0.99)(dateDiff('millisecond', started_at, ended_at)) AS p99_turn_duration_ms
            FROM
                {table_name}
            WHERE project_id = {{pb_0: String}}
                AND id = turn_id
                AND sortable_datetime > {{pb_1: String}} AND sortable_datetime < {{pb_2: String}}
            GROUP BY thread_id
            HAVING thread_id IS NOT NULL AND thread_id != ''
            ORDER BY turn_count DESC
            LIMIT {{pb_3: Int64}}
            OFFSET {{pb_4: Int64}}
            """

    assert_clickhouse_sql(
        expected_query,
        {
            "pb_0": "test_project",
            "pb_1": "2024-01-01 00:00:00.000000",
            "pb_2": "2024-12-31 00:00:00.000000",
            "pb_3": 15,
            "pb_4": 30,
        },
        read_table=read_table,
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
        SortBy(field="last_updated", direction="asc"),
        SortBy(field="thread_id", direction="desc"),
    ]

    assert_sqlite_sql(
        """
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
            AND started_at > ?
            AND thread_id IS NOT NULL
            AND thread_id != ''
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


@pytest.mark.parametrize(
    ("read_table", "table_name"),
    [
        (ReadTable.CALLS_MERGED, "calls_merged"),
        (ReadTable.CALLS_COMPLETE, "calls_complete"),
    ],
)
def test_clickhouse_only_after_date(read_table: ReadTable, table_name: str):
    """Test ClickHouse query with only after date filter."""
    after_date = datetime.datetime(2024, 1, 1, 0, 0, 0)

    if read_table == ReadTable.CALLS_MERGED:
        expected_query = f"""
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
                FROM {table_name}
                WHERE project_id = {{pb_0: String}}
                    AND sortable_datetime > {{pb_1: String}}
                GROUP BY (project_id, id)
                HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
            ) AS properly_merged_calls
            GROUP BY aggregated_thread_id
            ORDER BY last_updated DESC
            """
    else:
        expected_query = f"""
            SELECT
                thread_id AS thread_id,
                COUNT(*) AS turn_count,
                min(started_at) AS start_time,
                max(ended_at) AS last_updated,
                argMin(id, started_at) AS first_turn_id,
                argMax(id, ended_at) AS last_turn_id,
                quantile(0.5)(dateDiff('millisecond', started_at, ended_at)) AS p50_turn_duration_ms,
                quantile(0.99)(dateDiff('millisecond', started_at, ended_at)) AS p99_turn_duration_ms
            FROM
                {table_name}
            WHERE project_id = {{pb_0: String}}
                AND id = turn_id
                AND sortable_datetime > {{pb_1: String}}
            GROUP BY thread_id
            HAVING thread_id IS NOT NULL AND thread_id != ''
            ORDER BY last_updated DESC
            """

    assert_clickhouse_sql(
        expected_query,
        {"pb_0": "test_project", "pb_1": "2024-01-01 00:00:00.000000"},
        read_table=read_table,
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
            AND started_at < ?
            AND thread_id IS NOT NULL
            AND thread_id != ''
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
        invalid_sort = [SortBy(field="nonexistent_field", direction="asc")]
        make_threads_query_sqlite(project_id="test_project", sort_by=invalid_sort)


# Turn-ID Filtering Behavior Tests


def test_turn_filtering_explanation():
    """Test that demonstrates the key behavior: only turn calls are included.

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
    clickhouse_query = make_threads_query(
        project_id="test", pb=pb, read_table=ReadTable.CALLS_MERGED
    )
    sqlite_query, _ = make_threads_query_sqlite(project_id="test")

    # Check that turn filtering is present
    assert "id = any(turn_id)" in clickhouse_query
    assert "id = turn_id" in sqlite_query

    # Check that thread filtering is also present (non-null, non-empty)
    # For ClickHouse, filtering is now in the HAVING clause using aggregated_thread_id
    assert (
        "aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''"
        in clickhouse_query
    )
    assert "thread_id IS NOT NULL" in sqlite_query
    assert "thread_id != ''" in sqlite_query


# Thread ID Filtering Tests


@pytest.mark.parametrize(
    ("read_table", "table_name"),
    [
        (ReadTable.CALLS_MERGED, "calls_merged"),
        (ReadTable.CALLS_COMPLETE, "calls_complete"),
    ],
)
def test_clickhouse_with_thread_id_filter(read_table: ReadTable, table_name: str):
    """Test ClickHouse query with thread_id filter."""
    if read_table == ReadTable.CALLS_MERGED:
        expected_query = f"""
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
                FROM {table_name}
                WHERE project_id = {{pb_0: String}}
                    AND (thread_id IS NULL OR thread_id IN ({{pb_1: String}}))
                GROUP BY (project_id, id)
                HAVING id = any(turn_id) AND aggregated_thread_id IN ({{pb_1: String}})
            ) AS properly_merged_calls
            GROUP BY aggregated_thread_id
             ORDER BY last_updated DESC
            """
    else:
        expected_query = f"""
            SELECT
                thread_id AS thread_id,
                COUNT(*) AS turn_count,
                min(started_at) AS start_time,
                max(ended_at) AS last_updated,
                argMin(id, started_at) AS first_turn_id,
                argMax(id, ended_at) AS last_turn_id,
                quantile(0.5)(dateDiff('millisecond', started_at, ended_at)) AS p50_turn_duration_ms,
                quantile(0.99)(dateDiff('millisecond', started_at, ended_at)) AS p99_turn_duration_ms
            FROM
                {table_name}
            WHERE project_id = {{pb_0: String}}
                AND id = turn_id
                AND (thread_id IS NULL OR thread_id IN ({{pb_1: String}}))
            GROUP BY thread_id
            HAVING thread_id IN ({{pb_1: String}})
             ORDER BY last_updated DESC
            """

    assert_clickhouse_sql(
        expected_query,
        {"pb_0": "test_project", "pb_1": "my_specific_thread"},
        read_table=read_table,
        project_id="test_project",
        thread_ids=["my_specific_thread"],
    )


def test_sqlite_with_thread_id_filter():
    """Test SQLite query with thread_id filter."""
    assert_sqlite_sql(
        """
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
            AND thread_id IN (?)
        GROUP BY thread_id
        ORDER BY last_updated DESC
        """,
        ["test_project", "another_thread_id"],
        project_id="test_project",
        thread_ids=["another_thread_id"],
    )


@pytest.mark.parametrize(
    ("read_table", "table_name"),
    [
        (ReadTable.CALLS_MERGED, "calls_merged"),
        (ReadTable.CALLS_COMPLETE, "calls_complete"),
    ],
)
def test_clickhouse_with_thread_id_and_date_filters(
    read_table: ReadTable, table_name: str
):
    """Test ClickHouse query with both thread_id and date filters."""
    after_date = datetime.datetime(2024, 1, 1, 12, 0, 0)
    before_date = datetime.datetime(2024, 12, 31, 23, 59, 59)

    if read_table == ReadTable.CALLS_MERGED:
        expected_query = f"""
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
                FROM {table_name}
                WHERE project_id = {{pb_0: String}}
                    AND sortable_datetime > {{pb_1: String}} AND sortable_datetime < {{pb_2: String}}
                    AND (thread_id IS NULL OR thread_id IN ({{pb_3: String}}))
                GROUP BY (project_id, id)
                HAVING id = any(turn_id) AND aggregated_thread_id IN ({{pb_3: String}})
            ) AS properly_merged_calls
            GROUP BY aggregated_thread_id
             ORDER BY last_updated DESC
            """
    else:
        expected_query = f"""
            SELECT
                thread_id AS thread_id,
                COUNT(*) AS turn_count,
                min(started_at) AS start_time,
                max(ended_at) AS last_updated,
                argMin(id, started_at) AS first_turn_id,
                argMax(id, ended_at) AS last_turn_id,
                quantile(0.5)(dateDiff('millisecond', started_at, ended_at)) AS p50_turn_duration_ms,
                quantile(0.99)(dateDiff('millisecond', started_at, ended_at)) AS p99_turn_duration_ms
            FROM
                {table_name}
            WHERE project_id = {{pb_0: String}}
                AND id = turn_id
                AND sortable_datetime > {{pb_1: String}} AND sortable_datetime < {{pb_2: String}}
                AND (thread_id IS NULL OR thread_id IN ({{pb_3: String}}))
            GROUP BY thread_id
            HAVING thread_id IN ({{pb_3: String}})
             ORDER BY last_updated DESC
            """

    assert_clickhouse_sql(
        expected_query,
        {
            "pb_0": "test_project",
            "pb_1": "2024-01-01 12:00:00.000000",
            "pb_2": "2024-12-31 23:59:59.000000",
            "pb_3": "thread_with_dates",
        },
        read_table=read_table,
        project_id="test_project",
        sortable_datetime_after=after_date,
        sortable_datetime_before=before_date,
        thread_ids=["thread_with_dates"],
    )


def test_sqlite_with_thread_id_and_date_filters():
    """Test SQLite query with both thread_id and date filters."""
    after_date = datetime.datetime(2024, 6, 15, 10, 30, 0)
    before_date = datetime.datetime(2024, 6, 15, 18, 0, 0)

    assert_sqlite_sql(
        """
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
            AND started_at > ? AND started_at < ?
            AND thread_id IN (?)
        GROUP BY thread_id
        ORDER BY last_updated DESC
        """,
        [
            "test_project",
            "2024-06-15T10:30:00",
            "2024-06-15T18:00:00",
            "specific_thread",
        ],
        project_id="test_project",
        sortable_datetime_after=after_date,
        sortable_datetime_before=before_date,
        thread_ids=["specific_thread"],
    )


@pytest.mark.parametrize(
    ("read_table", "table_name"),
    [
        (ReadTable.CALLS_MERGED, "calls_merged"),
        (ReadTable.CALLS_COMPLETE, "calls_complete"),
    ],
)
def test_clickhouse_with_thread_id_and_all_options(
    read_table: ReadTable, table_name: str
):
    """Test ClickHouse query with thread_id, dates, sorting, and pagination."""
    after_date = datetime.datetime(2024, 1, 1)
    before_date = datetime.datetime(2024, 12, 31)
    sort_by = [SortBy(field="turn_count", direction="desc")]

    if read_table == ReadTable.CALLS_MERGED:
        expected_query = f"""
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
                FROM {table_name}
                WHERE project_id = {{pb_0: String}}
                    AND sortable_datetime > {{pb_1: String}} AND sortable_datetime < {{pb_2: String}}
                    AND (thread_id IS NULL OR thread_id IN ({{pb_3: String}}))
                GROUP BY (project_id, id)
                HAVING id = any(turn_id) AND aggregated_thread_id IN ({{pb_3: String}})
            ) AS properly_merged_calls
            GROUP BY aggregated_thread_id
             ORDER BY turn_count DESC
             LIMIT {{pb_4: Int64}}
             OFFSET {{pb_5: Int64}}
            """
    else:
        expected_query = f"""
            SELECT
                thread_id AS thread_id,
                COUNT(*) AS turn_count,
                min(started_at) AS start_time,
                max(ended_at) AS last_updated,
                argMin(id, started_at) AS first_turn_id,
                argMax(id, ended_at) AS last_turn_id,
                quantile(0.5)(dateDiff('millisecond', started_at, ended_at)) AS p50_turn_duration_ms,
                quantile(0.99)(dateDiff('millisecond', started_at, ended_at)) AS p99_turn_duration_ms
            FROM
                {table_name}
            WHERE project_id = {{pb_0: String}}
                AND id = turn_id
                AND sortable_datetime > {{pb_1: String}} AND sortable_datetime < {{pb_2: String}}
                AND (thread_id IS NULL OR thread_id IN ({{pb_3: String}}))
            GROUP BY thread_id
            HAVING thread_id IN ({{pb_3: String}})
             ORDER BY turn_count DESC
             LIMIT {{pb_4: Int64}}
             OFFSET {{pb_5: Int64}}
            """

    assert_clickhouse_sql(
        expected_query,
        {
            "pb_0": "test_project",
            "pb_1": "2024-01-01 00:00:00.000000",
            "pb_2": "2024-12-31 00:00:00.000000",
            "pb_3": "full_featured_thread",
            "pb_4": 15,
            "pb_5": 30,
        },
        read_table=read_table,
        project_id="test_project",
        sortable_datetime_after=after_date,
        sortable_datetime_before=before_date,
        sort_by=sort_by,
        limit=15,
        offset=30,
        thread_ids=["full_featured_thread"],
    )


def test_sqlite_with_thread_id_and_all_options():
    """Test SQLite query with thread_id, dates, sorting, and pagination."""
    after_date = datetime.datetime(2024, 3, 15)
    sort_by = [
        SortBy(field="last_updated", direction="asc"),
        SortBy(field="thread_id", direction="desc"),
    ]

    assert_sqlite_sql(
        """
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
            AND started_at > ?
            AND thread_id IN (?)
        GROUP BY thread_id
        ORDER BY last_updated ASC, thread_id DESC
        LIMIT ?
        """,
        ["test_project", "2024-03-15T00:00:00", "comprehensive_thread", 5],
        project_id="test_project",
        sortable_datetime_after=after_date,
        sort_by=sort_by,
        limit=5,
        thread_ids=["comprehensive_thread"],
    )


@pytest.mark.parametrize(
    "read_table", [ReadTable.CALLS_MERGED, ReadTable.CALLS_COMPLETE]
)
def test_thread_id_filter_no_match(read_table: ReadTable):
    """Test that thread_id filter doesn't break query even if no threads match."""
    # This test verifies that the SQL generation doesn't break with thread_id filter
    pb = ParamBuilder("pb")
    query = make_threads_query(
        project_id="test_project",
        pb=pb,
        thread_ids=["nonexistent_thread"],
        read_table=read_table,
    )

    # Should contain the thread filter
    assert "thread_id IN ({pb_1: String})" in query

    # Should have the expected parameter
    params = pb.get_params()
    assert "pb_1" in params
    assert params["pb_1"] == "nonexistent_thread"


@pytest.mark.parametrize(
    "read_table", [ReadTable.CALLS_MERGED, ReadTable.CALLS_COMPLETE]
)
def test_thread_id_filter_consistency(read_table: ReadTable):
    """Test that both ClickHouse and SQLite handle thread_id filtering consistently."""
    pb = ParamBuilder("pb")

    # Generate both queries with same parameters
    clickhouse_query = make_threads_query(
        project_id="test_project",
        pb=pb,
        thread_ids=["consistency_test"],
        read_table=read_table,
    )
    sqlite_query, sqlite_params = make_threads_query_sqlite(
        project_id="test_project", thread_ids=["consistency_test"]
    )

    # Both should filter by thread_ids
    assert "thread_id IN ({pb_1: String})" in clickhouse_query  # ClickHouse style
    assert "AND thread_id IN (?)" in sqlite_query  # SQLite style

    # Parameters should be consistent
    ch_params = pb.get_params()
    assert ch_params["pb_1"] == "consistency_test"
    assert "consistency_test" in sqlite_params


@pytest.mark.parametrize(
    "read_table", [ReadTable.CALLS_MERGED, ReadTable.CALLS_COMPLETE]
)
def test_query_structure_documentation(read_table: ReadTable):
    """Test that documents the structure and purpose of the threads query.

    This test serves AS living documentation of what the threads query does
    and why it's structured the way it is.
    """
    pb = ParamBuilder("pb")
    query = make_threads_query(project_id="test_project", pb=pb, read_table=read_table)

    # All queries should have a SELECT
    assert "SELECT" in query

    if read_table == ReadTable.CALLS_MERGED:
        # CALLS_MERGED uses two-level aggregation for ClickHouse
        assert "FROM (" in query  # Inner subquery
        assert "GROUP BY aggregated_thread_id" in query  # Outer aggregation by thread
        assert "GROUP BY (project_id, id)" in query  # Inner aggregation by call
        # Should include key aggregations using subquery aliases
        assert "min(call_start_time) AS start_time" in query
        assert "max(call_end_time) AS last_updated" in query
        # Turn filtering in HAVING clause (after aggregation)
        assert "id = any(turn_id)" in query
    else:
        # CALLS_COMPLETE uses single-level aggregation (no subquery)
        assert "FROM (" not in query  # No subquery
        assert "GROUP BY thread_id" in query  # Direct aggregation by thread
        # Should include key aggregations using actual column names
        assert "min(started_at) AS start_time" in query
        assert "max(ended_at) AS last_updated" in query
        # Turn filtering in WHERE clause (before aggregation)
        assert "id = turn_id" in query

    # Common assertions for both table types
    assert "COUNT(*) AS turn_count" in query
    assert "ORDER BY last_updated DESC" in query  # Default ordering
