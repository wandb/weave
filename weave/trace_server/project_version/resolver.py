"""Concrete project version resolver with explicit provider order."""

import time
from typing import Any, Optional

from weave.trace_server.project_version.clickhouse_provider import (
    ClickHouseProjectVersionProvider,
)
from weave.trace_server.project_version.gorilla_provider import (
    GorillaProjectVersionProvider,
)
from weave.trace_server.project_version.redis_provider import RedisProjectVersionProvider


class ProjectVersionResolver:
    """
    Resolves project versions by trying providers in explicit order.

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
        gorilla_client: Optional[Any] = None,
        cache_ttl_seconds: float = 300,
    ):
        # Initialize providers (no chaining, just independent instances)
        self._clickhouse_provider = ClickHouseProjectVersionProvider(ch_client=ch_client)
        self._gorilla_provider = GorillaProjectVersionProvider(gorilla_client=gorilla_client)
        self._redis_provider = RedisProjectVersionProvider(
            redis_client=redis_client, enabled=redis_enabled
        )

        # In-memory cache state
        self._cache_ttl = cache_ttl_seconds
        self._cache: dict[str, tuple[int, float]] = {}

    async def get_project_version(self, project_id: str) -> int:
        """
        Resolve project version through explicit provider checks.

        Returns:
            0 for legacy schema (calls_merged), 1 for new schema (calls_complete).
        """
        # 1. Check in-memory cache first (fastest)
        now = time.time()
        cached = self._cache.get(project_id)
        if cached is not None:
            version, expires_at = cached
            if now < expires_at:
                return version

        # 2. Try Redis cache if enabled
        try:
            version = await self._redis_provider.get_project_version(project_id)
            self._cache[project_id] = (version, now + self._cache_ttl)
            return version
        except Exception:
            pass  # Fall through to next provider

        # 3. Try Gorilla config if available
        try:
            version = await self._gorilla_provider.get_project_version(project_id)
            self._cache[project_id] = (version, now + self._cache_ttl)
            return version
        except Exception:
            pass  # Fall through to ClickHouse

        # 4. Finally, check ClickHouse (always succeeds, returns 0 or 1)
        version = await self._clickhouse_provider.get_project_version(project_id)
        self._cache[project_id] = (version, now + self._cache_ttl)
        return version

