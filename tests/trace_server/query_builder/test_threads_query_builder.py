import datetime

import pytest

from tests.trace_server.query_builder.utils import assert_clickhouse_sql
from weave.trace_server.common_interface import SortBy
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable
from weave.trace_server.threads_query_builder import (
    _validate_and_map_sort_field,
    make_threads_query,
)

# Basic Functionality Tests


@pytest.mark.parametrize(
    ("read_table", "expected_table"),
    [
        (ReadTable.CALLS_MERGED, "calls_merged"),
        (ReadTable.CALLS_COMPLETE, "calls_complete"),
    ],
)
def test_clickhouse_basic_query(read_table: ReadTable, expected_table: str):
    """Test basic ClickHouse threads query uses correct table and full query shape."""
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
            FROM {expected_table}
            WHERE project_id = {{pb_0: String}}

            GROUP BY (project_id, id)
            HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
        ) AS properly_merged_calls
        GROUP BY aggregated_thread_id
        ORDER BY last_updated DESC
    """
    assert_clickhouse_sql(
        expected_query,
        {"pb_0": "test_project"},
        project_id="test_project",
        read_table=read_table,
    )


# Sorting Tests


def test_clickhouse_custom_sorting():
    """Test ClickHouse query with custom sorting."""
    sort_by = [
        SortBy(field="turn_count", direction="asc"),
        SortBy(field="start_time", direction="desc"),
    ]

    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}

            GROUP BY (project_id, id)
            HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
        ) AS properly_merged_calls
        GROUP BY aggregated_thread_id
        ORDER BY turn_count ASC, start_time DESC
        """,
        {"pb_0": "test_project"},
        project_id="test_project",
        sort_by=sort_by,
    )


# Pagination Tests


def test_clickhouse_with_limit():
    """Test ClickHouse query with limit."""
    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}

            GROUP BY (project_id, id)
            HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
        ) AS properly_merged_calls
        GROUP BY aggregated_thread_id
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
            WHERE project_id = {pb_0: String}

            GROUP BY (project_id, id)
            HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
        ) AS properly_merged_calls
        GROUP BY aggregated_thread_id
        ORDER BY last_updated DESC
        LIMIT {pb_1: Int64}
        OFFSET {pb_2: Int64}
        """,
        {"pb_0": "test_project", "pb_1": 25, "pb_2": 100},
        project_id="test_project",
        limit=25,
        offset=100,
    )


# Date Filtering Tests


def test_clickhouse_with_date_filters():
    """Test ClickHouse query with sortable_datetime filters."""
    after_date = datetime.datetime(2024, 1, 1, 12, 0, 0)
    before_date = datetime.datetime(2024, 12, 31, 23, 59, 59)

    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}
                AND sortable_datetime > {pb_1: String} AND sortable_datetime < {pb_2: String}
            GROUP BY (project_id, id)
            HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
        ) AS properly_merged_calls
        GROUP BY aggregated_thread_id
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


# Complex Scenarios


def test_clickhouse_full_featured_query():
    """Test ClickHouse query with all features: custom sorting, pagination, and date filtering."""
    after_date = datetime.datetime(2024, 1, 1)
    before_date = datetime.datetime(2024, 12, 31)
    sort_by = [SortBy(field="turn_count", direction="desc")]

    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}
                AND sortable_datetime > {pb_1: String} AND sortable_datetime < {pb_2: String}
            GROUP BY (project_id, id)
            HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
        ) AS properly_merged_calls
        GROUP BY aggregated_thread_id
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


# Edge Cases


def test_clickhouse_only_after_date():
    """Test ClickHouse query with only after date filter."""
    after_date = datetime.datetime(2024, 1, 1, 0, 0, 0)

    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}
                AND sortable_datetime > {pb_1: String}
            GROUP BY (project_id, id)
            HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
        ) AS properly_merged_calls
        GROUP BY aggregated_thread_id
        ORDER BY last_updated DESC
        """,
        {"pb_0": "test_project", "pb_1": "2024-01-01 00:00:00.000000"},
        project_id="test_project",
        sortable_datetime_after=after_date,
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
    with pytest.raises(
        ValueError, match="Unsupported sort field: first_turn_id"
    ) as exc_info:
        _validate_and_map_sort_field("first_turn_id")
    assert "Unsupported sort field: first_turn_id" in str(exc_info.value)

    with pytest.raises(
        ValueError, match="Unsupported sort field: last_turn_id"
    ) as exc_info:
        _validate_and_map_sort_field("last_turn_id")
    assert "Unsupported sort field: last_turn_id" in str(exc_info.value)

    with pytest.raises(
        ValueError, match="Unsupported sort field: invalid_field"
    ) as exc_info:
        _validate_and_map_sort_field("invalid_field")
    assert "Unsupported sort field: invalid_field" in str(exc_info.value)
    assert (
        "Supported fields: ['thread_id', 'turn_count', 'start_time', 'last_updated', 'p50_turn_duration_ms', 'p99_turn_duration_ms']"
        in str(exc_info.value)
    )


def test_sort_field_validation_in_query():
    """Test that invalid sort fields raise errors in query generation."""
    invalid_sort = [SortBy(field="nonexistent_field", direction="asc")]
    with pytest.raises(ValueError, match="Unsupported sort field"):
        make_threads_query(
            project_id="test_project", pb=ParamBuilder("pb"), sort_by=invalid_sort
        )


# Turn-ID Filtering Behavior Tests


def test_turn_filtering_explanation():
    """Test that demonstrates the key behavior: only turn calls are included.

    This test is more about documenting the expected behavior than testing
    implementation details. It shows that the filtering `id = turn_id` ensures
    only turn calls are included in thread statistics, not their descendants.
    """
    # The key filtering condition: "id = any(turn_id)" in the HAVING clause.

    # This means:
    # ✅ Turn calls (where call.id == call.turn_id) are included
    # ❌ Descendant calls (where call.id != call.turn_id) are excluded
    pb = ParamBuilder("pb")
    clickhouse_query = make_threads_query(project_id="test", pb=pb)

    # Check that turn filtering is present
    assert "id = any(turn_id)" in clickhouse_query

    # Check that thread filtering is also present (non-null, non-empty),
    # in the HAVING clause using aggregated_thread_id
    assert (
        "aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''"
        in clickhouse_query
    )


# Thread ID Filtering Tests


def test_clickhouse_with_thread_id_filter():
    """Test ClickHouse query with thread_id filter."""
    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}
                AND (thread_id IS NULL OR thread_id IN ({pb_1: String}))
            GROUP BY (project_id, id)
            HAVING id = any(turn_id) AND aggregated_thread_id IN ({pb_1: String})
        ) AS properly_merged_calls
        GROUP BY aggregated_thread_id
         ORDER BY last_updated DESC
        """,
        {"pb_0": "test_project", "pb_1": "my_specific_thread"},
        project_id="test_project",
        thread_ids=["my_specific_thread"],
    )


def test_clickhouse_with_thread_id_and_date_filters():
    """Test ClickHouse query with both thread_id and date filters."""
    after_date = datetime.datetime(2024, 1, 1, 12, 0, 0)
    before_date = datetime.datetime(2024, 12, 31, 23, 59, 59)

    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}
                AND sortable_datetime > {pb_1: String} AND sortable_datetime < {pb_2: String}
                AND (thread_id IS NULL OR thread_id IN ({pb_3: String}))
            GROUP BY (project_id, id)
            HAVING id = any(turn_id) AND aggregated_thread_id IN ({pb_3: String})
        ) AS properly_merged_calls
        GROUP BY aggregated_thread_id
         ORDER BY last_updated DESC
        """,
        {
            "pb_0": "test_project",
            "pb_1": "2024-01-01 12:00:00.000000",
            "pb_2": "2024-12-31 23:59:59.000000",
            "pb_3": "thread_with_dates",
        },
        project_id="test_project",
        sortable_datetime_after=after_date,
        sortable_datetime_before=before_date,
        thread_ids=["thread_with_dates"],
    )


def test_clickhouse_with_thread_id_and_all_options():
    """Test ClickHouse query with thread_id, dates, sorting, and pagination."""
    after_date = datetime.datetime(2024, 1, 1)
    before_date = datetime.datetime(2024, 12, 31)
    sort_by = [SortBy(field="turn_count", direction="desc")]

    assert_clickhouse_sql(
        """
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
            WHERE project_id = {pb_0: String}
                AND sortable_datetime > {pb_1: String} AND sortable_datetime < {pb_2: String}
                AND (thread_id IS NULL OR thread_id IN ({pb_3: String}))
            GROUP BY (project_id, id)
            HAVING id = any(turn_id) AND aggregated_thread_id IN ({pb_3: String})
        ) AS properly_merged_calls
        GROUP BY aggregated_thread_id
         ORDER BY turn_count DESC
         LIMIT {pb_4: Int64}
         OFFSET {pb_5: Int64}
        """,
        {
            "pb_0": "test_project",
            "pb_1": "2024-01-01 00:00:00.000000",
            "pb_2": "2024-12-31 00:00:00.000000",
            "pb_3": "full_featured_thread",
            "pb_4": 15,
            "pb_5": 30,
        },
        project_id="test_project",
        sortable_datetime_after=after_date,
        sortable_datetime_before=before_date,
        sort_by=sort_by,
        limit=15,
        offset=30,
        thread_ids=["full_featured_thread"],
    )


def test_thread_id_filter_no_match():
    """Test that thread_id filter doesn't break query even if no threads match."""
    # This test verifies that the SQL generation doesn't break with thread_id filter
    pb = ParamBuilder("pb")
    query = make_threads_query(
        project_id="test_project", pb=pb, thread_ids=["nonexistent_thread"]
    )

    # Should contain the thread filter
    assert "thread_id IN ({pb_1: String})" in query

    # Should have the expected parameter
    params = pb.get_params()
    assert "pb_1" in params
    assert params["pb_1"] == "nonexistent_thread"


def test_query_structure_documentation():
    """Test that documents the structure and purpose of the threads query.

    This test serves AS living documentation of what the threads query does
    and why it's structured the way it is.
    """
    pb = ParamBuilder("pb")
    query = make_threads_query(project_id="test_project", pb=pb)

    # Should be a two-level aggregation for ClickHouse
    assert "SELECT" in query  # Outer query
    assert "FROM (" in query  # Inner subquery
    assert "GROUP BY aggregated_thread_id" in query  # Outer aggregation by thread
    assert "GROUP BY (project_id, id)" in query  # Inner aggregation by call

    # Should include key aggregations
    assert "COUNT(*) AS turn_count" in query
    assert "min(call_start_time) AS start_time" in query
    assert "max(call_end_time) AS last_updated" in query

    # Should include turn filtering
    assert "id = any(turn_id)" in query

    # Should have default ordering
    assert "ORDER BY last_updated DESC" in query
