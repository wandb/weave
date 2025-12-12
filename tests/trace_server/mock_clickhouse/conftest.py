"""Pytest fixtures for mock ClickHouse tests.

This conftest provides fixtures for testing the mock ClickHouse backend.
These fixtures are automatically available to tests in this directory.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest

from tests.trace_server.mock_clickhouse import MockClickHouseClient, MockClickHouseStorage


@pytest.fixture
def mock_storage() -> Generator[MockClickHouseStorage, None, None]:
    """Provide a fresh mock ClickHouse storage instance for each test."""
    storage = MockClickHouseStorage()
    yield storage
    storage.reset()


@pytest.fixture
def mock_client(mock_storage: MockClickHouseStorage) -> Generator[MockClickHouseClient, None, None]:
    """Provide a mock ClickHouse client using the test storage."""
    client = MockClickHouseClient(storage=mock_storage, database="test_db")
    yield client
    client.close()
