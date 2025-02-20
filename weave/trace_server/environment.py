import os
from typing import Optional


def wf_clickhouse_host() -> str:
    """The host of the clickhouse server."""
    return os.environ.get("WF_CLICKHOUSE_HOST", "localhost")


def wf_clickhouse_port() -> int:
    """The port of the clickhouse server."""
    return int(os.environ.get("WF_CLICKHOUSE_PORT", 8123))


def wf_clickhouse_user() -> str:
    """The user of the clickhouse server."""
    return os.environ.get("WF_CLICKHOUSE_USER", "default")


def wf_clickhouse_pass() -> str:
    """The password of the clickhouse server."""
    return os.environ.get("WF_CLICKHOUSE_PASS", "")


def wf_clickhouse_database() -> str:
    """The name of the clickhouse database."""
    return os.environ.get("WF_CLICKHOUSE_DATABASE", "default")


# BYOB Settings


def wf_file_storage_uri() -> Optional[str]:
    """The storage bucket URI."""
    return os.environ.get("WF_FILE_STORAGE_URI")


def wf_storage_bucket_aws_access_key_id() -> Optional[str]:
    """The AWS access key ID."""
    return os.environ.get("WF_STORAGE_BUCKET_AWS_ACCESS_KEY_ID")


def wf_storage_bucket_aws_secret_access_key() -> Optional[str]:
    """The AWS secret access key."""
    return os.environ.get("WF_STORAGE_BUCKET_AWS_SECRET_ACCESS_KEY")


def wf_storage_bucket_aws_session_token() -> Optional[str]:
    """The AWS session token."""
    return os.environ.get("WF_STORAGE_BUCKET_AWS_SESSION_TOKEN")


def wf_storage_bucket_azure_connection_string() -> Optional[str]:
    """The Azure connection string."""
    return os.environ.get("WF_STORAGE_BUCKET_AZURE_CONNECTION_STRING")


def wf_storage_bucket_azure_account_url() -> Optional[str]:
    """The Azure account URL."""
    return os.environ.get("WF_STORAGE_BUCKET_AZURE_ACCOUNT_URL")


def wf_storage_bucket_azure_credential() -> Optional[str]:
    """The Azure credential."""
    return os.environ.get("WF_STORAGE_BUCKET_AZURE_CREDENTIAL")


def wf_storage_bucket_gcp_credentials_json() -> Optional[str]:
    """The GCP credentials JSON string."""
    return os.environ.get("WF_STORAGE_BUCKET_GCP_CREDENTIALS_JSON")
