"""Integration tests for project version read path routing."""

from unittest.mock import MagicMock

from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_query_builder import make_project_stats_query
from weave.trace_server.project_version.types import ProjectVersion
from weave.trace_server.threads_query_builder import make_threads_query


def test_threads_query_routes_to_correct_table(monkeypatch):
    """Test make_threads_query uses correct table based on project version."""

    class MockResolver:
        def __init__(self, version):
            self.version = version

        def get_project_version_sync(self, project_id):
            return self.version

    # Mock CH client to avoid needing real database
    mock_client = MagicMock()
    monkeypatch.setattr(
        "weave.trace_server.clickhouse_trace_server_batched.clickhouse_connect.get_client",
        lambda **kwargs: mock_client,
    )

    server = ClickHouseTraceServer(host="localhost")
    pb = ParamBuilder()

    # Test OLD_VERSION -> calls_merged
    monkeypatch.setattr(
        server, "_project_version_service", MockResolver(ProjectVersion.OLD_VERSION)
    )
    table_name = server._get_calls_table("test-project")
    sql = make_threads_query(project_id="test-project", pb=pb, table_name=table_name)
    assert "calls_merged" in sql
    assert "calls_complete" not in sql

    # Test NEW_VERSION -> calls_complete
    monkeypatch.setattr(
        server, "_project_version_service", MockResolver(ProjectVersion.NEW_VERSION)
    )
    table_name = server._get_calls_table("test-project")
    sql = make_threads_query(project_id="test-project", pb=pb, table_name=table_name)
    assert "calls_complete" in sql
    assert "calls_merged" not in sql


def test_project_stats_query_routes_to_correct_stats_table(monkeypatch):
    """Test make_project_stats_query uses correct stats table based on project version."""

    class MockResolver:
        def __init__(self, version):
            self.version = version

        def get_project_version_sync(self, project_id):
            return self.version

    # Mock CH client to avoid needing real database
    mock_client = MagicMock()
    monkeypatch.setattr(
        "weave.trace_server.clickhouse_trace_server_batched.clickhouse_connect.get_client",
        lambda **kwargs: mock_client,
    )

    server = ClickHouseTraceServer(host="localhost")
    pb = ParamBuilder()

    # Test OLD_VERSION -> calls_merged_stats
    monkeypatch.setattr(
        server, "_project_version_service", MockResolver(ProjectVersion.OLD_VERSION)
    )
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

    # Test NEW_VERSION -> calls_complete_stats
    monkeypatch.setattr(
        server, "_project_version_service", MockResolver(ProjectVersion.NEW_VERSION)
    )
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
