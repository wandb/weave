"""Per-project (team-level) BYOB storage resolver.

Two storage paths now exist in weave-trace; operators pick one:

1. `WF_FILE_STORAGE_URI` (existing, single bucket per server). Right for
   single-tenant self-hosted clusters - leave `WF_BYOB_RESOLVER_ENABLED` off.
2. `WF_BYOB_RESOLVER_ENABLED` (this module, additive). Resolves
   `project_id -> team-owned bucket` via gorilla, with dual-read fallback to
   `WF_FILE_STORAGE_URI` for pre-flip files. Right for mtsaas.

Maps `project_id -> ResolvedStorageTarget`. Implements the fail-closed truth
table from the spec (§4.3). Cache state, last known status per project, and
TTL handling live here. Singleflight, sweeper, and pool are post-MVP.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from weave.trace_server.byob.models import (
    ResolvedStorageTarget,
    StorageResolutionError,
    StorageResolvePurpose,
    StorageResolveStatus,
)

logger = logging.getLogger(__name__)

BYOB_RESOLVER_TTL_SECONDS = 300
BYOB_RESOLVER_CACHE_MAX_ENTRIES = 10_000
CREDENTIAL_EXPIRY_SKEW_SECONDS = 60


class GorillaResolverTransport(Protocol):
    """Transport that fetches a `ResolvedStorageTarget` from gorilla.

    Raises any exception on failure - the resolver converts it into a
    fail-closed `StorageResolutionError` after applying the truth table.
    """

    def resolve(self, project_id: str) -> ResolvedStorageTarget: ...


@dataclass
class _CacheEntry:
    target: ResolvedStorageTarget
    expires_at_monotonic: float


class StorageResolver:
    """Resolves a `project_id` to a `ResolvedStorageTarget`, fail-closed.

    Single in-process cache keyed by `project_id`. One lock around both the
    cache and the last-status map. TTL is `min(ttl_seconds, expiry - skew)`.
    """

    def __init__(
        self,
        transport: GorillaResolverTransport,
        ttl_seconds: int = BYOB_RESOLVER_TTL_SECONDS,
        max_entries: int = BYOB_RESOLVER_CACHE_MAX_ENTRIES,
        expiry_skew_seconds: int = CREDENTIAL_EXPIRY_SKEW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._expiry_skew_seconds = expiry_skew_seconds
        self._clock = clock
        self._cache: dict[str, _CacheEntry] = {}
        self._last_status: dict[str, StorageResolveStatus] = {}
        self._lock = threading.Lock()

    def resolve(
        self,
        project_id: str,
        purpose: StorageResolvePurpose,
    ) -> ResolvedStorageTarget:
        # MVP: every purpose routes the same way. Reserved for post-MVP.
        if purpose not in {
            StorageResolvePurpose.WRITE,
            StorageResolvePurpose.READ,
            StorageResolvePurpose.INTERNAL_JOB,
        }:
            raise StorageResolutionError(f"unknown purpose: {purpose!r}")

        now = self._clock()
        with self._lock:
            entry = self._cache.get(project_id)
            if entry is not None and entry.expires_at_monotonic > now:
                return entry.target
            last_status = self._last_status.get(project_id)
            stale_entry = entry

        try:
            target = self._transport.resolve(project_id)
        except Exception as e:
            return self._handle_transport_failure(
                project_id=project_id,
                last_status=last_status,
                stale_entry=stale_entry,
                cause=e,
            )

        self._store_entry(project_id, target, now)
        return target

    def _handle_transport_failure(
        self,
        project_id: str,
        last_status: StorageResolveStatus | None,
        stale_entry: _CacheEntry | None,
        cause: Exception,
    ) -> ResolvedStorageTarget:
        if last_status is None:
            raise StorageResolutionError(
                f"gorilla unreachable, no last-known status for project {project_id}"
            ) from cause
        if last_status == StorageResolveStatus.DEFAULT and stale_entry is not None:
            # Ambient creds never expire - safe to keep using the stale default.
            return stale_entry.target
        if last_status == StorageResolveStatus.BYOB:
            raise StorageResolutionError(
                f"gorilla unreachable for BYOB project {project_id}"
            ) from cause
        if last_status == StorageResolveStatus.DEFAULT:
            # Last status was default but we evicted the entry. Fail closed -
            # we cannot synthesize a default target without the transport.
            raise StorageResolutionError(
                f"gorilla unreachable and default target evicted for project {project_id}"
            ) from cause
        raise StorageResolutionError(
            f"gorilla unreachable, unhandled last status {last_status!r} for project {project_id}"
        ) from cause

    def _store_entry(
        self,
        project_id: str,
        target: ResolvedStorageTarget,
        now: float,
    ) -> None:
        cache_seconds = self._cache_seconds_for(target)
        with self._lock:
            if len(self._cache) >= self._max_entries and project_id not in self._cache:
                # Soft cap exceeded - raise loudly per spec §3.
                raise StorageResolutionError(
                    f"BYOB resolver cache exceeded max entries ({self._max_entries})"
                )
            self._cache[project_id] = _CacheEntry(
                target=target,
                expires_at_monotonic=now + cache_seconds,
            )
            self._last_status[project_id] = target.status

    def _cache_seconds_for(self, target: ResolvedStorageTarget) -> float:
        if target.credentials_expires_at is None:
            return float(self._ttl_seconds)
        seconds_until_expiry = (
            target.credentials_expires_at - datetime.now(timezone.utc)
        ).total_seconds() - self._expiry_skew_seconds
        return max(0.0, min(float(self._ttl_seconds), seconds_until_expiry))
