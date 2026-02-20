"""TTL (Time-To-Live) settings cache for per-project call data retention.

Provides a cached lookup of per-project retention settings from ClickHouse,
and helpers to compute the ttl_at timestamp for new inserts.

Cache pattern mirrors project_version/project_version.py.
"""

from __future__ import annotations

import datetime
import threading

from cachetools import LRUCache
from clickhouse_connect.driver.client import Client as CHClient

PROJECT_TTL_CACHE_SIZE = 10_000

# Global cache shared across all threads. Keyed by project_id.
# Value is retention_days (int). 0 means no TTL (sentinel 2100-01-01).
_project_ttl_cache: LRUCache[str, int] = LRUCache(maxsize=PROJECT_TTL_CACHE_SIZE)
_project_ttl_cache_lock = threading.Lock()

_TTL_SENTINEL = datetime.datetime(2100, 1, 1)


def get_project_retention_days(project_id: str, ch_client: CHClient) -> int:
    """Return retention_days for a project (0 = no TTL / infinite). Cached.

    On cache miss, queries project_ttl_settings FINAL for the latest setting.
    If no row exists, returns 0 (no TTL configured).

    Args:
        project_id: The internal project ID.
        ch_client: ClickHouse client instance.

    Returns:
        retention_days for the project. 0 means infinite retention.

    Examples:
        >>> get_project_retention_days("entity/project", ch_client)
        90
    """
    with _project_ttl_cache_lock:
        cached = _project_ttl_cache.get(project_id)
    if cached is not None:
        return cached

    result = ch_client.query(
        "SELECT retention_days FROM project_ttl_settings FINAL "
        "WHERE project_id = {project_id:String} "
        "LIMIT 1",
        parameters={"project_id": project_id},
    )

    if result.row_count == 0:
        retention_days = 0
    else:
        retention_days = int(result.first_row[0])

    with _project_ttl_cache_lock:
        _project_ttl_cache[project_id] = retention_days

    return retention_days


def compute_ttl_at(
    retention_days: int, started_at: datetime.datetime
) -> datetime.datetime:
    """Compute the ttl_at timestamp for a call.

    If retention_days == 0, returns the far-future sentinel (2100-01-01),
    meaning the row will never expire. Otherwise returns
    started_at + timedelta(days=retention_days).

    Args:
        retention_days: Project retention setting (0 = no TTL).
        started_at: The call's start timestamp.

    Returns:
        datetime to store in the ttl_at column.

    Examples:
        >>> compute_ttl_at(0, datetime(2025, 1, 1))
        datetime.datetime(2100, 1, 1, 0, 0)
        >>> compute_ttl_at(90, datetime(2025, 1, 1))
        datetime.datetime(2025, 4, 1, 0, 0)
    """
    if retention_days == 0:
        return _TTL_SENTINEL
    return started_at.replace(tzinfo=None) + datetime.timedelta(days=retention_days)


def invalidate_ttl_cache(project_id: str) -> None:
    """Remove a project from the TTL cache.

    Call this after updating a project's TTL settings so the next
    insert picks up the new value.

    Args:
        project_id: The internal project ID to invalidate.

    Examples:
        >>> invalidate_ttl_cache("entity/project")
    """
    with _project_ttl_cache_lock:
        _project_ttl_cache.pop(project_id, None)


def reset_ttl_cache() -> None:
    """Clear the entire TTL cache. Primarily for testing.

    Examples:
        >>> reset_ttl_cache()
    """
    with _project_ttl_cache_lock:
        _project_ttl_cache.clear()
