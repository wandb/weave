import os
from unittest import mock

import pytest

from weave.trace_server.file_management import (
    get_aws_credentials,
    get_azure_credentials,
    get_gcp_credentials,
    parse_storage_uri,
    split_bucket_and_path,
)


def test_parse_storage_uri():
    # Test valid URIs
    assert parse_storage_uri("s3://bucket/path") == ("s3", "bucket/path")
    assert parse_storage_uri("gs://bucket/path") == ("gs", "bucket/path")
    assert parse_storage_uri("azure://container/path") == ("azure", "container/path")

    # Test invalid URIs
    with pytest.raises(ValueError, match="Invalid storage URI format"):
        parse_storage_uri("")
    with pytest.raises(ValueError, match="Invalid storage URI format"):
        parse_storage_uri("invalid-uri")
    with pytest.raises(ValueError, match="No path specified"):
        parse_storage_uri("s3://")
    with pytest.raises(ValueError, match="Unsupported storage provider"):
        parse_storage_uri("invalid://bucket/path")


def test_split_bucket_and_path():
    # Test valid paths
    assert split_bucket_and_path("bucket/path", "s3") == ("bucket", "path")
    assert split_bucket_and_path("bucket/path/nested", "gs") == ("bucket", "path/nested")
    assert split_bucket_and_path("container/blob/path", "azure") == ("container", "blob/path")

    # Test invalid paths
    with pytest.raises(ValueError, match="Invalid path format"):
        split_bucket_and_path("invalid-path", "s3")
    with pytest.raises(ValueError, match="Invalid path format"):
        split_bucket_and_path("", "gs")


def test_get_aws_credentials():
    # Test with all credentials set
    with mock.patch.dict(
        os.environ,
        {
            "WF_STORAGE_BUCKET_AWS_ACCESS_KEY_ID": "test-key",
            "WF_STORAGE_BUCKET_AWS_SECRET_ACCESS_KEY": "test-secret",
            "WF_STORAGE_BUCKET_AWS_SESSION_TOKEN": "test-token",
        },
    ):
        creds = get_aws_credentials()
        assert isinstance(creds, dict)
        assert creds["access_key_id"] == "test-key"
        assert creds["secret_access_key"] == "test-secret"
        assert creds["session_token"] == "test-token"

    # Test with required credentials only (no session token)
    with mock.patch.dict(
        os.environ,
        {
            "WF_STORAGE_BUCKET_AWS_ACCESS_KEY_ID": "test-key",
            "WF_STORAGE_BUCKET_AWS_SECRET_ACCESS_KEY": "test-secret",
        },
    ):
        creds = get_aws_credentials()
        assert isinstance(creds, dict)
        assert creds["access_key_id"] == "test-key"
        assert creds["secret_access_key"] == "test-secret"
        assert "session_token" not in creds

    # Test with missing required credentials
    with mock.patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="AWS credentials not set"):
            get_aws_credentials()


def test_get_azure_credentials():
    # Test with connection string
    with mock.patch.dict(
        os.environ,
        {
            "WF_STORAGE_BUCKET_AZURE_CONNECTION_STRING": "test-connection-string",
        },
    ):
        creds = get_azure_credentials()
        assert isinstance(creds, dict)
        # Check for connection string credentials structure
        assert "connection_string" in creds
        assert creds["connection_string"] == "test-connection-string"

    # Test with account credentials
    with mock.patch.dict(
        os.environ,
        {
            "WF_STORAGE_BUCKET_AZURE_ACCOUNT_URL": "test-url",
            "WF_STORAGE_BUCKET_AZURE_CREDENTIAL": "test-credential",
        },
    ):
        creds = get_azure_credentials()
        assert isinstance(creds, dict)
        # Check for account credentials structure
        assert "account_url" in creds
        assert "credential" in creds
        assert creds["account_url"] == "test-url"
        assert creds["credential"] == "test-credential"

    # Test with missing credentials
    with mock.patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="Azure credentials not set"):
            get_azure_credentials()


def test_get_gcp_credentials():
    test_creds_json = '''
    {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "test-key-id",
        "private_key": "test-key",
        "client_email": "test@test.com",
        "client_id": "test-client-id"
    }
    '''

    # Test with valid JSON
    with mock.patch.dict(
        os.environ,
        {
            "WF_STORAGE_BUCKET_GCP_CREDENTIALS_JSON": test_creds_json,
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
            "WF_STORAGE_BUCKET_GCP_CREDENTIALS_JSON": "invalid-json",
        },
    ):
        with pytest.raises(ValueError, match="Invalid GCP credentials JSON"):
            get_gcp_credentials()
