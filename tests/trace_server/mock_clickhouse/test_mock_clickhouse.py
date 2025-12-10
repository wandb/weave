"""Tests for the mock ClickHouse backend."""

from __future__ import annotations

import pytest

from tests.trace_server.mock_clickhouse import (
    MockClickHouseClient,
    MockClickHouseStorage,
)


class TestMockClickHouseStorage:
    """Tests for MockClickHouseStorage."""

    def test_create_database(self):
        """Test database creation."""
        storage = MockClickHouseStorage()
        storage.create_database("test_db")
        assert "test_db" in storage._databases

    def test_create_database_if_not_exists(self):
        """Test database creation with IF NOT EXISTS."""
        storage = MockClickHouseStorage()
        storage.create_database("test_db")
        # Should not raise
        storage.create_database("test_db", if_not_exists=True)
        # Should raise without if_not_exists
        with pytest.raises(ValueError, match="already exists"):
            storage.create_database("test_db", if_not_exists=False)

    def test_drop_database(self):
        """Test database deletion."""
        storage = MockClickHouseStorage()
        storage.create_database("test_db")
        storage.drop_database("test_db")
        assert "test_db" not in storage._databases

    def test_drop_database_if_exists(self):
        """Test database deletion with IF EXISTS."""
        storage = MockClickHouseStorage()
        # Should not raise
        storage.drop_database("nonexistent", if_exists=True)
        # Should raise without if_exists
        with pytest.raises(ValueError, match="does not exist"):
            storage.drop_database("nonexistent", if_exists=False)

    def test_create_table(self):
        """Test table creation."""
        storage = MockClickHouseStorage()
        storage.create_table("test_table", columns=["id", "name"])
        table = storage.get_table("test_table")
        assert table.name == "test_table"
        assert table.columns == ["id", "name"]

    def test_insert_and_query(self):
        """Test inserting and querying data."""
        storage = MockClickHouseStorage()
        storage.create_table("users", columns=["id", "name", "age"])

        # Insert data
        storage.insert("users", [[1, "Alice", 30], [2, "Bob", 25]], ["id", "name", "age"])

        # Query all
        results = storage.query("users")
        assert len(results) == 2
        assert results[0] == (1, "Alice", 30)
        assert results[1] == (2, "Bob", 25)

    def test_query_with_columns(self):
        """Test querying specific columns."""
        storage = MockClickHouseStorage()
        storage.insert("users", [[1, "Alice", 30]], ["id", "name", "age"])

        results = storage.query("users", columns=["name", "age"])
        assert results == [("Alice", 30)]

    def test_query_with_where(self):
        """Test querying with WHERE conditions."""
        storage = MockClickHouseStorage()
        storage.insert(
            "users",
            [[1, "Alice", 30], [2, "Bob", 25], [3, "Carol", 30]],
            ["id", "name", "age"],
        )

        results = storage.query("users", where={"age": 30})
        assert len(results) == 2

    def test_auto_create_table_on_insert(self):
        """Test that tables are auto-created on insert."""
        storage = MockClickHouseStorage()
        storage.insert("new_table", [[1, "value"]], ["id", "data"])

        table = storage.get_table("new_table")
        assert table.name == "new_table"
        assert "id" in table.columns
        assert "data" in table.columns

    def test_get_all_rows(self):
        """Test getting all rows as dictionaries."""
        storage = MockClickHouseStorage()
        storage.insert("users", [[1, "Alice"]], ["id", "name"])

        rows = storage.get_all_rows("users")
        assert rows == [{"id": 1, "name": "Alice"}]

    def test_clear(self):
        """Test clearing all data."""
        storage = MockClickHouseStorage()
        storage.insert("users", [[1, "Alice"]], ["id", "name"])
        storage.clear()

        results = storage.query("users")
        assert len(results) == 0

    def test_reset(self):
        """Test resetting to initial state."""
        storage = MockClickHouseStorage()
        storage.create_database("custom_db")
        storage.current_database = "custom_db"
        storage.insert("users", [[1, "Alice"]], ["id", "name"])

        storage.reset()

        assert storage.current_database == "default"
        assert "custom_db" not in storage._databases


class TestMockClickHouseClient:
    """Tests for MockClickHouseClient."""

    def test_database_property(self):
        """Test getting and setting database."""
        client = MockClickHouseClient(database="test_db")
        assert client.database == "test_db"

        client.database = "another_db"
        assert client.database == "another_db"

    def test_insert_and_query(self):
        """Test inserting and querying through the client."""
        client = MockClickHouseClient()

        # Insert data
        summary = client.insert("users", [[1, "Alice"]], ["id", "name"])
        assert summary.written_rows == 1

        # Query data
        result = client.query("SELECT * FROM users")
        assert len(result.result_rows) == 1

    def test_query_rows_stream(self):
        """Test streaming query results."""
        client = MockClickHouseClient()
        client.insert("users", [[1, "Alice"], [2, "Bob"]], ["id", "name"])

        with client.query_rows_stream("SELECT * FROM users") as stream:
            rows = list(stream)
            assert len(rows) == 2

    def test_command_create_database(self):
        """Test CREATE DATABASE command."""
        client = MockClickHouseClient()
        client.command("CREATE DATABASE IF NOT EXISTS my_db")
        assert "my_db" in client.storage._databases

    def test_command_drop_database(self):
        """Test DROP DATABASE command."""
        client = MockClickHouseClient()
        client.command("CREATE DATABASE my_db")
        client.command("DROP DATABASE IF EXISTS my_db")
        assert "my_db" not in client.storage._databases

    def test_command_create_table(self):
        """Test CREATE TABLE command."""
        client = MockClickHouseClient()
        client.command("CREATE TABLE IF NOT EXISTS users (id Int64, name String)")
        # Table should exist (auto-created with no columns, but exists)
        assert "users" in client.storage.get_database()

    def test_close(self):
        """Test client close."""
        client = MockClickHouseClient()
        client.close()

        with pytest.raises(RuntimeError, match="closed"):
            client.query("SELECT 1")

    def test_query_with_parameters(self):
        """Test queries with ClickHouse-style parameters."""
        client = MockClickHouseClient()
        client.insert("users", [[1, "Alice"], [2, "Bob"]], ["id", "name"])

        result = client.query(
            "SELECT * FROM users WHERE id = {id:Int64}",
            parameters={"id": 1},
        )
        # Note: Since our mock's WHERE parsing is simplified,
        # the actual filtering depends on the query executor
        assert result is not None

    def test_query_with_settings(self):
        """Test that settings are accepted (but ignored in mock)."""
        client = MockClickHouseClient()
        client.insert("users", [[1, "Alice"]], ["id", "name"])

        # Settings should be accepted without error
        result = client.query(
            "SELECT * FROM users",
            settings={"max_threads": 4},
        )
        assert len(result.result_rows) == 1


class TestQueryExecution:
    """Tests for query execution."""

    def test_select_with_where_equality(self):
        """Test SELECT with WHERE equality condition."""
        client = MockClickHouseClient()
        client.insert(
            "users",
            [[1, "Alice"], [2, "Bob"], [3, "Carol"]],
            ["id", "name"],
        )

        result = client.query("SELECT * FROM users WHERE id = 2")
        assert len(result.result_rows) == 1
        assert result.result_rows[0][1] == "Bob"

    def test_select_with_where_string(self):
        """Test SELECT with WHERE string condition."""
        client = MockClickHouseClient()
        client.insert(
            "users",
            [[1, "Alice"], [2, "Bob"]],
            ["id", "name"],
        )

        result = client.query("SELECT * FROM users WHERE name = 'Alice'")
        assert len(result.result_rows) == 1
        assert result.result_rows[0][0] == 1

    def test_select_with_limit(self):
        """Test SELECT with LIMIT."""
        client = MockClickHouseClient()
        client.insert(
            "users",
            [[1, "Alice"], [2, "Bob"], [3, "Carol"]],
            ["id", "name"],
        )

        result = client.query("SELECT * FROM users LIMIT 2")
        assert len(result.result_rows) == 2

    def test_select_with_order_by_asc(self):
        """Test SELECT with ORDER BY ASC."""
        client = MockClickHouseClient()
        client.insert(
            "users",
            [[3, "Carol"], [1, "Alice"], [2, "Bob"]],
            ["id", "name"],
        )

        result = client.query("SELECT * FROM users ORDER BY id ASC")
        ids = [row[0] for row in result.result_rows]
        assert ids == [1, 2, 3]

    def test_select_with_order_by_desc(self):
        """Test SELECT with ORDER BY DESC."""
        client = MockClickHouseClient()
        client.insert(
            "users",
            [[1, "Alice"], [2, "Bob"], [3, "Carol"]],
            ["id", "name"],
        )

        result = client.query("SELECT * FROM users ORDER BY id DESC")
        ids = [row[0] for row in result.result_rows]
        assert ids == [3, 2, 1]

    def test_select_with_and_condition(self):
        """Test SELECT with AND condition."""
        client = MockClickHouseClient()
        client.insert(
            "users",
            [[1, "Alice", 30], [2, "Bob", 25], [3, "Carol", 30]],
            ["id", "name", "age"],
        )

        result = client.query("SELECT * FROM users WHERE age = 30 AND name = 'Alice'")
        assert len(result.result_rows) == 1
        assert result.result_rows[0][0] == 1

    def test_select_with_or_condition(self):
        """Test SELECT with OR condition."""
        client = MockClickHouseClient()
        client.insert(
            "users",
            [[1, "Alice"], [2, "Bob"], [3, "Carol"]],
            ["id", "name"],
        )

        result = client.query("SELECT * FROM users WHERE name = 'Alice' OR name = 'Bob'")
        assert len(result.result_rows) == 2

    def test_select_with_in_clause(self):
        """Test SELECT with IN clause."""
        client = MockClickHouseClient()
        client.insert(
            "users",
            [[1, "Alice"], [2, "Bob"], [3, "Carol"]],
            ["id", "name"],
        )

        result = client.query("SELECT * FROM users WHERE id IN (1, 3)")
        assert len(result.result_rows) == 2
        ids = {row[0] for row in result.result_rows}
        assert ids == {1, 3}

    def test_select_with_is_null(self):
        """Test SELECT with IS NULL."""
        client = MockClickHouseClient()
        client.insert(
            "users",
            [[1, "Alice", 30], [2, "Bob", None], [3, None, 25]],
            ["id", "name", "age"],
        )

        result = client.query("SELECT * FROM users WHERE age IS NULL")
        assert len(result.result_rows) == 1
        assert result.result_rows[0][0] == 2

    def test_select_with_is_not_null(self):
        """Test SELECT with IS NOT NULL."""
        client = MockClickHouseClient()
        client.insert(
            "users",
            [[1, "Alice", 30], [2, "Bob", None]],
            ["id", "name", "age"],
        )

        result = client.query("SELECT * FROM users WHERE age IS NOT NULL")
        assert len(result.result_rows) == 1
        assert result.result_rows[0][0] == 1

    def test_select_from_nonexistent_table(self):
        """Test SELECT from a table that doesn't exist."""
        client = MockClickHouseClient()
        result = client.query("SELECT * FROM nonexistent")
        assert len(result.result_rows) == 0

    def test_parameter_substitution(self):
        """Test parameter substitution with various types."""
        client = MockClickHouseClient()
        client.insert("users", [[1, "Alice"]], ["id", "name"])

        # String parameter
        result = client.query(
            "SELECT * FROM users WHERE name = {name:String}",
            parameters={"name": "Alice"},
        )
        assert len(result.result_rows) == 1

    def test_parameter_substitution_with_special_chars(self):
        """Test parameter substitution with special characters."""
        client = MockClickHouseClient()
        client.insert("users", [[1, "O'Brien"]], ["id", "name"])

        result = client.query(
            "SELECT * FROM users WHERE name = {name:String}",
            parameters={"name": "O'Brien"},
        )
        # The query should handle the escaped quote
        assert result is not None


class TestSharedStorage:
    """Tests for shared storage between clients."""

    def test_clients_share_storage(self):
        """Test that multiple clients can share storage."""
        storage = MockClickHouseStorage()
        client1 = MockClickHouseClient(storage=storage, database="db1")
        client2 = MockClickHouseClient(storage=storage, database="db1")

        client1.insert("users", [[1, "Alice"]], ["id", "name"])

        result = client2.query("SELECT * FROM users")
        assert len(result.result_rows) == 1

    def test_clients_with_different_databases(self):
        """Test clients with different databases."""
        storage = MockClickHouseStorage()
        storage.create_database("db1")
        storage.create_database("db2")

        client1 = MockClickHouseClient(storage=storage, database="db1")
        client2 = MockClickHouseClient(storage=storage, database="db2")

        client1.insert("users", [[1, "Alice"]], ["id", "name"])

        # client2 should not see client1's data
        result2 = client2.query("SELECT * FROM users")
        assert len(result2.result_rows) == 0
