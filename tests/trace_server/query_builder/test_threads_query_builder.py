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


def _basic_query(table: str) -> str:
    return f"""
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
            FROM {table}
            WHERE project_id = {{pb_0: String}}

            GROUP BY (project_id, id)
            HAVING id = any(turn_id) AND aggregated_thread_id IS NOT NULL AND aggregated_thread_id != ''
        ) AS properly_merged_calls
        GROUP BY aggregated_thread_id
        ORDER BY last_updated DESC
    """


# Each row asserts the COMPLETE ClickHouse query so every WHERE/ORDER BY/LIMIT/
# OFFSET/thread-id branch keeps full-SQL coverage.
_CLICKHOUSE_CASES = [
    pytest.param(
        {"read_table": ReadTable.CALLS_MERGED},
        _basic_query("calls_merged"),
        {"pb_0": "test_project"},
        id="basic_calls_merged",
    ),
    pytest.param(
        {"read_table": ReadTable.CALLS_COMPLETE},
        _basic_query("calls_complete"),
        {"pb_0": "test_project"},
        id="basic_calls_complete",
    ),
    pytest.param(
        {
            "sort_by": [
                SortBy(field="turn_count", direction="asc"),
                SortBy(field="start_time", direction="desc"),
            ]
        },
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
        id="custom_sorting",
    ),
    pytest.param(
        {"limit": 50},
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
        id="limit",
    ),
    pytest.param(
        {"limit": 25, "offset": 100},
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
        id="limit_and_offset",
    ),
    pytest.param(
        {
            "sortable_datetime_after": datetime.datetime(2024, 1, 1, 12, 0, 0),
            "sortable_datetime_before": datetime.datetime(2024, 12, 31, 23, 59, 59),
        },
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
        id="date_filters",
    ),
    pytest.param(
        {"sortable_datetime_after": datetime.datetime(2024, 1, 1, 0, 0, 0)},
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
        id="only_after_date",
    ),
    pytest.param(
        {
            "sortable_datetime_after": datetime.datetime(2024, 1, 1),
            "sortable_datetime_before": datetime.datetime(2024, 12, 31),
            "sort_by": [SortBy(field="turn_count", direction="desc")],
            "limit": 15,
            "offset": 30,
        },
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
        id="full_featured",
    ),
    pytest.param(
        {"thread_ids": ["my_specific_thread"]},
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
        id="thread_id_filter",
    ),
    pytest.param(
        {
            "sortable_datetime_after": datetime.datetime(2024, 1, 1, 12, 0, 0),
            "sortable_datetime_before": datetime.datetime(2024, 12, 31, 23, 59, 59),
            "thread_ids": ["thread_with_dates"],
        },
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
        id="thread_id_and_date_filters",
    ),
    pytest.param(
        {
            "sortable_datetime_after": datetime.datetime(2024, 1, 1),
            "sortable_datetime_before": datetime.datetime(2024, 12, 31),
            "sort_by": [SortBy(field="turn_count", direction="desc")],
            "limit": 15,
            "offset": 30,
            "thread_ids": ["full_featured_thread"],
        },
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
        id="thread_id_and_all_options",
    ),
]


@pytest.mark.parametrize(
    ("kwargs", "expected_query", "expected_params"), _CLICKHOUSE_CASES
)
def test_clickhouse_query_shapes(
    kwargs: dict, expected_query: str, expected_params: dict
):
    """Each input combination produces the full expected ClickHouse SQL + params."""
    assert_clickhouse_sql(
        expected_query, expected_params, project_id="test_project", **kwargs
    )


def test_validate_and_map_sort_field():
    """Test the sort field validation function."""
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

    # Call IDs are identifiers, not sortable fields.
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
