"""Concrete project version resolver with explicit provider order."""

import asyncio
import logging
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
            print(
                f"...... Project version cache hit for project {project_id}: {cached}"
            )
            return cached

        # 2. Try Redis cache if enabled
        try:
            version = await self._redis_provider.get_project_version(project_id)
        except Exception:
            pass  # Fall through to next provider
        else:
            self._cache[project_id] = version
            print(
                f"...... Project version cache set for project {project_id}: {version}"
            )
            return version

        # 3. Finally, check ClickHouse (always succeeds, returns 0, 1, or -1)
        version = await self._clickhouse_provider.get_project_version(project_id)
        print(
            f"...... Project version clickhouse hit for project {project_id}: {version}"
        )
        if version != ProjectVersion.EMPTY_PROJECT:
            # only set cache when we know what sdk is writing to it, if empty
            # it can be either new or old
            self._cache[project_id] = version

        return version

    def get_project_version_sync(self, project_id: str) -> ProjectVersion:
        """Get the project version for routing decisions.

        Returns:
            Union[ProjectVersion, int]: ProjectVersion enum or int for backwards compatibility.
        """
        try:
            loop = asyncio.get_running_loop()
            # If we're already in an async context, we can't use run_until_complete or asyncio.run
            raise RuntimeError(
                "get_project_version_sync cannot be called from an async context. "
                "Use await get_project_version() instead."
            )
        except RuntimeError:
            # No running loop in this thread, we can safely use asyncio.run
            pass

        return asyncio.run(self.get_project_version(project_id))
