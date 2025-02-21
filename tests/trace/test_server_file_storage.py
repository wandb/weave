import os
from unittest import mock

import boto3
import pytest
from azure.storage.blob import BlobServiceClient
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth.credentials import AnonymousCredentials
from moto import mock_aws

from tests.trace.util import client_is_sqlite
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import FileContentReadReq, FileCreateReq


def generate_test_private_key():
    """Generate a valid RSA private key for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    return private_key_bytes.decode('utf-8')


@pytest.fixture
def s3():
    """Moto S3 mock that actually implements the S3 API"""
    with mock_aws():
        s3_client = boto3.client(
            "s3",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="us-east-1",
        )
        # Create the test bucket
        s3_client.create_bucket(Bucket="test-bucket")
        yield s3_client


@pytest.fixture
def mock_gcp_credentials():
    """Mock GCP credentials to prevent any actual authentication."""
    with mock.patch('google.oauth2.service_account.Credentials.from_service_account_info') as mock_creds:
        # Create a mock credentials object that won't try to authenticate
        mock_creds.return_value = AnonymousCredentials()
        yield


@pytest.fixture
def gcs():
    """Google Cloud Storage mock using method patches"""
    # Create a mock storage client
    mock_storage_client = mock.MagicMock()
    mock_bucket = mock.MagicMock()
    mock_blob = mock.MagicMock()

    # Setup the mock chain
    mock_storage_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_blob.download_as_bytes.return_value = b"Hello, world!"

    # Store uploaded data for verification
    uploaded_data = {}
    def mock_upload(data, timeout=None):
        uploaded_data['content'] = data
    mock_blob.upload_from_string.side_effect = mock_upload

    with mock.patch('google.cloud.storage.Client', return_value=mock_storage_client):
        yield mock_storage_client


@pytest.fixture
def azure_blob():
    """Azure Blob Storage using Azurite emulator"""
    conn_str = (
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
        "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
        "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
    )
    client = BlobServiceClient.from_connection_string(conn_str)

    # Create test container
    try:
        client.create_container("test-bucket")
    except Exception:
        # Container might already exist in Azurite
        pass

    yield client


@pytest.fixture
def aws_storage_env():
    """Setup AWS storage environment"""
    with mock.patch.dict(
        os.environ,
        {
            "WF_FILE_STORAGE_BUCKET_AWS_ACCESS_KEY_ID": "test-key",
            "WF_FILE_STORAGE_BUCKET_AWS_SECRET_ACCESS_KEY": "test-secret",
            "WF_FILE_STORAGE_URI": "s3://test-bucket",
        },
    ):
        yield


@pytest.fixture
def gcp_storage_env():
    """Setup GCP storage environment"""
    with mock.patch.dict(
        os.environ,
        {
            "WF_FILE_STORAGE_BUCKET_GCP_CREDENTIALS_JSON": """{
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
            }""",
            "WF_FILE_STORAGE_URI": "gcs://test-bucket",
        },
    ):
        yield


@pytest.fixture
def azure_storage_env():
    """Setup Azure storage environment"""
    with mock.patch.dict(
        os.environ,
        {
            "WF_FILE_STORAGE_BUCKET_AZURE_CREDENTIAL_B64": "1234567890",
            "WF_FILE_STORAGE_URI": "az://test-account/test-bucket",
        },
    ):
        yield


def run_test(client: WeaveClient):
    """Run the basic file storage test"""
    # Create a new trace
    res = client.server.file_create(
        FileCreateReq(
            project_id=client._project_id(),
            name="test.txt",
            content=b"Hello, world!",
        )
    )
    assert res.digest is not None
    assert res.digest != ""

    # Get the file
    file = client.server.file_content_read(
        FileContentReadReq(project_id=client._project_id(), digest=res.digest)
    )
    assert file.content == b"Hello, world!"

    return res


@pytest.mark.usefixtures("aws_storage_env")
def test_aws_storage(client: WeaveClient, s3):
    if client_is_sqlite(client):
        pytest.skip("Not implemented in SQLite")
    """Test file storage using AWS S3"""
    res = run_test(client)

    response = s3.list_objects_v2(Bucket="test-bucket")

    # Verify we can see all the objects
    assert "Contents" in response
    assert len(response["Contents"]) == 1

    # Verify each object exists and has correct size
    obj = response["Contents"][0]
    # Get the specific object
    obj_response = s3.get_object(Bucket="test-bucket", Key=obj["Key"])
    content = obj_response["Body"].read()
    assert content == b"Hello, world!"


@pytest.mark.usefixtures("gcp_storage_env", "mock_gcp_credentials")
def test_gcp_storage(client: WeaveClient, gcs):
    if client_is_sqlite(client):
        pytest.skip("Not implemented in SQLite")
    """Test file storage using Google Cloud Storage"""
    res = run_test(client)

    # Verify the object exists in GCS and has correct content
    bucket = gcs.bucket("test-bucket")
    blob = bucket.blob(res.digest)
    assert blob.download_as_bytes() == b"Hello, world!"


@pytest.mark.usefixtures("azure_storage_env")
def test_azure_storage(client: WeaveClient, azure_blob):
    if client_is_sqlite(client):
        pytest.skip("Not implemented in SQLite")
    """Test file storage using Azure Blob Storage"""
    res = run_test(client)

    # Verify the object exists in Azure and has correct content
    container_client = azure_blob.get_container_client("test-bucket")
    blob_client = container_client.get_blob_client(res.digest)
    assert blob_client.download_blob().readall() == b"Hello, world!"
