"""Protocol for cache service implementations."""

from typing import Protocol


class CacheProtocol(Protocol):
    """Protocol defining the interface for cache implementations."""

    async def get(self, key: str) -> str | None:
        """Get a value from the cache.

        Args:
            key (str): The cache key to retrieve.

        Returns:
            str | None: The cached value if it exists and hasn't expired, None otherwise.

        Examples:
            >>> cache = MemoryCache()
            >>> await cache.set("key", "value")
            >>> await cache.get("key")
            'value'
        """
        ...

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Set a value in the cache.

        Args:
            key (str): The cache key to set.
            value (str): The value to cache.
            ttl (int | None): Time-to-live in seconds. If None, the value never expires.

        Examples:
            >>> cache = MemoryCache()
            >>> await cache.set("key", "value", ttl=60)
        """
        ...

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
        ...

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
        ...
