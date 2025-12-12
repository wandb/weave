#!/usr/bin/env python
"""Standalone test runner for mock ClickHouse backend.

This script can be run directly without pytest to verify the mock backend works.
"""

from __future__ import annotations

import sys
import traceback


def test_storage_create_database():
    """Test database creation."""
    from tests.trace_server.mock_clickhouse import MockClickHouseStorage

    storage = MockClickHouseStorage()
    storage.create_database("test_db")
    assert "test_db" in storage._databases
    print("  PASS: test_storage_create_database")


def test_storage_create_database_if_not_exists():
    """Test database creation with IF NOT EXISTS."""
    from tests.trace_server.mock_clickhouse import MockClickHouseStorage

    storage = MockClickHouseStorage()
    storage.create_database("test_db")
    # Should not raise
    storage.create_database("test_db", if_not_exists=True)
    # Should raise without if_not_exists
    try:
        storage.create_database("test_db", if_not_exists=False)
        assert False, "Should have raised"
    except ValueError as e:
        assert "already exists" in str(e)
    print("  PASS: test_storage_create_database_if_not_exists")


def test_storage_drop_database():
    """Test database deletion."""
    from tests.trace_server.mock_clickhouse import MockClickHouseStorage

    storage = MockClickHouseStorage()
    storage.create_database("test_db")
    storage.drop_database("test_db")
    assert "test_db" not in storage._databases
    print("  PASS: test_storage_drop_database")


def test_storage_insert_and_query():
    """Test inserting and querying data."""
    from tests.trace_server.mock_clickhouse import MockClickHouseStorage

    storage = MockClickHouseStorage()
    storage.create_table("users", columns=["id", "name", "age"])
    storage.insert("users", [[1, "Alice", 30], [2, "Bob", 25]], ["id", "name", "age"])

    results = storage.query("users")
    assert len(results) == 2
    assert results[0] == (1, "Alice", 30)
    assert results[1] == (2, "Bob", 25)
    print("  PASS: test_storage_insert_and_query")


def test_storage_query_with_columns():
    """Test querying specific columns."""
    from tests.trace_server.mock_clickhouse import MockClickHouseStorage

    storage = MockClickHouseStorage()
    storage.insert("users", [[1, "Alice", 30]], ["id", "name", "age"])

    results = storage.query("users", columns=["name", "age"])
    assert results == [("Alice", 30)]
    print("  PASS: test_storage_query_with_columns")


def test_storage_query_with_where():
    """Test querying with WHERE conditions."""
    from tests.trace_server.mock_clickhouse import MockClickHouseStorage

    storage = MockClickHouseStorage()
    storage.insert(
        "users",
        [[1, "Alice", 30], [2, "Bob", 25], [3, "Carol", 30]],
        ["id", "name", "age"],
    )

    results = storage.query("users", where={"age": 30})
    assert len(results) == 2
    print("  PASS: test_storage_query_with_where")


def test_storage_auto_create_table():
    """Test that tables are auto-created on insert."""
    from tests.trace_server.mock_clickhouse import MockClickHouseStorage

    storage = MockClickHouseStorage()
    storage.insert("new_table", [[1, "value"]], ["id", "data"])

    table = storage.get_table("new_table")
    assert table.name == "new_table"
    assert "id" in table.columns
    assert "data" in table.columns
    print("  PASS: test_storage_auto_create_table")


def test_client_database_property():
    """Test getting and setting database."""
    from tests.trace_server.mock_clickhouse import MockClickHouseClient

    client = MockClickHouseClient(database="test_db")
    assert client.database == "test_db"

    client.database = "another_db"
    assert client.database == "another_db"
    print("  PASS: test_client_database_property")


def test_client_insert_and_query():
    """Test inserting and querying through the client."""
    from tests.trace_server.mock_clickhouse import MockClickHouseClient

    client = MockClickHouseClient()

    summary = client.insert("users", [[1, "Alice"]], ["id", "name"])
    assert summary.written_rows == 1

    result = client.query("SELECT * FROM users")
    assert len(result.result_rows) == 1
    print("  PASS: test_client_insert_and_query")


def test_client_query_rows_stream():
    """Test streaming query results."""
    from tests.trace_server.mock_clickhouse import MockClickHouseClient

    client = MockClickHouseClient()
    client.insert("users", [[1, "Alice"], [2, "Bob"]], ["id", "name"])

    with client.query_rows_stream("SELECT * FROM users") as stream:
        rows = list(stream)
        assert len(rows) == 2
    print("  PASS: test_client_query_rows_stream")


def test_client_command_create_database():
    """Test CREATE DATABASE command."""
    from tests.trace_server.mock_clickhouse import MockClickHouseClient

    client = MockClickHouseClient()
    client.command("CREATE DATABASE IF NOT EXISTS my_db")
    assert "my_db" in client.storage._databases
    print("  PASS: test_client_command_create_database")


def test_client_command_drop_database():
    """Test DROP DATABASE command."""
    from tests.trace_server.mock_clickhouse import MockClickHouseClient

    client = MockClickHouseClient()
    client.command("CREATE DATABASE my_db")
    client.command("DROP DATABASE IF EXISTS my_db")
    assert "my_db" not in client.storage._databases
    print("  PASS: test_client_command_drop_database")


def test_client_close():
    """Test client close."""
    from tests.trace_server.mock_clickhouse import MockClickHouseClient

    client = MockClickHouseClient()
    client.close()

    try:
        client.query("SELECT 1")
        assert False, "Should have raised"
    except RuntimeError as e:
        assert "closed" in str(e)
    print("  PASS: test_client_close")


def test_query_with_where_equality():
    """Test SELECT with WHERE equality condition."""
    from tests.trace_server.mock_clickhouse import MockClickHouseClient

    client = MockClickHouseClient()
    client.insert("users", [[1, "Alice"], [2, "Bob"], [3, "Carol"]], ["id", "name"])

    result = client.query("SELECT * FROM users WHERE id = 2")
    assert len(result.result_rows) == 1
    assert result.result_rows[0][1] == "Bob"
    print("  PASS: test_query_with_where_equality")


def test_query_with_where_string():
    """Test SELECT with WHERE string condition."""
    from tests.trace_server.mock_clickhouse import MockClickHouseClient

    client = MockClickHouseClient()
    client.insert("users", [[1, "Alice"], [2, "Bob"]], ["id", "name"])

    result = client.query("SELECT * FROM users WHERE name = 'Alice'")
    assert len(result.result_rows) == 1
    assert result.result_rows[0][0] == 1
    print("  PASS: test_query_with_where_string")


def test_query_with_limit():
    """Test SELECT with LIMIT."""
    from tests.trace_server.mock_clickhouse import MockClickHouseClient

    client = MockClickHouseClient()
    client.insert("users", [[1, "Alice"], [2, "Bob"], [3, "Carol"]], ["id", "name"])

    result = client.query("SELECT * FROM users LIMIT 2")
    assert len(result.result_rows) == 2
    print("  PASS: test_query_with_limit")


def test_query_with_order_by():
    """Test SELECT with ORDER BY."""
    from tests.trace_server.mock_clickhouse import MockClickHouseClient

    client = MockClickHouseClient()
    client.insert("users", [[3, "Carol"], [1, "Alice"], [2, "Bob"]], ["id", "name"])

    result = client.query("SELECT * FROM users ORDER BY id ASC")
    ids = [row[0] for row in result.result_rows]
    assert ids == [1, 2, 3]
    print("  PASS: test_query_with_order_by")


def test_query_with_and_condition():
    """Test SELECT with AND condition."""
    from tests.trace_server.mock_clickhouse import MockClickHouseClient

    client = MockClickHouseClient()
    client.insert(
        "users",
        [[1, "Alice", 30], [2, "Bob", 25], [3, "Carol", 30]],
        ["id", "name", "age"],
    )

    result = client.query("SELECT * FROM users WHERE age = 30 AND name = 'Alice'")
    assert len(result.result_rows) == 1
    assert result.result_rows[0][0] == 1
    print("  PASS: test_query_with_and_condition")


def test_query_with_in_clause():
    """Test SELECT with IN clause."""
    from tests.trace_server.mock_clickhouse import MockClickHouseClient

    client = MockClickHouseClient()
    client.insert("users", [[1, "Alice"], [2, "Bob"], [3, "Carol"]], ["id", "name"])

    result = client.query("SELECT * FROM users WHERE id IN (1, 3)")
    assert len(result.result_rows) == 2
    ids = {row[0] for row in result.result_rows}
    assert ids == {1, 3}
    print("  PASS: test_query_with_in_clause")


def test_query_with_is_null():
    """Test SELECT with IS NULL."""
    from tests.trace_server.mock_clickhouse import MockClickHouseClient

    client = MockClickHouseClient()
    client.insert(
        "users",
        [[1, "Alice", 30], [2, "Bob", None], [3, None, 25]],
        ["id", "name", "age"],
    )

    result = client.query("SELECT * FROM users WHERE age IS NULL")
    assert len(result.result_rows) == 1
    assert result.result_rows[0][0] == 2
    print("  PASS: test_query_with_is_null")


def test_query_with_parameters():
    """Test queries with ClickHouse-style parameters."""
    from tests.trace_server.mock_clickhouse import MockClickHouseClient

    client = MockClickHouseClient()
    client.insert("users", [[1, "Alice"], [2, "Bob"]], ["id", "name"])

    result = client.query(
        "SELECT * FROM users WHERE name = {name:String}",
        parameters={"name": "Alice"},
    )
    assert len(result.result_rows) == 1
    print("  PASS: test_query_with_parameters")


def test_shared_storage():
    """Test that multiple clients can share storage."""
    from tests.trace_server.mock_clickhouse import (
        MockClickHouseClient,
        MockClickHouseStorage,
    )

    storage = MockClickHouseStorage()
    client1 = MockClickHouseClient(storage=storage, database="db1")
    client2 = MockClickHouseClient(storage=storage, database="db1")

    client1.insert("users", [[1, "Alice"]], ["id", "name"])

    result = client2.query("SELECT * FROM users")
    assert len(result.result_rows) == 1
    print("  PASS: test_shared_storage")


def test_different_databases():
    """Test clients with different databases."""
    from tests.trace_server.mock_clickhouse import (
        MockClickHouseClient,
        MockClickHouseStorage,
    )

    storage = MockClickHouseStorage()
    storage.create_database("db1")
    storage.create_database("db2")

    client1 = MockClickHouseClient(storage=storage, database="db1")
    client2 = MockClickHouseClient(storage=storage, database="db2")

    client1.insert("users", [[1, "Alice"]], ["id", "name"])

    result2 = client2.query("SELECT * FROM users")
    assert len(result2.result_rows) == 0
    print("  PASS: test_different_databases")


def run_all_tests():
    """Run all tests."""
    tests = [
        test_storage_create_database,
        test_storage_create_database_if_not_exists,
        test_storage_drop_database,
        test_storage_insert_and_query,
        test_storage_query_with_columns,
        test_storage_query_with_where,
        test_storage_auto_create_table,
        test_client_database_property,
        test_client_insert_and_query,
        test_client_query_rows_stream,
        test_client_command_create_database,
        test_client_command_drop_database,
        test_client_close,
        test_query_with_where_equality,
        test_query_with_where_string,
        test_query_with_limit,
        test_query_with_order_by,
        test_query_with_and_condition,
        test_query_with_in_clause,
        test_query_with_is_null,
        test_query_with_parameters,
        test_shared_storage,
        test_different_databases,
    ]

    print(f"Running {len(tests)} tests...")
    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {test.__name__}")
            traceback.print_exc()
            failed += 1
        except Exception as e:
            print(f"  ERROR: {test.__name__}")
            traceback.print_exc()
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
