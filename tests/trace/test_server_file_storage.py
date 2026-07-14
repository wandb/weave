"""Tests for file storage implementations (S3, GCS, Azure Blob).

This module tests the different cloud storage backends used for file storage.
Each storage implementation is tested with similar patterns but with their
specific setup requirements.
"""

import base64
import datetime
import os
import socket
import uuid
from unittest import mock

import boto3
import pytest
from azure.core.exceptions import ResourceExistsError
from google.api_core import exceptions
from google.auth import credentials as ga_credentials
from google.cloud import storage
from moto import mock_aws

from tests.trace.util import NOT_CLICKHOUSE_BACKEND
from weave.shared.digest import compute_file_digest
from weave.trace.weave_client import WeaveClient
from weave.trace_server import (
    clickhouse_trace_server_batched,
    clickhouse_trace_server_settings,
    file_storage,
)
from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallEndV2Req,
    CallStartReq,
    CallStartRes,
    CallStartV2Req,
    CallStartV2Res,
    EndedCallSchemaForInsert,
    EndedCallSchemaForInsertWithStartedAt,
    FileContentReadReq,
    FileCreateReq,
    StartedCallSchemaForInsert,
)
from weave.trace_server_bindings.client_interface import TraceServerClientInterface

# Test Data Constants
TEST_CONTENT = b"Hello, world!"
TEST_BUCKET = "test-bucket"


@pytest.fixture
def run_storage_test(client: WeaveClient):
    """Shared test runner for all storage implementations."""

    def _run_test():
        # Create a new trace
        res = client.server.file_create(
            FileCreateReq(
                project_id=client.project_id,
                name="test.txt",
                content=TEST_CONTENT,
            )
        )
        assert res.digest is not None
        assert res.digest != ""

        # Get the file
        file = client.server.file_content_read(
            FileContentReadReq(project_id=client.project_id, digest=res.digest)
        )
        assert file.content == TEST_CONTENT
        return res

    return _run_test


class TestS3Storage:
    """Tests for AWS S3 storage implementation."""

    @pytest.fixture
    def s3(self):
        """Moto S3 mock that implements the S3 API."""
        with mock_aws():
            s3_client = boto3.client(
                "s3",
                aws_access_key_id="test-key",
                aws_secret_access_key="test-secret",
                region_name="us-east-1",
            )
            s3_client.create_bucket(Bucket=TEST_BUCKET)
            yield s3_client

    @pytest.fixture
    def aws_storage_env(self):
        """Setup AWS storage environment."""
        with mock.patch.dict(
            os.environ,
            {
                "WF_FILE_STORAGE_AWS_ACCESS_KEY_ID": "test-key",
                "WF_FILE_STORAGE_AWS_SECRET_ACCESS_KEY": "test-secret",
                "WF_FILE_STORAGE_URI": f"s3://{TEST_BUCKET}",
                "WF_FILE_STORAGE_PROJECT_ALLOW_LIST": "c2hhd24vdGVzdC1wcm9qZWN0",
            },
        ):
            yield

    @pytest.mark.usefixtures("aws_storage_env")
    @pytest.mark.skipif(
        NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
    )
    def test_aws_storage(self, run_storage_test, s3):
        """Test file storage using AWS S3."""
        res = run_storage_test()

        # Verify the object exists in S3
        response = s3.list_objects_v2(Bucket=TEST_BUCKET)
        assert "Contents" in response
        assert len(response["Contents"]) == 1

        # Verify content
        obj = response["Contents"][0]
        obj_response = s3.get_object(Bucket=TEST_BUCKET, Key=obj["Key"])
        assert obj_response["Body"].read() == TEST_CONTENT

    @pytest.mark.skipif(
        NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
    )
    def test_large_file_migration(self, run_storage_test, s3, client: WeaveClient):
        # This test is critical in that it ensures that the system works correctly for large files. Both
        # before and after the migration to file storage, we should be able to read the file correctly.
        def _run_single_test():
            chunk_size = 100000
            num_chunks = 3
            file_part = b"1234567890"
            large_file = file_part * (chunk_size * num_chunks // len(file_part))

            # Create a new trace
            res = client.server.file_create(
                FileCreateReq(
                    project_id=client.project_id,
                    name="test.txt",
                    content=large_file,
                )
            )
            assert res.digest is not None
            assert res.digest != ""

            # Get the file
            file = client.server.file_content_read(
                FileContentReadReq(project_id=client.project_id, digest=res.digest)
            )
            assert file.content == large_file
            return res.digest

        def _run_test():
            # Run with disabled storage:
            d1 = _run_single_test()
            # Now "enable" bucket storage:
            with mock.patch.dict(
                os.environ,
                {
                    "WF_FILE_STORAGE_AWS_ACCESS_KEY_ID": "test-key",
                    "WF_FILE_STORAGE_AWS_SECRET_ACCESS_KEY": "test-secret",
                    "WF_FILE_STORAGE_URI": f"s3://{TEST_BUCKET}",
                    "WF_FILE_STORAGE_PROJECT_ALLOW_LIST": "c2hhd24vdGVzdC1wcm9qZWN0",
                },
            ):
                # This line would error before the fix
                d2 = _run_single_test()
            # Run again with disabled storage:
            d3 = _run_single_test()
            assert d1 == d2 == d3

        _run_test()


class TestGCSStorage:
    """Tests for Google Cloud Storage implementation.

    `gcs`, `gcp_storage_env`, and `mock_gcp_credentials` live in
    `tests/trace/conftest.py` so other suites in the package can drive the
    bucket write path without copy-pasting the SDK mock.
    """

    @pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials")
    @pytest.mark.skipif(
        NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
    )
    def test_gcp_storage(self, run_storage_test, gcs, client: WeaveClient):
        """Test file storage using Google Cloud Storage."""
        res = run_storage_test()

        # GCS path uses the base64-encoded project_id (matches azure test).
        project_b64 = base64.b64encode(client.project_id.encode()).decode()
        expected_key = f"weave/projects/{project_b64}/files/{res.digest}"
        assert gcs.state.blob_data[expected_key] == TEST_CONTENT
        assert gcs.state.upload_count == 1

    @pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials")
    @pytest.mark.skipif(
        NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
    )
    def test_gcp_storage_skips_duplicate_write(self, client: WeaveClient):
        """Test that writing the same content twice skips the second write.

        This verifies the if_generation_match=0 conditional write works correctly
        to prevent GCS rate limiting when multiple pods write the same object.
        """
        upload_count = 0
        blob_data = {}

        def mock_upload_from_string(
            data, timeout=None, if_generation_match=None, **kwargs
        ):
            nonlocal upload_count
            blob_name = mock_blob.name

            # Simulate GCS behavior: if_generation_match=0 means only write if not exists
            if if_generation_match == 0 and blob_name in blob_data:
                raise exceptions.PreconditionFailed("Object already exists")

            upload_count += 1
            blob_data[blob_name] = data

        def mock_download_as_bytes(timeout=None, **kwargs):
            blob_name = mock_blob.name
            return blob_data.get(blob_name, b"")

        mock_storage_client = mock.MagicMock()
        mock_bucket = mock.MagicMock()
        mock_blob = mock.MagicMock()

        mock_storage_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.upload_from_string.side_effect = mock_upload_from_string
        mock_blob.download_as_bytes.side_effect = mock_download_as_bytes

        with mock.patch(
            "google.cloud.storage.Client", return_value=mock_storage_client
        ):
            # First write should succeed
            res1 = client.server.file_create(
                FileCreateReq(
                    project_id=client.project_id,
                    name="test.txt",
                    content=TEST_CONTENT,
                )
            )
            assert upload_count == 1

            # Second write with same content should be skipped (no error, no upload)
            res2 = client.server.file_create(
                FileCreateReq(
                    project_id=client.project_id,
                    name="test.txt",
                    content=TEST_CONTENT,
                )
            )
            # Should still be 1 - second write was skipped
            assert upload_count == 1
            # Both should return the same digest
            assert res1.digest == res2.digest

            # Verify we can still read the content
            file = client.server.file_content_read(
                FileContentReadReq(project_id=client.project_id, digest=res1.digest)
            )
            assert file.content == TEST_CONTENT


class _ScopedFakeCredentials(ga_credentials.Credentials, ga_credentials.Scoped):
    """Service-account-like credentials that require scoping before use."""

    def __init__(self, scopes: list[str] | None = None):
        super().__init__()
        self._scopes = scopes

    @property
    def requires_scopes(self) -> bool:
        return not self._scopes

    @property
    def scopes(self) -> list[str] | None:
        return self._scopes

    def with_scopes(self, scopes, default_scopes=None) -> "_ScopedFakeCredentials":
        return _ScopedFakeCredentials(scopes=list(scopes))

    def refresh(self, request) -> None:
        self.token = "fake-token"


def test_keepalive_gcs_client_scopes_credentials_for_session():
    """Regression for #7221: the keep-alive GCS session must carry scoped credentials."""
    expected_scopes = list(storage.Client.SCOPE)

    unscoped = _ScopedFakeCredentials()
    assert unscoped.requires_scopes
    client = file_storage._build_keepalive_gcs_client(unscoped)

    # The session that mints tokens must hold scoped creds, else invalid_scope.
    assert client._http.credentials.scopes == expected_scopes
    assert not client._http.credentials.requires_scopes
    assert isinstance(
        client._http.get_adapter("https://storage.googleapis.com"),
        file_storage._KeepAliveHTTPAdapter,
    )

    # Already-scoped creds (local user creds) pass through, so prod-only repro.
    prescoped = _ScopedFakeCredentials(scopes=["existing-scope"])
    passthrough = file_storage._build_keepalive_gcs_client(prescoped)
    assert passthrough._http.credentials.scopes == ["existing-scope"]


def test_keepalive_adapter_sets_tcp_user_timeout():
    """In-flight stalls need TCP_USER_TIMEOUT; keep-alive only covers idle sockets."""
    adapter = file_storage._KeepAliveHTTPAdapter(
        pool_maxsize=file_storage.GCS_POOL_MAXSIZE
    )
    socket_options = adapter.poolmanager.connection_pool_kw["socket_options"]

    assert (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1) in socket_options
    # Linux-only knob (skipped on macOS/BSD where the constant is absent).
    if hasattr(socket, "TCP_USER_TIMEOUT"):
        assert (
            socket.IPPROTO_TCP,
            socket.TCP_USER_TIMEOUT,
            file_storage.GCS_TCP_USER_TIMEOUT_MS,
        ) in socket_options


class _CountingStorageClient(file_storage.FileStorageClient):
    """Records store() calls so a test can assert the dedup cache skips repeats."""

    def __init__(self, base_uri: file_storage.FileStorageURI):
        super().__init__(base_uri)
        self.store_calls = 0

    def store(self, uri: file_storage.FileStorageURI, data: bytes) -> None:
        self.store_calls += 1

    def read(self, uri: file_storage.FileStorageURI) -> bytes:
        raise NotImplementedError


def test_store_in_bucket_dedups_repeat_keys():
    """A repeat content-addressed write is served from the per-pod cache, not the backend."""
    file_storage.reset_stored_key_cache()
    base = file_storage.FileStorageURI.parse_uri_str("gs://dedup-test-bucket")
    client = _CountingStorageClient(base)

    path = file_storage.key_for_project_digest("proj", "digestA")
    uri1 = file_storage.store_in_bucket(client, path, b"data")
    uri2 = file_storage.store_in_bucket(client, path, b"data")
    assert uri1.to_uri_str() == uri2.to_uri_str()
    assert client.store_calls == 1  # second call served from cache

    file_storage.store_in_bucket(
        client, file_storage.key_for_project_digest("proj", "digestB"), b"x"
    )
    assert client.store_calls == 2  # a distinct key still reaches the backend

    # reset re-arms the backend write for an already-seen key.
    file_storage.reset_stored_key_cache()
    file_storage.store_in_bucket(client, path, b"data")
    assert client.store_calls == 3


class TestAzureStorage:
    """Tests for Azure Blob Storage implementation using mocks."""

    @pytest.fixture
    def azure_blob(self):
        """Fully mocked Azure Blob Storage client."""
        mock_service_client = mock.MagicMock()
        mock_container_client = mock.MagicMock()
        mock_blob_client = mock.MagicMock()

        mock_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client

        # In-memory storage for blobs
        blob_data = {}

        def mock_upload_blob(data, overwrite=False, **kwargs):
            blob_name = mock_blob_client.blob_name
            blob_data[blob_name] = data

        def mock_download_blob(**kwargs):
            blob_name = mock_blob_client.blob_name
            download = mock.MagicMock()
            download.readall.return_value = blob_data.get(blob_name, b"")
            return download

        # Track blob_name through get_blob_client calls
        def mock_get_blob_client(name):
            mock_blob_client.blob_name = name
            return mock_blob_client

        mock_container_client.get_blob_client.side_effect = mock_get_blob_client
        mock_blob_client.upload_blob.side_effect = mock_upload_blob
        mock_blob_client.download_blob.side_effect = mock_download_blob

        with mock.patch(
            "weave.trace_server.file_storage.BlobServiceClient",
            return_value=mock_service_client,
        ) as mock_cls:
            mock_cls.from_connection_string.return_value = mock_service_client
            yield mock_service_client

    @pytest.fixture
    def azure_storage_env(self):
        """Setup Azure storage environment."""
        with mock.patch.dict(
            os.environ,
            {
                "WF_FILE_STORAGE_AZURE_ACCESS_KEY": "fake-key",
                "WF_FILE_STORAGE_AZURE_ACCOUNT_URL": "http://fake-account.blob.core.windows.net",
                "WF_FILE_STORAGE_URI": f"az://fakeaccount/{TEST_BUCKET}",
                "WF_FILE_STORAGE_PROJECT_ALLOW_LIST": "c2hhd24vdGVzdC1wcm9qZWN0",
            },
        ):
            yield

    @pytest.mark.usefixtures("azure_storage_env")
    @pytest.mark.skipif(
        NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
    )
    def test_azure_storage(self, run_storage_test, azure_blob):
        """Test file storage using Azure Blob Storage."""
        res = run_storage_test()

        # Verify upload was called
        azure_blob.get_container_client.assert_called()
        container_client = azure_blob.get_container_client(TEST_BUCKET)
        project = "c2hhd24vdGVzdC1wcm9qZWN0"
        blob_client = container_client.get_blob_client(
            f"weave/projects/{project}/files/{res.digest}"
        )
        assert blob_client.download_blob().readall() == TEST_CONTENT

    @pytest.mark.usefixtures("azure_storage_env")
    @pytest.mark.skipif(
        NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
    )
    def test_azure_storage_does_not_overwrite_existing_blob(self, client: WeaveClient):
        """Azure store must not clobber an existing content-addressable blob.

        Mirrors `test_gcp_storage_skips_duplicate_write`. Content-addressable
        storage is a write-once contract: re-uploading at a known digest must
        be a no-op, not an overwrite. Otherwise any project with write scope
        can substitute content at a known URI.
        """
        blob_data: dict[str, bytes] = {}
        upload_calls: list[dict] = []

        mock_service_client = mock.MagicMock()
        mock_container_client = mock.MagicMock()
        mock_blob_client = mock.MagicMock()
        mock_service_client.get_container_client.return_value = mock_container_client

        def mock_get_blob_client(name):
            mock_blob_client.blob_name = name
            return mock_blob_client

        def mock_upload_blob(data, overwrite=False, **kwargs):
            blob_name = mock_blob_client.blob_name
            upload_calls.append({"name": blob_name, "overwrite": overwrite})
            # Azure semantics: overwrite=False on an existing blob raises.
            if blob_name in blob_data and not overwrite:
                raise ResourceExistsError("blob already exists")
            blob_data[blob_name] = data

        def mock_download_blob(**kwargs):
            blob_name = mock_blob_client.blob_name
            download = mock.MagicMock()
            download.readall.return_value = blob_data.get(blob_name, b"")
            return download

        mock_container_client.get_blob_client.side_effect = mock_get_blob_client
        mock_blob_client.upload_blob.side_effect = mock_upload_blob
        mock_blob_client.download_blob.side_effect = mock_download_blob

        original = b"original-content"

        with mock.patch(
            "weave.trace_server.file_storage.BlobServiceClient",
            return_value=mock_service_client,
        ) as mock_cls:
            mock_cls.from_connection_string.return_value = mock_service_client

            res1 = client.server.file_create(
                FileCreateReq(
                    project_id=client.project_id,
                    name="test.txt",
                    content=original,
                )
            )
            res2 = client.server.file_create(
                FileCreateReq(
                    project_id=client.project_id,
                    name="test.txt",
                    content=original,
                )
            )

            assert res1.digest == res2.digest
            assert upload_calls, "upload_blob was never invoked"
            assert all(call["overwrite"] is False for call in upload_calls), (
                f"upload_blob called with overwrite=True: {upload_calls}"
            )

            stored = blob_data[next(iter(blob_data))]
            assert stored == original

            file = client.server.file_content_read(
                FileContentReadReq(project_id=client.project_id, digest=res1.digest)
            )
            assert file.content == original


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
)
def test_support_for_variable_length_chunks(client: WeaveClient):
    """Test that the system supports variable length chunks.
    We don't actually want to change this often, but we need to make sure it works.
    """

    def create_and_read_file(content: bytes):
        res = client.server.file_create(
            FileCreateReq(
                project_id=client.project_id, name="test.txt", content=content
            )
        )
        assert res.digest is not None
        assert res.digest != ""

        file = client.server.file_content_read(
            FileContentReadReq(project_id=client.project_id, digest=res.digest)
        )
        assert file.content == content

        return res.digest

    base_chunk_size = 100000
    num_chunks = 3
    file_part = b"1234567890"
    large_file = file_part * (base_chunk_size * num_chunks // len(file_part))
    large_digest = create_and_read_file(large_file)

    #  Test increasing and decreasing chunk sizes
    for size in [
        base_chunk_size,
        2 * base_chunk_size,
        3 * base_chunk_size,
        4 * base_chunk_size,
        base_chunk_size,
        base_chunk_size // 2,
    ]:
        with mock.patch.object(
            clickhouse_trace_server_settings, "FILE_CHUNK_SIZE", size
        ):
            digest = create_and_read_file(large_file)
            assert digest == large_digest


@pytest.mark.disable_logging_error_check
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
)
def test_file_storage_retry_limit(client: WeaveClient):
    """Test that file storage operations retry exactly 3 times on storage failures."""
    attempt_count = 0

    def mock_upload_fail(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        # Simulate a 429 rate limit error
        from google.api_core import exceptions

        raise exceptions.TooManyRequests("Rate limit exceeded")

    with mock.patch.dict(
        os.environ,
        {
            "WF_FILE_STORAGE_GCP_CREDENTIALS_JSON_B64": base64.b64encode(
                b"""{
                "type": "service_account",
                "project_id": "test-project",
                "private_key_id": "test-key-id",
                "private_key": "test-key",
                "client_email": "test@test-project.iam.gserviceaccount.com",
                "client_id": "test-client-id",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }"""
            ).decode(),
            "WF_FILE_STORAGE_URI": f"gs://{TEST_BUCKET}",
            "WF_FILE_STORAGE_PROJECT_ALLOW_LIST": "*",
        },
    ):
        # Mock GCS client
        mock_storage_client = mock.MagicMock()
        mock_bucket = mock.MagicMock()
        mock_blob = mock.MagicMock()

        # Setup mock chain
        mock_storage_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.upload_from_string.side_effect = mock_upload_fail

        with (
            mock.patch("google.cloud.storage.Client", return_value=mock_storage_client),
            mock.patch(
                "google.oauth2.service_account.Credentials.from_service_account_info"
            ),
        ):
            # GCS should fail after 3 attempts, then fall back to database storage
            result = client.server.file_create(
                FileCreateReq(
                    project_id=client.project_id,
                    name="test.txt",
                    content=TEST_CONTENT,
                )
            )
            # Should succeed via database fallback
            assert result.digest is not None

        # Verify GCS was attempted exactly 3 times before fallback
        assert attempt_count == 3, f"Expected 3 GCS attempts, got {attempt_count}"


# ---------------------------------------------------------------------------
# Parallel bucket-upload fan-out during call_batch
# ---------------------------------------------------------------------------
#
# These drive the trace server's bucket-storage path with the shared `gcs`
# fixture (mocked at `google.cloud.storage.Client`). Multiple `file_create`
# calls inside one `call_batch()` context should stage and then fan out to
# GCS in parallel on context exit.


def _unique_payload(unique: str, size: int) -> bytes:
    """Build a deterministic, unique payload of the requested size."""
    body = (unique + "_" + ("x" * size)).encode()
    return body


@pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials")
@pytest.mark.disable_logging_error_check
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
)
def test_call_batch_uploads_files_to_bucket_in_parallel(client: WeaveClient, gcs):
    """Multiple file_create calls inside one call_batch fan out to GCS in
    parallel: concurrent uploads happen, identical content within the batch
    collapses to one upload, and every stored object lands under the
    expected project prefix.
    """
    # 4 unique blobs + 2 duplicates of the first => 4 GCS uploads after dedup.
    # Barrier makes the peak deterministic so it can't flake under CI scheduler
    # jitter (each upload blocks until all 4 are simultaneously in-flight).
    gcs.state.expected_concurrency = 4
    payload_size = 50_000
    payloads = [
        _unique_payload("alpha", payload_size),
        _unique_payload("beta", payload_size),
        _unique_payload("gamma", payload_size),
        _unique_payload("delta", payload_size),
        _unique_payload("alpha", payload_size),  # dup
        _unique_payload("alpha", payload_size),  # dup
    ]
    server = client.server

    with server.call_batch():
        for i, content in enumerate(payloads):
            server.file_create(
                FileCreateReq(
                    project_id=client.project_id, name=f"f{i}.bin", content=content
                )
            )

    # Pool defaults to 8 workers, so all 4 unique uploads run concurrently;
    # the upload barrier guarantees the peak reaches 4.
    assert gcs.state.concurrent_peak == 4, (
        f"expected 4 concurrent uploads, peak={gcs.state.concurrent_peak}"
    )

    # Dedup: 4 unique blobs => 4 GCS uploads, not 6.
    assert gcs.state.upload_count == 4
    project_b64 = base64.b64encode(client.project_id.encode()).decode()
    expected_prefix = f"weave/projects/{project_b64}/files/"
    assert all(k.startswith(expected_prefix) for k in gcs.state.blob_data)


@pytest.fixture
def no_server_cache(monkeypatch: pytest.MonkeyPatch):
    """Disable the client-side file_create cache.

    It memoizes file_create by (project, digest) and would mask the server-side
    cross-pod pre-check under test (the prod trace server has no such client
    cache). With it on, a repeat file_create never reaches ClickHouse.
    """
    monkeypatch.setattr(
        "weave.trace_server_bindings.caching_middleware_trace_server.use_server_cache",
        lambda: False,
    )


@pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials", "no_server_cache")
@pytest.mark.disable_logging_error_check
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
)
def test_cross_pod_precheck_skips_redundant_bucket_upload(client: WeaveClient, gcs):
    """A digest already recorded in the shared `files` table is not re-uploaded
    even after the per-pod stored-key cache is cleared (simulating a second
    pod). Genuinely new content in the same later batch still uploads, and both
    digests read back byte-for-byte.
    """
    server = client.server
    shared = _unique_payload("shared", 50_000)
    shared_digest = compute_file_digest(shared)

    with server.call_batch():
        server.file_create(
            FileCreateReq(project_id=client.project_id, name="a.bin", content=shared)
        )
    assert gcs.state.upload_attempts == 1
    assert gcs.state.upload_count == 1

    # Second pod: same shared ClickHouse, cold per-pod LRU. The cross-pod
    # pre-check must recognize `shared` is already stored and skip its upload.
    file_storage.reset_stored_key_cache()

    fresh = _unique_payload("fresh", 50_000)
    fresh_digest = compute_file_digest(fresh)
    with server.call_batch():
        server.file_create(
            FileCreateReq(project_id=client.project_id, name="a.bin", content=shared)
        )
        server.file_create(
            FileCreateReq(project_id=client.project_id, name="b.bin", content=fresh)
        )

    # Only the new payload is attempted; the redundant 412 write is avoided.
    assert gcs.state.upload_attempts == 2
    assert gcs.state.upload_count == 2

    for digest, expected in ((shared_digest, shared), (fresh_digest, fresh)):
        read = server.file_content_read(
            FileContentReadReq(project_id=client.project_id, digest=digest)
        )
        assert read.content == expected


@pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials", "no_server_cache")
@pytest.mark.disable_logging_error_check
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
)
def test_precheck_skips_bucket_upload_when_only_inline_row_exists(
    client: WeaveClient, gcs
):
    """A digest first stored as inline-CH chunks (storage disabled) is still
    recognized by the pre-check on a later bucket-enabled write: the row means
    the content is readable, so no bucket upload is attempted and the read path
    serves the inline chunks.
    """
    server = client.server
    payload = _unique_payload("inline", 50_000)
    digest = compute_file_digest(payload)

    # Storage disabled for this project => inline CH chunks, no bucket URI row.
    with mock.patch.dict(
        os.environ, {"WF_FILE_STORAGE_PROJECT_ALLOW_LIST": "some-other-project"}
    ):
        with server.call_batch():
            server.file_create(
                FileCreateReq(
                    project_id=client.project_id, name="i.bin", content=payload
                )
            )
    assert gcs.state.upload_attempts == 0

    file_storage.reset_stored_key_cache()

    # Storage now enabled: the pre-check sees the inline row and skips the upload.
    with server.call_batch():
        server.file_create(
            FileCreateReq(project_id=client.project_id, name="i.bin", content=payload)
        )
    assert gcs.state.upload_attempts == 0

    read = server.file_content_read(
        FileContentReadReq(project_id=client.project_id, digest=digest)
    )
    assert read.content == payload


@pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials", "no_server_cache")
@pytest.mark.disable_logging_error_check
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
)
def test_precheck_failure_falls_back_to_upload(
    client: WeaveClient, gcs, monkeypatch: pytest.MonkeyPatch
):
    """If the existence pre-check query throws, the write proceeds unconditionally
    (backstopped by GCS if_generation_match=0) rather than failing the batch.
    """
    server = client.server
    payload = _unique_payload("boom", 50_000)
    digest = compute_file_digest(payload)

    with server.call_batch():
        server.file_create(
            FileCreateReq(project_id=client.project_id, name="c.bin", content=payload)
        )
    assert gcs.state.upload_attempts == 1
    file_storage.reset_stored_key_cache()

    def _raise(*args: object, **kwargs: object) -> str:
        raise RuntimeError("pre-check boom")

    monkeypatch.setattr(
        clickhouse_trace_server_batched,
        "make_files_digests_existence_query",
        _raise,
    )
    with server.call_batch():
        server.file_create(
            FileCreateReq(project_id=client.project_id, name="c.bin", content=payload)
        )
    # No dedup => the upload is attempted again (and 412s harmlessly at GCS).
    assert gcs.state.upload_attempts == 2

    read = server.file_content_read(
        FileContentReadReq(project_id=client.project_id, digest=digest)
    )
    assert read.content == payload


@pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials")
@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize(
    "fail_payload_size",
    [
        # Single inline-CH chunk fallback (< FILE_CHUNK_SIZE = 100_000).
        50_000,
        # Multi-chunk fallback: 250KB content splits into 3 inline-CH chunks,
        # exercising the chunk_index / n_chunks reassembly on read.
        250_000,
    ],
    ids=["single-chunk-fallback", "multi-chunk-fallback"],
)
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
)
def test_call_batch_falls_back_to_clickhouse_on_per_file_bucket_failure(
    client: WeaveClient, gcs, fail_payload_size: int
):
    """When one upload in a batch hits a non-retriable GCS error, the server
    should fall back to inline ClickHouse chunks for that file only; other
    uploads in the same batch keep their bucket URIs, and the whole batch
    still completes. We verify by reading the failed file back through the
    server's read path -- it must reassemble bit-for-bit from CH chunks for
    both single-chunk and multi-chunk payloads.
    """
    server = client.server
    project_b64 = base64.b64encode(client.project_id.encode()).decode()

    # Compute the digest directly so the only `files` row at
    # (project, digest, chunk_index=0) comes from the in-batch fallback.
    # Doing a probe file_create first would write a bucket-URI row with the
    # same primary key, and the read query's row_number() pick across two
    # rows at the same key is non-deterministic.
    fail_payload = _unique_payload("fail", fail_payload_size)
    fail_digest = compute_file_digest(fail_payload)
    fail_key = f"weave/projects/{project_b64}/files/{fail_digest}"
    gcs.state.fail_paths.add(fail_key)

    ok_payload = _unique_payload("ok", 50_000)
    with server.call_batch():
        server.file_create(
            FileCreateReq(
                project_id=client.project_id, name="ok.bin", content=ok_payload
            )
        )
        server.file_create(
            FileCreateReq(
                project_id=client.project_id, name="fail.bin", content=fail_payload
            )
        )

    # The successful upload made it through.
    assert any(
        k.startswith(f"weave/projects/{project_b64}/files/")
        for k in gcs.state.blob_data
    )
    # The failing one is not present in the bucket.
    assert fail_key not in gcs.state.blob_data
    # ...but is readable via the server, because it landed as inline chunks.
    # For multi-chunk payloads, byte-equality here implicitly verifies that
    # all chunk_index rows reassembled correctly.
    fallback_read = server.file_content_read(
        FileContentReadReq(project_id=client.project_id, digest=fail_digest)
    )
    assert fallback_read.content == fail_payload


def _data_uri(mimetype: str, size: int) -> str:
    """Build a distinct data URI whose decoded body exceeds AUTO_CONVERSION_MIN_SIZE."""
    raw = (mimetype + "_" + "x" * size).encode()
    return f"data:{mimetype};base64," + base64.b64encode(raw).decode()


@pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials")
@pytest.mark.disable_logging_error_check
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
)
@pytest.mark.parametrize("version", ["v1", "v2"])
def test_call_start_offloads_attachments_to_bucket_in_parallel(
    client: WeaveClient, gcs, version: str
):
    """Eager call/start (v1 and v2) with many inline data-URI inputs fans the
    auto-extracted attachment uploads across the bucket pool instead of one
    serial PUT each. The barrier of 2 makes the parallel floor deterministic;
    the pre-fix serial path only ever had one upload in flight.
    """
    gcs.state.expected_concurrency = 2
    # Distinct mimetype+size keeps every content and metadata digest unique, so
    # dedup can't collapse the upload set below the barrier width.
    inputs = {
        "png": _data_uri("image/png", 20_000),
        "jpeg": _data_uri("image/jpeg", 30_000),
        "bin": _data_uri("application/octet-stream", 40_000),
    }
    res = _start_call(
        client.server,
        version,
        StartedCallSchemaForInsert(
            project_id=client.project_id,
            id=str(uuid.uuid4()),
            trace_id=str(uuid.uuid4()),
            op_name="test_op",
            started_at=datetime.datetime.now(datetime.timezone.utc),
            attributes={},
            inputs=inputs,
        ),
    )

    assert res.id
    assert res.trace_id
    assert gcs.state.concurrent_peak >= 2, (
        f"expected parallel attachment uploads, peak={gcs.state.concurrent_peak}"
    )
    project_b64 = base64.b64encode(client.project_id.encode()).decode()
    expected_prefix = f"weave/projects/{project_b64}/files/"
    assert gcs.state.blob_data
    assert all(k.startswith(expected_prefix) for k in gcs.state.blob_data)


@pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials")
@pytest.mark.disable_logging_error_check
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: bucket file storage machinery"
)
@pytest.mark.parametrize("version", ["v1", "v2"])
def test_call_end_offloads_attachments_to_bucket_in_parallel(
    client: WeaveClient, gcs, version: str
):
    """Eager call/end (v1 and v2) fans its output-attachment uploads across the
    bucket pool too (and, for calls_complete projects, finishes them before the
    end UPDATE references them). Barrier of 2 pins the parallel floor; the
    pre-fix serial path peaked at 1.
    """
    call_id = str(uuid.uuid4())
    started_at = datetime.datetime.now(datetime.timezone.utc)
    _start_call(
        client.server,
        version,
        StartedCallSchemaForInsert(
            project_id=client.project_id,
            id=call_id,
            trace_id=str(uuid.uuid4()),
            op_name="test_op",
            started_at=started_at,
            attributes={},
            inputs={},
        ),
    )

    # Set the barrier only now so it gates the end's uploads, not the empty start.
    gcs.state.expected_concurrency = 2
    output = {
        "png": _data_uri("image/png", 20_000),
        "jpeg": _data_uri("image/jpeg", 30_000),
        "bin": _data_uri("application/octet-stream", 40_000),
    }
    _end_call(
        client.server,
        version,
        project_id=client.project_id,
        call_id=call_id,
        started_at=started_at,
        ended_at=started_at + datetime.timedelta(seconds=1),
        output=output,
    )

    assert gcs.state.concurrent_peak >= 2, (
        f"expected parallel attachment uploads, peak={gcs.state.concurrent_peak}"
    )
    project_b64 = base64.b64encode(client.project_id.encode()).decode()
    expected_prefix = f"weave/projects/{project_b64}/files/"
    assert gcs.state.blob_data
    assert all(k.startswith(expected_prefix) for k in gcs.state.blob_data)


def _start_call(
    server: TraceServerClientInterface,
    version: str,
    start: StartedCallSchemaForInsert,
) -> CallStartRes | CallStartV2Res:
    """Dispatch a single eager call/start to the v1 or v2 write path."""
    if version == "v1":
        return server.call_start(CallStartReq(start=start))
    if version == "v2":
        return server.call_start_v2(CallStartV2Req(start=start))
    raise ValueError(f"unknown call version: {version}")


def _end_call(
    server: TraceServerClientInterface,
    version: str,
    *,
    project_id: str,
    call_id: str,
    started_at: datetime.datetime,
    ended_at: datetime.datetime,
    output: dict[str, str],
) -> None:
    """Dispatch a single eager call/end to the v1 or v2 write path."""
    if version == "v1":
        server.call_end(
            CallEndReq(
                end=EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    ended_at=ended_at,
                    output=output,
                    summary={},
                )
            )
        )
    elif version == "v2":
        server.call_end_v2(
            CallEndV2Req(
                end=EndedCallSchemaForInsertWithStartedAt(
                    project_id=project_id,
                    id=call_id,
                    started_at=started_at,
                    ended_at=ended_at,
                    output=output,
                    summary={},
                )
            )
        )
    else:
        raise ValueError(f"unknown call version: {version}")
