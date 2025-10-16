"""In-memory LRU cache with TTL for project version lookups."""

import time
from typing import Optional

from weave.trace_server.project_version.base import ProjectVersionService


class InMemoryProjectVersionCache:
    """
    Fast in-process cache with TTL expiration.

    Args:
        upstream: Fallback provider to query on cache miss.
        ttl_seconds: Time-to-live for cached entries.

    Examples:
        >>> cache = InMemoryProjectVersionCache(upstream=redis_provider, ttl_seconds=300)
        >>> version = await cache.get_project_version("proj-123")
    """

    def __init__(
        self,
        upstream: ProjectVersionService,
        ttl_seconds: float = 300,
    ):
        self._upstream = upstream
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[int, float]] = {}

    async def get_project_version(self, project_id: str) -> int:
        """Return cached version or fetch from upstream."""
        now = time.time()
        cached = self._cache.get(project_id)

        if cached is not None:
            version, expires_at = cached
            if now < expires_at:
                return version

        version = await self._upstream.get_project_version(project_id)
        self._cache[project_id] = (version, now + self._ttl)
        return version

