"""Tests for file storage implementations (S3, GCS, Azure Blob).

This module tests the different cloud storage backends used for file storage.
Each storage implementation is tested with similar patterns but with their
specific setup requirements.
"""

import base64
import os
from unittest import mock

import boto3
import pytest
from azure.storage.blob import BlobServiceClient
from google.api_core import exceptions
from google.auth.credentials import AnonymousCredentials
from moto import mock_aws

from tests.trace.util import client_is_sqlite
from weave.trace.weave_client import WeaveClient
from weave.trace_server.clickhouse_query_layer import (
    settings as clickhouse_trace_server_settings,
)
from weave.trace_server.trace_server_interface import FileContentReadReq, FileCreateReq

# Test Data Constants
TEST_CONTENT = b"Hello, world!"
TEST_BUCKET = "test-bucket"

# Azure Constants
AZURITE_ACCOUNT = "devstoreaccount1"
AZURITE_KEY = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
AZURITE_URL = f"http://127.0.0.1:10000/{AZURITE_ACCOUNT}"


@pytest.fixture
def run_storage_test(client: WeaveClient):
    """Shared test runner for all storage implementations."""

    def _run_test():
        # Create a new trace
        res = client.server.file_create(
            FileCreateReq(
                project_id=client._project_id(),
                name="test.txt",
                content=TEST_CONTENT,
            )
        )
        assert res.digest is not None
        assert res.digest != ""

        # Get the file
        file = client.server.file_content_read(
            FileContentReadReq(project_id=client._project_id(), digest=res.digest)
        )
        assert file.content == TEST_CONTENT
        return res

    if client_is_sqlite(client):
        pytest.skip("Not implemented in SQLite")
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
                    project_id=client._project_id(),
                    name="test.txt",
                    content=large_file,
                )
            )
            assert res.digest is not None
            assert res.digest != ""

            # Get the file
            file = client.server.file_content_read(
                FileContentReadReq(project_id=client._project_id(), digest=res.digest)
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

        if client_is_sqlite(client):
            pytest.skip("Not implemented in SQLite")

        _run_test()


class TestGCSStorage:
    """Tests for Google Cloud Storage implementation."""

    @pytest.fixture
    def mock_gcp_credentials(self):
        """Mock GCP credentials to prevent authentication."""
        with mock.patch(
            "google.oauth2.service_account.Credentials.from_service_account_info"
        ) as mock_creds:
            mock_creds.return_value = AnonymousCredentials()
            yield

    @pytest.fixture
    def gcs(self):
        """Google Cloud Storage mock using method patches."""
        mock_storage_client = mock.MagicMock()
        mock_bucket = mock.MagicMock()
        mock_blob = mock.MagicMock()

        # Setup mock chain
        mock_storage_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # In-memory storage for all blobs
        blob_data = {}

        def mock_upload_from_string(
            data, timeout=None, if_generation_match=None, **kwargs
        ):
            # Get the blob name from the mock's name attribute
            blob_name = mock_blob.name
            # Simulate GCS if_generation_match=0 behavior (only write if not exists)
            if if_generation_match == 0 and blob_name in blob_data:
                raise exceptions.PreconditionFailed("Object already exists")
            blob_data[blob_name] = data

        def mock_download_as_bytes(timeout=None, **kwargs):
            # Get the blob name from the mock's name attribute
            blob_name = mock_blob.name
            return blob_data.get(blob_name, b"")

        mock_blob.upload_from_string.side_effect = mock_upload_from_string
        mock_blob.download_as_bytes.side_effect = mock_download_as_bytes

        with mock.patch(
            "google.cloud.storage.Client", return_value=mock_storage_client
        ):
            yield mock_storage_client

    @pytest.fixture
    def gcp_storage_env(self):
        """Setup GCP storage environment."""
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
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test@test-project.iam.gserviceaccount.com"
                }"""
                ).decode(),
                "WF_FILE_STORAGE_URI": f"gs://{TEST_BUCKET}",
                "WF_FILE_STORAGE_PROJECT_ALLOW_LIST": "c2hhd24vdGVzdC1wcm9qZWN0",
            },
        ):
            yield

    @pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials")
    def test_gcp_storage(self, run_storage_test, gcs):
        """Test file storage using Google Cloud Storage."""
        res = run_storage_test()

        # Verify the object exists in GCS
        bucket = gcs.bucket(TEST_BUCKET)
        blob = bucket.blob(res.digest)
        assert blob.download_as_bytes() == TEST_CONTENT

    @pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials")
    def test_gcp_storage_skips_duplicate_write(self, client: WeaveClient):
        """Test that writing the same content twice skips the second write.

        This verifies the if_generation_match=0 conditional write works correctly
        to prevent GCS rate limiting when multiple pods write the same object.
        """
        if client_is_sqlite(client):
            pytest.skip("Not implemented in SQLite")

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
                    project_id=client._project_id(),
                    name="test.txt",
                    content=TEST_CONTENT,
                )
            )
            assert upload_count == 1

            # Second write with same content should be skipped (no error, no upload)
            res2 = client.server.file_create(
                FileCreateReq(
                    project_id=client._project_id(),
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
                FileContentReadReq(project_id=client._project_id(), digest=res1.digest)
            )
            assert file.content == TEST_CONTENT


class TestAzureStorage:
    """Tests for Azure Blob Storage implementation."""

    @pytest.fixture
    def azure_blob(self):
        """Azure Blob Storage using Azurite emulator."""
        conn_str = (
            f"DefaultEndpointsProtocol=http;"
            f"AccountName={AZURITE_ACCOUNT};"
            f"AccountKey={AZURITE_KEY};"
            f"BlobEndpoint={AZURITE_URL};"
        )

        # Create the Azurite client
        azurite_client = BlobServiceClient.from_connection_string(conn_str)

        # Mock the client creation to always return our Azurite client
        with mock.patch("azure.storage.blob.BlobServiceClient") as mock_client:
            mock_client.from_connection_string.return_value = azurite_client

            # Create test container
            try:
                azurite_client.create_container(TEST_BUCKET)
            except Exception:
                # Container might already exist
                pass

            yield azurite_client

    @pytest.fixture
    def azure_storage_env(self):
        """Setup Azure storage environment."""
        with mock.patch.dict(
            os.environ,
            {
                "WF_FILE_STORAGE_AZURE_ACCESS_KEY": AZURITE_KEY,
                "WF_FILE_STORAGE_AZURE_ACCOUNT_URL": AZURITE_URL,
                "WF_FILE_STORAGE_URI": f"az://{AZURITE_ACCOUNT}/{TEST_BUCKET}",
                "WF_FILE_STORAGE_PROJECT_ALLOW_LIST": "c2hhd24vdGVzdC1wcm9qZWN0",
            },
        ):
            yield

    @pytest.mark.flaky(reruns=3, reruns_delay=2)
    @pytest.mark.usefixtures("azure_storage_env")
    def test_azure_storage(self, run_storage_test, azure_blob):
        """Test file storage using Azure Blob Storage."""
        res = run_storage_test()

        # Verify the object exists in Azure
        container_client = azure_blob.get_container_client(TEST_BUCKET)
        # Hard-coding project for ease. If we change how CI generates projects, this is ok to change
        project = "c2hhd24vdGVzdC1wcm9qZWN0"
        blob_client = container_client.get_blob_client(
            f"weave/projects/{project}/files/{res.digest}"
        )
        assert blob_client.download_blob().readall() == TEST_CONTENT


def test_support_for_variable_length_chunks(client: WeaveClient):
    """Test that the system supports variable length chunks.
    We don't actually want to change this often, but we need to make sure it works.
    """
    if client_is_sqlite(client):
        pytest.skip("Not implemented in SQLite")

    def create_and_read_file(content: bytes):
        res = client.server.file_create(
            FileCreateReq(
                project_id=client._project_id(), name="test.txt", content=content
            )
        )
        assert res.digest is not None
        assert res.digest != ""

        file = client.server.file_content_read(
            FileContentReadReq(project_id=client._project_id(), digest=res.digest)
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
def test_file_storage_retry_limit(client: WeaveClient):
    """Test that file storage operations retry exactly 3 times on storage failures."""
    if client_is_sqlite(client):
        pytest.skip("Not implemented in SQLite")

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
                    project_id=client._project_id(),
                    name="test.txt",
                    content=TEST_CONTENT,
                )
            )
            # Should succeed via database fallback
            assert result.digest is not None

        # Verify GCS was attempted exactly 3 times before fallback
        assert attempt_count == 3, f"Expected 3 GCS attempts, got {attempt_count}"
