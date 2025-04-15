import base64
import os
from unittest import mock

import pytest

from weave.trace_server.file_storage_credentials import (
    get_aws_credentials,
    get_azure_credentials,
    get_gcp_credentials,
)


def test_get_aws_credentials():
    # Test with all credentials set
    with mock.patch.dict(
        os.environ,
        {
            "WF_FILE_STORAGE_AWS_ACCESS_KEY_ID": "test-key",
            "WF_FILE_STORAGE_AWS_SECRET_ACCESS_KEY": "test-secret",
            "WF_FILE_STORAGE_AWS_SESSION_TOKEN": "test-token",
            "WF_FILE_STORAGE_AWS_REGION": "us-east-1",
            "WF_FILE_STORAGE_AWS_KMS_KEY": "test-kms-key",
        },
    ):
        creds = get_aws_credentials()
        assert creds == {
            "access_key_id": "test-key",
            "secret_access_key": "test-secret",
            "session_token": "test-token",
            "region": "us-east-1",
            "kms_key": "test-kms-key",
        }

    # Test with required credentials only (no session token)
    with mock.patch.dict(
        os.environ,
        {
            "WF_FILE_STORAGE_AWS_ACCESS_KEY_ID": "test-key",
            "WF_FILE_STORAGE_AWS_SECRET_ACCESS_KEY": "test-secret",
        },
    ):
        creds = get_aws_credentials()
        assert creds == {
            "access_key_id": "test-key",
            "secret_access_key": "test-secret",
            "session_token": None,
            "region": None,
            "kms_key": None,
        }

    # Test with missing required credentials
    with mock.patch.dict(
        os.environ,
        {
            "WF_FILE_STORAGE_AWS_ACCESS_KEY_ID": "key-id",
        },
        clear=True,
    ):
        with pytest.raises(ValueError, match="AWS credentials not set"):
            get_aws_credentials()


def test_get_azure_credentials():
    # Test with connection string
    with mock.patch.dict(
        os.environ,
        {
            "WF_FILE_STORAGE_AZURE_CONNECTION_STRING": "test-connection-string",
        },
    ):
        creds = get_azure_credentials()
        assert creds == {
            "connection_string": "test-connection-string",
        }

    # Test with account credentials
    with mock.patch.dict(
        os.environ,
        {
            "WF_FILE_STORAGE_AZURE_ACCESS_KEY": "test-credential",
        },
    ):
        creds = get_azure_credentials()
        assert creds == {
            "access_key": "test-credential",
            "account_url": None,
        }

    with mock.patch.dict(
        os.environ,
        {
            "WF_FILE_STORAGE_AZURE_ACCESS_KEY": "test-credential",
            "WF_FILE_STORAGE_AZURE_ACCOUNT_URL": "some_account_url",
        },
    ):
        creds = get_azure_credentials()
        assert creds == {
            "access_key": "test-credential",
            "account_url": "some_account_url",
        }

    # Test with missing credentials
    with mock.patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="Azure access key not set"):
            get_azure_credentials()


def test_get_gcp_credentials():
    test_creds_json = """
    {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "test-key-id",
        "private_key": "test-key",
        "client_email": "test@test.com",
        "client_id": "test-client-id"
    }
    """

    # Test with valid JSON
    with mock.patch.dict(
        os.environ,
        {
            "WF_FILE_STORAGE_GCP_CREDENTIALS_JSON_B64": base64.b64encode(
                test_creds_json.encode()
            ).decode(),
        },
    ):
        with mock.patch("google.oauth2.service_account.Credentials") as mock_creds:
            get_gcp_credentials()
            mock_creds.from_service_account_info.assert_called_once()

    # Test with missing credentials
    with mock.patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="No GCP credentials found"):
            get_gcp_credentials()

    # Test with invalid JSON
    with mock.patch.dict(
        os.environ,
        {
            "WF_FILE_STORAGE_GCP_CREDENTIALS_JSON_B64": "invalid-json",
            "WF_FILE_STORAGE_GCP_CREDENTIALS_JSON_B64": base64.b64encode(
                b"invalid-json"
            ).decode(),
        },
    ):
        with pytest.raises(ValueError, match="Invalid GCP credentials JSON"):
            get_gcp_credentials()
