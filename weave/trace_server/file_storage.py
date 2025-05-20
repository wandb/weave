"""
Currently 3 storage backends are supported:
- AWS S3
- Google Cloud Storage
- Azure Blob Storage

Each of these can be configured at the application layer, or at the environment layer.

Common configuration options:
- `WF_FILE_STORAGE_URI`: sets the default storage backend to use. looks like `s3://my-bucket` or `gs://my-bucket` or `az://my-account/my-container`.
- `WF_FILE_STORAGE_PROJECT_ALLOW_LIST`: a list of project ids that are allowed to use the default storage bucket (at write time). Value of '*' allows all projects.

AWS S3 specific configuration options:
- `WF_FILE_STORAGE_AWS_REGION`: the region for the aws account.
- `WF_FILE_STORAGE_AWS_KMS_KEY`: the kms key to use for encryption.
- If connecting to a local bucket:
    - `WF_FILE_STORAGE_AWS_ACCESS_KEY_ID`: the access key id for the aws account.
    - `WF_FILE_STORAGE_AWS_SECRET_ACCESS_KEY`: the secret access key for the aws account.
    - `WF_FILE_STORAGE_AWS_SESSION_TOKEN`: (optional) the session token for the aws account.
- If connecting to a remote bucket:
    - Configure the running instance to have it's account permissions set to access the bucket. The
    instance should automatically assume the role of the running user.

GCS specific configuration options:
- If connecting to a local bucket:
    - `WF_FILE_STORAGE_GCP_CREDENTIALS_JSON_B64`: the base64 encoded json string for the gcp service account key.
- If connecting to a remote bucket:
    - Configure the running instance to have it's account permissions set to access the bucket. The
    instance should automatically assume the role of the running user.

Azure specific configuration options:
There are two ways to authenticate with Azure Blob Storage:
1. Connection string (simple)
2. Account and key (more complex)

1. Connection string:
    - `WF_FILE_STORAGE_AZURE_CONNECTION_STRING`: the connection string for the azure account.

2. Account and key:
    - `WF_FILE_STORAGE_AZURE_ACCESS_KEY`: the access key for the azure account.
    - `WF_FILE_STORAGE_AZURE_ACCOUNT_URL`: (optional) the account url for the azure account - defaults to `https://<account>.blob.core.windows.net/`
"""

import logging
from abc import abstractmethod
from typing import Any, Callable, Optional, Union, cast

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

from weave.trace_server.environment import wf_file_storage_uri
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


class FileStorageClient:
    """Abstract base class defining the interface for cloud storage operations.
    Implementations are provided for AWS S3, Google Cloud Storage, and Azure Blob Storage."""

    base_uri: FileStorageURI

    def __init__(self, base_uri: FileStorageURI):
        assert isinstance(base_uri, FileStorageURI)
        self.base_uri = base_uri

    @abstractmethod
    def store(self, uri: FileStorageURI, data: bytes) -> None:
        """Store data at the specified URI location in cloud storage."""
        pass

    @abstractmethod
    def read(self, uri: FileStorageURI) -> bytes:
        """Read data from the specified URI location in cloud storage."""
        pass


class FileStorageWriteError(Exception):
    """Exception for failed file writes."""

    pass


class FileStorageReadError(Exception):
    """Exception for failed file reads."""

    pass


def store_in_bucket(
    client: FileStorageClient, path: str, data: bytes
) -> FileStorageURI:
    """Store a file in a storage bucket."""
    try:
        target_file_storage_uri = client.base_uri.with_path(path)
        client.store(target_file_storage_uri, data)
    except Exception as e:
        logger.exception(
            "Failed to store file at %s: %s", target_file_storage_uri, str(e)
        )
        raise FileStorageWriteError(f"Failed to store file at {path}: {str(e)}") from e
    return target_file_storage_uri


def read_from_bucket(
    client: FileStorageClient, file_storage_uri: FileStorageURI
) -> bytes:
    """Read a file from a storage bucket."""
    try:
        return client.read(file_storage_uri)
    except Exception as e:
        logger.exception("Failed to read file from %s: %s", file_storage_uri, str(e))
        raise FileStorageReadError(
            f"Failed to read file from {file_storage_uri}: {str(e)}"
        ) from e


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


class S3StorageClient(FileStorageClient):
    """AWS S3 storage implementation with retry logic and configurable timeouts."""

    def __init__(self, base_uri: FileStorageURI, credentials: AWSCredentials):
        """Initialize S3 client with credentials and default timeout configuration."""
        assert isinstance(base_uri, S3FileStorageURI)
        super().__init__(base_uri)
        config = Config(
            connect_timeout=DEFAULT_CONNECT_TIMEOUT,
            read_timeout=DEFAULT_READ_TIMEOUT,
            retries={"max_attempts": 0},
        )
        credential_params = {}
        credential_params["aws_access_key_id"] = credentials.get("access_key_id")
        credential_params["aws_secret_access_key"] = credentials.get(
            "secret_access_key"
        )
        credential_params["aws_session_token"] = credentials.get("session_token")
        credential_params["region_name"] = credentials.get("region")
        # Store KMS key as an instance variable for use in operations
        self.kms_key = credentials.get("kms_key")
        self.client = boto3.client(
            "s3",
            **credential_params,
            config=config,
        )

    @create_retry_decorator("s3_storage")
    def store(self, uri: S3FileStorageURI, data: bytes) -> None:
        """Store data in S3 bucket with automatic retries on failure."""
        assert isinstance(uri, S3FileStorageURI) and uri.to_uri_str().startswith(
            self.base_uri.to_uri_str()
        )
        # Use KMS key for encryption if available
        put_object_params = {"Bucket": uri.bucket, "Key": uri.path, "Body": data}

        # Add ServerSideEncryption with KMS if KMS key is provided
        if self.kms_key:
            put_object_params["ServerSideEncryption"] = "aws:kms"
            put_object_params["SSEKMSKeyId"] = self.kms_key

        self.client.put_object(**put_object_params)

    @create_retry_decorator("s3_read")
    def read(self, uri: S3FileStorageURI) -> bytes:
        """Read data from S3 bucket with automatic retries on failure."""
        assert isinstance(uri, S3FileStorageURI) and uri.to_uri_str().startswith(
            self.base_uri.to_uri_str()
        )
        response = self.client.get_object(Bucket=uri.bucket, Key=uri.path)
        return response["Body"].read()


class GCSStorageClient(FileStorageClient):
    """Google Cloud Storage implementation with retry logic and configurable timeouts."""

    def __init__(
        self, base_uri: FileStorageURI, credentials: Optional[GCPCredentials] = None
    ):
        """Initialize GCS client with credentials and default timeout configuration."""
        assert isinstance(base_uri, GCSFileStorageURI)
        super().__init__(base_uri)
        self.client = storage.Client(
            credentials=credentials,
        )

    @create_retry_decorator("gcs_storage")
    def store(self, uri: GCSFileStorageURI, data: bytes) -> None:
        """Store data in GCS bucket with automatic retries on failure."""
        assert isinstance(uri, GCSFileStorageURI) and uri.to_uri_str().startswith(
            self.base_uri.to_uri_str()
        )
        bucket = self.client.bucket(uri.bucket)
        blob = bucket.blob(uri.path)
        blob.upload_from_string(data, timeout=DEFAULT_READ_TIMEOUT)

    @create_retry_decorator("gcs_read")
    def read(self, uri: GCSFileStorageURI) -> bytes:
        """Read data from GCS bucket with automatic retries on failure."""
        assert isinstance(uri, GCSFileStorageURI) and uri.to_uri_str().startswith(
            self.base_uri.to_uri_str()
        )
        bucket = self.client.bucket(uri.bucket)
        blob = bucket.blob(uri.path)
        return blob.download_as_bytes(timeout=DEFAULT_READ_TIMEOUT)


class AzureStorageClient(FileStorageClient):
    """Azure Blob Storage implementation supporting both connection string and account credentials."""

    def __init__(
        self,
        base_uri: FileStorageURI,
        credentials: Union[AzureConnectionCredentials, AzureAccountCredentials],
    ):
        """Initialize Azure client with either connection string or account credentials."""
        assert isinstance(base_uri, AzureFileStorageURI)
        super().__init__(base_uri)
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
            if "account_url" in account_creds and account_creds["account_url"]:
                account_url = account_creds["account_url"]
            else:
                account_url = f"https://{account}.blob.core.windows.net/"
            return BlobServiceClient(
                account_url=account_url,
                credential=account_creds["access_key"],
                connection_timeout=DEFAULT_CONNECT_TIMEOUT,
                read_timeout=DEFAULT_READ_TIMEOUT,
            )

    @create_retry_decorator("azure_storage")
    def store(self, uri: AzureFileStorageURI, data: bytes) -> None:
        """Store data in Azure container with automatic retries on failure."""
        assert isinstance(uri, AzureFileStorageURI) and uri.to_uri_str().startswith(
            self.base_uri.to_uri_str()
        )
        client = self._get_client(uri.account)
        container_client = client.get_container_client(uri.container)
        blob_client = container_client.get_blob_client(uri.path)
        blob_client.upload_blob(data, overwrite=True)

    @create_retry_decorator("azure_read")
    def read(self, uri: AzureFileStorageURI) -> bytes:
        """Read data from Azure container with automatic retries on failure."""
        assert isinstance(uri, AzureFileStorageURI) and uri.to_uri_str().startswith(
            self.base_uri.to_uri_str()
        )
        client = self._get_client(uri.account)
        container_client = client.get_container_client(uri.container)
        blob_client = container_client.get_blob_client(uri.path)
        stream = blob_client.download_blob()
        return stream.readall()


def maybe_get_storage_client_from_env() -> Optional[FileStorageClient]:
    """Factory method that returns appropriate storage client based on URI type.
    Supports S3, GCS, and Azure storage URIs."""
    file_storage_uri = wf_file_storage_uri()
    if not file_storage_uri:
        return None
    try:
        parsed_uri = FileStorageURI.parse_uri_str(file_storage_uri)
    except Exception as e:
        logger.warning(f"Error parsing file storage URI: {e}")
        return None
    if parsed_uri.has_path():
        logger.error(
            f"Supplied file storage uri contains path components: {file_storage_uri}"
        )
        return None

    if isinstance(parsed_uri, S3FileStorageURI):
        return S3StorageClient(parsed_uri, get_aws_credentials())
    elif isinstance(parsed_uri, GCSFileStorageURI):
        return GCSStorageClient(parsed_uri, get_gcp_credentials())
    elif isinstance(parsed_uri, AzureFileStorageURI):
        return AzureStorageClient(parsed_uri, get_azure_credentials())
    else:
        raise NotImplementedError(
            f"Storage client for URI type {type(file_storage_uri)} not supported"
        )
