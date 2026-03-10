"""Redis client for weave trace server."""

import redis

from weave.trace_server.environment import redis_url

_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis | None:
    """Get the Redis client.

    Returns None if Redis is not configured (REDIS_URL not set).
    The redis-py library handles connection pooling and thread safety internally.
    """
    global _redis_client

    if _redis_client is None:
        url = redis_url()

        if url:
            _redis_client = redis.from_url(url, decode_responses=True)

    return _redis_client
