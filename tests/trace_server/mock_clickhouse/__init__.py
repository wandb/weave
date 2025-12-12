"""Mock ClickHouse backend for testing.

This module provides an in-memory mock implementation of the ClickHouse client
that can be used in place of the actual ClickHouse server in tests.

Usage:
    # Using fixtures in pytest:
    def test_something(mock_clickhouse_client):
        mock_clickhouse_client.insert("my_table", [[1, "a"]], ["id", "name"])
        result = mock_clickhouse_client.query("SELECT * FROM my_table")
        assert len(result.result_rows) == 1

    # Using with trace server:
    def test_with_trace_server(get_mock_ch_trace_server):
        trace_server = get_mock_ch_trace_server()
        # Use trace_server normally...

    # Direct usage without fixtures:
    from tests.trace_server.mock_clickhouse import MockClickHouseClient, MockClickHouseStorage

    storage = MockClickHouseStorage()
    client = MockClickHouseClient(storage=storage)
    client.insert("my_table", [[1, "value"]], ["id", "data"])
"""

from __future__ import annotations

from tests.trace_server.mock_clickhouse.client import (
    MockClickHouseClient,
    MockQueryResult,
    MockQuerySummary,
    MockRowStream,
)
from tests.trace_server.mock_clickhouse.storage import MockClickHouseStorage, Table

__all__ = [
    # Client
    "MockClickHouseClient",
    "MockQueryResult",
    "MockQuerySummary",
    "MockRowStream",
    # Storage
    "MockClickHouseStorage",
    "Table",
]


def __getattr__(name: str):
    """Lazy import fixtures to avoid pytest dependency at import time."""
    if name in (
        "get_mock_ch_trace_server",
        "mock_clickhouse_client",
        "mock_clickhouse_storage",
        "mock_trace_server",
        "patch_clickhouse_with_mock",
    ):
        from tests.trace_server.mock_clickhouse import fixtures

        return getattr(fixtures, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
