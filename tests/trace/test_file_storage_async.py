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

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def s3_uri():
    """S3 URI fixture for testing."""
    return S3FileStorageURI(bucket="test-bucket", path="")


@pytest.fixture
def s3_credentials():
    """AWS credentials fixture for testing."""
    return {
        "access_key_id": "test-key",
        "secret_access_key": "test-secret",
        "region": "us-east-1",
        "session_token": None,
        "kms_key": None,
    }


@pytest.fixture
def mock_sync_s3_client(s3_uri):
    """Create a mock sync S3 client."""
    client = mock.MagicMock(spec=S3StorageClient)
    client.base_uri = s3_uri
    return client


@pytest.fixture
def gcs_uri():
    """GCS URI fixture for testing."""
    return GCSFileStorageURI(bucket="test-bucket", path="")


@pytest.fixture
def mock_sync_gcs_client(gcs_uri):
    """Create a mock sync GCS client."""
    client = mock.MagicMock(spec=GCSStorageClient)
    client.base_uri = gcs_uri
    return client


@pytest.fixture
def mock_async_client():
    """Create a mock async storage client for store_in_bucket_async tests."""
    client = mock.AsyncMock(spec=AsyncFileStorageClient)
    client.base_uri = S3FileStorageURI(bucket="test-bucket", path="")
    client.base_uri.with_path = lambda p: S3FileStorageURI(bucket="test-bucket", path=p)
    return client


# =============================================================================
# AsyncS3StorageClient Tests
# =============================================================================


@pytest.mark.asyncio
async def test_s3_store_async_calls_aiobotocore(
    s3_uri, s3_credentials, mock_sync_s3_client
):
    """Test that S3 store_async uses aiobotocore client."""
    async_client = AsyncS3StorageClient(s3_uri, s3_credentials, mock_sync_s3_client)

    mock_aio_client = mock.AsyncMock()
    mock_aio_client.put_object = mock.AsyncMock()

    with mock.patch.object(async_client, "_get_async_s3_client") as mock_get_client:
        mock_get_client.return_value.__aenter__ = mock.AsyncMock(
            return_value=mock_aio_client
        )
        mock_get_client.return_value.__aexit__ = mock.AsyncMock()

        target_uri = s3_uri.with_path("test/file.txt")
        await async_client.store_async(target_uri, b"test content")

        mock_get_client.assert_called_once()


@pytest.mark.asyncio
async def test_s3_read_async_calls_aiobotocore(
    s3_uri, s3_credentials, mock_sync_s3_client
):
    """Test that S3 read_async uses aiobotocore client."""
    async_client = AsyncS3StorageClient(s3_uri, s3_credentials, mock_sync_s3_client)

    mock_stream = mock.AsyncMock()
    mock_stream.read = mock.AsyncMock(return_value=b"test content")
    mock_aio_client = mock.AsyncMock()
    mock_aio_client.get_object = mock.AsyncMock(return_value={"Body": mock_stream})
    mock_stream.__aenter__ = mock.AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = mock.AsyncMock()

    with mock.patch.object(async_client, "_get_async_s3_client") as mock_get_client:
        mock_get_client.return_value.__aenter__ = mock.AsyncMock(
            return_value=mock_aio_client
        )
        mock_get_client.return_value.__aexit__ = mock.AsyncMock()

        target_uri = s3_uri.with_path("test/file.txt")
        await async_client.read_async(target_uri)

        mock_get_client.assert_called_once()


@pytest.mark.asyncio
async def test_s3_session_reused(s3_uri, s3_credentials, mock_sync_s3_client):
    """Test that the aiobotocore session is reused across calls."""
    async_client = AsyncS3StorageClient(s3_uri, s3_credentials, mock_sync_s3_client)

    # First call creates session
    session1 = async_client._get_session()
    # Second call reuses session
    session2 = async_client._get_session()

    assert session1 is session2


# =============================================================================
# AsyncGCSStorageClient Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["store", "read"])
async def test_gcs_async_uses_thread_pool(gcs_uri, mock_sync_gcs_client, operation):
    """Test that GCS async operations use thread pool wrapper."""
    async_client = AsyncGCSStorageClient(gcs_uri, None, mock_sync_gcs_client)
    target_uri = gcs_uri.with_path("test/file.txt")

    if operation == "store":
        mock_sync_gcs_client.store.return_value = None
        with mock.patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = None
            await async_client.store_async(target_uri, b"test content")
            mock_to_thread.assert_called_once_with(
                mock_sync_gcs_client.store, target_uri, b"test content"
            )
    else:
        mock_sync_gcs_client.read.return_value = b"test content"
        with mock.patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = b"test content"
            result = await async_client.read_async(target_uri)
            mock_to_thread.assert_called_once_with(
                mock_sync_gcs_client.read, target_uri
            )
            assert result == b"test content"


# =============================================================================
# store_in_bucket_async Tests
# =============================================================================


@pytest.mark.asyncio
async def test_store_in_bucket_async_success(mock_async_client):
    """Test successful async bucket storage returns correct URI."""
    mock_async_client.store_async.return_value = None

    result = await store_in_bucket_async(
        mock_async_client, "test/path/file.txt", b"content"
    )

    assert result.bucket == "test-bucket"
    assert result.path == "test/path/file.txt"
    mock_async_client.store_async.assert_called_once()


@pytest.mark.asyncio
async def test_store_in_bucket_async_failure_raises_error(mock_async_client):
    """Test async bucket storage failure raises FileStorageWriteError."""
    mock_async_client.store_async.side_effect = Exception("Storage failed")

    with pytest.raises(FileStorageWriteError) as exc_info:
        await store_in_bucket_async(mock_async_client, "test/path/file.txt", b"content")

    assert "Failed to store file" in str(exc_info.value)


# =============================================================================
# Concurrency Tests
# =============================================================================


@pytest.mark.asyncio
async def test_concurrent_operations_complete_in_parallel():
    """Test that multiple async operations run concurrently, not serially."""

    async def mock_async_operation(delay: float, name: str) -> str:
        await asyncio.sleep(delay)
        return name

    # Run 3 operations concurrently, each taking 0.1s
    tasks = [mock_async_operation(0.1, f"op{i}") for i in range(3)]

    start = time.monotonic()
    results = await asyncio.gather(*tasks)
    total_time = time.monotonic() - start

    assert set(results) == {"op0", "op1", "op2"}
    # If truly concurrent, total time should be ~0.1s, not 0.3s
    assert total_time < 0.25, f"Operations took {total_time}s, expected < 0.25s"


@pytest.mark.asyncio
async def test_event_loop_not_blocked():
    """Test that async operations don't block the event loop."""
    event_loop_blocked = False

    async def check_event_loop():
        nonlocal event_loop_blocked
        for _ in range(5):
            start = time.monotonic()
            await asyncio.sleep(0.01)
            elapsed = time.monotonic() - start
            if elapsed > 0.05:
                event_loop_blocked = True
                break

    async def fast_async_operation():
        await asyncio.sleep(0.02)
        return "done"

    checker_task = asyncio.create_task(check_event_loop())
    result = await fast_async_operation()
    await checker_task

    assert result == "done"
    assert not event_loop_blocked, "Event loop was blocked during async operation"
