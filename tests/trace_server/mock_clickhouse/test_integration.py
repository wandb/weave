"""Integration tests demonstrating mock ClickHouse usage with trace server.

These tests show how to use the mock backend with the ClickHouseTraceServer
to run tests without requiring a real ClickHouse database.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.trace_server.mock_clickhouse import MockClickHouseClient, MockClickHouseStorage


@pytest.fixture
def mock_storage():
    """Create a fresh mock storage for each test."""
    return MockClickHouseStorage()


@pytest.fixture
def mock_client(mock_storage):
    """Create a mock client using the test storage."""
    return MockClickHouseClient(storage=mock_storage, database="test_db")


class TestMockWithTraceServer:
    """Tests demonstrating mock usage with ClickHouseTraceServer."""

    def test_mock_client_is_used(self, mock_storage):
        """Verify that the mock client is properly substituted."""
        from weave.trace_server.clickhouse_trace_server_batched import (
            ClickHouseTraceServer,
        )

        def create_mock_client():
            return MockClickHouseClient(storage=mock_storage, database="test_db")

        with patch.object(
            ClickHouseTraceServer, "_mint_client", side_effect=create_mock_client
        ):
            server = ClickHouseTraceServer(
                host="mock",
                port=8123,
                database="test_db",
            )

            # Verify we're using the mock client
            assert type(server.ch_client).__name__ == "MockClickHouseClient"

    def test_mock_stores_data(self, mock_storage):
        """Verify that data inserted through the mock is persisted."""
        from weave.trace_server.clickhouse_trace_server_batched import (
            ClickHouseTraceServer,
        )

        def create_mock_client():
            return MockClickHouseClient(storage=mock_storage, database="test_db")

        with patch.object(
            ClickHouseTraceServer, "_mint_client", side_effect=create_mock_client
        ):
            server = ClickHouseTraceServer(
                host="mock",
                port=8123,
                database="test_db",
            )

            # Insert some data
            server.ch_client.insert(
                "call_parts",
                [[1, "proj_123", "trace_abc"]],
                ["id", "project_id", "trace_id"],
            )

            # Query it back
            result = server.ch_client.query("SELECT * FROM call_parts")
            assert len(result.result_rows) == 1
            assert result.result_rows[0][0] == 1

    def test_multiple_servers_share_storage(self, mock_storage):
        """Verify that multiple servers can share the same storage."""
        from weave.trace_server.clickhouse_trace_server_batched import (
            ClickHouseTraceServer,
        )

        def create_mock_client():
            return MockClickHouseClient(storage=mock_storage, database="test_db")

        with patch.object(
            ClickHouseTraceServer, "_mint_client", side_effect=create_mock_client
        ):
            server1 = ClickHouseTraceServer(
                host="mock",
                port=8123,
                database="test_db",
            )
            server2 = ClickHouseTraceServer(
                host="mock",
                port=8123,
                database="test_db",
            )

            # Insert through server1
            server1.ch_client.insert(
                "shared_table",
                [[1, "from_server1"]],
                ["id", "source"],
            )

            # Query through server2
            result = server2.ch_client.query("SELECT * FROM shared_table")
            assert len(result.result_rows) == 1
            assert result.result_rows[0][1] == "from_server1"

    def test_database_commands(self, mock_storage):
        """Test DDL commands work through the mock."""
        from weave.trace_server.clickhouse_trace_server_batched import (
            ClickHouseTraceServer,
        )

        def create_mock_client():
            return MockClickHouseClient(storage=mock_storage, database="test_db")

        with patch.object(
            ClickHouseTraceServer, "_mint_client", side_effect=create_mock_client
        ):
            server = ClickHouseTraceServer(
                host="mock",
                port=8123,
                database="test_db",
            )

            # Test CREATE DATABASE command
            server.ch_client.command("CREATE DATABASE IF NOT EXISTS custom_db")
            assert "custom_db" in mock_storage._databases

            # Test DROP DATABASE command
            server.ch_client.command("DROP DATABASE IF EXISTS custom_db")
            assert "custom_db" not in mock_storage._databases


class TestQueryCapabilities:
    """Tests for SQL query capabilities of the mock."""

    def test_where_with_parameters(self, mock_client):
        """Test parameterized WHERE queries."""
        mock_client.insert(
            "users",
            [[1, "Alice"], [2, "Bob"], [3, "Carol"]],
            ["id", "name"],
        )

        result = mock_client.query(
            "SELECT * FROM users WHERE name = {name:String}",
            parameters={"name": "Bob"},
        )
        assert len(result.result_rows) == 1
        assert result.result_rows[0][0] == 2

    def test_limit_and_order(self, mock_client):
        """Test LIMIT and ORDER BY."""
        mock_client.insert(
            "items",
            [[3, "c"], [1, "a"], [2, "b"]],
            ["id", "name"],
        )

        result = mock_client.query("SELECT * FROM items ORDER BY id ASC LIMIT 2")
        assert len(result.result_rows) == 2
        ids = [row[0] for row in result.result_rows]
        assert ids == [1, 2]

    def test_in_clause(self, mock_client):
        """Test IN clause filtering."""
        mock_client.insert(
            "products",
            [[1, "a"], [2, "b"], [3, "c"], [4, "d"]],
            ["id", "name"],
        )

        result = mock_client.query("SELECT * FROM products WHERE id IN (1, 3, 4)")
        assert len(result.result_rows) == 3

    def test_null_handling(self, mock_client):
        """Test NULL value handling."""
        mock_client.insert(
            "data",
            [[1, "value"], [2, None], [3, "other"]],
            ["id", "optional_field"],
        )

        # IS NULL
        result = mock_client.query("SELECT * FROM data WHERE optional_field IS NULL")
        assert len(result.result_rows) == 1
        assert result.result_rows[0][0] == 2

        # IS NOT NULL
        result = mock_client.query(
            "SELECT * FROM data WHERE optional_field IS NOT NULL"
        )
        assert len(result.result_rows) == 2


class TestStreamingQueries:
    """Tests for streaming query support."""

    def test_query_rows_stream(self, mock_client):
        """Test streaming query results."""
        mock_client.insert(
            "large_table",
            [[i, f"row_{i}"] for i in range(100)],
            ["id", "name"],
        )

        with mock_client.query_rows_stream("SELECT * FROM large_table") as stream:
            rows = list(stream)
            assert len(rows) == 100

    def test_stream_with_source(self, mock_client):
        """Test that stream provides access to source/summary."""
        mock_client.insert("test", [[1]], ["id"])

        with mock_client.query_rows_stream("SELECT * FROM test") as stream:
            # The stream should have a source attribute
            assert hasattr(stream, "source")
            assert stream.source is not None
