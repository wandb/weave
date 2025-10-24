"""Concrete project version resolver with explicit provider order."""
import threading
import asyncio
import logging
from concurrent.futures import Future
from typing import Any, Optional

from cachetools import LRUCache

from weave.trace_server.project_version.base import ProjectVersionService
from weave.trace_server.project_version.clickhouse_provider import (
    ClickHouseProjectVersionProvider,
)
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

    async def get_project_version(self, project_id: str) -> ProjectVersion:
        """Resolve project version through explicit provider checks.

        Returns:
            ProjectVersion enum (or int for backwards compatibility):
                - EMPTY_PROJECT (-1): No calls in either table
                - CALLS_MERGED_VERSION (0): Legacy schema (calls_merged)
                - CALLS_COMPLETE_VERSION (1): New schema (calls_complete)
        """
        # 1. Check in-memory cache first (fastest)
        cached = self._cache.get(project_id)
        if cached is not None:
            return cached

        # 2. Try Redis cache if enabled
        try:
            version = await self._redis_provider.get_project_version(project_id)
        except Exception:
            pass  # Fall through to next provider
        else:
            self._cache[project_id] = version
            return version

        # 3. Finally, check ClickHouse (always succeeds, returns 0, 1, or -1)
        version = await self._clickhouse_provider.get_project_version(project_id)
        if version != ProjectVersion.EMPTY_PROJECT:
            # only set cache when we know what sdk is writing to it, if empty
            # it can be either new or old
            self._cache[project_id] = version

        return version

    def get_project_version_sync(self, project_id: str) -> ProjectVersion:
        """Get the project version synchronously.

        First checks the in-memory cache (always safe). If not cached and an event
        loop is running, falls back to ClickHouse provider directly to avoid
        deadlock issues with nested sync/async contexts.

        Returns:
            ProjectVersion: ProjectVersion enum or int for backwards compatibility.
        """
        # Check cache first (always sync-safe)
        cached = self._cache.get(project_id)
        if cached is not None:
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
            return asyncio.run(self.get_project_version(project_id))

        # Edge case: event loop is running (sync parent called from async grandparent).
        # We can't use asyncio.run() or run_until_complete() as they would deadlock.
        # Spawn a new thread with its own event loop.
        logger.debug(
            f"get_project_version_sync called with running loop for {project_id}, "
            "delegating to new thread"
        )
        import threading

        result: list[ProjectVersion] = []
        exception: list[Exception] = []

        def run_in_new_loop() -> None:
            try:
                result.append(asyncio.run(self.get_project_version(project_id)))
            except Exception as e:
                exception.append(e)

        thread = threading.Thread(target=run_in_new_loop)
        thread.start()
        thread.join()

        if exception:
            raise exception[0]

        return result[0]
