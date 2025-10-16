"""Integration tests for project version read path routing."""

import pytest

from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    build_calls_stats_query,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.threads_query_builder import make_threads_query
from weave.trace_server.project_query_builder import make_project_stats_query
from weave.trace_server.project_version.base import ProjectVersionService


class MockProjectVersionService:
    """Test double for ProjectVersionService."""

    def __init__(self, version: int = 0):
        self.version = version
        self.call_count = 0

    async def get_project_version(self, project_id: str) -> int:
        """Return pre-configured version."""
        self.call_count += 1
        return self.version


class TestCallsQueryRouting:
    """Test that CallsQuery routing is deferred to Stage 4."""

    def test_v0_project_uses_calls_merged(self):
        """V0 projects should generate queries against calls_merged."""
        pvs = MockProjectVersionService(version=0)
        server = ClickHouseTraceServer(
            host="localhost",
            project_version_service=pvs,
        )

        cq = CallsQuery(project_id="test-project")
        cq.add_field("id")
        pb = ParamBuilder()

        # CallsQuery always uses calls_merged for now
        sql = cq.as_sql(pb)

        assert "calls_merged" in sql
        assert "calls_complete" not in sql

    def test_v1_project_raises_not_implemented(self):
        """V1 projects should raise NotImplementedError until Stage 4."""
        from weave.trace_server import trace_server_interface as tsi
        
        pvs = MockProjectVersionService(version=1)
        server = ClickHouseTraceServer(
            host="localhost",
            project_version_service=pvs,
        )

        req = tsi.CallsQueryReq(project_id="test-project")
        
        with pytest.raises(NotImplementedError, match="V1 projects"):
            # This should raise NotImplementedError in calls_query_stream
            server.calls_query(req)


class TestCallsStatsQueryRouting:
    """Test that build_calls_stats_query routes to correct table."""

    def test_v0_project_stats_uses_calls_merged(self):
        """V0 projects should query calls_merged table."""
        from weave.trace_server import trace_server_interface as tsi

        pvs = MockProjectVersionService(version=0)
        server = ClickHouseTraceServer(
            host="localhost",
            project_version_service=pvs,
        )

        req = tsi.CallsQueryStatsReq(project_id="test-project")
        pb = ParamBuilder()

        table_name = server._get_calls_table("test-project")
        sql, _ = build_calls_stats_query(req, pb, table_alias=table_name)

        assert "calls_merged" in sql or "calls_complete" not in sql

    def test_v1_project_stats_simple_query_uses_calls_complete(self):
        """V1 projects can use optimized stats queries with calls_complete table."""
        from weave.trace_server import trace_server_interface as tsi

        pvs = MockProjectVersionService(version=1)
        server = ClickHouseTraceServer(
            host="localhost",
            project_version_service=pvs,
        )

        # Simple existence check uses optimized path
        req = tsi.CallsQueryStatsReq(project_id="test-project", limit=1)
        pb = ParamBuilder()

        table_name = server._get_calls_table("test-project")
        sql, _ = build_calls_stats_query(req, pb, table_alias=table_name)

        # Should use calls_complete in the optimized query
        assert "calls_complete" in sql
        assert "calls_merged" not in sql

    def test_v1_project_stats_complex_query_raises_not_implemented(self):
        """V1 projects raise NotImplementedError for complex stats queries."""
        from weave.trace_server import trace_server_interface as tsi

        pvs = MockProjectVersionService(version=1)
        server = ClickHouseTraceServer(
            host="localhost",
            project_version_service=pvs,
        )

        # Complex query without limit=1 falls back to general path
        req = tsi.CallsQueryStatsReq(project_id="test-project")
        pb = ParamBuilder()

        table_name = server._get_calls_table("test-project")
        
        with pytest.raises(NotImplementedError, match="Stats queries on V1 projects"):
            build_calls_stats_query(req, pb, table_alias=table_name)


class TestThreadsQueryRouting:
    """Test that make_threads_query routes to correct table."""

    def test_v0_project_threads_uses_calls_merged(self):
        """V0 projects should query calls_merged for threads."""
        pvs = MockProjectVersionService(version=0)
        server = ClickHouseTraceServer(
            host="localhost",
            project_version_service=pvs,
        )

        pb = ParamBuilder()
        table_name = server._get_calls_table("test-project")
        sql = make_threads_query(
            project_id="test-project",
            pb=pb,
            table_name=table_name,
        )

        assert "calls_merged" in sql
        assert "calls_complete" not in sql

    def test_v1_project_threads_uses_calls_complete(self):
        """V1 projects should query calls_complete for threads."""
        pvs = MockProjectVersionService(version=1)
        server = ClickHouseTraceServer(
            host="localhost",
            project_version_service=pvs,
        )

        pb = ParamBuilder()
        table_name = server._get_calls_table("test-project")
        sql = make_threads_query(
            project_id="test-project",
            pb=pb,
            table_name=table_name,
        )

        assert "calls_complete" in sql
        assert "calls_merged" not in sql


class TestProjectStatsQueryRouting:
    """Test that make_project_stats_query routes to correct stats table."""

    def test_v0_project_stats_uses_calls_merged_stats(self):
        """V0 projects should query calls_merged_stats."""
        pvs = MockProjectVersionService(version=0)
        server = ClickHouseTraceServer(
            host="localhost",
            project_version_service=pvs,
        )

        pb = ParamBuilder()
        calls_stats_table = server._get_calls_stats_table("test-project")
        sql, _ = make_project_stats_query(
            project_id="test-project",
            pb=pb,
            include_trace_storage_size=True,
            include_objects_storage_size=False,
            include_tables_storage_size=False,
            include_files_storage_size=False,
            calls_stats_table=calls_stats_table,
        )

        assert "calls_merged_stats" in sql
        assert "calls_complete_stats" not in sql

    def test_v1_project_stats_uses_calls_complete_stats(self):
        """V1 projects should query calls_complete_stats."""
        pvs = MockProjectVersionService(version=1)
        server = ClickHouseTraceServer(
            host="localhost",
            project_version_service=pvs,
        )

        pb = ParamBuilder()
        calls_stats_table = server._get_calls_stats_table("test-project")
        sql, _ = make_project_stats_query(
            project_id="test-project",
            pb=pb,
            include_trace_storage_size=True,
            include_objects_storage_size=False,
            include_tables_storage_size=False,
            include_files_storage_size=False,
            calls_stats_table=calls_stats_table,
        )

        assert "calls_complete_stats" in sql
        assert "calls_merged_stats" not in sql


class TestEndToEndTableRouting:
    """End-to-end tests verifying table routing is transparent to API consumers."""

    def test_multiple_projects_different_versions(self):
        """Different projects can have different versions simultaneously."""
        # Simulate mixed environment: some V0, some V1
        class MultiVersionService:
            async def get_project_version(self, project_id: str) -> int:
                if project_id.endswith("-v1"):
                    return 1
                return 0

        server = ClickHouseTraceServer(
            host="localhost",
            project_version_service=MultiVersionService(),
        )

        # V0 project
        table_v0 = server._get_calls_table("project-v0")
        assert table_v0 == "calls_merged"

        # V1 project
        table_v1 = server._get_calls_table("project-v1")
        assert table_v1 == "calls_complete"

    def test_no_version_service_defaults_to_v0(self):
        """Without a version service, all projects should use V0 tables."""
        server = ClickHouseTraceServer(
            host="localhost",
            project_version_service=None,
        )

        table = server._get_calls_table("any-project")
        assert table == "calls_merged"

        stats_table = server._get_calls_stats_table("any-project")
        assert stats_table == "calls_merged_stats"

