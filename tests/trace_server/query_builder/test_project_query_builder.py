"""Unit tests for project_query_builder.make_project_stats_query.

Tests verify that the query builder correctly selects the appropriate
stats table based on the read_table parameter.
"""

import pytest

from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_query_builder import make_project_stats_query
from weave.trace_server.project_version.types import ReadTable


class TestMakeProjectStatsQuery:
    """Tests for make_project_stats_query function."""

    def test_calls_merged_stats_table_used_by_default(self) -> None:
        """Verify calls_merged_stats is used when read_table is CALLS_MERGED."""
        pb = ParamBuilder()
        query, columns = make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=True,
            include_objects_storage_size=False,
            include_tables_storage_size=False,
            include_files_storage_size=False,
        )

        # Should use calls_merged_stats table
        assert "calls_merged_stats" in query
        assert "calls_complete_stats" not in query
        assert "trace_storage_size_bytes" in columns

    def test_calls_complete_stats_table_used_when_specified(self) -> None:
        """Verify calls_complete_stats is used when read_table is CALLS_COMPLETE."""
        pb = ParamBuilder()
        query, columns = make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=True,
            include_objects_storage_size=False,
            include_tables_storage_size=False,
            include_files_storage_size=False,
            read_table=ReadTable.CALLS_COMPLETE,
        )

        # Should use calls_complete_stats table
        assert "calls_complete_stats" in query
        assert "calls_merged_stats" not in query
        assert "trace_storage_size_bytes" in columns

    def test_explicit_calls_merged_table(self) -> None:
        """Verify explicit CALLS_MERGED uses calls_merged_stats."""
        pb = ParamBuilder()
        query, columns = make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=True,
            include_objects_storage_size=False,
            include_tables_storage_size=False,
            include_files_storage_size=False,
            read_table=ReadTable.CALLS_MERGED,
        )

        assert "calls_merged_stats" in query
        assert "calls_complete_stats" not in query

    def test_all_storage_sizes_with_calls_complete(self) -> None:
        """Verify all storage size queries work with calls_complete."""
        pb = ParamBuilder()
        query, columns = make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=True,
            include_objects_storage_size=True,
            include_tables_storage_size=True,
            include_files_storage_size=True,
            read_table=ReadTable.CALLS_COMPLETE,
        )

        # Should use calls_complete_stats for trace storage
        assert "calls_complete_stats" in query
        assert "calls_merged_stats" not in query

        # Other storage tables are not affected by read_table
        assert "object_versions_stats" in query
        assert "table_rows_stats" in query
        assert "files_stats" in query

        # All columns should be present
        assert "trace_storage_size_bytes" in columns
        assert "objects_storage_size_bytes" in columns
        assert "tables_storage_size_bytes" in columns
        assert "files_storage_size_bytes" in columns

    def test_all_storage_sizes_with_calls_merged(self) -> None:
        """Verify all storage size queries work with calls_merged."""
        pb = ParamBuilder()
        query, columns = make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=True,
            include_objects_storage_size=True,
            include_tables_storage_size=True,
            include_files_storage_size=True,
            read_table=ReadTable.CALLS_MERGED,
        )

        # Should use calls_merged_stats for trace storage
        assert "calls_merged_stats" in query
        assert "calls_complete_stats" not in query

        # Other storage tables are not affected by read_table
        assert "object_versions_stats" in query
        assert "table_rows_stats" in query
        assert "files_stats" in query

    def test_raises_when_no_storage_sizes_requested(self) -> None:
        """Verify ValueError raised when all include_* params are False."""
        pb = ParamBuilder()
        with pytest.raises(ValueError, match="At least one of"):
            make_project_stats_query(
                project_id="test_project",
                pb=pb,
                include_trace_storage_size=False,
                include_objects_storage_size=False,
                include_tables_storage_size=False,
                include_files_storage_size=False,
            )

    def test_only_objects_storage_calls_complete(self) -> None:
        """Verify non-trace storage works without calls stats table query."""
        pb = ParamBuilder()
        query, columns = make_project_stats_query(
            project_id="test_project",
            pb=pb,
            include_trace_storage_size=False,
            include_objects_storage_size=True,
            include_tables_storage_size=False,
            include_files_storage_size=False,
            read_table=ReadTable.CALLS_COMPLETE,
        )

        # Should not reference any calls stats table since trace_storage not requested
        assert "calls_merged_stats" not in query
        assert "calls_complete_stats" not in query
        assert "object_versions_stats" in query
        assert columns == ["objects_storage_size_bytes"]

    def test_parameterization_is_consistent(self) -> None:
        """Verify parameters are correctly set up for SQL injection safety."""
        pb = ParamBuilder()
        query, _ = make_project_stats_query(
            project_id="malicious'--project",
            pb=pb,
            include_trace_storage_size=True,
            include_objects_storage_size=True,
            include_tables_storage_size=True,
            include_files_storage_size=True,
            read_table=ReadTable.CALLS_COMPLETE,
        )

        # Project ID should be parameterized, not directly in query
        assert "malicious" not in query
        # Should have parameter placeholder
        params = pb.get_params()
        assert len(params) == 1
        assert "malicious'--project" in params.values()
