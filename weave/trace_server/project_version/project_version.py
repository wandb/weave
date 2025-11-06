"""Project version resolution with clean sync/async entry points."""

import asyncio
import logging
import threading
from collections.abc import Callable
from typing import Any, Optional

import ddtrace
from cachetools import LRUCache

from weave.trace_server.project_version.clickhouse_project_version import (
    get_project_version_from_clickhouse,
)
from weave.trace_server.project_version.types import ProjectVersion, ProjectVersionMode

logger = logging.getLogger(__name__)

PER_REPLICA_CACHE_SIZE = 10_000

# Global singleton instance shared across all requests
_global_resolver: Optional["ProjectVersionResolver"] = None
_global_resolver_lock = threading.Lock()


class ProjectVersionResolver:
    """Resolves project versions by trying cache then ClickHouse.

    This is the main entry point for project version resolution. It provides
    two clear methods for consumers:
    - get_project_version_sync(): For sync contexts (uses sync methods directly)
    - get_project_version_async(): For async contexts (wraps sync for now)

    Resolution order:
        1. In-memory cache (fast)
        2. ClickHouse (queries both tables)

    Args:
        ch_client_factory: Callable that returns a ClickHouse client.
            This allows each thread to get its own thread-local client.
        cache_size: Size of the in-memory cache (defaults to 10,000).

    Examples:
        >>> # Sync usage (uses real sync methods)
        >>> resolver = ProjectVersionResolver(ch_client_factory=lambda: get_ch_client())
        >>> version = resolver.get_project_version_sync("my-project")

        >>> # Async usage (wraps sync for now since no async ClickHouse client)
        >>> resolver = ProjectVersionResolver(ch_client_factory=lambda: get_ch_client())
        >>> version = await resolver.get_project_version_async("my-project")
    """

    def __init__(
        self,
        ch_client_factory: Callable[[], Any],
        cache_size: int = PER_REPLICA_CACHE_SIZE,
    ):
        self._cache: LRUCache[str, ProjectVersion] = LRUCache(maxsize=cache_size)
        self._ch_client_factory = ch_client_factory
        self._mode = ProjectVersionMode.from_env()

    @classmethod
    def get_global_instance(
        cls,
        ch_client_factory: Callable[[], Any],
        cache_size: int = PER_REPLICA_CACHE_SIZE,
    ) -> "ProjectVersionResolver":
        """Get or create the global singleton resolver instance.

        This ensures the cache is shared across all requests rather than being
        per-request. The resolver is created once at application startup and
        reused for all subsequent requests.

        Args:
            ch_client_factory: Callable that returns a ClickHouse client.
            cache_size: Size of the in-memory cache (defaults to 10,000).

        Returns:
            The global singleton ProjectVersionResolver instance.
        """
        global _global_resolver
        with _global_resolver_lock:
            if _global_resolver is None:
                _global_resolver = cls(
                    ch_client_factory=ch_client_factory,
                    cache_size=cache_size,
                )
        return _global_resolver

    @ddtrace.tracer.wrap(name="project_version_resolver.resolve_version_sync")
    def _resolve_version_sync(self, project_id: str) -> ProjectVersion:
        """Resolve version through provider chain synchronously."""
        cached = self._cache.get(project_id)
        if cached is not None:
            return cached

        version = get_project_version_from_clickhouse(
            project_id, self._ch_client_factory
        )

        # Cache non-empty projects
        if version != ProjectVersion.EMPTY_PROJECT:
            self._cache[project_id] = version

        root_span = ddtrace.tracer.current_root_span()
        if root_span:
            root_span.set_tag("cache_size", len(self._cache))

        return version

    @ddtrace.tracer.wrap(name="project_version_resolver.get_project_version_sync")
    def get_project_version_sync(
        self, project_id: str, is_write: bool = False
    ) -> ProjectVersion:
        """Get project version synchronously.

        Args:
            project_id: The project identifier.
            is_write: Whether this is for a write operation.

        Returns:
            ProjectVersion enum indicating which table to use.
        """
        if self._mode == ProjectVersionMode.OFF:
            return ProjectVersion.CALLS_MERGED_VERSION

        if self._mode == ProjectVersionMode.CALLS_MERGED_READ and not is_write:
            return ProjectVersion.CALLS_MERGED_VERSION

        version = self._resolve_version_sync(project_id)

        # CALLS_MERGED mode queries DB for performance measurement but overrides result
        if self._mode == ProjectVersionMode.CALLS_MERGED:
            return ProjectVersion.CALLS_MERGED_VERSION

        return version

    @ddtrace.tracer.wrap(name="project_version_resolver.get_project_version_async")
    async def get_project_version_async(
        self, project_id: str, is_write: bool = False
    ) -> ProjectVersion:
        """Get project version asynchronously.

        TODO: update this with async clickhouse client

        Detects if we're in an async context and uses a thread to avoid
        blocking if needed.
        """
        if self._mode == ProjectVersionMode.OFF:
            return ProjectVersion.CALLS_MERGED_VERSION

        if self._mode == ProjectVersionMode.CALLS_MERGED_READ and not is_write:
            return ProjectVersion.CALLS_MERGED_VERSION

        # Since we don't have an async ClickHouse client, we need to run
        # the sync version in a thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        version = await loop.run_in_executor(
            None, lambda: self._resolve_version_sync(project_id)
        )

        # CALLS_MERGED mode queries DB for performance measurement but overrides result
        if self._mode == ProjectVersionMode.CALLS_MERGED:
            return ProjectVersion.CALLS_MERGED_VERSION

        return version
