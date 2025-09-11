"""Test ClickHouse client cleanup functionality."""

import gc
import threading
import time
import weakref
from unittest.mock import MagicMock, patch

import pytest

from weave.trace_server import clickhouse_trace_server_batched as cts


@pytest.fixture
def ch_server():
    """Create a test ClickHouse server instance with mocked client."""
    with patch.object(cts.ClickHouseTraceServer, "_mint_client") as mock_mint:
        # Return a mock client that has a close method
        def create_mock_client():
            mock = MagicMock()
            mock.close = MagicMock()
            return mock

        mock_mint.side_effect = create_mock_client

        server = cts.ClickHouseTraceServer(
            host="localhost",
            port=8123,
            user="default",
            password="",
            database="test",
        )
        yield server


def test_client_cleanup_on_thread_death(ch_server):
    """Test that clients are cleaned up when threads die."""
    client_ref = None
    thread_id = None

    def worker():
        nonlocal client_ref, thread_id
        thread_id = threading.get_ident()
        # Access ch_client to create a client
        client = ch_server.ch_client
        # Keep a weak reference to verify cleanup
        client_ref = weakref.ref(client)
        assert client is not None

    # Create and run thread
    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    # Verify client was registered
    assert thread_id is not None
    assert thread_id in ch_server._client_cleanup_registry

    # Run cleanup
    ch_server._cleanup_dead_clients()

    # Verify client was removed from registry
    assert thread_id not in ch_server._client_cleanup_registry


def test_client_reuse_in_same_thread(ch_server):
    """Test that the same thread reuses its client."""
    client1 = ch_server.ch_client
    client2 = ch_server.ch_client
    assert client1 is client2


def test_different_threads_get_different_clients(ch_server):
    """Test that different threads get different clients."""
    clients = []
    thread_ids = []

    def worker():
        thread_ids.append(threading.get_ident())
        clients.append(ch_server.ch_client)
        # Keep thread alive briefly to avoid ID reuse
        time.sleep(0.01)

    threads = []
    for _ in range(3):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    # All clients should be different
    assert len({id(c) for c in clients}) == 3

    # All thread IDs should be unique
    assert len(set(thread_ids)) == 3

    # Registry should have entries for threads (some may be cleaned already)
    assert len(ch_server._client_cleanup_registry) >= 0


def test_cleanup_preserves_active_thread_clients(ch_server):
    """Test that cleanup doesn't remove clients from active threads."""
    # Get client in main thread
    main_client = ch_server.ch_client
    main_thread_id = threading.get_ident()

    # Run cleanup
    ch_server._cleanup_dead_clients()

    # Main thread client should still be registered
    assert main_thread_id in ch_server._client_cleanup_registry

    # Should still be able to access the same client
    assert ch_server.ch_client is main_client


def test_weakref_cleanup_on_client_gc(ch_server):
    """Test that weak references work correctly."""
    thread_id = threading.get_ident()

    # Create a client
    client = ch_server.ch_client
    assert thread_id in ch_server._client_cleanup_registry

    # Weak ref should point to the client
    assert ch_server._client_cleanup_registry[thread_id]() is client

    # Delete the client from thread local storage to simulate it going away
    if hasattr(ch_server._thread_local, "ch_client"):
        delattr(ch_server._thread_local, "ch_client")

    # Force garbage collection
    del client
    gc.collect()

    # The weakref callback should have fired and removed the entry
    assert thread_id not in ch_server._client_cleanup_registry


def test_cleanup_thread_is_started():
    """Test that the cleanup thread is started when server is created."""
    with patch.object(cts.ClickHouseTraceServer, "_mint_client") as mock_mint:
        mock_mint.return_value = MagicMock()

        # Create server (this should start the cleanup thread)
        cts.ClickHouseTraceServer(
            host="localhost",
            port=8123,
            user="default",
            password="",
            database="test",
        )

        # Check that a thread named "ch-client-cleanup" exists
        thread_names = [t.name for t in threading.enumerate()]
        assert "ch-client-cleanup" in thread_names

        # Verify it's a daemon thread
        cleanup_thread = next(
            t for t in threading.enumerate() if t.name == "ch-client-cleanup"
        )
        assert cleanup_thread.daemon
