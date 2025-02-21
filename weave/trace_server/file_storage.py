import logging
from typing import Any, Callable, Union, cast

import boto3
import botocore
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


def key_for_project_digest(project_id: str, digest: str) -> str:
    return f"weave/projects/{project_id}/files/{digest}"


def create_retry_decorator(operation_name: str) -> Callable[[Any], Any]:
    """
    Creates a retry decorator with consistent retry policy.

    Args:
        operation_name: Name of the operation for error messaging
    """

    def after_retry(retry_state: RetryCallState) -> None:
        """Log retry attempt information."""
        if retry_state.attempt_number > 1:  # Only log retries, not the first attempt
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
        before_sleep=before_sleep_log(
            logger, logging.DEBUG
        ),  # Log before retry attempts at DEBUG level
        after=after_retry,
    )


def get_s3_client(credentials: AWSCredentials) -> botocore.client.BaseClient:
    # Configure timeouts
    config = Config(
        connect_timeout=DEFAULT_CONNECT_TIMEOUT,
        read_timeout=DEFAULT_READ_TIMEOUT,
        retries={"max_attempts": 0},  # Disable boto3's built-in retry to use our own
    )

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=credentials.get("access_key_id"),
        aws_secret_access_key=credentials.get("secret_access_key"),
        aws_session_token=credentials.get("session_token"),
        config=config,
    )

    return s3_client


@create_retry_decorator("s3_storage")
def handle_s3_store(
    file_storage_uri: S3FileStorageURI, data: bytes, credentials: AWSCredentials
) -> None:
    """Handle storage for AWS S3."""
    s3_client = get_s3_client(credentials)
    s3_client.put_object(
        Bucket=file_storage_uri.bucket, Key=file_storage_uri.path, Body=data
    )


@create_retry_decorator("s3_read")
def handle_s3_read(
    file_storage_uri: S3FileStorageURI, credentials: AWSCredentials
) -> bytes:
    """Handle reading from AWS S3."""
    s3_client = get_s3_client(credentials)
    response = s3_client.get_object(
        Bucket=file_storage_uri.bucket, Key=file_storage_uri.path
    )
    return response["Body"].read()


def get_gcs_client(credentials: GCPCredentials) -> storage.Client:
    return storage.Client(
        credentials=credentials,
        client_options={"api_endpoint": "storage.googleapis.com"},
        timeout=DEFAULT_CONNECT_TIMEOUT,
    )


@create_retry_decorator("gcs_storage")
def handle_gcs_store(
    file_storage_uri: GCSFileStorageURI, data: bytes, credentials: GCPCredentials
) -> None:
    """Handle storage for Google Cloud Storage."""
    storage_client = get_gcs_client(credentials)
    bucket = storage_client.bucket(file_storage_uri.bucket)
    blob = bucket.blob(file_storage_uri.path)
    blob.upload_from_string(data, timeout=DEFAULT_READ_TIMEOUT)


@create_retry_decorator("gcs_read")
def handle_gcs_read(
    file_storage_uri: GCSFileStorageURI, credentials: GCPCredentials
) -> bytes:
    """Handle reading from Google Cloud Storage."""
    storage_client = get_gcs_client(credentials)
    bucket = storage_client.bucket(file_storage_uri.bucket)
    blob = bucket.blob(file_storage_uri.path)
    return blob.download_as_bytes(timeout=DEFAULT_READ_TIMEOUT)


def get_azure_client(
    account: str,
    credentials: Union[AzureConnectionCredentials, AzureAccountCredentials],
) -> BlobServiceClient:
    # Configure client with timeouts
    if "connection_string" in credentials:
        credentials = cast(AzureConnectionCredentials, credentials)
        logger.debug("Initializing Azure client with connection string")
        blob_service_client = BlobServiceClient.from_connection_string(
            credentials["connection_string"],
            connection_timeout=DEFAULT_CONNECT_TIMEOUT,
            read_timeout=DEFAULT_READ_TIMEOUT,
        )
    else:
        logger.debug("Initializing Azure client with account URL")
        credentials = cast(AzureAccountCredentials, credentials)
        account__url = f"https://{account}.blob.core.windows.net/"
        blob_service_client = BlobServiceClient(
            account_url=account__url,
            credential=credentials["credential"],
            connection_timeout=DEFAULT_CONNECT_TIMEOUT,
            read_timeout=DEFAULT_READ_TIMEOUT,
        )

    return blob_service_client


@create_retry_decorator("azure_storage")
def handle_azure_store(
    file_storage_uri: AzureFileStorageURI,
    data: bytes,
    credentials: Union[AzureConnectionCredentials, AzureAccountCredentials],
) -> None:
    """Handle storage for Azure Blob Storage."""
    blob_service_client = get_azure_client(file_storage_uri.account, credentials)
    container_client = blob_service_client.get_container_client(
        file_storage_uri.container
    )
    blob_client = container_client.get_blob_client(file_storage_uri.path)
    blob_client.upload_blob(data, overwrite=True)


@create_retry_decorator("azure_read")
def handle_azure_read(
    file_storage_uri: AzureFileStorageURI,
    credentials: Union[AzureConnectionCredentials, AzureAccountCredentials],
) -> bytes:
    """Handle reading from Azure Blob Storage."""
    blob_service_client = get_azure_client(file_storage_uri.account, credentials)
    container_client = blob_service_client.get_container_client(
        file_storage_uri.container
    )
    blob_client = container_client.get_blob_client(file_storage_uri.path)
    stream = blob_client.download_blob()
    return stream.readall()


def store_in_bucket(file_storage_uri: FileStorageURI, bytes: bytes) -> None:
    """
    Stores a file in a storage bucket. file_storage_uri is the uri of the
    bucket to store the file in - supports the following providers: Azure,
    GCP, and S3.

    Args:
        file_storage_uri: The complete URI where the file should be stored
            Format examples:
            - AWS: s3://bucket-name/path/to/file
            - GCP: gs://bucket-name/path/to/file
            - Azure: az://container-name/path/to/file
            - Local: file:///path/to/file (currently not supported)
        bytes: The file contents to store

    Returns:
        str: The complete URI of the stored file

    Raises:
        ValueError: If the URI format is invalid or provider is unsupported
        NotImplementedError: For unimplemented providers (like local files)
        Various provider-specific exceptions for storage/auth failures
    """
    try:
        if isinstance(file_storage_uri, S3FileStorageURI):
            handle_s3_store(file_storage_uri, bytes, get_aws_credentials())

        elif isinstance(file_storage_uri, S3FileStorageURI):
            handle_gcs_store(file_storage_uri, bytes, get_gcp_credentials())

        elif isinstance(file_storage_uri, S3FileStorageURI):
            handle_azure_store(file_storage_uri, bytes, get_azure_credentials())

        else:
            raise NotImplementedError(
                f"file_storage_uri of type {type(file_storage_uri)} not supported"
            )

    except Exception as e:
        logger.exception("Failed to store file at %s: %s", file_storage_uri, str(e))
        # Re-raise with more context
        raise type(e)(f"Failed to store file at {file_storage_uri}: {str(e)}") from e


# READ LAYER


def read_from_bucket(file_storage_uri: FileStorageURI) -> bytes:
    """
    Reads a file from a storage bucket. file_storage_uri is the uri of the
    bucket to read the file from - supports the following providers: Azure,
    GCP, and S3.

    Args:
        file_storage_uri: The complete URI where the file should be read from
            Format examples:
            - AWS: s3://bucket-name/path/to/file
            - GCP: gs://bucket-name/path/to/file
            - Azure: az://container-name/path/to/file
            - Local: file:///path/to/file (currently not supported)

    Returns:
        bytes: The contents of the file

    Raises:
        ValueError: If the URI format is invalid or provider is unsupported
        NotImplementedError: For unimplemented providers (like local files)
        Various provider-specific exceptions for storage/auth failures
    """
    try:
        if isinstance(file_storage_uri, S3FileStorageURI):
            return handle_s3_read(file_storage_uri, bytes, get_aws_credentials())

        elif isinstance(file_storage_uri, S3FileStorageURI):
            return handle_gcs_read(file_storage_uri, bytes, get_gcp_credentials())

        elif isinstance(file_storage_uri, S3FileStorageURI):
            return handle_azure_read(file_storage_uri, bytes, get_azure_credentials())

        else:
            raise NotImplementedError(
                f"file_storage_uri of type {type(file_storage_uri)} not supported"
            )

    except Exception as e:
        logger.exception("Failed to read file from %s: %s", file_storage_uri, str(e))
        # Re-raise with more context
        raise type(e)(f"Failed to read file from {file_storage_uri}: {str(e)}") from e
