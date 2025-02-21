import base64
from typing import Optional, TypedDict, Union

from azure.core.credentials import TokenCredential
from google.oauth2.credentials import Credentials as GCPCredentials

from weave.trace_server import environment


class AWSCredentials(TypedDict, total=False):
    """AWS authentication credentials for S3 access.
    The session_token is optional and only required for temporary credentials."""

    access_key_id: str
    secret_access_key: str
    session_token: Optional[str]


class AzureConnectionCredentials(TypedDict):
    """Azure authentication using connection string format.
    This is the preferred method for Azure authentication."""

    connection_string: str


class AzureAccountCredentials(TypedDict):
    """Azure authentication using account-based credentials.
    Supports SAS tokens, connection strings, or Azure credential objects."""

    credential: Union[str, TokenCredential]


def get_aws_credentials() -> AWSCredentials:
    """Retrieves AWS credentials from environment variables.

    Required env vars:
        - WF_FILE_STORAGE_BUCKET_AWS_ACCESS_KEY_ID
        - WF_FILE_STORAGE_BUCKET_AWS_SECRET_ACCESS_KEY
    Optional env vars:
        - WF_FILE_STORAGE_BUCKET_AWS_SESSION_TOKEN

    Returns:
        AWSCredentials with access key, secret key, and optional session token

    Raises:
        ValueError: If required credentials are not set
    """
    access_key_id = environment.wf_storage_bucket_aws_access_key_id()
    secret_access_key = environment.wf_storage_bucket_aws_secret_access_key()
    session_token = environment.wf_storage_bucket_aws_session_token()
    if access_key_id is None or secret_access_key is None:
        raise ValueError("AWS credentials not set")

    creds: AWSCredentials = {
        "access_key_id": access_key_id,
        "secret_access_key": secret_access_key,
    }
    if session_token is not None:
        creds["session_token"] = session_token
    return creds


def get_gcp_credentials() -> GCPCredentials:
    """Retrieves GCP service account credentials from environment variables.

    Required env vars:
        - WF_FILE_STORAGE_BUCKET_GCP_CREDENTIALS_JSON: JSON string containing service account info

    Returns:
        GCPCredentials object configured for GCS access

    Raises:
        ValueError: If credentials are missing or invalid JSON format
    """
    import json

    from google.oauth2 import service_account

    creds_json = environment.wf_storage_bucket_gcp_credentials_json()
    if not creds_json:
        raise ValueError(
            "No GCP credentials found. Set WF_FILE_STORAGE_BUCKET_GCP_CREDENTIALS_JSON environment variable."
        )

    try:
        creds_dict = json.loads(creds_json)
        return service_account.Credentials.from_service_account_info(creds_dict)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid GCP credentials JSON: {e}")


def get_azure_credentials() -> (
    Union[AzureConnectionCredentials, AzureAccountCredentials]
):
    """Retrieves Azure credentials from environment variables.
    Supports both connection string and account-based authentication.

    Required env vars (one of):
        - WF_FILE_STORAGE_BUCKET_AZURE_CONNECTION_STRING
        - WF_FILE_STORAGE_BUCKET_AZURE_CREDENTIAL_B64 (base64 encoded)

    Returns:
        Either AzureConnectionCredentials or AzureAccountCredentials based on available env vars

    Raises:
        ValueError: If neither credential type is properly configured
    """
    connection_string = environment.wf_storage_bucket_azure_connection_string()
    if connection_string is not None:
        return AzureConnectionCredentials(connection_string=connection_string)
    b64_credential = environment.wf_storage_bucket_azure_credential()
    if b64_credential is None:
        raise ValueError("Azure credentials not set")
    credential = base64.b64decode(b64_credential).decode("utf-8")
    return AzureAccountCredentials(credential=credential)
