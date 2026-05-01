"""TTL (Time-To-Live) settings cache for per-project call data retention.

Provides a cached lookup of per-project retention settings from ClickHouse,
and helpers to compute the expire_at timestamp for new inserts.

Two-layer cache over per-project retention_days:
  L1: in-process, time-based eviction via cachetools.TTLCache
  L2: Redis (optional)

Noun overload warning: the cached *value* is itself a TTL setting
(retention_days). "TTLCache" here refers to the L1 eviction strategy, not the
value being cached.
"""

from __future__ import annotations

import datetime
import logging
import threading

import ddtrace
import redis
from cachetools import TTLCache
from clickhouse_connect.driver.client import Client as CHClient

from weave.trace_server.datadog import set_current_span_dd_tags
from weave.trace_server.redis_client import get_redis_client

logger = logging.getLogger(__name__)

PROJECT_TTL_CACHE_SIZE = 10_000
# 5 minutes; bounds staleness in multi-instance deploys
PROJECT_TTL_CACHE_TTL_SECS = 300

REDIS_TTL_KEY_PREFIX = "weave:project_ttl:"
REDIS_TTL_EXPIRY_SECS = 300

# Stored retention_days value meaning "no TTL configured for this project".
# Used as the on-disk encoding for "unset" since the column is non-null.
RETENTION_DAYS_NO_TTL = 0

# Global cache shared across all threads. Keyed by project_id.
# Value is retention_days (int). RETENTION_DAYS_NO_TTL means no TTL.
_project_ttl_cache: TTLCache[str, int] = TTLCache(
    maxsize=PROJECT_TTL_CACHE_SIZE, ttl=PROJECT_TTL_CACHE_TTL_SECS
)
_project_ttl_cache_lock = threading.Lock()


@ddtrace.tracer.wrap(name="ttl_settings.get_project_retention_days")
def get_project_retention_days(
    project_id: str,
    ch_client: CHClient,
) -> int:
    """Return retention_days for a project (RETENTION_DAYS_NO_TTL = no TTL). Cached.

    Read path: L1 (in-process) -> L2 (Redis, if REDIS_URL is set) -> ClickHouse
    (argMax). A fall-through to ClickHouse is a full cache miss; if ClickHouse
    has no row for the project, returns RETENTION_DAYS_NO_TTL.

    Redis client is resolved lazily via get_redis_client() (lru_cached
    process singleton). ch_client must come from the calling thread — it is
    a thread-local resource in ClickHouseTraceServer.
    """
    cached = _l1_get(project_id)
    if cached is not None:
        set_current_span_dd_tags({"ttl.cache_hit": "L1"})
        return cached

    redis_client = get_redis_client()
    if redis_client is not None:
        redis_val = _l2_get(redis_client, project_id)
        if redis_val is not None:
            _l1_set(project_id, redis_val)
            set_current_span_dd_tags({"ttl.cache_hit": "L2"})
            return redis_val

    retention_days = _query_clickhouse(ch_client, project_id)
    set_current_span_dd_tags(
        {"ttl.cache_hit": "clickhouse", "ttl.retention_days": retention_days}
    )

    if redis_client is not None:
        _l2_set(redis_client, project_id, retention_days)
    _l1_set(project_id, retention_days)

    return retention_days


def compute_expire_at(
    retention_days: int, started_at: datetime.datetime
) -> datetime.datetime | None:
    """Compute the expire_at timestamp for a call.

    If retention_days is RETENTION_DAYS_NO_TTL, returns None, meaning no TTL.
    Otherwise returns started_at + timedelta(days=retention_days). DB adapters
    convert None to their non-null storage sentinel at the write boundary.
    """
    if retention_days == RETENTION_DAYS_NO_TTL:
        return None

    anchor = started_at
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=datetime.timezone.utc)

    if retention_days > 0:
        return anchor + datetime.timedelta(days=retention_days)
    # Negative values encode minutes-based retention (e.g. -5 = 5 minutes) for admin/testing use only
    return anchor + datetime.timedelta(minutes=-retention_days)


def invalidate_ttl_cache(project_id: str) -> None:
    """Remove a project from the TTL cache (both L1 and L2).

    Call this after updating a project's TTL settings so the next insert
    picks up the new value. Note: only invalidates L1 in the *current*
    process — other replicas will still see stale L1 entries until their
    own L1 TTL expires. Multi-replica invalidation would need pub/sub.
    """
    with _project_ttl_cache_lock:
        _project_ttl_cache.pop(project_id, None)
    redis_client = get_redis_client()
    if redis_client is not None:
        _l2_delete(redis_client, project_id)


def reset_ttl_cache() -> None:
    """Clear the entire TTL cache. Primarily for testing."""
    with _project_ttl_cache_lock:
        _project_ttl_cache.clear()


# ---------------------------------------------------------------------------
# Cache-layer helpers
# ---------------------------------------------------------------------------


def _ttl_cache_key(project_id: str) -> str:
    return f"{REDIS_TTL_KEY_PREFIX}{project_id}"


def _l1_get(project_id: str) -> int | None:
    """Read from the in-process TTLCache."""
    with _project_ttl_cache_lock:
        return _project_ttl_cache.get(project_id)


def _l1_set(project_id: str, retention_days: int) -> None:
    """Write to the in-process TTLCache."""
    with _project_ttl_cache_lock:
        _project_ttl_cache[project_id] = retention_days


def _l2_get(redis_client: redis.Redis, project_id: str) -> int | None:
    """Try to read retention_days from Redis. Returns None on miss or error."""
    try:
        val = redis_client.get(_ttl_cache_key(project_id))
        if val is not None:
            return int(val)
    except Exception:
        logger.exception("Redis L2 cache read failed for project %s", project_id)
    return None


def _l2_set(redis_client: redis.Redis, project_id: str, retention_days: int) -> None:
    """Try to write retention_days to Redis with TTL. Logs errors but does not raise."""
    try:
        redis_client.set(
            _ttl_cache_key(project_id), str(retention_days), ex=REDIS_TTL_EXPIRY_SECS
        )
    except Exception:
        logger.exception("Redis L2 cache write failed for project %s", project_id)


def _l2_delete(redis_client: redis.Redis, project_id: str) -> None:
    """Try to delete a key from Redis. Logs errors but does not raise."""
    try:
        redis_client.delete(_ttl_cache_key(project_id))
    except Exception:
        logger.exception("Redis L2 cache delete failed for project %s", project_id)


def _query_clickhouse(ch_client: CHClient, project_id: str) -> int:
    """Query ClickHouse for the latest retention_days via argMax.

    Returns RETENTION_DAYS_NO_TTL on miss.
    """
    result = ch_client.query(
        "SELECT argMax(retention_days, updated_at) "
        "FROM project_ttl_settings "
        "WHERE project_id = {project_id:String}",
        parameters={"project_id": project_id},
    )
    if result.row_count == 0:
        return RETENTION_DAYS_NO_TTL
    return int(result.first_row[0])
