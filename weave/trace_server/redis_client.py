"""Redis client for weave trace server."""

import functools

import redis

from weave.trace_server.environment import redis_url


@functools.lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis | None:
    """Get the Redis client.

    Returns None if Redis is not configured (REDIS_URL not set).
    The redis-py library handles connection pooling and thread safety internally.
    """
    url = redis_url()
    if url:
        return redis.from_url(url, decode_responses=True)
    return None
