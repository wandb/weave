"""In-memory cache implementation."""

import asyncio
import time
from typing import Optional


class MemoryCache:
    """In-memory cache implementation with TTL support.

    This implementation stores cache entries in a dictionary and supports
    time-to-live (TTL) expiration. Expired entries are removed lazily on access.
    """

    def __init__(self) -> None:
        """Initialize the in-memory cache."""
        self._cache: dict[str, tuple[str, Optional[float]]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[str]:
        """Get a value from the cache.

        Args:
            key (str): The cache key to retrieve.

        Returns:
            Optional[str]: The cached value if it exists and hasn't expired, None otherwise.

        Examples:
            >>> cache = MemoryCache()
            >>> await cache.set("key", "value")
            >>> await cache.get("key")
            'value'
        """
        async with self._lock:
            if key not in self._cache:
                return None

            value, expiry = self._cache[key]

            # Check if the entry has expired
            if expiry is not None and time.time() > expiry:
                del self._cache[key]
                return None

            return value

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        """Set a value in the cache.

        Args:
            key (str): The cache key to set.
            value (str): The value to cache.
            ttl (Optional[int]): Time-to-live in seconds. If None, the value never expires.

        Examples:
            >>> cache = MemoryCache()
            >>> await cache.set("key", "value", ttl=60)
        """
        async with self._lock:
            expiry = None if ttl is None else time.time() + ttl
            self._cache[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        """Delete a key from the cache.

        Args:
            key (str): The cache key to delete.

        Examples:
            >>> cache = MemoryCache()
            >>> await cache.set("key", "value")
            >>> await cache.delete("key")
            >>> await cache.get("key")
            None
        """
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        """Clear all entries from the cache.

        Examples:
            >>> cache = MemoryCache()
            >>> await cache.set("key1", "value1")
            >>> await cache.set("key2", "value2")
            >>> await cache.clear()
            >>> await cache.get("key1")
            None
        """
        async with self._lock:
            self._cache.clear()
