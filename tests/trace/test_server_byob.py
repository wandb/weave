import os
from unittest import mock

import boto3
import pytest
from azure.storage.blob import BlobServiceClient
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage
from moto import mock_s3

from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import FileContentReadReq, FileCreateReq


@pytest.fixture
def s3():
    """Moto S3 mock that actually implements the S3 API"""
    with mock_s3():
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
    """Google Cloud Storage emulator using fakestorage"""
    storage_client = storage.Client(
        project="test-project",
        credentials=AnonymousCredentials(),
        _http=storage._http.Connection(),
        client_options={"api_endpoint": "http://localhost:8888"},
    )
    # Create the test bucket
    bucket = storage_client.bucket("test-bucket")
    bucket.create()
    yield storage_client


@pytest.fixture
def azure_blob():
    """Azure Blob Storage emulator client"""
    # Using Azurite connection string format
    conn_str = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
    client = BlobServiceClient.from_connection_string(conn_str)
    # Create the test container
    client.create_container("test-bucket")
    yield client


@pytest.fixture
def storage_env():
    """Setup all storage credentials environment variables"""
    with mock.patch.dict(
        os.environ,
        {
            # AWS credentials
            "WF_STORAGE_BUCKET_AWS_ACCESS_KEY_ID": "test-key",
            "WF_STORAGE_BUCKET_AWS_SECRET_ACCESS_KEY": "test-secret",
            # GCP credentials - using anonymous credentials for emulator
            "WF_STORAGE_BUCKET_GCP_CREDENTIALS_JSON": '''{
                "type": "authorized_user",
                "client_id": "",
                "client_secret": "",
                "refresh_token": ""
            }''',
            # Azure credentials - using Azurite connection string
            "WF_STORAGE_BUCKET_AZURE_CONNECTION_STRING": "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;",
        },
    ):
        yield


@pytest.fixture(params=["s3", "gs", "azure"])
def storage_config(request, storage_env):
    """Parametrized fixture to test all storage providers"""
    provider = request.param
    if provider == "s3":
        uri = "s3://test-bucket"
    elif provider == "gs":
        uri = "gs://test-bucket"
    else:  # azure
        uri = "azure://test-bucket"

    with mock.patch.dict(os.environ, {"WF_STORAGE_BUCKET_URI": uri}):
        yield provider


@pytest.mark.integration
@pytest.mark.usefixtures("s3", "gcs", "azure_blob", "storage_config")
def test_byob_storage(client: WeaveClient):
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
