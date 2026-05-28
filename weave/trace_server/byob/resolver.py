"""Abstract per-project storage resolver contract for weave-trace.

Defines the interface only. Concrete implementations live in
`services/weave-trace` (in `wandb/core`) where the gorilla integration,
STS assume-role dance, credential caching, and provider-specific
client building happen.

Two storage paths now exist in weave-trace; operators pick one:

1. Single-bucket `WF_FILE_STORAGE_URI` (existing; pass no resolver).
   Right for single-tenant self-hosted clusters.
2. Per-project BYOB via a `BYOBResolver` implementation. Right for mtsaas.
   The concrete implementation reads `Entity.settings.storageBucketInfo`
   from gorilla and does its own STS assume-role.

Implementations must be **fail-closed**: raise `StorageResolutionError`
rather than silently route to the wrong bucket when uncertain.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from pydantic import BaseModel, SecretStr

if TYPE_CHECKING:
    from weave.trace_server.file_storage import FileStorageClient
    from weave.trace_server.file_storage_uris import FileStorageURI


class StorageResolutionError(Exception):
    """Fail-closed signal from a BYOBResolver implementation."""


class ExportStorageCredentials(BaseModel):
    """STS-derived S3 credentials for `INSERT INTO FUNCTION s3()`.

    Distinct from the per-blob `FileStorageClient` path: the export
    handler builds a CH NAMED COLLECTION from these and never proxies
    bytes itself.
    """

    access_key_id: str
    secret_access_key: SecretStr
    session_token: SecretStr


class ResolvedExportTarget(BaseModel):
    """Per-team S3 destination plus temporary credentials for a bulk export."""

    bucket_uri: str
    bucket_name: str
    region: str | None = None
    credentials: ExportStorageCredentials
    source_project_id: str


class BYOBResolver(abc.ABC):
    """Per-project storage routing contract.

    Concrete implementations resolve a `project_id` to a write client
    (with optional key prefix), handle reads with dual-bucket fallback
    to the default client for pre-attachment data, and produce STS-backed
    targets for the bulk-export path.
    """

    @abc.abstractmethod
    def resolve_write(
        self,
        project_id: str,
        default_client: FileStorageClient | None,
    ) -> tuple[FileStorageClient | None, str]:
        """Pick `(storage_client, key_prefix)` for writes to `project_id`.

        Returns `(default_client, "")` when the project routes to default
        (no BYOB attached). Raises `StorageResolutionError` when the
        resolver cannot decide safely.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def resolve_read(
        self,
        project_id: str | None,
        stored_uri: FileStorageURI,
        default_client: FileStorageClient | None,
    ) -> bytes:
        """Read a file chunk at `stored_uri`.

        For BYOB-attached projects, implementations should try the team
        bucket first and fall back to `default_client` on not-found
        (pre-attachment data). Raises `StorageResolutionError` on
        unrecoverable failures.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def resolve_export_target(self, project_id: str) -> ResolvedExportTarget:
        """Resolve a project to STS creds plus bucket for `INSERT INTO FUNCTION s3()`.

        Distinct from `resolve_write`: the bulk-export path needs raw
        credentials to interpolate into a ClickHouse NAMED COLLECTION
        backing a detached `INSERT INTO FUNCTION s3()` query, not a
        per-blob client proxy. Raises `StorageResolutionError` when no
        team bucket is attached or when the resolver cannot mint creds.
        """
        raise NotImplementedError


__all__ = [
    "BYOBResolver",
    "ExportStorageCredentials",
    "ResolvedExportTarget",
    "StorageResolutionError",
]
