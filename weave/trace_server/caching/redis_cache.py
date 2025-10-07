"""Redis cache implementation."""

from typing import Optional

import redis.asyncio as aioredis


class RedisCache:
    """Redis cache implementation with TTL support.

    This implementation uses Redis for distributed caching with automatic
    expiration support through Redis's native TTL functionality.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        **kwargs: str,
    ) -> None:
        """Initialize the Redis cache.

        Args:
            host (str): Redis host address.
            port (int): Redis port number.
            db (int): Redis database number.
            password (Optional[str]): Redis password for authentication.
            **kwargs: Additional arguments to pass to Redis client.
        """
        self._redis: Optional[aioredis.Redis] = None
        self._host = host
        self._port = port
        self._db = db
        self._password = password
        self._kwargs = kwargs

    async def _ensure_connection(self) -> aioredis.Redis:
        """Ensure Redis connection is established."""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                f"redis://{self._host}:{self._port}/{self._db}",
                password=self._password,
                decode_responses=True,
                **self._kwargs,
            )
        return self._redis

    async def get(self, key: str) -> Optional[str]:
        """Get a value from the cache.

        Args:
            key (str): The cache key to retrieve.

        Returns:
            Optional[str]: The cached value if it exists and hasn't expired, None otherwise.

        Examples:
            >>> cache = RedisCache()
            >>> await cache.set("key", "value")
            >>> await cache.get("key")
            'value'
        """
        redis = await self._ensure_connection()
        value = await redis.get(key)
        return value

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        """Set a value in the cache.

        Args:
            key (str): The cache key to set.
            value (str): The value to cache.
            ttl (Optional[int]): Time-to-live in seconds. If None, the value never expires.

        Examples:
            >>> cache = RedisCache()
            >>> await cache.set("key", "value", ttl=60)
        """
        redis = await self._ensure_connection()
        if ttl is not None:
            await redis.setex(key, ttl, value)
        else:
            await redis.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete a key from the cache.

        Args:
            key (str): The cache key to delete.

        Examples:
            >>> cache = RedisCache()
            >>> await cache.set("key", "value")
            >>> await cache.delete("key")
            >>> await cache.get("key")
            None
        """
        redis = await self._ensure_connection()
        await redis.delete(key)

    async def clear(self) -> None:
        """Clear all entries from the cache.

        Note: This will flush the entire Redis database, not just keys created by this cache.

        Examples:
            >>> cache = RedisCache()
            >>> await cache.set("key1", "value1")
            >>> await cache.set("key2", "value2")
            >>> await cache.clear()
            >>> await cache.get("key1")
            None
        """
        redis = await self._ensure_connection()
        await redis.flushdb()

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
