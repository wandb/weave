"""Construct a `FileStorageClient` from a `ResolvedStorageTarget`.

MVP: build a fresh client per resolve. Post-MVP introduces a pool keyed by
`(provider, bucket_name, region, credentials_fingerprint)`.
"""

from __future__ import annotations

from weave.trace_server.byob.models import (
    AmbientCredentials,
    AzureSasCredentials,
    GCSAccessTokenCredentials,
    ResolvedStorageTarget,
    S3TemporaryCredentials,
    StorageProvider,
    StorageResolutionError,
)
from weave.trace_server.file_storage import (
    AzureStorageClient,
    FileStorageClient,
    GCSStorageClient,
    S3StorageClient,
)
from weave.trace_server.file_storage_credentials import (
    AWSCredentials,
    AzureAccountCredentials,
)
from weave.trace_server.file_storage_uris import (
    AzureFileStorageURI,
    FileStorageURI,
    GCSFileStorageURI,
    S3FileStorageURI,
    URIParseError,
)


def build_storage_client(target: ResolvedStorageTarget) -> FileStorageClient:
    try:
        base_uri = FileStorageURI.parse_uri_str(target.bucket_uri)
    except URIParseError as e:
        raise StorageResolutionError(
            f"gorilla returned unparseable bucket_uri {target.bucket_uri!r} "
            f"for project {target.source_project_id!r}: {e!s}"
        ) from e
    if target.provider == StorageProvider.S3:
        if not isinstance(base_uri, S3FileStorageURI):
            raise StorageResolutionError(
                f"provider=s3 but bucket_uri parsed to {type(base_uri).__name__}"
            )
        return _build_s3_client(base_uri, target)
    if target.provider == StorageProvider.GCS:
        if not isinstance(base_uri, GCSFileStorageURI):
            raise StorageResolutionError(
                f"provider=gs but bucket_uri parsed to {type(base_uri).__name__}"
            )
        return _build_gcs_client(base_uri, target)
    if target.provider == StorageProvider.AZURE:
        if not isinstance(base_uri, AzureFileStorageURI):
            raise StorageResolutionError(
                f"provider=az but bucket_uri parsed to {type(base_uri).__name__}"
            )
        return _build_azure_client(base_uri, target)
    raise StorageResolutionError(f"unhandled provider {target.provider!r}")


def _build_s3_client(
    base_uri: S3FileStorageURI, target: ResolvedStorageTarget
) -> S3StorageClient:
    if isinstance(target.credentials, S3TemporaryCredentials):
        aws_creds: AWSCredentials = {
            "access_key_id": target.credentials.access_key_id,
            "secret_access_key": target.credentials.secret_access_key.get_secret_value(),
            "session_token": target.credentials.session_token.get_secret_value(),
            "region": target.region,
            "kms_key": None,
        }
        return S3StorageClient(base_uri, aws_creds)
    if isinstance(target.credentials, AmbientCredentials):
        aws_creds = {
            "access_key_id": None,
            "secret_access_key": None,
            "session_token": None,
            "region": target.region,
            "kms_key": None,
        }
        return S3StorageClient(base_uri, aws_creds)
    raise StorageResolutionError(
        f"S3 provider with unsupported credential_type "
        f"{target.credentials.credential_type!r}"
    )


def _build_gcs_client(
    base_uri: GCSFileStorageURI, target: ResolvedStorageTarget
) -> GCSStorageClient:
    if isinstance(target.credentials, (GCSAccessTokenCredentials, AmbientCredentials)):
        # GCSStorageClient accepts None credentials and falls back to ambient.
        # Access-token wiring is a post-MVP follow-up.
        return GCSStorageClient(base_uri, credentials=None)
    raise StorageResolutionError(
        f"GCS provider with unsupported credential_type "
        f"{target.credentials.credential_type!r}"
    )


def _build_azure_client(
    base_uri: AzureFileStorageURI, target: ResolvedStorageTarget
) -> AzureStorageClient:
    if isinstance(target.credentials, AzureSasCredentials):
        az_creds: AzureAccountCredentials = {
            "access_key": target.credentials.sas_token.get_secret_value(),
            "account_url": None,
        }
        return AzureStorageClient(base_uri, az_creds)
    raise StorageResolutionError(
        f"Azure provider with unsupported credential_type "
        f"{target.credentials.credential_type!r}"
    )
