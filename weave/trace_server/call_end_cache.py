"""Lightweight in-memory cache for call end IDs."""

import os
from typing import Protocol

from cachetools import TTLCache


class CallEndCache(Protocol):
    """Protocol for call end cache implementations."""

    def get_call_end_ids(self, project_id: str) -> set[str]:
        """Get cached call end IDs for a project.

        Args:
            project_id (str): The project ID to fetch call end IDs for.

        Returns:
            set[str]: Set of call end IDs for the project.
        """
        ...

    def set_call_end_ids(self, project_id: str, call_end_ids: set[str]) -> None:
        """Set cached call end IDs for a project.

        Args:
            project_id (str): The project ID to cache call end IDs for.
            call_end_ids (set[str]): Set of call end IDs to cache.
        """
        ...


class InMemoryCallEndCache:
    """Simple in-memory TTL cache for call end IDs with 24-hour expiration."""

    def __init__(self) -> None:
        # TTL cache with 24 hours (86400 seconds) expiration
        # maxsize=10000 allows up to 10k projects to be cached
        self._cache: TTLCache[str, set[str]] = TTLCache(maxsize=10000, ttl=86400)

    def get_call_end_ids(self, project_id: str) -> set[str]:
        """Get cached call end IDs for a project.

        Args:
            project_id (str): The project ID to fetch call end IDs for.

        Returns:
            set[str]: Set of call end IDs for the project, empty set if not cached.

        Examples:
            >>> cache = InMemoryCallEndCache()
            >>> cache.get_call_end_ids("project1")
            set()
        """
        return self._cache.get(project_id, set())

    def set_call_end_ids(self, project_id: str, call_end_ids: set[str]) -> None:
        """Set cached call end IDs for a project.

        Entries automatically expire after 24 hours.

        Args:
            project_id (str): The project ID to cache call end IDs for.
            call_end_ids (set[str]): Set of call end IDs to cache.

        Examples:
            >>> cache = InMemoryCallEndCache()
            >>> cache.set_call_end_ids("project1", {"id1", "id2"})
            >>> cache.get_call_end_ids("project1")
            {'id1', 'id2'}
        """
        self._cache[project_id] = call_end_ids


def get_call_end_cache_from_env() -> CallEndCache:
    """Create a call end cache based on environment configuration.

    Reads the USE_REDIS_CACHE env var to determine cache backend.
    Currently only supports in-memory cache.

    Returns:
        CallEndCache: A call end cache instance.

    Raises:
        NotImplementedError: If USE_REDIS_CACHE=1 is set.

    Examples:
        >>> cache = get_call_end_cache_from_env()
        >>> isinstance(cache, InMemoryCallEndCache)
        True
    """
    use_redis = os.getenv("USE_REDIS_CACHE", "0") == "1"
    if use_redis:
        raise NotImplementedError(
            "Redis cache is not yet implemented. Set USE_REDIS_CACHE=0 or unset it."
        )
    return InMemoryCallEndCache()
