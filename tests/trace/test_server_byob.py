import os
from unittest import mock

import boto3
import pytest
from azure.storage.blob import BlobServiceClient
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage
from moto import mock_aws

from weave.trace.weave_client import WeaveClient
from weave.trace_server.file_management import key_for_project_digest
from weave.trace_server.trace_server_interface import FileContentReadReq, FileCreateReq


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
def gcs():
    """Google Cloud Storage mock using in-memory storage"""
    # Create a mock GCS client that uses in-memory storage
    storage_client = storage.Client(
        project="test-project",
        credentials=AnonymousCredentials(),
    )
    # Patch the _http and _connection to prevent actual API calls
    storage_client._http = mock.Mock()
    storage_client._connection = mock.Mock()

    # Mock the bucket operations
    bucket = storage_client.bucket("test-bucket")
    bucket._properties = {"name": "test-bucket"}  # Minimum required properties

    # Mock the basic blob operations
    def mock_blob_upload(data):
        blob._properties["size"] = len(data)
        return None

    def mock_blob_download():
        return b"Hello, world!"

    blob = bucket.blob("test/path")
    blob.upload_from_string = mock_blob_upload
    blob.download_as_bytes = mock_blob_download

    yield storage_client


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
            "WF_STORAGE_BUCKET_AWS_ACCESS_KEY_ID": "test-key",
            "WF_STORAGE_BUCKET_AWS_SECRET_ACCESS_KEY": "test-secret",
            "WF_STORAGE_BUCKET_URI": "s3://test-bucket",
        },
    ):
        yield


@pytest.fixture
def gcp_storage_env():
    """Setup GCP storage environment"""
    with mock.patch.dict(
        os.environ,
        {
            "WF_STORAGE_BUCKET_GCP_CREDENTIALS_JSON": '''{
                "type": "authorized_user",
                "client_id": "",
                "client_secret": "",
                "refresh_token": ""
            }''',
            "WF_STORAGE_BUCKET_URI": "gs://test-bucket",
        },
    ):
        yield


@pytest.fixture
def azure_storage_env():
    """Setup Azure storage environment"""
    with mock.patch.dict(
        os.environ,
        {
            "WF_STORAGE_BUCKET_AZURE_CONNECTION_STRING": (
                "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
                "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
                "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
            ),
            "WF_STORAGE_BUCKET_URI": "azure://test-bucket",
        },
    ):
        yield

def run_test(client: WeaveClient):
    """Run the basic file storage test"""
    # Create a new trace
    res = client.server.file_create(FileCreateReq(
        project_id=client._project_id(),
        name="test.txt",
        content=b"Hello, world!",
    ))
    assert res.digest is not None
    assert res.digest != ""

    # Get the file
    file = client.server.file_content_read(FileContentReadReq(
        project_id=client._project_id(),
        digest=res.digest))
    assert file.content == b"Hello, world!"

    return res

@pytest.mark.usefixtures("aws_storage_env")
def test_aws_storage(client: WeaveClient, s3):
    """Test file storage using AWS S3"""
    res = run_test(client)

    # Verify the object exists in S3 and has correct content
    key = key_for_project_digest(client._project_id(), res.digest)
    response = s3.get_object(Bucket='test-bucket', Key=key)
    assert response['Body'].read() == b"Hello, world!"

    response = s3.list_objects_v2(Bucket='test-bucket')

    # Verify we can see all the objects
    assert 'Contents' in response
    assert len(response['Contents']) == 1

    # Verify each object exists and has correct size
    obj = response['Contents'][0]
    # Get the specific object
    obj_response = s3.get_object(Bucket='test-bucket', Key=obj['Key'])
    content = obj_response['Body'].read()
    assert content == b"Hello, world!"




@pytest.mark.usefixtures("gcp_storage_env")
def test_gcp_storage(client: WeaveClient, gcs):
    """Test file storage using Google Cloud Storage"""
    res = run_test(client)

    # Verify the object exists in GCS and has correct content
    bucket = gcs.bucket("test-bucket")
    blob = bucket.blob(res.digest)
    assert blob.download_as_bytes() == b"Hello, world!"


@pytest.mark.usefixtures("azure_storage_env")
def test_azure_storage(client: WeaveClient, azure_blob):
    """Test file storage using Azure Blob Storage"""
    res = run_test(client)

    # Verify the object exists in Azure and has correct content
    container_client = azure_blob.get_container_client("test-bucket")
    blob_client = container_client.get_blob_client(res.digest)
    assert blob_client.download_blob().readall() == b"Hello, world!"
