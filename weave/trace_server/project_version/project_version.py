"""Project version resolution with clean sync/async entry points.

This module determines which database table (calls_merged vs calls_complete) to use
for each project. It maintains a shared in-memory cache across all requests.

Usage:
    1. At application startup, initialize once:
       >>> from weave.trace_server.project_version import init_resolver
       >>> init_resolver(ch_client_factory=lambda: get_ch_client())

    2. Everywhere else, just call the functions:
       >>> from weave.trace_server.project_version import get_project_version_sync
       >>> version = get_project_version_sync(project_id)
       >>>
       >>> # Or async:
       >>> from weave.trace_server.project_version import get_project_version_async
       >>> version = await get_project_version_async(project_id)

The module maintains a singleton resolver internally that ensures:
    - One shared cache across all requests (not per-request)
    - Thread-safe initialization
    - Fails fast if used before initialization
"""

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

# Module-level singleton (internal, not exported)
_resolver: Optional["ProjectVersionResolver"] = None
_resolver_lock = threading.Lock()


# Public API - Module-level functions


def init_resolver(
    ch_client_factory: Callable[[], Any],
    cache_size: int = PER_REPLICA_CACHE_SIZE,
) -> None:
    """Initialize the project version resolver.

    Call this once at application startup. Subsequent calls are ignored
    (the first initialization wins).

    Args:
        ch_client_factory: Callable that returns a ClickHouse client.
        cache_size: Size of the in-memory cache (defaults to 10,000).
    """
    global _resolver
    with _resolver_lock:
        if _resolver is None:
            _resolver = ProjectVersionResolver(
                ch_client_factory=ch_client_factory,
                cache_size=cache_size,
            )


def get_project_version_sync(project_id: str) -> ProjectVersion:
    """Get project version synchronously.

    Args:
        project_id: The project identifier.

    Returns:
        ProjectVersion enum indicating which table to use.

    Raises:
        RuntimeError: If init_resolver() has not been called yet.
    """
    if _resolver is None:
        raise RuntimeError(
            "init_resolver() must be called before get_project_version_sync()"
        )
    return _resolver.get_project_version_sync(project_id)


async def get_project_version_async(project_id: str) -> ProjectVersion:
    """Get project version asynchronously.

    Args:
        project_id: The project identifier.

    Returns:
        ProjectVersion enum indicating which table to use.

    Raises:
        RuntimeError: If init_resolver() has not been called yet.
    """
    if _resolver is None:
        raise RuntimeError(
            "init_resolver() must be called before get_project_version_async()"
        )
    return await _resolver.get_project_version_async(project_id)


# Internal implementation


class ProjectVersionResolver:
    """Internal resolver class. Use module-level functions instead.

    Resolution order:
        1. In-memory cache (fast)
        2. ClickHouse (queries both tables)

    Args:
        ch_client_factory: Callable that returns a ClickHouse client.
            This allows each thread to get its own thread-local client.
        cache_size: Size of the in-memory cache (defaults to 10,000).
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
    def get_instance(cls) -> "ProjectVersionResolver":
        """Get the initialized singleton resolver instance.

        Returns:
            The initialized ProjectVersionResolver instance.

        Raises:
            RuntimeError: If init_resolver() has not been called yet.
        """
        if _resolver is None:
            raise RuntimeError("init_resolver() must be called before get_instance()")
        return _resolver

    @ddtrace.tracer.wrap(name="project_version_resolver.resolve_version_sync")
    def _resolve_version_sync(self, project_id: str) -> ProjectVersion:
        """Resolve version through provider chain synchronously."""
        cached = self._cache.get(project_id)
        if cached is not None:
            return cached

        version = get_project_version_from_clickhouse(
            project_id, self._ch_client_factory, self._mode
        )

        # Cache non-empty projects
        if version != ProjectVersion.EMPTY_PROJECT:
            self._cache[project_id] = version

        root_span = ddtrace.tracer.current_root_span()
        if root_span:
            root_span.set_tag("cache_size", len(self._cache))

        return version

    @ddtrace.tracer.wrap(name="project_version_resolver.get_project_version_sync")
    def get_project_version_sync(self, project_id: str) -> ProjectVersion:
        if self._mode == ProjectVersionMode.OFF:
            return ProjectVersion.CALLS_MERGED_VERSION

        version = self._resolve_version_sync(project_id)

        # FORCE_ONLY_CALLS_MERGED mode queries DB for performance measurement but overrides result
        if self._mode == ProjectVersionMode.FORCE_ONLY_CALLS_MERGED:
            return ProjectVersion.CALLS_MERGED_VERSION

        return version

    @ddtrace.tracer.wrap(name="project_version_resolver.get_project_version_async")
    async def get_project_version_async(self, project_id: str) -> ProjectVersion:
        """Get project version asynchronously.

        TODO: update this with async clickhouse client

        Detects if we're in an async context and uses a thread to avoid
        blocking if needed.
        """
        if self._mode == ProjectVersionMode.OFF:
            return ProjectVersion.CALLS_MERGED_VERSION

        # Since we don't have an async ClickHouse client, we need to run
        # the sync version in a thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        version = await loop.run_in_executor(
            None, lambda: self._resolve_version_sync(project_id)
        )

        # FORCE_ONLY_CALLS_MERGED mode queries DB for performance measurement but overrides result
        if self._mode == ProjectVersionMode.FORCE_ONLY_CALLS_MERGED:
            return ProjectVersion.CALLS_MERGED_VERSION

        return version
