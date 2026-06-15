"""Tests for file storage implementations (S3, GCS, Azure Blob).

Each cloud backend is tested with a similar store-then-read pattern, plus the
write-once (no-overwrite) contract and the call_batch fan-out path. Only the
cloud SDKs are mocked (external services); the trace server runs for real.
"""

import base64
import os
from unittest import mock

import boto3
import pytest
from azure.core.exceptions import ResourceExistsError
from google.api_core import exceptions
from moto import mock_aws

from weave.shared.digest import compute_file_digest
from weave.trace.weave_client import WeaveClient
from weave.trace_server import clickhouse_trace_server_settings
from weave.trace_server.trace_server_interface import FileContentReadReq, FileCreateReq

TEST_CONTENT = b"Hello, world!"
TEST_BUCKET = "test-bucket"


@pytest.mark.usefixtures("aws_storage_env")
def test_aws_storage(run_storage_test, s3):
    """File storage round-trips through AWS S3 and the object lands in the bucket."""
    res = run_storage_test()

    response = s3.list_objects_v2(Bucket=TEST_BUCKET)
    assert "Contents" in response
    assert len(response["Contents"]) == 1

    obj = response["Contents"][0]
    obj_response = s3.get_object(Bucket=TEST_BUCKET, Key=obj["Key"])
    assert obj_response["Body"].read() == TEST_CONTENT


def test_large_file_migration(s3, client: WeaveClient):
    """Large files read back identically with storage disabled, enabled, then
    disabled again, yielding a stable digest across the migration."""
    chunk_size = 100000
    num_chunks = 3
    file_part = b"1234567890"
    large_file = file_part * (chunk_size * num_chunks // len(file_part))

    def _run_single_test():
        res = client.server.file_create(
            FileCreateReq(
                project_id=client.project_id, name="test.txt", content=large_file
            )
        )
        assert res.digest is not None
        assert res.digest != ""
        file = client.server.file_content_read(
            FileContentReadReq(project_id=client.project_id, digest=res.digest)
        )
        assert file.content == large_file
        return res.digest

    d1 = _run_single_test()
    with mock.patch.dict(
        os.environ,
        {
            "WF_FILE_STORAGE_AWS_ACCESS_KEY_ID": "test-key",
            "WF_FILE_STORAGE_AWS_SECRET_ACCESS_KEY": "test-secret",
            "WF_FILE_STORAGE_URI": f"s3://{TEST_BUCKET}",
            "WF_FILE_STORAGE_PROJECT_ALLOW_LIST": "c2hhd24vdGVzdC1wcm9qZWN0",
        },
    ):
        d2 = _run_single_test()
    d3 = _run_single_test()
    assert d1 == d2 == d3


@pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials")
def test_gcp_storage(run_storage_test, gcs, client: WeaveClient):
    """File storage round-trips through Google Cloud Storage under the b64 project key."""
    res = run_storage_test()

    project_b64 = base64.b64encode(client.project_id.encode()).decode()
    expected_key = f"weave/projects/{project_b64}/files/{res.digest}"
    assert gcs.state.blob_data[expected_key] == TEST_CONTENT
    assert gcs.state.upload_count == 1


@pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials")
def test_gcp_storage_skips_duplicate_write(client: WeaveClient):
    """The if_generation_match=0 conditional write skips a second write of identical
    content, returning the same digest and remaining readable."""
    upload_count = 0
    blob_data = {}

    def mock_upload_from_string(data, timeout=None, if_generation_match=None, **kwargs):
        nonlocal upload_count
        blob_name = mock_blob.name
        if if_generation_match == 0 and blob_name in blob_data:
            raise exceptions.PreconditionFailed("Object already exists")
        upload_count += 1
        blob_data[blob_name] = data

    def mock_download_as_bytes(timeout=None, **kwargs):
        return blob_data.get(mock_blob.name, b"")

    mock_storage_client = mock.MagicMock()
    mock_bucket = mock.MagicMock()
    mock_blob = mock.MagicMock()
    mock_storage_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_blob.upload_from_string.side_effect = mock_upload_from_string
    mock_blob.download_as_bytes.side_effect = mock_download_as_bytes

    with mock.patch("google.cloud.storage.Client", return_value=mock_storage_client):
        res1 = client.server.file_create(
            FileCreateReq(
                project_id=client.project_id, name="test.txt", content=TEST_CONTENT
            )
        )
        assert upload_count == 1
        res2 = client.server.file_create(
            FileCreateReq(
                project_id=client.project_id, name="test.txt", content=TEST_CONTENT
            )
        )
        assert upload_count == 1
        assert res1.digest == res2.digest

        file = client.server.file_content_read(
            FileContentReadReq(project_id=client.project_id, digest=res1.digest)
        )
        assert file.content == TEST_CONTENT


@pytest.mark.usefixtures("azure_storage_env")
def test_azure_storage(run_storage_test, azure_blob):
    """File storage round-trips through Azure Blob Storage under the b64 project key."""
    res = run_storage_test()

    azure_blob.get_container_client.assert_called()
    container_client = azure_blob.get_container_client(TEST_BUCKET)
    project = "c2hhd24vdGVzdC1wcm9qZWN0"
    blob_client = container_client.get_blob_client(
        f"weave/projects/{project}/files/{res.digest}"
    )
    assert blob_client.download_blob().readall() == TEST_CONTENT


@pytest.mark.usefixtures("azure_storage_env")
def test_azure_storage_does_not_overwrite_existing_blob(client: WeaveClient):
    """Content-addressable storage is write-once: re-uploading at a known digest is a
    no-op (overwrite=False), so a write-scoped project cannot substitute content."""
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
        if blob_name in blob_data and not overwrite:
            raise ResourceExistsError("blob already exists")
        blob_data[blob_name] = data

    def mock_download_blob(**kwargs):
        download = mock.MagicMock()
        download.readall.return_value = blob_data.get(mock_blob_client.blob_name, b"")
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
                project_id=client.project_id, name="test.txt", content=original
            )
        )
        res2 = client.server.file_create(
            FileCreateReq(
                project_id=client.project_id, name="test.txt", content=original
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


def test_support_for_variable_length_chunks(client: WeaveClient):
    """File read-back is stable across a range of increasing and decreasing chunk sizes."""

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
            assert create_and_read_file(large_file) == large_digest


@pytest.mark.disable_logging_error_check
def test_file_storage_retry_limit(client: WeaveClient):
    """File storage retries a 429 exactly 3 times, then falls back to database storage."""
    attempt_count = 0

    def mock_upload_fail(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
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
        mock_storage_client = mock.MagicMock()
        mock_bucket = mock.MagicMock()
        mock_blob = mock.MagicMock()
        mock_storage_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.upload_from_string.side_effect = mock_upload_fail

        with (
            mock.patch(
                "google.cloud.storage.Client", return_value=mock_storage_client
            ),
            mock.patch(
                "google.oauth2.service_account.Credentials.from_service_account_info"
            ),
        ):
            result = client.server.file_create(
                FileCreateReq(
                    project_id=client.project_id, name="test.txt", content=TEST_CONTENT
                )
            )
            assert result.digest is not None

        assert attempt_count == 3, f"Expected 3 GCS attempts, got {attempt_count}"


@pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials")
@pytest.mark.disable_logging_error_check
def test_call_batch_uploads_files_to_bucket_in_parallel(client: WeaveClient, gcs):
    """file_create calls inside one call_batch fan out to GCS in parallel, identical
    content collapses to one upload, and every object lands under the project prefix."""
    gcs.state.delay = 0.1
    payload_size = 50_000
    payloads = [
        _unique_payload("alpha", payload_size),
        _unique_payload("beta", payload_size),
        _unique_payload("gamma", payload_size),
        _unique_payload("delta", payload_size),
        _unique_payload("alpha", payload_size),
        _unique_payload("alpha", payload_size),
    ]
    server = client.server

    with server.call_batch():
        for i, content in enumerate(payloads):
            server.file_create(
                FileCreateReq(
                    project_id=client.project_id, name=f"f{i}.bin", content=content
                )
            )

    # concurrent_peak is the load-bearing parallelism signal; wall-time assertions
    # would flake on contended CI runners.
    assert gcs.state.concurrent_peak >= 4, (
        f"expected 4 concurrent uploads, peak={gcs.state.concurrent_peak}"
    )
    assert gcs.state.upload_count == 4
    project_b64 = base64.b64encode(client.project_id.encode()).decode()
    expected_prefix = f"weave/projects/{project_b64}/files/"
    assert all(k.startswith(expected_prefix) for k in gcs.state.blob_data)


@pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials")
@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize(
    "fail_payload_size",
    [50_000, 250_000],
    ids=["single-chunk-fallback", "multi-chunk-fallback"],
)
def test_call_batch_falls_back_to_clickhouse_on_per_file_bucket_failure(
    client: WeaveClient, gcs, fail_payload_size: int
):
    """When one upload in a batch hits a non-retriable GCS error, that file falls back
    to inline ClickHouse chunks while the others keep bucket URIs; the failed file
    reassembles bit-for-bit on read for single- and multi-chunk payloads."""
    server = client.server
    project_b64 = base64.b64encode(client.project_id.encode()).decode()

    # Compute the digest directly so the only `files` row at chunk_index=0 comes
    # from the in-batch fallback (a probe file_create would race the read query).
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

    assert any(
        k.startswith(f"weave/projects/{project_b64}/files/")
        for k in gcs.state.blob_data
    )
    assert fail_key not in gcs.state.blob_data
    fallback_read = server.file_content_read(
        FileContentReadReq(project_id=client.project_id, digest=fail_digest)
    )
    assert fallback_read.content == fail_payload


@pytest.fixture
def run_storage_test(client: WeaveClient):
    """Store TEST_CONTENT and read it back, asserting the digest round-trips."""

    def _run_test():
        res = client.server.file_create(
            FileCreateReq(
                project_id=client.project_id, name="test.txt", content=TEST_CONTENT
            )
        )
        assert res.digest is not None
        assert res.digest != ""
        file = client.server.file_content_read(
            FileContentReadReq(project_id=client.project_id, digest=res.digest)
        )
        assert file.content == TEST_CONTENT
        return res

    return _run_test


@pytest.fixture
def s3():
    """Moto S3 mock implementing the S3 API with TEST_BUCKET created."""
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
def aws_storage_env():
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


@pytest.fixture
def azure_blob():
    """Fully mocked Azure Blob Storage client backed by an in-memory dict."""
    mock_service_client = mock.MagicMock()
    mock_container_client = mock.MagicMock()
    mock_blob_client = mock.MagicMock()
    mock_service_client.get_container_client.return_value = mock_container_client
    mock_container_client.get_blob_client.return_value = mock_blob_client

    blob_data = {}

    def mock_upload_blob(data, overwrite=False, **kwargs):
        blob_data[mock_blob_client.blob_name] = data

    def mock_download_blob(**kwargs):
        download = mock.MagicMock()
        download.readall.return_value = blob_data.get(mock_blob_client.blob_name, b"")
        return download

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
def azure_storage_env():
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


def _unique_payload(unique: str, size: int) -> bytes:
    """Build a deterministic, unique payload of the requested size."""
    return (unique + "_" + ("x" * size)).encode()
