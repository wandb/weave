"""Redis client for weave trace server."""

import functools
import logging
from urllib.parse import parse_qs, urlparse

import redis
from redis.sentinel import Sentinel

from weave.trace_server.environment import redis_url

logger = logging.getLogger(__name__)

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

    Returns None if Redis is not configured (WEAVE_REDIS_URL not set) or
    if the URL is malformed in any way that prevents client construction.
    Callers already treat the L2 cache as optional, so a construction
    failure must fall through to ClickHouse-only rather than 500 every
    request. The lru_cache means the None is also cached, so a misconfig
    won't re-parse on every request until the process restarts.

    If the URL includes `?master=<name>`, the client is resolved via Redis
    Sentinel at the URL's host:port so writes always route to the current
    master. This mirrors the `?master=` convention used by
    `services/connectors/redis.go`.
    """
    url = redis_url()
    if not url:
        return None

    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        master = query.get("master", [None])[0]
        if not master:
            # WEAVE_REDIS_URL may carry wandb-specific query params (tls,
            # caCertPath, ttlInSeconds, poolSize, ...) consumed by the Go
            # connector at `services/connectors/redis.go`. redis-py forwards
            # unknown URL params straight into Connection.__init__ kwargs and
            # blows up at first command with `AbstractConnection.__init__() got
            # an unexpected keyword argument 'tls'`. Strip the whole querystring
            # and translate the bits redis-py understands.
            tls = query.get("tls", [None])[0] == "true"
            ca_cert_path = query.get("caCertPath", [None])[0]
            if tls:
                # redis-py picks SSLConnection from the URL scheme, not kwargs.
                parsed = parsed._replace(scheme="rediss")
            clean_url = parsed._replace(query="").geturl()
            ssl_kwargs: dict[str, str] = {}
            if tls and ca_cert_path:
                ssl_kwargs["ssl_ca_certs"] = ca_cert_path
            return redis.from_url(
                clean_url,
                decode_responses=True,
                socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECS,
                socket_timeout=REDIS_SOCKET_TIMEOUT_SECS,
                **ssl_kwargs,
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
    except Exception:
        # Construction failures (malformed URL, unresolvable sentinel, etc.)
        # must not take down request handling. Log once and disable L2.
        logger.exception(
            "Failed to construct Redis client from WEAVE_REDIS_URL; "
            "falling through to ClickHouse-only (no L2 cache)"
        )
        return None
