"""Unit tests for project_query_builder.make_project_stats_query.

Tests verify that the query builder correctly generates SQL for computing
storage sizes from various stats tables.
"""

import pytest
import sqlparse

from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_query_builder import make_project_stats_query
from weave.trace_server.project_version.types import ReadTable


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


class TestMakeProjectStatsQuery:
    """Tests for make_project_stats_query function."""

    def test_trace_storage_only_calls_merged(self) -> None:
        """Verify SQL when only trace storage is requested with calls_merged (default)."""
        pb = ParamBuilder("pb")
        query, columns = make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=True,
            include_objects_storage_size=False,
            include_tables_storage_size=False,
            include_files_storage_size=False,
        )

        expected_sql = """
            SELECT
                (SELECT sum(
                    COALESCE(attributes_size_bytes, 0) +
                    COALESCE(inputs_size_bytes, 0) +
                    COALESCE(output_size_bytes, 0) +
                    COALESCE(summary_size_bytes, 0)
                    )
                    FROM calls_merged_stats
                    WHERE project_id = {pb_0: String}
                ) AS trace_storage_size_bytes
        """
        assert_sql(query, expected_sql, pb.get_params(), {"pb_0": "test_project"})
        assert columns == ["trace_storage_size_bytes"]

    def test_trace_storage_only_calls_complete(self) -> None:
        """Verify SQL when only trace storage is requested with calls_complete."""
        pb = ParamBuilder("pb")
        query, columns = make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=True,
            include_objects_storage_size=False,
            include_tables_storage_size=False,
            include_files_storage_size=False,
            read_table=ReadTable.CALLS_COMPLETE,
        )

        expected_sql = """
            SELECT
                (SELECT sum(
                    COALESCE(attributes_size_bytes, 0) +
                    COALESCE(inputs_size_bytes, 0) +
                    COALESCE(output_size_bytes, 0) +
                    COALESCE(summary_size_bytes, 0)
                    )
                    FROM calls_complete_stats
                    WHERE project_id = {pb_0: String}
                ) AS trace_storage_size_bytes
        """
        assert_sql(query, expected_sql, pb.get_params(), {"pb_0": "test_project"})
        assert columns == ["trace_storage_size_bytes"]

    def test_objects_storage_only(self) -> None:
        """Verify SQL when only objects storage is requested."""
        pb = ParamBuilder("pb")
        query, columns = make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=False,
            include_objects_storage_size=True,
            include_tables_storage_size=False,
            include_files_storage_size=False,
        )

        expected_sql = """
            SELECT
                (SELECT sum(size_bytes)
                    FROM object_versions_stats
                    WHERE project_id = {pb_0: String}
                ) AS objects_storage_size_bytes
        """
        assert_sql(query, expected_sql, pb.get_params(), {"pb_0": "test_project"})
        assert columns == ["objects_storage_size_bytes"]

    def test_tables_storage_only(self) -> None:
        """Verify SQL when only tables storage is requested."""
        pb = ParamBuilder("pb")
        query, columns = make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=False,
            include_objects_storage_size=False,
            include_tables_storage_size=True,
            include_files_storage_size=False,
        )

        expected_sql = """
            SELECT
                (SELECT sum(size_bytes)
                    FROM table_rows_stats
                    WHERE project_id = {pb_0: String}
                ) AS tables_storage_size_bytes
        """
        assert_sql(query, expected_sql, pb.get_params(), {"pb_0": "test_project"})
        assert columns == ["tables_storage_size_bytes"]

    def test_files_storage_only(self) -> None:
        """Verify SQL when only files storage is requested."""
        pb = ParamBuilder("pb")
        query, columns = make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=False,
            include_objects_storage_size=False,
            include_tables_storage_size=False,
            include_files_storage_size=True,
        )

        expected_sql = """
            SELECT
                (SELECT sum(size_bytes)
                    FROM files_stats
                    WHERE project_id = {pb_0: String}
                ) AS files_storage_size_bytes
        """
        assert_sql(query, expected_sql, pb.get_params(), {"pb_0": "test_project"})
        assert columns == ["files_storage_size_bytes"]

    def test_all_storage_sizes_calls_merged(self) -> None:
        """Verify SQL when all storage sizes are requested with calls_merged."""
        pb = ParamBuilder("pb")
        query, columns = make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=True,
            include_objects_storage_size=True,
            include_tables_storage_size=True,
            include_files_storage_size=True,
            read_table=ReadTable.CALLS_MERGED,
        )

        expected_sql = """
            SELECT
                (SELECT sum(
                    COALESCE(attributes_size_bytes, 0) +
                    COALESCE(inputs_size_bytes, 0) +
                    COALESCE(output_size_bytes, 0) +
                    COALESCE(summary_size_bytes, 0)
                    )
                    FROM calls_merged_stats
                    WHERE project_id = {pb_0: String}
                ) AS trace_storage_size_bytes,
                (SELECT sum(size_bytes)
                    FROM object_versions_stats
                    WHERE project_id = {pb_0: String}
                ) AS objects_storage_size_bytes,
                (SELECT sum(size_bytes)
                    FROM table_rows_stats
                    WHERE project_id = {pb_0: String}
                ) AS tables_storage_size_bytes,
                (SELECT sum(size_bytes)
                    FROM files_stats
                    WHERE project_id = {pb_0: String}
                ) AS files_storage_size_bytes
        """
        assert_sql(query, expected_sql, pb.get_params(), {"pb_0": "test_project"})
        assert columns == [
            "trace_storage_size_bytes",
            "objects_storage_size_bytes",
            "tables_storage_size_bytes",
            "files_storage_size_bytes",
        ]

    def test_all_storage_sizes_calls_complete(self) -> None:
        """Verify SQL when all storage sizes are requested with calls_complete."""
        pb = ParamBuilder("pb")
        query, columns = make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=True,
            include_objects_storage_size=True,
            include_tables_storage_size=True,
            include_files_storage_size=True,
            read_table=ReadTable.CALLS_COMPLETE,
        )

        expected_sql = """
            SELECT
                (SELECT sum(
                    COALESCE(attributes_size_bytes, 0) +
                    COALESCE(inputs_size_bytes, 0) +
                    COALESCE(output_size_bytes, 0) +
                    COALESCE(summary_size_bytes, 0)
                    )
                    FROM calls_complete_stats
                    WHERE project_id = {pb_0: String}
                ) AS trace_storage_size_bytes,
                (SELECT sum(size_bytes)
                    FROM object_versions_stats
                    WHERE project_id = {pb_0: String}
                ) AS objects_storage_size_bytes,
                (SELECT sum(size_bytes)
                    FROM table_rows_stats
                    WHERE project_id = {pb_0: String}
                ) AS tables_storage_size_bytes,
                (SELECT sum(size_bytes)
                    FROM files_stats
                    WHERE project_id = {pb_0: String}
                ) AS files_storage_size_bytes
        """
        assert_sql(query, expected_sql, pb.get_params(), {"pb_0": "test_project"})
        assert columns == [
            "trace_storage_size_bytes",
            "objects_storage_size_bytes",
            "tables_storage_size_bytes",
            "files_storage_size_bytes",
        ]

    def test_raises_when_no_storage_sizes_requested(self) -> None:
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

    def test_parameterization_prevents_sql_injection(self) -> None:
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

        expected_sql = """
            SELECT
                (SELECT sum(
                    COALESCE(attributes_size_bytes, 0) +
                    COALESCE(inputs_size_bytes, 0) +
                    COALESCE(output_size_bytes, 0) +
                    COALESCE(summary_size_bytes, 0)
                    )
                    FROM calls_merged_stats
                    WHERE project_id = {pb_0: String}
                ) AS trace_storage_size_bytes
        """
        # Project ID should be parameterized, not directly in query
        assert "malicious" not in query
        assert_sql(
            query, expected_sql, pb.get_params(), {"pb_0": "malicious'--project"}
        )

    def test_only_objects_storage_with_calls_complete(self) -> None:
        """Verify non-trace storage works without including calls stats table."""
        pb = ParamBuilder("pb")
        query, columns = make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=False,
            include_objects_storage_size=True,
            include_tables_storage_size=False,
            include_files_storage_size=False,
            read_table=ReadTable.CALLS_COMPLETE,
        )

        expected_sql = """
            SELECT
                (SELECT sum(size_bytes)
                    FROM object_versions_stats
                    WHERE project_id = {pb_0: String}
                ) AS objects_storage_size_bytes
        """
        assert_sql(query, expected_sql, pb.get_params(), {"pb_0": "test_project"})
        assert columns == ["objects_storage_size_bytes"]
