"""Utility functions for query builder tests."""

import sqlparse

from weave.trace_server.calls_query_builder.calls_query_builder import CallsQuery
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.threads_query_builder import (
    make_threads_query,
    make_threads_query_sqlite,
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
