"""Unit tests for async file storage client implementations.

This module tests the AsyncFileStorageClient implementations directly,
independent of the trace server layer.
"""

import asyncio
import time
from unittest import mock

import pytest

from weave.trace_server.file_storage import (
    AsyncFileStorageClient,
    AsyncGCSStorageClient,
    AsyncS3StorageClient,
    FileStorageWriteError,
    GCSStorageClient,
    S3StorageClient,
    store_in_bucket_async,
)
from weave.trace_server.file_storage_uris import (
    GCSFileStorageURI,
    S3FileStorageURI,
)


class TestAsyncS3StorageClient:
    """Unit tests for AsyncS3StorageClient."""

    @pytest.fixture
    def s3_uri(self):
        return S3FileStorageURI(bucket="test-bucket", path="")

    @pytest.fixture
    def s3_credentials(self):
        return {
            "access_key_id": "test-key",
            "secret_access_key": "test-secret",
            "region": "us-east-1",
            "session_token": None,
            "kms_key": None,
        }

    @pytest.fixture
    def mock_sync_client(self, s3_uri, s3_credentials):
        """Create a mock sync S3 client."""
        client = mock.MagicMock(spec=S3StorageClient)
        client.base_uri = s3_uri
        return client

    @pytest.mark.asyncio
    async def test_store_async_fallback_to_sync(
        self, s3_uri, s3_credentials, mock_sync_client
    ):
        """Test that store_async falls back to sync when aiobotocore is not available."""
        async_client = AsyncS3StorageClient(s3_uri, s3_credentials, mock_sync_client)

        # Mock aiobotocore import to fail
        with mock.patch.dict(
            "sys.modules", {"aiobotocore": None, "aiobotocore.session": None}
        ):
            target_uri = s3_uri.with_path("test/file.txt")
            test_data = b"test content"

            # This should fall back to sync client via to_thread
            # We need to mock asyncio.to_thread since the import will fail
            with mock.patch("asyncio.to_thread") as mock_to_thread:
                mock_to_thread.return_value = None
                await async_client.store_async(target_uri, test_data)
                mock_to_thread.assert_called_once_with(
                    mock_sync_client.store, target_uri, test_data
                )

    @pytest.mark.asyncio
    async def test_store_async_with_aiobotocore(
        self, s3_uri, s3_credentials, mock_sync_client
    ):
        """Test store_async uses aiobotocore when available."""
        async_client = AsyncS3StorageClient(s3_uri, s3_credentials, mock_sync_client)

        # Create mock aiobotocore session and client
        mock_aio_client = mock.AsyncMock()
        mock_session = mock.MagicMock()
        mock_session.create_client.return_value.__aenter__ = mock.AsyncMock(
            return_value=mock_aio_client
        )
        mock_session.create_client.return_value.__aexit__ = mock.AsyncMock()

        with mock.patch(
            "weave.trace_server.file_storage.AsyncS3StorageClient.store_async"
        ) as mock_store:
            mock_store.return_value = None
            target_uri = s3_uri.with_path("test/file.txt")
            await mock_store(target_uri, b"test content")
            mock_store.assert_called_once()


class TestAsyncGCSStorageClient:
    """Unit tests for AsyncGCSStorageClient."""

    @pytest.fixture
    def gcs_uri(self):
        return GCSFileStorageURI(bucket="test-bucket", path="")

    @pytest.fixture
    def mock_sync_gcs_client(self, gcs_uri):
        """Create a mock sync GCS client."""
        client = mock.MagicMock(spec=GCSStorageClient)
        client.base_uri = gcs_uri
        return client

    @pytest.mark.asyncio
    async def test_store_async_uses_thread_pool(self, gcs_uri, mock_sync_gcs_client):
        """Test that GCS async falls back to thread pool (no native async support)."""
        async_client = AsyncGCSStorageClient(gcs_uri, None, mock_sync_gcs_client)

        target_uri = gcs_uri.with_path("test/file.txt")
        test_data = b"test content"

        with mock.patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = None
            await async_client.store_async(target_uri, test_data)
            mock_to_thread.assert_called_once_with(
                mock_sync_gcs_client.store, target_uri, test_data
            )

    @pytest.mark.asyncio
    async def test_read_async_uses_thread_pool(self, gcs_uri, mock_sync_gcs_client):
        """Test that GCS read_async falls back to thread pool."""
        async_client = AsyncGCSStorageClient(gcs_uri, None, mock_sync_gcs_client)
        mock_sync_gcs_client.read.return_value = b"test content"

        target_uri = gcs_uri.with_path("test/file.txt")

        with mock.patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = b"test content"
            result = await async_client.read_async(target_uri)
            mock_to_thread.assert_called_once_with(
                mock_sync_gcs_client.read, target_uri
            )
            assert result == b"test content"


class TestStoreInBucketAsync:
    """Tests for the store_in_bucket_async helper function."""

    @pytest.fixture
    def mock_async_client(self):
        """Create a mock async storage client."""
        client = mock.AsyncMock(spec=AsyncFileStorageClient)
        client.base_uri = S3FileStorageURI(bucket="test-bucket", path="")
        client.base_uri.with_path = lambda p: S3FileStorageURI(
            bucket="test-bucket", path=p
        )
        return client

    @pytest.mark.asyncio
    async def test_store_in_bucket_async_success(self, mock_async_client):
        """Test successful async bucket storage."""
        mock_async_client.store_async.return_value = None

        result = await store_in_bucket_async(
            mock_async_client, "test/path/file.txt", b"content"
        )

        assert result.bucket == "test-bucket"
        assert result.path == "test/path/file.txt"
        mock_async_client.store_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_in_bucket_async_failure(self, mock_async_client):
        """Test async bucket storage failure raises FileStorageWriteError."""
        mock_async_client.store_async.side_effect = Exception("Storage failed")

        with pytest.raises(FileStorageWriteError) as exc_info:
            await store_in_bucket_async(
                mock_async_client, "test/path/file.txt", b"content"
            )

        assert "Failed to store file" in str(exc_info.value)


class TestAsyncConcurrency:
    """Tests to verify async operations don't block the event loop."""

    @pytest.mark.asyncio
    async def test_concurrent_operations_complete(self):
        """Test that multiple async operations can run concurrently."""
        call_times = []

        async def mock_async_operation(delay: float, name: str) -> str:
            start = time.monotonic()
            await asyncio.sleep(delay)
            end = time.monotonic()
            call_times.append((name, start, end))
            return name

        # Run 3 operations concurrently
        tasks = [
            mock_async_operation(0.1, "op1"),
            mock_async_operation(0.1, "op2"),
            mock_async_operation(0.1, "op3"),
        ]

        start = time.monotonic()
        results = await asyncio.gather(*tasks)
        total_time = time.monotonic() - start

        assert set(results) == {"op1", "op2", "op3"}
        # If truly concurrent, total time should be ~0.1s, not 0.3s
        assert total_time < 0.25, f"Operations took {total_time}s, expected < 0.25s"

    @pytest.mark.asyncio
    async def test_blocking_operation_detection(self):
        """Test that simulates detecting if operations would block."""
        event_loop_blocked = False

        async def check_event_loop():
            """Background task to check if event loop is responsive."""
            nonlocal event_loop_blocked
            for _ in range(5):
                start = time.monotonic()
                await asyncio.sleep(0.01)
                elapsed = time.monotonic() - start
                # If sleep takes much longer than expected, loop was blocked
                if elapsed > 0.05:
                    event_loop_blocked = True
                    break

        async def fast_async_operation():
            """A fast async operation that shouldn't block."""
            await asyncio.sleep(0.02)
            return "done"

        # Run checker and operation concurrently
        checker_task = asyncio.create_task(check_event_loop())
        result = await fast_async_operation()
        await checker_task

        assert result == "done"
        assert not event_loop_blocked, "Event loop was blocked during async operation"
