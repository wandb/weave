from typing import Optional

import redis  # type: ignore

from weave.trace_server.environment import (
    redis_db,
    redis_host,
    redis_password,
    redis_port,
)


class RedisClient:
    """Simple Redis client wrapper for caching.

    Args:
        client (redis.Redis): Redis client instance.

    Examples:
        >>> redis_client = RedisClient.from_env()
        >>> redis_client.set("key", "value")
        >>> redis_client.get("key")
        'value'
    """

    def __init__(self, client: redis.Redis):
        self._client = client

    @classmethod
    def from_env(cls) -> "RedisClient":
        client = redis.Redis(
            host=redis_host(),
            port=redis_port(),
            password=redis_password(),
            db=redis_db(),
            decode_responses=True,
        )
        return cls(client)

    def get(self, key: str) -> Optional[str]:
        """Get value from cache.

        Args:
            key (str): Cache key.

        Returns:
            Optional[str]: Cached value or None if not found.
        """
        return self._client.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set value in cache.

        Args:
            key (str): Cache key.
            value (str): Value to cache.
            ex (Optional[int]): Expiration time in seconds.

        Returns:
            bool: True if successful.
        """
        return self._client.set(key, value, ex=ex)
