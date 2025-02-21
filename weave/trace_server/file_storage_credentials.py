import base64
from typing import Optional, TypedDict, Union

from azure.core.credentials import TokenCredential
from google.oauth2.credentials import Credentials as GCPCredentials

from weave.trace_server import environment


class AWSCredentials(TypedDict, total=False):
    """Type for AWS credentials dictionary."""

    access_key_id: str
    secret_access_key: str
    session_token: Optional[str]  # Optional


class AzureConnectionCredentials(TypedDict):
    """Type for Azure connection string credentials."""

    connection_string: str


class AzureAccountCredentials(TypedDict):
    """Type for Azure account credentials."""

    account_url: str
    credential: Union[
        str, TokenCredential
    ]  # Can be connection string, SAS token, or credential object


AllCredentials = Union[
    AWSCredentials, GCPCredentials, AzureConnectionCredentials, AzureAccountCredentials
]


def get_aws_credentials() -> AWSCredentials:
    """
    Returns AWS credentials needed for S3 access.

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

    creds: AWSCredentials = {
        "access_key_id": access_key_id,
        "secret_access_key": secret_access_key,
    }
    if session_token is not None:
        creds["session_token"] = session_token
    return creds


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
    b64_credential = environment.wf_storage_bucket_azure_credential()
    if account_url is None or b64_credential is None:
        raise ValueError("Azure credentials not set")
    credential = base64.b64decode(b64_credential).decode("utf-8")
    return AzureAccountCredentials(account_url=account_url, credential=credential)
