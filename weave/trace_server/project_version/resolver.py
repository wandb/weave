"""Concrete project version resolver with explicit provider order."""

from typing import Any, Optional, Union

from cachetools import TTLCache

from weave.trace_server.project_version.clickhouse_provider import (
    ClickHouseProjectVersionProvider,
)
from weave.trace_server.project_version.gorilla_provider import (
    GorillaProjectVersionProvider,
)
from weave.trace_server.project_version.redis_provider import (
    RedisProjectVersionProvider,
)
from weave.trace_server.project_version.types import ProjectVersion


class ProjectVersionResolver:
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
        gorilla_client: Optional Gorilla client.
        cache_ttl_seconds: TTL for in-memory cache (default: 300s).

    Examples:
        >>> resolver = ProjectVersionResolver(
        ...     ch_client=clickhouse_client,
        ...     redis_client=redis_client,
        ...     redis_enabled=True,
        ...     gorilla_client=gorilla_client,
        ...     cache_ttl_seconds=300,
        ... )
        >>> version = await resolver.get_project_version("my-project")
    """

    def __init__(
        self,
        ch_client: Any,
        redis_client: Optional[Any] = None,
        redis_enabled: bool = False,
        auth_params: Optional[Any] = None,
        cache_ttl_seconds: float = 60 * 60,  # 1 hour
    ):
        # Initialize providers (no chaining, just independent instances)
        self._clickhouse_provider = ClickHouseProjectVersionProvider(
            ch_client=ch_client
        )
        self._gorilla_provider = GorillaProjectVersionProvider(auth_params=auth_params)
        self._redis_provider = RedisProjectVersionProvider(
            redis_client=redis_client, enabled=redis_enabled
        )
        self._cache: TTLCache = TTLCache(maxsize=10000, ttl=cache_ttl_seconds)

    async def get_project_version(self, project_id: str) -> Union[ProjectVersion, int]:
        """Resolve project version through explicit provider checks.

        Returns:
            ProjectVersion enum (or int for backwards compatibility):
                - OLD_VERSION (0): Legacy schema (calls_merged)
                - NEW_VERSION (1): New schema (calls_complete)
                - EMPTY_PROJECT (-1): No calls in either table
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

        # 3. Try Gorilla config if available
        try:
            gorilla_version = await self._gorilla_provider.get_project_version(
                project_id
            )
            # Gorilla only stores 0 or 1, never -1
            # If it returns None, fall through to ClickHouse
            if gorilla_version is not None:
                self._cache[project_id] = gorilla_version
                return gorilla_version
        except Exception:
            pass  # Fall through to ClickHouse

        # 4. Finally, check ClickHouse (always succeeds, returns 0, 1, or -1)
        version = await self._clickhouse_provider.get_project_version(project_id)
        self._cache[project_id] = version

        # 5. Set in gorilla if it's not empty project!
        # We only persist OLD_VERSION (0) or NEW_VERSION (1) to Gorilla
        # EMPTY_PROJECT (-1) shouldn't be persisted until the first write
        if version != ProjectVersion.EMPTY_PROJECT:
            await self._gorilla_provider.set_project_version(project_id, int(version))

        return version
