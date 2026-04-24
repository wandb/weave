"""Redis client for weave trace server."""

import functools
from urllib.parse import parse_qs, urlparse

import redis
from redis.sentinel import Sentinel

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

    Returns None if Redis is not configured (WEAVE_REDIS_URL not set).

    If the URL includes `?master=<name>`, the client is resolved via Redis
    Sentinel at the URL's host:port so writes always route to the current
    master. This mirrors the `?master=` convention used by
    `services/connectors/redis.go`.
    """
    url = redis_url()
    if not url:
        return None

    parsed = urlparse(url)
    master = parse_qs(parsed.query).get("master", [None])[0]
    if not master:
        return redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECS,
            socket_timeout=REDIS_SOCKET_TIMEOUT_SECS,
        )

    if not parsed.hostname:
        raise ValueError(f"WEAVE_REDIS_URL is missing a hostname: {url!r}")

    sentinel = Sentinel(
        [(parsed.hostname, parsed.port or 26379)],
        socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECS,
        socket_timeout=REDIS_SOCKET_TIMEOUT_SECS,
    )
    return sentinel.master_for(
        master,
        decode_responses=True,
        socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECS,
        socket_timeout=REDIS_SOCKET_TIMEOUT_SECS,
    )
