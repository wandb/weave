"""Tests for table routing via ClickHouseTraceServer._get_calls_table()."""

from unittest.mock import MagicMock

from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.project_version.types import ProjectVersion


def test_get_calls_table_routing(monkeypatch):
    """Test _get_calls_table routes to correct table based on project version."""

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

    # Test CALLS_MERGED_VERSION (0) -> calls_merged
    monkeypatch.setattr(
        server,
        "_project_version_service",
        MockResolver(ProjectVersion.CALLS_MERGED_VERSION),
    )
    assert server._get_calls_table("test-project") == "calls_merged"

    # Test CALLS_COMPLETE_VERSION (1) -> calls_complete
    monkeypatch.setattr(
        server,
        "_project_version_service",
        MockResolver(ProjectVersion.CALLS_COMPLETE_VERSION),
    )
    assert server._get_calls_table("test-project") == "calls_complete"

    # Test EMPTY_PROJECT (-1) -> default_table
    monkeypatch.setattr(
        server, "_project_version_service", MockResolver(ProjectVersion.EMPTY_PROJECT)
    )
    assert (
        server._get_calls_table("test-project", default_table="calls_complete")
        == "calls_complete"
    )
    assert (
        server._get_calls_table("test-project", default_table="calls_merged")
        == "calls_merged"
    )

    # Test no service -> calls_merged (backwards compatibility)
    server._project_version_service = None
    assert server._get_calls_table("test-project") == "calls_merged"


def test_get_calls_stats_table_routing(monkeypatch):
    """Test _get_calls_stats_table returns correct stats table based on calls table."""

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

    # Test CALLS_MERGED_VERSION -> calls_merged_stats
    monkeypatch.setattr(
        server,
        "_project_version_service",
        MockResolver(ProjectVersion.CALLS_MERGED_VERSION),
    )
    assert server._get_calls_stats_table("test-project") == "calls_merged_stats"

    # Test CALLS_COMPLETE_VERSION -> calls_complete_stats
    monkeypatch.setattr(
        server,
        "_project_version_service",
        MockResolver(ProjectVersion.CALLS_COMPLETE_VERSION),
    )
    assert server._get_calls_stats_table("test-project") == "calls_complete_stats"

    # Test EMPTY -> default_table appends _stats
    monkeypatch.setattr(
        server, "_project_version_service", MockResolver(ProjectVersion.EMPTY_PROJECT)
    )
    assert (
        server._get_calls_stats_table("test-project", default_table="calls_complete")
        == "calls_complete_stats"
    )
