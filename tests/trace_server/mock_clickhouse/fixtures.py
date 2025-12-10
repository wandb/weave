"""Pytest fixtures for mock ClickHouse backend.

This module provides fixtures that allow tests to use the mock ClickHouse
backend instead of a real ClickHouse server.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from tests.trace_server.mock_clickhouse.client import MockClickHouseClient
from tests.trace_server.mock_clickhouse.storage import MockClickHouseStorage

if TYPE_CHECKING:
    from tests.trace_server.conftest_lib.trace_server_external_adapter import (
        TestOnlyUserInjectingExternalTraceServer,
    )


@pytest.fixture
def mock_clickhouse_storage() -> Generator[MockClickHouseStorage, None, None]:
    """Provide a shared mock ClickHouse storage instance.

    This fixture creates a fresh MockClickHouseStorage instance for each test.
    The storage is shared among all mock clients in the same test.
    """
    storage = MockClickHouseStorage()
    yield storage
    storage.reset()


@pytest.fixture
def mock_clickhouse_client(
    mock_clickhouse_storage: MockClickHouseStorage,
) -> Generator[MockClickHouseClient, None, None]:
    """Provide a mock ClickHouse client.

    This fixture creates a MockClickHouseClient that uses the shared storage
    from the mock_clickhouse_storage fixture.
    """
    client = MockClickHouseClient(storage=mock_clickhouse_storage)
    yield client
    client.close()


@pytest.fixture
def get_mock_ch_trace_server(
    mock_clickhouse_storage: MockClickHouseStorage,
) -> Callable[[], "TestOnlyUserInjectingExternalTraceServer"]:
    """Provide a factory for creating trace servers with mock ClickHouse backend.

    This fixture returns a callable that creates a new ClickHouseTraceServer
    instance using the mock backend. It can be used as a drop-in replacement
    for the get_ch_trace_server fixture.

    Usage:
        def test_something(get_mock_ch_trace_server):
            trace_server = get_mock_ch_trace_server()
            # Use trace_server...
    """
    from tests.trace_server.conftest_lib.trace_server_external_adapter import (
        DummyIdConverter,
        externalize_trace_server,
    )
    from tests.trace_server.workers.evaluate_model_test_worker import (
        EvaluateModelTestDispatcher,
    )
    from weave.trace_server.clickhouse_trace_server_batched import (
        ClickHouseTraceServer,
    )

    servers_to_cleanup: list[ClickHouseTraceServer] = []

    def factory() -> "TestOnlyUserInjectingExternalTraceServer":
        # Create a mock client that will be returned by _mint_client
        def create_mock_client() -> MockClickHouseClient:
            return MockClickHouseClient(storage=mock_clickhouse_storage)

        # Patch _mint_client to return our mock client
        with patch.object(
            ClickHouseTraceServer, "_mint_client", side_effect=create_mock_client
        ):
            id_converter = DummyIdConverter()
            server = ClickHouseTraceServer(
                host="mock",
                port=8123,
                database="test_db",
                evaluate_model_dispatcher=EvaluateModelTestDispatcher(
                    id_converter=id_converter
                ),
            )
            servers_to_cleanup.append(server)

            # The server is already initialized with a mock client through the patch
            # We don't need to run migrations since the mock doesn't require them

            return externalize_trace_server(
                server, "test_entity", id_converter=id_converter
            )

    yield factory

    # Cleanup
    for server in servers_to_cleanup:
        try:
            server.ch_client.close()
        except Exception:
            pass


def patch_clickhouse_with_mock(
    storage: MockClickHouseStorage | None = None,
) -> Callable[[type], type]:
    """Decorator to patch ClickHouseTraceServer to use mock backend.

    This can be used as a class decorator on test classes to make all tests
    in the class use the mock backend.

    Usage:
        @patch_clickhouse_with_mock()
        class TestMyFeature:
            def test_something(self):
                # ClickHouseTraceServer will use mock backend
                pass

    Args:
        storage: Optional shared storage instance. If not provided, a new
            storage instance is created for each server.

    Returns:
        Class decorator
    """

    def decorator(cls: type) -> type:
        original_setup = getattr(cls, "setup_method", None)

        def new_setup(self, method):
            self._mock_storage = storage or MockClickHouseStorage()

            def create_mock_client(server_self):
                return MockClickHouseClient(storage=self._mock_storage)

            self._mock_patch = patch.object(
                "weave.trace_server.clickhouse_trace_server_batched.ClickHouseTraceServer",
                "_mint_client",
                create_mock_client,
            )
            self._mock_patch.start()

            if original_setup:
                original_setup(self, method)

        original_teardown = getattr(cls, "teardown_method", None)

        def new_teardown(self, method):
            if original_teardown:
                original_teardown(self, method)
            if hasattr(self, "_mock_patch"):
                self._mock_patch.stop()
            if hasattr(self, "_mock_storage"):
                self._mock_storage.reset()

        cls.setup_method = new_setup
        cls.teardown_method = new_teardown
        return cls

    return decorator


@pytest.fixture
def mock_trace_server(
    get_mock_ch_trace_server: Callable[[], "TestOnlyUserInjectingExternalTraceServer"],
) -> "TestOnlyUserInjectingExternalTraceServer":
    """Provide a trace server instance with mock ClickHouse backend.

    This is a convenience fixture that calls get_mock_ch_trace_server()
    to create a single server instance.
    """
    return get_mock_ch_trace_server()
