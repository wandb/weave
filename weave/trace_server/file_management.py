import logging
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
    AllCredentials,
    AWSCredentials,
    AzureAccountCredentials,
    AzureConnectionCredentials,
    get_aws_credentials,
    get_azure_credentials,
    get_gcp_credentials,
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


def determine_bucket_uri(
    base_file_storage_uri: str, project_id: str, digest: str
) -> str:
    # BBBAAADDD
    assert base_file_storage_uri.endswith("/")
    return f"{base_file_storage_uri}{key_for_project_digest(project_id, digest)}"


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


def parse_storage_uri(uri: str) -> tuple[str, str]:
    """
    Parses a storage URI into provider and path components.

    Args:
        uri: Storage URI (e.g., s3://bucket/path, gs://bucket/path, azure://container/path)

    Returns:
        Tuple of (provider, path)

    Raises:
        ValueError: If the URI format is invalid or provider is unsupported
    """
    if not uri or "://" not in uri:
        raise ValueError(f"Invalid storage URI format: {uri}")

    provider, path = uri.split("://", 1)

    if not path:
        raise ValueError(f"No path specified in URI: {uri}")

    if provider not in ["s3", "gs", "azure", "file"]:
        raise ValueError(f"Unsupported storage provider: {provider}")

    # BBBAAADDD
    name, path = path.split("/", 1)
    return provider, path


def split_bucket_and_path(path: str, provider: str) -> tuple[str, str]:
    """
    Splits a storage path into bucket/container name and object path.

    Args:
        path: The full path after the protocol (e.g., 'bucket-name/path/to/file')
        provider: The storage provider ('s3', 'gs', or 'azure')

    Returns:
        Tuple of (bucket_name, object_path)

    Raises:
        ValueError: If the path format is invalid
    """
    if "/" not in path:
        raise ValueError(
            f"Invalid path format for {provider}: {path}. Must include bucket/container and path."
        )
    parts = path.split("/", 1)
    return (parts[0], parts[1])  # Explicitly return a tuple


@create_retry_decorator("s3_storage")
def handle_s3_storage(path: str, data: bytes, credentials: AWSCredentials) -> None:
    """Handle storage for AWS S3."""
    bucket_name, object_path = split_bucket_and_path(path, "s3")
    logger.debug(
        "Preparing to upload to S3 bucket '%s' with path '%s'", bucket_name, object_path
    )

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

    logger.debug("Uploading %d bytes to S3", len(data))
    s3_client.put_object(Bucket=bucket_name, Key=object_path, Body=data)
    logger.info("Successfully uploaded to S3: s3://%s/%s", bucket_name, object_path)


@create_retry_decorator("gcs_storage")
def handle_gcs_storage(path: str, data: bytes, credentials: GCPCredentials) -> None:
    """Handle storage for Google Cloud Storage."""
    bucket_name, object_path = split_bucket_and_path(path, "gs")
    logger.debug(
        "Preparing to upload to GCS bucket '%s' with path '%s'",
        bucket_name,
        object_path,
    )

    # Configure client with timeouts
    storage_client = storage.Client(
        credentials=credentials,
        client_options={"api_endpoint": "storage.googleapis.com"},
        timeout=DEFAULT_CONNECT_TIMEOUT,
    )
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(object_path)

    # Use timeout for upload operation
    logger.debug("Uploading %d bytes to GCS", len(data))
    blob.upload_from_string(data, timeout=DEFAULT_READ_TIMEOUT)
    logger.info("Successfully uploaded to GCS: gs://%s/%s", bucket_name, object_path)


@create_retry_decorator("azure_storage")
def handle_azure_storage(
    path: str,
    data: bytes,
    credentials: Union[AzureConnectionCredentials, AzureAccountCredentials],
) -> None:
    """Handle storage for Azure Blob Storage."""
    container_name, blob_path = split_bucket_and_path(path, "azure")
    logger.debug(
        "Preparing to upload to Azure container '%s' with path '%s'",
        container_name,
        blob_path,
    )

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
        blob_service_client = BlobServiceClient(
            account_url=credentials["account_url"],
            credential=credentials["credential"],
            connection_timeout=DEFAULT_CONNECT_TIMEOUT,
            read_timeout=DEFAULT_READ_TIMEOUT,
        )

    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob_path)

    # Upload with retry and timeout handled by client config
    logger.debug("Uploading %d bytes to Azure Blob Storage", len(data))
    blob_client.upload_blob(data, overwrite=True)
    logger.info(
        "Successfully uploaded to Azure: azure://%s/%s", container_name, blob_path
    )


def store_in_bucket(file_storage_uri: str, bytes: bytes) -> str:
    """
    Stores a file in a storage bucket. file_storage_uri is the uri of the
    bucket to store the file in - supports the following providers: Azure,
    GCP, and S3.

    Args:
        file_storage_uri: The complete URI where the file should be stored
            Format examples:
            - AWS: s3://bucket-name/path/to/file
            - GCP: gs://bucket-name/path/to/file
            - Azure: azure://container-name/path/to/file
            - Local: file:///path/to/file (currently not supported)
        bytes: The file contents to store

    Returns:
        str: The complete URI of the stored file

    Raises:
        ValueError: If the URI format is invalid or provider is unsupported
        NotImplementedError: For unimplemented providers (like local files)
        Various provider-specific exceptions for storage/auth failures
    """
    provider, path = parse_storage_uri(file_storage_uri)
    logger.info("Storing %d bytes at %s", len(bytes), file_storage_uri)
    credentials: AllCredentials
    try:
        if provider == "s3":
            credentials = get_aws_credentials()
            handle_s3_storage(path, bytes, credentials)

        elif provider == "gs":
            credentials = get_gcp_credentials()
            handle_gcs_storage(path, bytes, credentials)

        elif provider == "azure":
            credentials = get_azure_credentials()
            handle_azure_storage(path, bytes, credentials)

        elif provider == "file":
            raise NotImplementedError("Local file storage not currently supported")

    except Exception as e:
        logger.exception("Failed to store file at %s: %s", file_storage_uri, str(e))
        # Re-raise with more context
        raise type(e)(f"Failed to store file at {file_storage_uri}: {str(e)}") from e

    return file_storage_uri  # Return the full URI as it uniquely identifies the stored file


# READ LAYER


@create_retry_decorator("s3_read")
def handle_s3_read(path: str, credentials: AWSCredentials) -> bytes:
    """Handle reading from AWS S3."""
    bucket_name, object_path = split_bucket_and_path(path, "s3")
    logger.debug(
        "Preparing to read from S3 bucket '%s' with path '%s'", bucket_name, object_path
    )

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

    logger.debug("Reading from S3")
    response = s3_client.get_object(Bucket=bucket_name, Key=object_path)
    data = response["Body"].read()
    logger.info(
        "Successfully read %d bytes from S3: s3://%s/%s",
        len(data),
        bucket_name,
        object_path,
    )
    return data


@create_retry_decorator("gcs_read")
def handle_gcs_read(path: str, credentials: GCPCredentials) -> bytes:
    """Handle reading from Google Cloud Storage."""
    bucket_name, object_path = split_bucket_and_path(path, "gs")
    logger.debug(
        "Preparing to read from GCS bucket '%s' with path '%s'",
        bucket_name,
        object_path,
    )

    # Configure client with timeouts
    storage_client = storage.Client(
        credentials=credentials,
        client_options={"api_endpoint": "storage.googleapis.com"},
        timeout=DEFAULT_CONNECT_TIMEOUT,
    )
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(object_path)

    # Use timeout for download operation
    logger.debug("Reading from GCS")
    data = blob.download_as_bytes(timeout=DEFAULT_READ_TIMEOUT)
    logger.info(
        "Successfully read %d bytes from GCS: gs://%s/%s",
        len(data),
        bucket_name,
        object_path,
    )
    return data


@create_retry_decorator("azure_read")
def handle_azure_read(
    path: str, credentials: Union[AzureConnectionCredentials, AzureAccountCredentials]
) -> bytes:
    """Handle reading from Azure Blob Storage."""
    container_name, blob_path = split_bucket_and_path(path, "azure")
    logger.debug(
        "Preparing to read from Azure container '%s' with path '%s'",
        container_name,
        blob_path,
    )

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
        blob_service_client = BlobServiceClient(
            account_url=credentials["account_url"],
            credential=credentials["credential"],
            connection_timeout=DEFAULT_CONNECT_TIMEOUT,
            read_timeout=DEFAULT_READ_TIMEOUT,
        )

    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob_path)

    # Download with retry and timeout handled by client config
    logger.debug("Reading from Azure Blob Storage")
    stream = blob_client.download_blob()
    data = stream.readall()
    logger.info(
        "Successfully read %d bytes from Azure: azure://%s/%s",
        len(data),
        container_name,
        blob_path,
    )
    return data


def read_from_bucket(file_storage_uri: str) -> bytes:
    """
    Reads a file from a storage bucket. file_storage_uri is the uri of the
    bucket to read the file from - supports the following providers: Azure,
    GCP, and S3.

    Args:
        file_storage_uri: The complete URI where the file should be read from
            Format examples:
            - AWS: s3://bucket-name/path/to/file
            - GCP: gs://bucket-name/path/to/file
            - Azure: azure://container-name/path/to/file
            - Local: file:///path/to/file (currently not supported)

    Returns:
        bytes: The contents of the file

    Raises:
        ValueError: If the URI format is invalid or provider is unsupported
        NotImplementedError: For unimplemented providers (like local files)
        Various provider-specific exceptions for storage/auth failures
    """
    provider, path = parse_storage_uri(file_storage_uri)
    logger.info("Reading from %s", file_storage_uri)

    credentials: AllCredentials

    try:
        if provider == "s3":
            credentials = get_aws_credentials()
            return handle_s3_read(path, credentials)

        elif provider == "gs":
            credentials = get_gcp_credentials()
            return handle_gcs_read(path, credentials)

        elif provider == "azure":
            credentials = get_azure_credentials()
            return handle_azure_read(path, credentials)

        elif provider == "file":
            raise NotImplementedError("Local file storage not currently supported")

        else:
            raise ValueError(f"Unsupported storage provider: {provider}")

    except Exception as e:
        logger.exception("Failed to read file from %s: %s", file_storage_uri, str(e))
        # Re-raise with more context
        raise type(e)(f"Failed to read file from {file_storage_uri}: {str(e)}") from e
