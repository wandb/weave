import base64
from typing import Optional, TypedDict, Union

from google.oauth2.credentials import Credentials as GCPCredentials
from typing_extensions import NotRequired

from weave.trace_server import environment


class AWSCredentials(TypedDict):
    """AWS authentication credentials for S3 access.
    The session_token is optional and only required for temporary credentials."""

    access_key_id: NotRequired[Optional[str]]
    secret_access_key: NotRequired[Optional[str]]
    session_token: NotRequired[Optional[str]]
    kms_key: NotRequired[Optional[str]]
    region: NotRequired[Optional[str]]


class AzureConnectionCredentials(TypedDict):
    """Azure authentication using connection string format."""

    connection_string: str


class AzureAccountCredentials(TypedDict):
    """Azure authentication using account-based credentials."""

    access_key: str
    account_url: NotRequired[Optional[str]]


def get_aws_credentials() -> AWSCredentials:
    """Retrieves AWS credentials from environment variables.

    Required env vars:
        - WF_FILE_STORAGE_AWS_ACCESS_KEY_ID
        - WF_FILE_STORAGE_AWS_SECRET_ACCESS_KEY
    Optional env vars:
        - WF_FILE_STORAGE_AWS_SESSION_TOKEN

    Returns:
        AWSCredentials with access key, secret key, and optional session token

    Raises:
        ValueError: If required credentials are not set
    """
    access_key_id = environment.wf_storage_bucket_aws_access_key_id()
    secret_access_key = environment.wf_storage_bucket_aws_secret_access_key()
    session_token = environment.wf_storage_bucket_aws_session_token()
    if access_key_id is not None and secret_access_key is None:
        raise ValueError("AWS credentials not set")
    kms_key = environment.wf_storage_bucket_aws_kms_key()
    region = environment.wf_storage_bucket_aws_region()

    return AWSCredentials(
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        session_token=session_token,
        kms_key=kms_key,
        region=region,
    )


def get_gcp_credentials() -> Optional[GCPCredentials]:
    """Retrieves GCP service account credentials from environment variables.

    Required env vars:
        - WF_FILE_STORAGE_GCP_CREDENTIALS_JSON_B64: JSON string containing service account info

    Returns:
        GCPCredentials object configured for GCS access

    Raises:
        ValueError: If credentials are missing or invalid JSON format
    """
    import json

    from google.oauth2 import service_account

    creds_json_b64 = environment.wf_storage_bucket_gcp_credentials_json_b64()
    if not creds_json_b64:
        return None

    try:
        creds_dict = json.loads(base64.b64decode(creds_json_b64).decode("utf-8"))
        return service_account.Credentials.from_service_account_info(creds_dict)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid GCP credentials JSON: {e}")


def get_azure_credentials() -> (
    Union[AzureConnectionCredentials, AzureAccountCredentials]
):
    """Retrieves Azure credentials from environment variables.
    Supports both connection string and account-based authentication.

    Required env vars (one of):
        - WF_FILE_STORAGE_AZURE_CONNECTION_STRING
        - WF_FILE_STORAGE_AZURE_ACCESS_KEY

    Returns:
        Either AzureConnectionCredentials or AzureAccountCredentials based on available env vars

    Raises:
        ValueError: If neither credential type is properly configured
    """
    connection_string = environment.wf_storage_bucket_azure_connection_string()
    if connection_string is not None:
        return AzureConnectionCredentials(connection_string=connection_string)
    access_key = environment.wf_storage_bucket_azure_access_key()
    if access_key is None:
        raise ValueError("Azure access key not set")
    account_url = environment.wf_storage_bucket_azure_account_url()
    return AzureAccountCredentials(access_key=access_key, account_url=account_url)
