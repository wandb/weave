"""Project version resolution with clean sync/async entry points."""

import asyncio
import logging
import threading
from typing import Any, Callable, Optional

import ddtrace

from weave.trace_server.project_version.providers.clickhouse_provider import (
    ClickHouseProjectVersionProvider,
)
from weave.trace_server.project_version.providers.memory_cache_provider import (
    PER_REPLICA_CACHE_SIZE,
    InMemoryCacheProvider,
)
from weave.trace_server.project_version.types import ProjectVersion, ProjectVersionMode

logger = logging.getLogger(__name__)

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
        self._cache = InMemoryCacheProvider(maxsize=cache_size)
        self._clickhouse_provider = ClickHouseProjectVersionProvider(
            ch_client_factory=ch_client_factory
        )
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

    def do_OTEL_shadow_write(self) -> bool:
        """Determine if OTEL shadow write should be performed.

        Returns:
            True if OTEL shadow write should be performed, False otherwise.
        """
        return self._mode != ProjectVersionMode.OFF

    def _apply_mode(
        self, resolved_version: ProjectVersion, is_write: bool
    ) -> ProjectVersion:
        """Apply mode-specific overrides to resolved version.

        Modes that skip DB queries return early in get_project_version_sync.
        This method only handles modes that override the resolved result.
        """
        if self._mode == ProjectVersionMode.CALLS_MERGED:
            return ProjectVersion.CALLS_MERGED_VERSION
        return resolved_version

    @ddtrace.tracer.wrap(name="project_version_resolver.resolve_version_sync")
    def _resolve_version_sync(self, project_id: str) -> ProjectVersion:
        """Resolve version through provider chain synchronously.

        TODO: Consider adding per-project locking to prevent thundering herd when
        multiple concurrent requests for the same uncached project arrive. This would
        ensure only the first request queries ClickHouse while others wait for the result.
        """
        # Try cache first
        cached = self._cache.get(project_id)
        if cached is not None:
            print(f":::ProjectVersion cache hit [{project_id}] >> {cached} <<")
            return cached

        version = self._clickhouse_provider.get_project_version_sync(project_id)

        print(f":::ProjectVersion ch query [{project_id}] >> {version} <<")

        # Cache non-empty projects
        if version != ProjectVersion.EMPTY_PROJECT:
            self._cache.set(project_id, version)

        # Set cache size tag on root span
        root_span = ddtrace.tracer.current_root_span()
        if root_span:
            root_span.set_tag("cache_size", self._cache.get_cache_size())

        return version

    @ddtrace.tracer.wrap(name="project_version_resolver.get_project_version_sync")
    def get_project_version_sync(
        self, project_id: str, is_write: bool = False
    ) -> ProjectVersion:
        """Get project version synchronously.

        This is the primary sync entry point. It uses actual sync methods
        directly (no asyncio.run or thread gymnastics).

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

        if self._mode == ProjectVersionMode.CALLS_COMPLETE_READ and not is_write:
            return ProjectVersion.CALLS_COMPLETE_VERSION

        version = self._resolve_version_sync(project_id)
        return self._apply_mode(version, is_write)

    @ddtrace.tracer.wrap(name="project_version_resolver.get_project_version_async")
    async def get_project_version_async(
        self, project_id: str, is_write: bool = False
    ) -> ProjectVersion:
        """Get project version asynchronously.

        This is the primary async entry point. Currently wraps the sync
        implementation since we don't have an async ClickHouse client.

        Detects if we're in an async context and uses a thread to avoid
        blocking if needed.

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

        if self._mode == ProjectVersionMode.CALLS_COMPLETE_READ and not is_write:
            return ProjectVersion.CALLS_COMPLETE_VERSION

        # Since we don't have an async ClickHouse client, we need to run
        # the sync version in a thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        version = await loop.run_in_executor(
            None, lambda: self._resolve_version_sync(project_id)
        )
        return self._apply_mode(version, is_write)
