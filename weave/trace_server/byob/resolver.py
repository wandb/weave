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

if TYPE_CHECKING:
    from weave.trace_server.file_storage import FileStorageClient
    from weave.trace_server.file_storage_uris import FileStorageURI


class StorageResolutionError(Exception):
    """Fail-closed signal from a BYOBResolver implementation."""


class BYOBResolver(abc.ABC):
    """Per-project storage routing contract.

    Concrete implementations resolve a `project_id` to a write client
    (with optional key prefix) and handle reads with dual-bucket fallback
    to the default client for pre-attachment data.
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


__all__ = ["BYOBResolver", "StorageResolutionError"]
