"""Unit tests for project_query_builder.make_project_stats_query.

Tests verify that the query builder correctly generates SQL for computing
storage sizes from various stats tables.
"""

import pytest
import sqlparse

from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable
from weave.trace_server.query_builder.project_query_builder import (
    make_project_stats_query,
)

_TRACE_SUBQUERY_MERGED = """(SELECT sum(
    COALESCE(attributes_size_bytes, 0) +
    COALESCE(inputs_size_bytes, 0) +
    COALESCE(output_size_bytes, 0) +
    COALESCE(summary_size_bytes, 0) +
    COALESCE(otel_dump_size_bytes, 0)
    )
    FROM calls_merged_stats
    WHERE project_id = {pb_0: String}
) AS trace_storage_size_bytes"""

_TRACE_SUBQUERY_COMPLETE = """(SELECT sum(
    COALESCE(attributes_size_bytes, 0) +
    COALESCE(inputs_size_bytes, 0) +
    COALESCE(output_size_bytes, 0) +
    COALESCE(summary_size_bytes, 0) +
    COALESCE(otel_size_bytes, 0)
    )
    FROM calls_complete_stats
    WHERE project_id = {pb_0: String}
) AS trace_storage_size_bytes"""

_OBJECTS_SUBQUERY = """(SELECT sum(size_bytes)
    FROM object_versions_stats
    WHERE project_id = {pb_0: String}
) AS objects_storage_size_bytes"""

_TABLES_SUBQUERY = """(SELECT sum(size_bytes)
    FROM table_rows_stats
    WHERE project_id = {pb_0: String}
) AS tables_storage_size_bytes"""

_FILES_SUBQUERY = """(SELECT sum(size_bytes)
    FROM files_stats
    WHERE project_id = {pb_0: String}
) AS files_storage_size_bytes"""


@pytest.mark.parametrize(
    ("include_kwargs", "read_table", "subquery", "columns"),
    [
        (
            {"include_trace_storage_size": True},
            ReadTable.CALLS_MERGED,
            _TRACE_SUBQUERY_MERGED,
            ["trace_storage_size_bytes"],
        ),
        (
            {"include_trace_storage_size": True},
            ReadTable.CALLS_COMPLETE,
            _TRACE_SUBQUERY_COMPLETE,
            ["trace_storage_size_bytes"],
        ),
        (
            {"include_objects_storage_size": True},
            ReadTable.CALLS_MERGED,
            _OBJECTS_SUBQUERY,
            ["objects_storage_size_bytes"],
        ),
        (
            {"include_tables_storage_size": True},
            ReadTable.CALLS_MERGED,
            _TABLES_SUBQUERY,
            ["tables_storage_size_bytes"],
        ),
        (
            {"include_files_storage_size": True},
            ReadTable.CALLS_MERGED,
            _FILES_SUBQUERY,
            ["files_storage_size_bytes"],
        ),
        (
            {"include_objects_storage_size": True},
            ReadTable.CALLS_COMPLETE,
            _OBJECTS_SUBQUERY,
            ["objects_storage_size_bytes"],
        ),
    ],
)
def test_single_storage_kind(include_kwargs, read_table, subquery, columns) -> None:
    """Each storage kind selects its own subquery; non-trace kinds ignore read_table."""
    pb = ParamBuilder("pb")
    query, found_columns = make_project_stats_query(
        project_id="test_project",
        pb=pb,
        include_trace_storage_size=include_kwargs.get(
            "include_trace_storage_size", False
        ),
        include_objects_storage_size=include_kwargs.get(
            "include_objects_storage_size", False
        ),
        include_tables_storage_size=include_kwargs.get(
            "include_tables_storage_size", False
        ),
        include_files_storage_size=include_kwargs.get(
            "include_files_storage_size", False
        ),
        read_table=read_table,
    )

    assert_sql(query, f"\nSELECT {subquery}", pb.get_params(), {"pb_0": "test_project"})
    assert found_columns == columns


@pytest.mark.parametrize(
    ("read_table", "trace_subquery"),
    [
        (ReadTable.CALLS_MERGED, _TRACE_SUBQUERY_MERGED),
        (ReadTable.CALLS_COMPLETE, _TRACE_SUBQUERY_COMPLETE),
    ],
)
def test_all_storage_sizes(read_table, trace_subquery) -> None:
    """All four kinds appear in fixed column order; trace subquery varies by read_table."""
    pb = ParamBuilder("pb")
    query, columns = make_project_stats_query(
        project_id="test_project",
        pb=pb,
        include_trace_storage_size=True,
        include_objects_storage_size=True,
        include_tables_storage_size=True,
        include_files_storage_size=True,
        read_table=read_table,
    )

    expected_sql = (
        f"\nSELECT {trace_subquery},\n"
        f"{_OBJECTS_SUBQUERY},\n"
        f"{_TABLES_SUBQUERY},\n"
        f"{_FILES_SUBQUERY}"
    )
    assert_sql(query, expected_sql, pb.get_params(), {"pb_0": "test_project"})
    assert columns == [
        "trace_storage_size_bytes",
        "objects_storage_size_bytes",
        "tables_storage_size_bytes",
        "files_storage_size_bytes",
    ]


def test_raises_when_no_storage_sizes_requested() -> None:
    """Verify ValueError raised when all include_* params are False."""
    pb = ParamBuilder("pb")
    with pytest.raises(ValueError, match="At least one of"):
        make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=False,
            include_objects_storage_size=False,
            include_tables_storage_size=False,
            include_files_storage_size=False,
        )


def test_parameterization_prevents_sql_injection() -> None:
    """Verify project_id is parameterized for SQL injection safety."""
    pb = ParamBuilder("pb")
    query, columns = make_project_stats_query(
        project_id="malicious'--project",
        pb=pb,
        include_trace_storage_size=True,
        include_objects_storage_size=False,
        include_tables_storage_size=False,
        include_files_storage_size=False,
    )

    assert "malicious" not in query
    assert_sql(
        query,
        f"\nSELECT {_TRACE_SUBQUERY_MERGED}",
        pb.get_params(),
        {"pb_0": "malicious'--project"},
    )


def assert_sql(query: str, expected: str, params: dict, expected_params: dict) -> None:
    """Assert SQL matches expected after normalizing whitespace."""
    expected_formatted = sqlparse.format(expected, reindent=True)
    found_formatted = sqlparse.format(query, reindent=True)

    assert expected_formatted == found_formatted, (
        f"\nExpected:\n{expected_formatted}\n\nGot:\n{found_formatted}"
    )
    assert expected_params == params, (
        f"\nExpected params: {expected_params}\n\nGot params: {params}"
    )
