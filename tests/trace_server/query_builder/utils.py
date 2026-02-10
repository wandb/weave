"""Utility functions for query builder tests."""

import datetime
from typing import Any

import sqlparse

from weave.trace_server.calls_query_builder.call_metrics_query_builder import (
    build_call_metrics_query,
)
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    build_calls_stats_query,
)
from weave.trace_server.calls_query_builder.usage_query_builder import (
    build_usage_query,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable
from weave.trace_server.threads_query_builder import (
    make_threads_query,
    make_threads_query_sqlite,
)
from weave.trace_server.trace_server_interface import (
    CallMetricSpec,
    CallsQueryStatsReq,
    CallStatsReq,
    UsageMetricSpec,
)


def assert_sql(cq: CallsQuery, exp_query: str, exp_params: dict) -> None:
    """Assert that the CallsQuery generates the expected SQL and parameters.

    Args:
        cq: The CallsQuery object to test
        exp_query: The expected SQL query string
        exp_params: The expected parameter dictionary
    """
    pb = ParamBuilder("pb")
    query = cq.as_sql(pb)
    params = pb.get_params()

    exp_formatted = sqlparse.format(exp_query, reindent=True)
    found_formatted = sqlparse.format(query, reindent=True)

    assert exp_formatted == found_formatted, (
        f"\nExpected:\n{exp_formatted}\n\nGot:\n{found_formatted}"
    )
    assert exp_params == params, (
        f"\nExpected params: {exp_params}\n\nGot params: {params}"
    )


def assert_clickhouse_sql(expected_query: str, expected_params: dict, **kwargs) -> None:
    """Helper to test ClickHouse query generation for threads.

    Args:
        expected_query: The expected SQL query string
        expected_params: The expected parameter dictionary
        **kwargs: Arguments to pass to make_threads_query
    """
    pb = ParamBuilder("pb")
    query = make_threads_query(pb=pb, **kwargs)
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


def assert_usage_sql(
    req: CallStatsReq,
    metrics: list[UsageMetricSpec],
    exp_query: str,
    exp_params: dict[str, Any],
    exp_columns: list[str],
    exp_granularity_seconds: int,
    exp_start: datetime.datetime | None = None,
    exp_end: datetime.datetime | None = None,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
) -> None:
    """Assert that the CallStatsReq generates the expected usage SQL and parameters.

    Args:
        req: The CallStatsReq object to test
        metrics: The usage metrics to query
        exp_query: The expected SQL query string
        exp_params: The expected parameter dictionary
        exp_columns: The expected output columns list
        exp_granularity_seconds: The expected granularity in seconds
        exp_start: The expected start datetime (if None, not checked)
        exp_end: The expected end datetime (if None, not checked)
        read_table: Which table to query (calls_merged or calls_complete)
    """
    pb = ParamBuilder("pb")
    sql, cols, params, granularity_seconds, start, end = build_usage_query(
        req, metrics, pb, read_table
    )

    exp_formatted = sqlparse.format(exp_query, reindent=True)
    found_formatted = sqlparse.format(sql, reindent=True)

    assert exp_formatted == found_formatted, (
        f"\nExpected:\n{exp_formatted}\n\nGot:\n{found_formatted}"
    )
    assert exp_params == params, (
        f"\nExpected params: {exp_params}\n\nGot params: {params}"
    )
    assert exp_columns == cols, f"\nExpected columns: {exp_columns}\n\nGot: {cols}"
    assert exp_granularity_seconds == granularity_seconds, (
        f"\nExpected granularity: {exp_granularity_seconds}\n\nGot: {granularity_seconds}"
    )
    if exp_start is not None:
        assert exp_start == start, f"\nExpected start: {exp_start}\n\nGot: {start}"
    if exp_end is not None:
        assert exp_end == end, f"\nExpected end: {exp_end}\n\nGot: {end}"


def assert_stats_sql(
    req: CallsQueryStatsReq,
    exp_query: str,
    exp_params: dict,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
) -> None:
    """Assert that build_calls_stats_query generates the expected SQL and parameters.

    Args:
        req: The stats query request
        exp_query: The expected SQL query string
        exp_params: The expected parameter dictionary
        read_table: Which table to query (calls_merged or calls_complete)
    """
    pb = ParamBuilder("pb")
    query, _columns = build_calls_stats_query(req, pb, read_table)
    params = pb.get_params()

    exp_formatted = sqlparse.format(exp_query, reindent=True).strip()
    found_formatted = sqlparse.format(query, reindent=True).strip()

    assert exp_formatted == found_formatted, (
        f"\nExpected:\n{exp_formatted}\n\nGot:\n{found_formatted}"
    )
    assert exp_params == params, (
        f"\nExpected params: {exp_params}\n\nGot params: {params}"
    )


def assert_call_metrics_sql(
    req: CallStatsReq,
    metrics: list[CallMetricSpec],
    exp_query: str,
    exp_params: dict[str, Any],
    exp_columns: list[str],
    exp_granularity_seconds: int,
    exp_start: datetime.datetime | None = None,
    exp_end: datetime.datetime | None = None,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
) -> None:
    """Assert that the CallStatsReq generates the expected call metrics SQL and parameters.

    Args:
        req: The CallStatsReq object to test
        metrics: The call metrics to query
        exp_query: The expected SQL query string
        exp_params: The expected parameter dictionary
        exp_columns: The expected output columns list
        exp_granularity_seconds: The expected granularity in seconds
        exp_start: The expected start datetime (if None, not checked)
        exp_end: The expected end datetime (if None, not checked)
        read_table: Which table to query (calls_merged or calls_complete)
    """
    pb = ParamBuilder("pb")
    sql, cols, params, granularity_seconds, start, end = build_call_metrics_query(
        req, metrics, pb, read_table
    )

    exp_formatted = sqlparse.format(exp_query, reindent=True)
    found_formatted = sqlparse.format(sql, reindent=True)

    assert exp_formatted == found_formatted, (
        f"\nExpected:\n{exp_formatted}\n\nGot:\n{found_formatted}"
    )
    assert exp_params == params, (
        f"\nExpected params: {exp_params}\n\nGot params: {params}"
    )
    assert exp_columns == cols, f"\nExpected columns: {exp_columns}\n\nGot: {cols}"
    assert exp_granularity_seconds == granularity_seconds, (
        f"\nExpected granularity: {exp_granularity_seconds}\n\nGot: {granularity_seconds}"
    )
    if exp_start is not None:
        assert exp_start == start, f"\nExpected start: {exp_start}\n\nGot: {start}"
    if exp_end is not None:
        assert exp_end == end, f"\nExpected end: {exp_end}\n\nGot: {end}"
