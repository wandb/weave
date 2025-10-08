"""Lightweight in-memory cache for call part IDs (starts and ends)."""

import os
import threading
from typing import Optional, Protocol

from cachetools import TTLCache


class CallPartCache(Protocol):
    """Protocol for call part cache implementations."""

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

    def get_call_start_ids(self, project_id: str) -> set[str]:
        """Get cached call start IDs for a project.

        Args:
            project_id (str): The project ID to fetch call start IDs for.

        Returns:
            set[str]: Set of call start IDs for the project.
        """
        ...

    def set_call_start_ids(self, project_id: str, call_start_ids: set[str]) -> None:
        """Set cached call start IDs for a project.

        Args:
            project_id (str): The project ID to cache call start IDs for.
            call_start_ids (set[str]): Set of call start IDs to cache.
        """
        ...

    def add_call_start_ids(self, project_id: str, call_start_ids: set[str]) -> None:
        """Add call start IDs to the cache, merging with existing cached IDs.

        Args:
            project_id (str): The project ID to add call start IDs for.
            call_start_ids (set[str]): Set of call start IDs to add to cache.
        """
        ...

    def add_call_end_ids(self, project_id: str, call_end_ids: set[str]) -> None:
        """Add call end IDs to the cache, merging with existing cached IDs.

        Args:
            project_id (str): The project ID to add call end IDs for.
            call_end_ids (set[str]): Set of call end IDs to add to cache.
        """
        ...

    def remove_call_start_ids(self, project_id: str, call_start_ids: set[str]) -> None:
        """Remove call start IDs from the cache.

        Args:
            project_id (str): The project ID to remove call start IDs for.
            call_start_ids (set[str]): Set of call start IDs to remove from cache.
        """
        ...

    def remove_call_end_ids(self, project_id: str, call_end_ids: set[str]) -> None:
        """Remove call end IDs from the cache.

        Args:
            project_id (str): The project ID to remove call end IDs for.
            call_end_ids (set[str]): Set of call end IDs to remove from cache.
        """
        ...


class InMemoryCallPartCache:
    """Thread-safe in-memory TTL cache for call part IDs (starts and ends).

    This cache is shared across all FastAPI worker threads and uses TTLCache
    which is thread-safe for basic operations. Entries automatically expire
    after 24 hours.
    """

    def __init__(self) -> None:
        # TTL cache with 24 hours (86400 seconds) expiration
        # maxsize=10000 allows up to 10k projects to be cached
        # Separate caches for call starts and ends
        # TTLCache is thread-safe for basic get/set operations
        self._call_end_cache: TTLCache[str, set[str]] = TTLCache(
            maxsize=10000, ttl=86400
        )
        self._call_start_cache: TTLCache[str, set[str]] = TTLCache(
            maxsize=10000, ttl=86400
        )

    def get_call_end_ids(self, project_id: str) -> set[str]:
        """Get cached call end IDs for a project.

        Args:
            project_id (str): The project ID to fetch call end IDs for.

        Returns:
            set[str]: Set of call end IDs for the project, empty set if not cached.

        Examples:
            >>> cache = InMemoryCallPartCache()
            >>> cache.get_call_end_ids("project1")
            set()
        """
        return self._call_end_cache.get(project_id, set())

    def set_call_end_ids(self, project_id: str, call_end_ids: set[str]) -> None:
        """Set cached call end IDs for a project.

        Entries automatically expire after 24 hours.

        Args:
            project_id (str): The project ID to cache call end IDs for.
            call_end_ids (set[str]): Set of call end IDs to cache.

        Examples:
            >>> cache = InMemoryCallPartCache()
            >>> cache.set_call_end_ids("project1", {"id1", "id2"})
            >>> cache.get_call_end_ids("project1")
            {'id1', 'id2'}
        """
        self._call_end_cache[project_id] = call_end_ids

    def get_call_start_ids(self, project_id: str) -> set[str]:
        """Get cached call start IDs for a project.

        Args:
            project_id (str): The project ID to fetch call start IDs for.

        Returns:
            set[str]: Set of call start IDs for the project, empty set if not cached.

        Examples:
            >>> cache = InMemoryCallPartCache()
            >>> cache.get_call_start_ids("project1")
            set()
        """
        return self._call_start_cache.get(project_id, set())

    def set_call_start_ids(self, project_id: str, call_start_ids: set[str]) -> None:
        """Set cached call start IDs for a project.

        Entries automatically expire after 24 hours.

        Args:
            project_id (str): The project ID to cache call start IDs for.
            call_start_ids (set[str]): Set of call start IDs to cache.

        Examples:
            >>> cache = InMemoryCallPartCache()
            >>> cache.set_call_start_ids("project1", {"id1", "id2"})
            >>> cache.get_call_start_ids("project1")
            {'id1', 'id2'}
        """
        self._call_start_cache[project_id] = call_start_ids

    def add_call_start_ids(self, project_id: str, call_start_ids: set[str]) -> None:
        """Add call start IDs to the cache, merging with existing cached IDs.

        Entries automatically expire after 24 hours.

        Args:
            project_id (str): The project ID to add call start IDs for.
            call_start_ids (set[str]): Set of call start IDs to add to cache.

        Examples:
            >>> cache = InMemoryCallPartCache()
            >>> cache.add_call_start_ids("project1", {"id1", "id2"})
            >>> cache.add_call_start_ids("project1", {"id3"})
            >>> cache.get_call_start_ids("project1")
            {'id1', 'id2', 'id3'}
        """
        existing = self._call_start_cache.get(project_id, set())
        self._call_start_cache[project_id] = existing | call_start_ids

    def add_call_end_ids(self, project_id: str, call_end_ids: set[str]) -> None:
        """Add call end IDs to the cache, merging with existing cached IDs.

        Entries automatically expire after 24 hours.

        Args:
            project_id (str): The project ID to add call end IDs for.
            call_end_ids (set[str]): Set of call end IDs to add to cache.

        Examples:
            >>> cache = InMemoryCallPartCache()
            >>> cache.add_call_end_ids("project1", {"id1", "id2"})
            >>> cache.add_call_end_ids("project1", {"id3"})
            >>> cache.get_call_end_ids("project1")
            {'id1', 'id2', 'id3'}
        """
        existing = self._call_end_cache.get(project_id, set())
        self._call_end_cache[project_id] = existing | call_end_ids

    def remove_call_start_ids(self, project_id: str, call_start_ids: set[str]) -> None:
        """Remove call start IDs from the cache.

        Args:
            project_id (str): The project ID to remove call start IDs for.
            call_start_ids (set[str]): Set of call start IDs to remove from cache.

        Examples:
            >>> cache = InMemoryCallPartCache()
            >>> cache.add_call_start_ids("project1", {"id1", "id2", "id3"})
            >>> cache.remove_call_start_ids("project1", {"id1", "id2"})
            >>> cache.get_call_start_ids("project1")
            {'id3'}
        """
        existing = self._call_start_cache.get(project_id, set())
        updated = existing - call_start_ids
        if updated:
            self._call_start_cache[project_id] = updated
        elif project_id in self._call_start_cache:
            # Remove empty set from cache to save memory
            del self._call_start_cache[project_id]

    def remove_call_end_ids(self, project_id: str, call_end_ids: set[str]) -> None:
        """Remove call end IDs from the cache.

        Args:
            project_id (str): The project ID to remove call end IDs for.
            call_end_ids (set[str]): Set of call end IDs to remove from cache.

        Examples:
            >>> cache = InMemoryCallPartCache()
            >>> cache.add_call_end_ids("project1", {"id1", "id2", "id3"})
            >>> cache.remove_call_end_ids("project1", {"id1", "id2"})
            >>> cache.get_call_end_ids("project1")
            {'id3'}
        """
        existing = self._call_end_cache.get(project_id, set())
        updated = existing - call_end_ids
        if updated:
            self._call_end_cache[project_id] = updated
        elif project_id in self._call_end_cache:
            # Remove empty set from cache to save memory
            del self._call_end_cache[project_id]


# Module-level singleton cache instance, shared across all threads
_global_cache: Optional[CallPartCache] = None
_cache_lock = threading.Lock()


def get_call_part_cache_from_env() -> CallPartCache:
    """Get or create a global call part cache shared across all threads.

    This returns a module-level singleton cache that's shared across all
    FastAPI worker threads and ClickHouseTraceServer instances.

    Reads the USE_REDIS_CACHE env var to determine cache backend.
    Currently only supports in-memory cache.

    Returns:
        CallPartCache: A shared call part cache instance.

    Raises:
        NotImplementedError: If USE_REDIS_CACHE=1 is set.

    Examples:
        >>> cache1 = get_call_part_cache_from_env()
        >>> cache2 = get_call_part_cache_from_env()
        >>> cache1 is cache2  # Same instance
        True
    """
    global _global_cache

    # Double-checked locking for thread-safe singleton initialization
    if _global_cache is not None:
        return _global_cache

    with _cache_lock:
        # Check again inside the lock
        if _global_cache is not None:
            return _global_cache

        use_redis = os.getenv("USE_REDIS_CACHE", "0") == "1"
        if use_redis:
            raise NotImplementedError(
                "Redis cache is not yet implemented. Set USE_REDIS_CACHE=0 or unset it."
            )

        _global_cache = InMemoryCallPartCache()
        return _global_cache
