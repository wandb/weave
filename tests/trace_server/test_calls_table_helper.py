"""Tests for table routing via ClickHouseTraceServer._get_calls_table()."""

import pytest

from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
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


def test_get_calls_table_returns_calls_merged_for_v0():
    """V0 projects should route to calls_merged table."""
    pvs = MockProjectVersionService(version=0)
    server = ClickHouseTraceServer(
        host="localhost",
        project_version_service=pvs,
    )
    table = server._get_calls_table("test-project")
    assert table == "calls_merged"
    assert pvs.call_count == 1


def test_get_calls_table_returns_calls_complete_for_v1():
    """V1 projects should route to calls_complete table."""
    pvs = MockProjectVersionService(version=1)
    server = ClickHouseTraceServer(
        host="localhost",
        project_version_service=pvs,
    )
    table = server._get_calls_table("test-project")
    assert table == "calls_complete"
    assert pvs.call_count == 1


def test_get_calls_table_defaults_to_calls_merged_for_unknown_version():
    """Unknown versions should default to calls_merged for backwards compatibility."""
    pvs = MockProjectVersionService(version=999)
    server = ClickHouseTraceServer(
        host="localhost",
        project_version_service=pvs,
    )
    table = server._get_calls_table("test-project")
    # Current behavior: only version=1 goes to calls_complete
    assert table == "calls_merged"


def test_get_calls_table_handles_different_projects():
    """Helper should work with different project IDs."""
    pvs = MockProjectVersionService(version=1)
    server = ClickHouseTraceServer(
        host="localhost",
        project_version_service=pvs,
    )
    
    table1 = server._get_calls_table("project-a")
    table2 = server._get_calls_table("project-b")
    
    assert table1 == "calls_complete"
    assert table2 == "calls_complete"
    assert pvs.call_count == 2


def test_get_calls_table_returns_calls_merged_when_no_service():
    """When no ProjectVersionService is provided, should default to calls_merged."""
    server = ClickHouseTraceServer(
        host="localhost",
        project_version_service=None,
    )
    table = server._get_calls_table("test-project")
    assert table == "calls_merged"

