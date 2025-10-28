"""Concrete project version resolver with explicit provider order."""

import asyncio
import logging
import threading
from typing import Any, Optional

from cachetools import LRUCache

from weave.trace_server.project_version.base import ProjectVersionService
from weave.trace_server.project_version.clickhouse_provider import (
    ClickHouseProjectVersionProvider,
)
from weave.trace_server.project_version.config import ProjectVersionMode
from weave.trace_server.project_version.redis_provider import (
    RedisProjectVersionProvider,
)
from weave.trace_server.project_version.types import ProjectVersion

# We only set the cache after getting the source of truth, its okay if this
# stays around forever.
PER_REPLICA_CACHE_SIZE = 10_000


logger = logging.getLogger(__name__)


class ProjectVersionResolver(ProjectVersionService):
    """Resolves project versions by trying providers in explicit order.

    Provider order (fastest to slowest):
        1. In-memory cache (5 min TTL)
        2. Redis cache (if enabled)
        3. Gorilla MySQL config (if available)
        4. ClickHouse fallback (checks for calls_complete rows)

    Args:
        ch_client: ClickHouse client.
        redis_client: Optional Redis client.
        redis_enabled: Whether to use Redis cache.

    Examples:
        >>> resolver = ProjectVersionResolver(
        ...     ch_client=clickhouse_client,
        ...     redis_client=redis_client,
        ...     redis_enabled=True,
        ... )
        >>> version = await resolver.get_project_version("my-project")
    """

    def __init__(
        self,
        ch_client: Any,
        redis_client: Optional[Any] = None,
        redis_enabled: bool = False,
    ):
        # Initialize providers (no chaining, just independent instances)
        self._clickhouse_provider = ClickHouseProjectVersionProvider(
            ch_client=ch_client
        )
        self._redis_provider = RedisProjectVersionProvider(
            redis_client=redis_client, enabled=redis_enabled
        )
        self._cache: LRUCache[str, ProjectVersion] = LRUCache(
            maxsize=PER_REPLICA_CACHE_SIZE
        )
        self._mode = ProjectVersionMode.from_env()
        # logger.info(f"ProjectVersionResolver initialized with mode: {self._mode.value}")

    async def get_project_version(
        self, project_id: str, is_write: bool = False
    ) -> ProjectVersion:
        """Resolve project version through explicit provider checks.

        Args:
            project_id: The project identifier.
            is_write: Whether this is for a write operation (affects routing in some modes).

        Returns:
            ProjectVersion enum (or int for backwards compatibility):
                - EMPTY_PROJECT (-1): No calls in either table
                - CALLS_MERGED_VERSION (0): Legacy schema (calls_merged)
                - CALLS_COMPLETE_VERSION (1): New schema (calls_complete)
        """
        # Handle non-auto modes
        if self._mode == ProjectVersionMode.OFF:
            # Skip DB entirely
            return ProjectVersion.CALLS_MERGED_VERSION

        if self._mode == ProjectVersionMode.CALLS_MERGED_READ and not is_write:
            # For reads in CALLS_MERGED_READ mode, skip resolution and use old table
            return ProjectVersion.CALLS_MERGED_VERSION

        # 1. Check in-memory cache first (fastest)
        cached = self._cache.get(project_id)
        if cached is not None:
            # Apply mode-specific overrides even for cached values
            if self._mode == ProjectVersionMode.CALLS_MERGED:
                return ProjectVersion.CALLS_MERGED_VERSION
            return cached

        # 2. Try Redis cache if enabled
        try:
            version = await self._redis_provider.get_project_version(project_id)
        except Exception:
            pass  # Fall through to next provider
        else:
            self._cache[project_id] = version
            # Apply mode-specific override
            if self._mode == ProjectVersionMode.CALLS_MERGED:
                return ProjectVersion.CALLS_MERGED_VERSION
            return version

        # 3. Finally, check ClickHouse
        version = await self._clickhouse_provider.get_project_version(project_id)
        if version != ProjectVersion.EMPTY_PROJECT:
            # only set cache when we know what sdk is writing to it, if empty
            # it can be either new or old
            self._cache[project_id] = version

        # Apply mode-specific override AFTER querying (to measure perf impact)
        if self._mode == ProjectVersionMode.CALLS_MERGED:
            return ProjectVersion.CALLS_MERGED_VERSION

        return version

    def get_project_version_sync(
        self, project_id: str, is_write: bool = False
    ) -> ProjectVersion:
        """Get the project version synchronously.

        First checks the in-memory cache (always safe). If not cached and an event
        loop is running, falls back to ClickHouse provider directly to avoid
        deadlock issues with nested sync/async contexts.

        Args:
            project_id: The project identifier.
            is_write: Whether this is for a write operation (affects routing in some modes).

        Returns:
            ProjectVersion: ProjectVersion enum or int for backwards compatibility.
        """
        # Handle OFF mode early (skip DB entirely)
        if self._mode == ProjectVersionMode.OFF:
            return ProjectVersion.CALLS_MERGED_VERSION

        # Handle CALLS_MERGED_READ mode for reads (skip DB for reads)
        if self._mode == ProjectVersionMode.CALLS_MERGED_READ and not is_write:
            return ProjectVersion.CALLS_MERGED_VERSION

        # Check cache first (always sync-safe)
        cached = self._cache.get(project_id)
        if cached is not None:
            # Apply mode-specific overrides even for cached values
            if self._mode == ProjectVersionMode.CALLS_MERGED:
                return ProjectVersion.CALLS_MERGED_VERSION
            return cached

        # Check if there's a running loop
        running_loop = None
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            # No loop running - this is the common/expected case
            pass

        # Normal case: no event loop running, safe to create one
        if running_loop is None:
            return asyncio.run(self.get_project_version(project_id, is_write=is_write))

        # Edge case: event loop is running (sync parent called from async grandparent).
        # Spawn a new thread with its own event loop.
        logger.debug(
            f"get_project_version_sync called with running loop for {project_id}, "
            "delegating to new thread"
        )

        result: list[ProjectVersion] = []
        exception: list[Exception] = []

        def run_in_new_loop() -> None:
            try:
                result.append(
                    asyncio.run(self.get_project_version(project_id, is_write=is_write))
                )
            except Exception as e:
                exception.append(e)

        thread = threading.Thread(target=run_in_new_loop)
        thread.start()
        thread.join()

        if exception:
            raise exception[0]

        return result[0]
