from datetime import datetime, timezone
from unittest import mock

from weave.trace_server.file_storage import AzureStorageClient
from weave.trace_server.file_storage_uris import AzureFileStorageURI


def test_workload_identity_creates_blob_service_client():
    base_uri = AzureFileStorageURI.parse_uri_str("az://account/container")
    credential = object()

    with mock.patch(
        "weave.trace_server.file_storage.BlobServiceClient"
    ) as blob_service_client:
        client = AzureStorageClient(
            base_uri,
            {"default_credential": credential},
        )
        client._get_client("account")

    blob_service_client.assert_called_once_with(
        account_url="https://account.blob.core.windows.net/",
        credential=credential,
        connection_timeout=10,
        read_timeout=30,
    )


def test_workload_identity_presign_uses_user_delegation_key():
    base_uri = AzureFileStorageURI.parse_uri_str("az://account/container")
    uri = base_uri.with_path("exports/result.json")
    credential = object()
    service_client = mock.Mock()
    service_client.account_name = "account"
    service_client.get_user_delegation_key.return_value = "delegation-key"
    service_client.get_container_client.return_value.get_blob_client.return_value.url = "https://account.blob.core.windows.net/container/exports/result.json"

    client = AzureStorageClient(base_uri, {"default_credential": credential})
    with (
        mock.patch.object(client, "_get_client", return_value=service_client),
        mock.patch(
            "weave.trace_server.file_storage.generate_blob_sas",
            return_value="signed-query",
        ) as generate_blob_sas,
    ):
        url = client.presign_read(uri, ttl=3600)

    assert url == (
        "https://account.blob.core.windows.net/container/exports/result.json"
        "?signed-query"
    )
    key_start, key_expiry = service_client.get_user_delegation_key.call_args.args
    assert key_start.tzinfo == timezone.utc
    assert key_expiry.tzinfo == timezone.utc
    assert key_start < datetime.now(timezone.utc) < key_expiry
    sas_arguments = generate_blob_sas.call_args.kwargs
    sas_arguments["permission"] = str(sas_arguments["permission"])
    assert sas_arguments == {
        "account_name": "account",
        "container_name": "container",
        "blob_name": "exports/result.json",
        "user_delegation_key": "delegation-key",
        "permission": "r",
        "expiry": key_expiry,
    }


def test_account_key_presign_remains_supported():
    base_uri = AzureFileStorageURI.parse_uri_str("az://account/container")
    uri = base_uri.with_path("exports/result.json")
    service_client = mock.Mock()
    service_client.account_name = "account"
    service_client.credential.account_key = "account-key"
    service_client.get_container_client.return_value.get_blob_client.return_value.url = "https://account.blob.core.windows.net/container/exports/result.json"

    client = AzureStorageClient(
        base_uri,
        {"access_key": "account-key", "account_url": None},
    )
    with (
        mock.patch.object(client, "_get_client", return_value=service_client),
        mock.patch(
            "weave.trace_server.file_storage.generate_blob_sas",
            return_value="signed-query",
        ) as generate_blob_sas,
    ):
        url = client.presign_read(uri, ttl=3600)

    assert url == (
        "https://account.blob.core.windows.net/container/exports/result.json"
        "?signed-query"
    )
    sas_arguments = generate_blob_sas.call_args.kwargs
    sas_arguments["permission"] = str(sas_arguments["permission"])
    assert sas_arguments == {
        "account_name": "account",
        "container_name": "container",
        "blob_name": "exports/result.json",
        "account_key": "account-key",
        "permission": "r",
        "expiry": sas_arguments["expiry"],
    }
    service_client.get_user_delegation_key.assert_not_called()
