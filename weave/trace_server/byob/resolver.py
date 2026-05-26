"""Per-project (team-level) BYOB storage resolver for mtsaas.

Two storage paths now exist in weave-trace; operators pick one:

1. `WF_FILE_STORAGE_URI` (existing, single bucket per server). Right for
   single-tenant self-hosted clusters. The BYOB resolver stays disabled.
2. `WF_BYOB_GORILLA_BASE_URL` (this module, additive). Setting it enables
   per-project resolution via gorilla, with dual-read fallback to
   `WF_FILE_STORAGE_URI` for pre-flip files. Right for mtsaas.

Implements the fail-closed truth table from the spec (§4.3). Cache state,
last known status per project, and TTL handling live here. Singleflight,
sweeper, and pool are post-MVP.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial

from weave.trace_server import environment as wf_env
from weave.trace_server.byob.client_factory import build_storage_client
from weave.trace_server.byob.gorilla import (
    GorillaUnknownProjectError,
    fetch_storage_target,
)
from weave.trace_server.byob.types import (
    ResolvedStorageTarget,
    StorageResolutionError,
    StorageResolvePurpose,
    StorageResolveStatus,
)
from weave.trace_server.file_storage import (
    FileStorageClient,
    FileStorageReadError,
    is_not_found_error,
    read_from_bucket,
)
from weave.trace_server.file_storage_uris import FileStorageURI

logger = logging.getLogger(__name__)

BYOB_RESOLVER_TTL_SECONDS = 300
BYOB_RESOLVER_CACHE_MAX_ENTRIES = 10_000
CREDENTIAL_EXPIRY_SKEW_SECONDS = 60

ResolveFn = Callable[[str], ResolvedStorageTarget]


@dataclass
class _CacheEntry:
    target: ResolvedStorageTarget
    expires_at_monotonic: float


class StorageResolver:
    """Resolves a `project_id` to a `ResolvedStorageTarget`, fail-closed.

    `resolve_fn` is anything that returns a target or raises. Single
    in-process cache keyed by `project_id`. TTL is
    `min(ttl_seconds, credential_expiry - skew)`.
    """

    def __init__(
        self,
        resolve_fn: ResolveFn,
        ttl_seconds: int = BYOB_RESOLVER_TTL_SECONDS,
        max_entries: int = BYOB_RESOLVER_CACHE_MAX_ENTRIES,
        expiry_skew_seconds: int = CREDENTIAL_EXPIRY_SKEW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._resolve_fn = resolve_fn
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._expiry_skew_seconds = expiry_skew_seconds
        self._clock = clock
        self._cache: dict[str, _CacheEntry] = {}
        self._last_status: dict[str, StorageResolveStatus] = {}
        self._lock = threading.Lock()

    def resolve(
        self, project_id: str, purpose: StorageResolvePurpose
    ) -> ResolvedStorageTarget:
        del purpose  # MVP: reserved for post-MVP routing.
        now = self._clock()
        with self._lock:
            entry = self._cache.get(project_id)
            if entry is not None and entry.expires_at_monotonic > now:
                return entry.target
            last_status = self._last_status.get(project_id)
            stale_entry = entry

        try:
            target = self._resolve_fn(project_id)
        except Exception as e:
            return self._handle_failure(project_id, last_status, stale_entry, e)

        self._store(project_id, target, now)
        return target

    def _handle_failure(
        self,
        project_id: str,
        last_status: StorageResolveStatus | None,
        stale_entry: _CacheEntry | None,
        cause: Exception,
    ) -> ResolvedStorageTarget:
        if last_status == StorageResolveStatus.DEFAULT and stale_entry is not None:
            # Ambient creds never expire; safe to keep using the stale default.
            return stale_entry.target
        if last_status == StorageResolveStatus.BYOB:
            raise StorageResolutionError(
                f"gorilla unreachable for BYOB project {project_id}"
            ) from cause
        raise StorageResolutionError(
            f"gorilla unreachable, no last-known status for project {project_id}"
        ) from cause

    def _store(
        self, project_id: str, target: ResolvedStorageTarget, now: float
    ) -> None:
        cache_seconds = self._cache_seconds_for(target)
        with self._lock:
            if len(self._cache) >= self._max_entries and project_id not in self._cache:
                raise StorageResolutionError(
                    f"BYOB resolver cache exceeded max entries ({self._max_entries})"
                )
            self._cache[project_id] = _CacheEntry(target, now + cache_seconds)
            self._last_status[project_id] = target.status

    def _cache_seconds_for(self, target: ResolvedStorageTarget) -> float:
        if target.credentials_expires_at is None:
            return float(self._ttl_seconds)
        seconds_until_expiry = (
            target.credentials_expires_at - datetime.now(timezone.utc)
        ).total_seconds() - self._expiry_skew_seconds
        return max(0.0, min(float(self._ttl_seconds), seconds_until_expiry))


def maybe_build_storage_resolver_from_env() -> StorageResolver | None:
    """Return a `StorageResolver` if `WF_BYOB_GORILLA_BASE_URL` is set, else None.

    Single env var: presence of the gorilla URL is the enable signal. Right
    for mtsaas; single-tenant deployments leave it unset and use the existing
    `WF_FILE_STORAGE_URI` path unchanged.
    """
    base_url = wf_env.wf_byob_gorilla_base_url()
    if not base_url:
        logger.info(
            "BYOB per-project resolver disabled. Using single-bucket "
            "WF_FILE_STORAGE_URI path."
        )
        return None
    if not wf_env.wf_file_storage_uri():
        logger.warning(
            "BYOB per-project resolver enabled but WF_FILE_STORAGE_URI is unset. "
            "Dual-read fallback for pre-BYOB files will fail."
        )
    logger.info("BYOB per-project resolver enabled. gorilla=%s", base_url)
    return StorageResolver(resolve_fn=partial(fetch_storage_target, base_url))


def resolve_write_target(
    resolver: StorageResolver | None,
    default_client: FileStorageClient | None,
    project_id: str,
) -> tuple[FileStorageClient | None, str]:
    """Pick the storage client + key prefix for a write to `project_id`.

    Returns `(client, key_prefix)`. When the resolver is off or returns
    DEFAULT, `key_prefix=""`. Raises `StorageResolutionError` when the
    resolver fails closed.
    """
    if resolver is None:
        return default_client, ""
    target = resolver.resolve(project_id, StorageResolvePurpose.WRITE)
    if target.status == StorageResolveStatus.BYOB:
        return build_storage_client(target), target.key_prefix
    if target.status == StorageResolveStatus.DEFAULT:
        return default_client, ""
    raise StorageResolutionError(f"unknown status {target.status!r}")


def resolve_read(
    resolver: StorageResolver | None,
    default_client: FileStorageClient | None,
    stored_uri: FileStorageURI,
    project_id: str | None,
) -> bytes:
    """Read a file chunk, with dual-read fallback for BYOB projects.

    For a BYOB project, tries the team bucket at the same object path
    first. On not-found, falls back to the stored URI (where it actually
    landed). Bounded by the stored URI: at most one extra GET.
    """
    if resolver is None or project_id is None:
        if default_client is None:
            raise FileStorageReadError("File storage client is not configured")
        return read_from_bucket(default_client, stored_uri)

    target = resolver.resolve(project_id, StorageResolvePurpose.READ)
    if target.status == StorageResolveStatus.DEFAULT:
        if default_client is None:
            raise FileStorageReadError("File storage client is not configured")
        return read_from_bucket(default_client, stored_uri)

    byob_client = build_storage_client(target)
    team_uri = byob_client.base_uri.with_path(stored_uri.path)
    try:
        return byob_client.read(team_uri)
    except Exception as e:
        if not is_not_found_error(e):
            raise FileStorageReadError(
                f"Failed to read file from {team_uri}: {e!s}"
            ) from e
    logger.info(
        "BYOB dual-read fallback: %s not in team bucket, retrying from %s",
        team_uri,
        stored_uri,
    )
    if default_client is None:
        raise FileStorageReadError(
            f"BYOB miss for {team_uri} and no default client configured "
            f"(set WF_FILE_STORAGE_URI to enable dual-read fallback)"
        )
    return read_from_bucket(default_client, stored_uri)


__all__ = [
    "BYOB_RESOLVER_CACHE_MAX_ENTRIES",
    "BYOB_RESOLVER_TTL_SECONDS",
    "CREDENTIAL_EXPIRY_SKEW_SECONDS",
    "GorillaUnknownProjectError",
    "ResolveFn",
    "StorageResolver",
    "maybe_build_storage_resolver_from_env",
    "resolve_read",
    "resolve_write_target",
]
