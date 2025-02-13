import logging
from typing import Any, Callable, TypedDict, Union, cast

import boto3
from azure.core.credentials import TokenCredential as AzureTokenCredential
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

from weave.trace_server import environment

# Configure logger
logger = logging.getLogger(__name__)

# Default timeout values (in seconds)
DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_READ_TIMEOUT = 30
RETRY_MAX_ATTEMPTS = 3
RETRY_MIN_WAIT = 1  # seconds
RETRY_MAX_WAIT = 10  # seconds

def determine_bucket_uri(
    project_id: str, digest: str, base_storage_bucket_uri: str
) -> str:
    return f"{base_storage_bucket_uri}/weave/projects/{project_id}/files/{digest}"


class AWSCredentials(TypedDict, total=False):
    """Type for AWS credentials dictionary."""

    access_key_id: str
    secret_access_key: str
    session_token: str  # Optional


class AzureConnectionCredentials(TypedDict):
    """Type for Azure connection string credentials."""

    connection_string: str


class AzureAccountCredentials(TypedDict):
    """Type for Azure account credentials."""

    account_url: str
    credential: Union[
        str, AzureTokenCredential
    ]  # Can be connection string, SAS token, or credential object


AllCredentials = Union[
    AWSCredentials, GCPCredentials, AzureConnectionCredentials, AzureAccountCredentials
]


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


def get_aws_credentials() -> AWSCredentials:
    """
    Returns AWS credentials needed for S3 access.
    To be implemented by the client.

    Returns:
        Dict containing AWS credentials with keys:
        - access_key_id: AWS access key ID
        - secret_access_key: AWS secret access key
        - session_token: Optional session token
    """
    access_key_id = environment.wf_storage_bucket_aws_access_key_id()
    secret_access_key = environment.wf_storage_bucket_aws_secret_access_key()
    session_token = environment.wf_storage_bucket_aws_session_token()
    if access_key_id is None or secret_access_key is None:
        raise ValueError("AWS credentials not set")
    return AWSCredentials(
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        session_token=session_token,
    )


def get_gcp_credentials() -> GCPCredentials:
    """
    Returns GCP credentials needed for GCS access.
    Uses a JSON string containing service account credentials.

    Returns:
        Google Cloud credentials object that can be used with storage client

    Raises:
        ValueError: If no valid GCP credentials are found
    """
    import json

    from google.oauth2 import service_account

    creds_json = environment.wf_storage_bucket_gcp_credentials_json()
    if not creds_json:
        raise ValueError(
            "No GCP credentials found. Set WF_STORAGE_BUCKET_GCP_CREDENTIALS_JSON environment variable."
        )

    try:
        creds_dict = json.loads(creds_json)
        return service_account.Credentials.from_service_account_info(creds_dict)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid GCP credentials JSON: {e}")


def get_azure_credentials() -> (
    Union[AzureConnectionCredentials, AzureAccountCredentials]
):
    """
    Returns Azure credentials needed for Blob storage access.
    To be implemented by the client.

    Returns:
        Either:
        - Dict with connection_string for connection string auth
        - Dict with account_url and credential for account-based auth
    """
    connection_string = environment.wf_storage_bucket_azure_connection_string()
    if connection_string is not None:
        return AzureConnectionCredentials(connection_string=connection_string)
    account_url = environment.wf_storage_bucket_azure_account_url()
    credential = environment.wf_storage_bucket_azure_credential()
    if account_url is None and credential is None:
        raise ValueError("Azure credentials not set")
    return AzureAccountCredentials(
        account_url=account_url, credential=credential
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


def store_in_bucket(storage_bucket_uri: str, bytes: bytes) -> str:
    """
    Stores a file in a storage bucket. storage_bucket_uri is the uri of the
    bucket to store the file in - supports the following providers: Azure,
    GCP, and S3.

    Args:
        storage_bucket_uri: The complete URI where the file should be stored
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
    provider, path = parse_storage_uri(storage_bucket_uri)
    logger.info("Storing %d bytes at %s", len(bytes), storage_bucket_uri)
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
        logger.exception("Failed to store file at %s: %s", storage_bucket_uri, str(e))
        # Re-raise with more context
        raise type(e)(f"Failed to store file at {storage_bucket_uri}: {str(e)}") from e

    return storage_bucket_uri  # Return the full URI as it uniquely identifies the stored file


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


def read_from_bucket(storage_bucket_uri: str) -> bytes:
    """
    Reads a file from a storage bucket. storage_bucket_uri is the uri of the
    bucket to read the file from - supports the following providers: Azure,
    GCP, and S3.

    Args:
        storage_bucket_uri: The complete URI where the file should be read from
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
    provider, path = parse_storage_uri(storage_bucket_uri)
    logger.info("Reading from %s", storage_bucket_uri)

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
        logger.exception("Failed to read file from %s: %s", storage_bucket_uri, str(e))
        # Re-raise with more context
        raise type(e)(f"Failed to read file from {storage_bucket_uri}: {str(e)}") from e
