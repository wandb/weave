"""Redis client for weave trace server."""

import functools

import redis

from weave.trace_server.environment import redis_url

# Redis here is an optional L2 cache in front of ClickHouse. When it's
# unreachable we must fall through quickly; without explicit timeouts the
# socket inherits the OS default TCP connect timeout (~2 min on Linux),
# which stalls every cache-miss request path. redis-py's default retry
# config is zero retries, so a single failure fails fast.
REDIS_CONNECT_TIMEOUT_SECS = 1
REDIS_SOCKET_TIMEOUT_SECS = 1


@functools.lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis | None:
    """Get the Redis client.

    Returns None if Redis is not configured (REDIS_URL not set).
    The redis-py library handles connection pooling and thread safety internally.
    """
    url = redis_url()
    if url:
        return redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECS,
            socket_timeout=REDIS_SOCKET_TIMEOUT_SECS,
        )
    return None
