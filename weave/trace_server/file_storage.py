import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Union, cast

import boto3
from azure.storage.blob import BlobServiceClient
from botocore.config import Config
from google.cloud import storage
from google.oauth2.credentials import Credentials as GCPCredentials
from tenacity import (
    RetryCallState,
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from weave.trace_server.file_storage_credentials import (
    AWSCredentials,
    AzureAccountCredentials,
    AzureConnectionCredentials,
    get_aws_credentials,
    get_azure_credentials,
    get_gcp_credentials,
)
from weave.trace_server.file_storage_uris import (
    AzureFileStorageURI,
    FileStorageURI,
    GCSFileStorageURI,
    S3FileStorageURI,
)

# Configure logger
logger = logging.getLogger(__name__)

# Default timeout values (in seconds)
DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_READ_TIMEOUT = 30
RETRY_MAX_ATTEMPTS = 3
RETRY_MIN_WAIT = 1  # seconds
RETRY_MAX_WAIT = 10  # seconds

# Publicly exposed methods:


def store_in_bucket(file_storage_uri: FileStorageURI, data: bytes) -> None:
    """Store a file in a storage bucket."""
    try:
        client = _get_storage_client(file_storage_uri)
        client.store(file_storage_uri, data)
    except Exception as e:
        logger.exception("Failed to store file at %s: %s", file_storage_uri, str(e))
        raise type(e)(f"Failed to store file at {file_storage_uri}: {str(e)}") from e


def read_from_bucket(file_storage_uri: FileStorageURI) -> bytes:
    """Read a file from a storage bucket."""
    try:
        client = _get_storage_client(file_storage_uri)
        return client.read(file_storage_uri)
    except Exception as e:
        logger.exception("Failed to read file from %s: %s", file_storage_uri, str(e))
        raise type(e)(f"Failed to read file from {file_storage_uri}: {str(e)}") from e


### Everything below here is interal


def key_for_project_digest(project_id: str, digest: str) -> str:
    return f"weave/projects/{project_id}/files/{digest}"


def create_retry_decorator(operation_name: str) -> Callable[[Any], Any]:
    """Creates a retry decorator with consistent retry policy."""

    def after_retry(retry_state: RetryCallState) -> None:
        if retry_state.attempt_number > 1:
            logger.info(
                "%s: Attempt %d/%d after %.2f seconds",
                operation_name,
                retry_state.attempt_number,
                RETRY_MAX_ATTEMPTS,
                retry_state.seconds_since_start,
            )

    return retry(
        stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.DEBUG),
        after=after_retry,
    )


class FileStorageClient(ABC):
    """Abstract base class defining the interface for cloud storage operations.
    Implementations are provided for AWS S3, Google Cloud Storage, and Azure Blob Storage."""

    @abstractmethod
    def store(self, uri: FileStorageURI, data: bytes) -> None:
        """Store data at the specified URI location in cloud storage."""
        pass

    @abstractmethod
    def read(self, uri: FileStorageURI) -> bytes:
        """Read data from the specified URI location in cloud storage."""
        pass


class S3StorageClient(FileStorageClient):
    """AWS S3 storage implementation with retry logic and configurable timeouts."""

    def __init__(self, credentials: AWSCredentials):
        """Initialize S3 client with credentials and default timeout configuration."""
        config = Config(
            connect_timeout=DEFAULT_CONNECT_TIMEOUT,
            read_timeout=DEFAULT_READ_TIMEOUT,
            retries={"max_attempts": 0},
        )
        self.client = boto3.client(
            "s3",
            aws_access_key_id=credentials.get("access_key_id"),
            aws_secret_access_key=credentials.get("secret_access_key"),
            aws_session_token=credentials.get("session_token"),
            config=config,
        )

    @create_retry_decorator("s3_storage")
    def store(self, uri: S3FileStorageURI, data: bytes) -> None:
        """Store data in S3 bucket with automatic retries on failure."""
        self.client.put_object(Bucket=uri.bucket, Key=uri.path, Body=data)

    @create_retry_decorator("s3_read")
    def read(self, uri: S3FileStorageURI) -> bytes:
        """Read data from S3 bucket with automatic retries on failure."""
        response = self.client.get_object(Bucket=uri.bucket, Key=uri.path)
        return response["Body"].read()


class GCSStorageClient(FileStorageClient):
    """Google Cloud Storage implementation with retry logic and configurable timeouts."""

    def __init__(self, credentials: GCPCredentials):
        """Initialize GCS client with credentials and default timeout configuration."""
        self.client = storage.Client(
            credentials=credentials,
            client_options={"api_endpoint": "storage.googleapis.com"},
            timeout=DEFAULT_CONNECT_TIMEOUT,
        )

    @create_retry_decorator("gcs_storage")
    def store(self, uri: GCSFileStorageURI, data: bytes) -> None:
        """Store data in GCS bucket with automatic retries on failure."""
        bucket = self.client.bucket(uri.bucket)
        blob = bucket.blob(uri.path)
        blob.upload_from_string(data, timeout=DEFAULT_READ_TIMEOUT)

    @create_retry_decorator("gcs_read")
    def read(self, uri: GCSFileStorageURI) -> bytes:
        """Read data from GCS bucket with automatic retries on failure."""
        bucket = self.client.bucket(uri.bucket)
        blob = bucket.blob(uri.path)
        return blob.download_as_bytes(timeout=DEFAULT_READ_TIMEOUT)


class AzureStorageClient(FileStorageClient):
    """Azure Blob Storage implementation supporting both connection string and account credentials."""

    def __init__(
        self, credentials: Union[AzureConnectionCredentials, AzureAccountCredentials]
    ):
        """Initialize Azure client with either connection string or account credentials."""
        self.credentials = credentials

    def _get_client(self, account: str) -> BlobServiceClient:
        """Create Azure client based on available credentials (connection string or account)."""
        if "connection_string" in self.credentials:
            connection_creds = cast(AzureConnectionCredentials, self.credentials)
            return BlobServiceClient.from_connection_string(
                connection_creds["connection_string"],
                connection_timeout=DEFAULT_CONNECT_TIMEOUT,
                read_timeout=DEFAULT_READ_TIMEOUT,
            )
        else:
            account_creds = cast(AzureAccountCredentials, self.credentials)
            account_url = f"https://{account}.blob.core.windows.net/"
            return BlobServiceClient(
                account_url=account_url,
                credential=account_creds["credential"],
                connection_timeout=DEFAULT_CONNECT_TIMEOUT,
                read_timeout=DEFAULT_READ_TIMEOUT,
            )

    @create_retry_decorator("azure_storage")
    def store(self, uri: AzureFileStorageURI, data: bytes) -> None:
        """Store data in Azure container with automatic retries on failure."""
        client = self._get_client(uri.account)
        container_client = client.get_container_client(uri.container)
        blob_client = container_client.get_blob_client(uri.path)
        blob_client.upload_blob(data, overwrite=True)

    @create_retry_decorator("azure_read")
    def read(self, uri: AzureFileStorageURI) -> bytes:
        """Read data from Azure container with automatic retries on failure."""
        client = self._get_client(uri.account)
        container_client = client.get_container_client(uri.container)
        blob_client = container_client.get_blob_client(uri.path)
        stream = blob_client.download_blob()
        return stream.readall()


def _get_storage_client(uri: FileStorageURI) -> FileStorageClient:
    """Factory method that returns appropriate storage client based on URI type.
    Supports S3, GCS, and Azure storage URIs."""
    if isinstance(uri, S3FileStorageURI):
        return S3StorageClient(get_aws_credentials())
    elif isinstance(uri, GCSFileStorageURI):
        return GCSStorageClient(get_gcp_credentials())
    elif isinstance(uri, AzureFileStorageURI):
        return AzureStorageClient(get_azure_credentials())
    else:
        raise NotImplementedError(
            f"Storage client for URI type {type(uri)} not supported"
        )
