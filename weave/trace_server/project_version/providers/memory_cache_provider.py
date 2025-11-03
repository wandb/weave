"""In-memory LRU cache provider for project versions."""

import logging
from typing import Optional

from cachetools import LRUCache

from weave.trace_server.project_version.types import ProjectVersion

logger = logging.getLogger(__name__)

PER_REPLICA_CACHE_SIZE = 10_000


class InMemoryCacheProvider:
    """In-memory LRU cache for project version resolution.

    This cache acts as the first level lookup before falling back to slower
    providers like ClickHouse. Uses an LRU eviction strategy.

    Note: This is a cache, not a provider - it returns Optional to indicate cache misses.

    Args:
        maxsize: Maximum number of project_id entries to cache.

    Examples:
        >>> cache = InMemoryCacheProvider(maxsize=10_000)
        >>> # Will return None on cache miss
        >>> version = cache.get(project_id="proj-123")
        >>> # Set value in cache
        >>> cache.set(project_id="proj-123", version=ProjectVersion.CALLS_COMPLETE_VERSION)
        >>> # Will return cached value
        >>> version = cache.get(project_id="proj-123")
    """

    def __init__(self, maxsize: int = PER_REPLICA_CACHE_SIZE):
        self._cache: LRUCache[str, ProjectVersion] = LRUCache[str, ProjectVersion](
            maxsize=maxsize
        )

    def get(self, project_id: str) -> Optional[ProjectVersion]:
        """Get project version from in-memory cache.

        Args:
            project_id: The project identifier.

        Returns:
            ProjectVersion if cached, None if not in cache.
        """
        return self._cache.get(project_id)

    def set(self, project_id: str, version: ProjectVersion) -> None:
        """Set project version in cache.

        Args:
            project_id: The project identifier.
            version: The ProjectVersion to cache.
        """
        self._cache[project_id] = version

    def clear(self) -> None:
        """Clear all entries from the cache."""
        self._cache.clear()

    def get_cache_size(self) -> int:
        """Get the current number of entries in the cache.

        Returns:
            Number of cached entries.
        """
        return len(self._cache)
