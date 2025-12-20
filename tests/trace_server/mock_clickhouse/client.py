"""Mock ClickHouse client implementation."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from tests.trace_server.mock_clickhouse.query_executor import QueryExecutor
from tests.trace_server.mock_clickhouse.storage import MockClickHouseStorage


@dataclass
class MockQuerySummary:
    """Mock implementation of QuerySummary."""

    written_rows: int = 0
    written_bytes: int = 0
    read_rows: int = 0
    read_bytes: int = 0
    elapsed: float = 0.0


@dataclass
class MockQueryResult:
    """Mock implementation of QueryResult."""

    result_rows: list[tuple] = field(default_factory=list)
    column_names: list[str] = field(default_factory=list)
    summary: MockQuerySummary = field(default_factory=MockQuerySummary)

    def __iter__(self):
        return iter(self.result_rows)

    def __len__(self):
        return len(self.result_rows)


class MockRowStream:
    """Mock implementation of query rows stream."""

    def __init__(self, result: MockQueryResult):
        self._result = result
        self._source = result
        self._iter: Iterator[tuple] | None = None

    @property
    def source(self) -> MockQueryResult:
        return self._source

    def __iter__(self) -> Iterator[tuple]:
        return iter(self._result.result_rows)

    def __enter__(self) -> "MockRowStream":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass


class MockClickHouseClient:
    """Mock ClickHouse client that stores data in memory.

    This client implements the key methods of the clickhouse_connect.driver.client.Client
    that are used by ClickHouseTraceServer:
    - query(): Execute a query and return results
    - query_rows_stream(): Stream query results
    - insert(): Insert data into a table
    - command(): Execute DDL commands
    - close(): Close the connection
    - database property: Get/set current database
    """

    def __init__(
        self,
        storage: MockClickHouseStorage | None = None,
        database: str = "default",
    ):
        """Initialize the mock client.

        Args:
            storage: Shared storage instance (creates new one if not provided)
            database: Initial database to use
        """
        self._storage = storage or MockClickHouseStorage()
        self._database = database
        self._executor = QueryExecutor(self._storage)
        self._closed = False
        # Ensure database exists
        self._storage.create_database(database, if_not_exists=True)
        self._storage.current_database = database

    @property
    def database(self) -> str:
        """Get the current database name."""
        return self._database

    @database.setter
    def database(self, value: str) -> None:
        """Set the current database name."""
        self._database = value
        self._storage.current_database = value

    @property
    def storage(self) -> MockClickHouseStorage:
        """Get the underlying storage instance."""
        return self._storage

    def query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        column_formats: dict[str, Any] | None = None,
        use_none: bool = False,
        settings: dict[str, Any] | None = None,
    ) -> MockQueryResult:
        """Execute a query and return results.

        Args:
            query: SQL query string
            parameters: Query parameters
            column_formats: Column format specifications (ignored in mock)
            use_none: Whether to use None for NULL values (always True in mock)
            settings: Query settings (ignored in mock)

        Returns:
            MockQueryResult with the query results
        """
        self._check_closed()
        return self._executor.execute(query, parameters or {}, self._database)

    def query_rows_stream(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        column_formats: dict[str, Any] | None = None,
        use_none: bool = False,
        settings: dict[str, Any] | None = None,
    ) -> MockRowStream:
        """Execute a query and return a streaming result.

        Args:
            query: SQL query string
            parameters: Query parameters
            column_formats: Column format specifications (ignored in mock)
            use_none: Whether to use None for NULL values (always True in mock)
            settings: Query settings (ignored in mock)

        Returns:
            MockRowStream that can be iterated over
        """
        self._check_closed()
        result = self._executor.execute(query, parameters or {}, self._database)
        return MockRowStream(result)

    def insert(
        self,
        table: str,
        data: list[list[Any]] | list[tuple[Any, ...]],
        column_names: list[str],
        settings: dict[str, Any] | None = None,
    ) -> MockQuerySummary:
        """Insert data into a table.

        Args:
            table: Table name
            data: List of rows to insert
            column_names: Column names for the data
            settings: Insert settings (ignored in mock)

        Returns:
            MockQuerySummary with insert statistics
        """
        self._check_closed()
        # Convert tuples to lists if necessary
        data_as_lists = [list(row) for row in data]
        num_rows = self._storage.insert(table, data_as_lists, column_names, self._database)
        return MockQuerySummary(written_rows=num_rows)

    def command(self, cmd: str, parameters: dict[str, Any] | None = None) -> None:
        """Execute a DDL command.

        Supports:
        - CREATE DATABASE [IF NOT EXISTS] <name>
        - DROP DATABASE [IF EXISTS] <name>
        - CREATE TABLE [IF NOT EXISTS] <name> (...)
        - DROP TABLE [IF EXISTS] <name>

        Args:
            cmd: DDL command string
            parameters: Command parameters (ignored in mock)
        """
        self._check_closed()
        cmd = cmd.strip()
        cmd_upper = cmd.upper()

        # CREATE DATABASE
        create_db_match = re.match(
            r"CREATE\s+DATABASE\s+(IF\s+NOT\s+EXISTS\s+)?(\w+)",
            cmd_upper,
        )
        if create_db_match:
            if_not_exists = create_db_match.group(1) is not None
            # Extract actual database name from original cmd to preserve case
            db_name = cmd.split()[-1]
            self._storage.create_database(db_name, if_not_exists=if_not_exists)
            return

        # DROP DATABASE
        drop_db_match = re.match(
            r"DROP\s+DATABASE\s+(IF\s+EXISTS\s+)?(\w+)",
            cmd_upper,
        )
        if drop_db_match:
            if_exists = drop_db_match.group(1) is not None
            db_name = cmd.split()[-1]
            self._storage.drop_database(db_name, if_exists=if_exists)
            return

        # CREATE TABLE - simplified parsing
        create_table_match = re.match(
            r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?(\S+)",
            cmd_upper,
        )
        if create_table_match:
            if_not_exists = create_table_match.group(1) is not None
            # Extract table name - handle database.table format
            parts = cmd.split()
            table_idx = 2
            if if_not_exists:
                table_idx = 5
            table_name = parts[table_idx] if len(parts) > table_idx else ""
            # Remove any trailing parenthesis or characters
            table_name = re.sub(r"[(\s].*", "", table_name)
            self._storage.create_table(table_name, if_not_exists=if_not_exists, database=self._database)
            return

        # DROP TABLE
        drop_table_match = re.match(
            r"DROP\s+TABLE\s+(IF\s+EXISTS\s+)?(\S+)",
            cmd_upper,
        )
        if drop_table_match:
            if_exists = drop_table_match.group(1) is not None
            parts = cmd.split()
            table_idx = 2
            if if_exists:
                table_idx = 4
            table_name = parts[table_idx] if len(parts) > table_idx else ""
            self._storage.drop_table(table_name, if_exists=if_exists, database=self._database)
            return

        # For other commands (like ALTER, etc.), just ignore them for now
        # In a more complete implementation, we'd parse and handle these

    def close(self) -> None:
        """Close the connection."""
        self._closed = True

    def _check_closed(self) -> None:
        """Raise an error if the client is closed."""
        if self._closed:
            raise RuntimeError("Client is closed")
