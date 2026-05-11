import logging
import threading

import ddtrace
import redis
from cachetools import LRUCache
from clickhouse_connect.driver.client import Client as CHClient

from weave.trace_server.datadog import (
    set_current_span_dd_tags,
    set_root_span_dd_tags,
)
from weave.trace_server.project_version.clickhouse_project_version import (
    get_project_data_residence,
)
from weave.trace_server.project_version.types import (
    CallsStorageServerMode,
    ProjectDataResidence,
    ReadTable,
    WriteTarget,
)
from weave.trace_server.redis_client import get_redis_client

logger = logging.getLogger(__name__)

PROJECT_RESIDENCE_CACHE_SIZE = 10_000

REDIS_RESIDENCE_KEY_PREFIX = "weave:project_residence:"
# 5 minutes; bounds staleness in multi-instance deploys
REDIS_RESIDENCE_EXPIRY_SECS = 300

# Global cache shared across all resolvers. Keyed by project_id.
_project_residence_cache: LRUCache[str, ProjectDataResidence] = LRUCache(
    maxsize=PROJECT_RESIDENCE_CACHE_SIZE
)
_project_residence_cache_lock = threading.Lock()


def reset_project_residence_cache() -> None:
    """Clear the in-process project data residence cache (L1).

    L2 (Redis) is left alone; use `invalidate_project_residence_cache`
    for a per-project L1+L2 eviction.

    Examples:
        >>> reset_project_residence_cache()

    """
    with _project_residence_cache_lock:
        _project_residence_cache.clear()


def invalidate_project_residence_cache(project_id: str) -> None:
    """Remove a project from both L1 and L2 caches.

    Only invalidates L1 in the *current* process — other replicas will still
    see stale L1 entries until their own entry is evicted.
    """
    with _project_residence_cache_lock:
        _project_residence_cache.pop(project_id, None)
    redis_client = get_redis_client()
    if redis_client is not None:
        _l2_delete(redis_client, project_id)


class TableRoutingResolver:
    """Resolver for determining which table to read from or write to based on project data residence.

    Uses a global cache of project data residence information shared across all threads.
    """

    def __init__(self) -> None:
        self._mode = CallsStorageServerMode.from_env()

    def _get_residence(
        self, project_id: str, ch_client: CHClient
    ) -> ProjectDataResidence:
        """Resolve project data residence with a two-layer cache.

        Read path: L1 (in-process LRU) -> L2 (Redis, if WEAVE_REDIS_URL is set)
        -> ClickHouse. EMPTY residency is never cached at either layer because
        the project could still grow into either table.
        """
        cached = _l1_get(project_id)
        if cached is not None:
            set_current_span_dd_tags({"project_version.cache_hit": "L1"})
            return cached

        redis_client = get_redis_client()
        if redis_client is not None:
            redis_val = _l2_get(redis_client, project_id)
            if redis_val is not None:
                _l1_set(project_id, redis_val)
                set_current_span_dd_tags({"project_version.cache_hit": "L2"})
                return redis_val

        # Only span the cache-miss path. Cache-hit calls are extremely high
        # volume and produce noisy DD spans with no useful information.
        with ddtrace.tracer.trace("table_routing.fetch_residence"):
            residence = get_project_data_residence(project_id, ch_client)

            set_root_span_dd_tags({"project_version.fetch_residence": residence.value})
            set_current_span_dd_tags({"project_version.cache_hit": "clickhouse"})

            # Log warning if we detect dual residency - data should only ever be in
            # calls_merged OR calls_complete, not both. This is handled gracefully but
            # indicates an unexpected state that should be investigated.
            if residence == ProjectDataResidence.BOTH:
                logger.warning(
                    "Detected dual call residency for project %s. ", project_id
                )
                set_current_span_dd_tags(
                    {
                        "project_version.dual_residency": "true",
                        "project_version.dual_residency.project_id": project_id,
                    }
                )

            # Don't cache if project is empty, we could write to either table.
            if residence != ProjectDataResidence.EMPTY:
                if redis_client is not None:
                    _l2_set(redis_client, project_id, residence)
                _l1_set(project_id, residence)

            return residence

    def resolve_read_table(self, project_id: str, ch_client: CHClient) -> ReadTable:
        """Resolve which table to read from for a given project."""
        result = self._resolve_read_table(project_id, ch_client)
        set_root_span_dd_tags({"call_project_residence": result.value})
        return result

    def _resolve_read_table(self, project_id: str, ch_client: CHClient) -> ReadTable:
        if self._mode == CallsStorageServerMode.OFF:
            return ReadTable.CALLS_MERGED

        residence = self._get_residence(project_id, ch_client)
        set_current_span_dd_tags(
            {
                "project_version.residence": residence.value,
                "project_version.project_id": project_id,
            }
        )

        if self._mode == CallsStorageServerMode.FORCE_LEGACY:
            return ReadTable.CALLS_MERGED

        if self._mode == CallsStorageServerMode.AUTO:
            if residence in {
                ProjectDataResidence.COMPLETE_ONLY,
                ProjectDataResidence.BOTH,
                ProjectDataResidence.EMPTY,
            }:
                return ReadTable.CALLS_COMPLETE
            if residence == ProjectDataResidence.MERGED_ONLY:
                return ReadTable.CALLS_MERGED

        raise ValueError(f"Invalid mode/residence: {self._mode}/{residence}")

    def resolve_v1_write_target(
        self,
        project_id: str,
        ch_client: CHClient,
    ) -> WriteTarget:
        """Resolve write target for V1 (legacy) API calls.

        V1 writes go to MERGED unless project has any COMPLETE data.
        In the COMPLETE_ONLY or BOTH case, the caller should raise an error
        to prompt users to upgrade their SDK.

        Args:
            project_id: The internal project ID.
            ch_client: ClickHouse client instance.

        Returns:
            WriteTarget indicating which table to write to.
        """
        result = self._resolve_v1_write_target(project_id, ch_client)
        set_root_span_dd_tags({"call_project_residence": result.value})
        return result

    def _resolve_v1_write_target(
        self, project_id: str, ch_client: CHClient
    ) -> WriteTarget:
        if self._mode == CallsStorageServerMode.OFF:
            return WriteTarget.CALLS_MERGED

        residence = self._get_residence(project_id, ch_client)
        set_current_span_dd_tags(
            {
                "project_version.residence": residence.value,
                "project_version.project_id": project_id,
            }
        )

        if self._mode == CallsStorageServerMode.FORCE_LEGACY:
            return WriteTarget.CALLS_MERGED

        if self._mode == CallsStorageServerMode.AUTO:
            # V1 writes go to MERGED unless project has any calls_complete data.
            # COMPLETE_ONLY or BOTH → return COMPLETE to signal caller should raise error.
            if residence in {
                ProjectDataResidence.COMPLETE_ONLY,
                ProjectDataResidence.BOTH,
            }:
                return WriteTarget.CALLS_COMPLETE
            return WriteTarget.CALLS_MERGED

        raise ValueError(f"Invalid mode/residence: {self._mode}/{residence}")

    def resolve_v2_write_target(
        self,
        project_id: str,
        ch_client: CHClient,
    ) -> WriteTarget:
        """Resolve write target for V2 API calls.

        V2 writes go to COMPLETE unless project already has MERGED data.

        Args:
            project_id: The internal project ID.
            ch_client: ClickHouse client instance.

        Returns:
            WriteTarget indicating which table to write to.
        """
        result = self._resolve_v2_write_target(project_id, ch_client)
        set_root_span_dd_tags({"call_project_residence": result.value})
        return result

    def _resolve_v2_write_target(
        self, project_id: str, ch_client: CHClient
    ) -> WriteTarget:
        if self._mode == CallsStorageServerMode.OFF:
            return WriteTarget.CALLS_MERGED

        residence = self._get_residence(project_id, ch_client)
        set_current_span_dd_tags(
            {
                "project_version.residence": residence.value,
                "project_version.project_id": project_id,
            }
        )

        if self._mode == CallsStorageServerMode.FORCE_LEGACY:
            return WriteTarget.CALLS_MERGED

        if self._mode == CallsStorageServerMode.AUTO:
            # V2 writes go to MERGED if there is already calls_merged data
            if residence == ProjectDataResidence.MERGED_ONLY:
                return WriteTarget.CALLS_MERGED
            return WriteTarget.CALLS_COMPLETE

        raise ValueError(f"Invalid mode/residence: {self._mode}/{residence}")


# ---------------------------------------------------------------------------
# Cache-layer helpers
# ---------------------------------------------------------------------------


def _residence_cache_key(project_id: str) -> str:
    return f"{REDIS_RESIDENCE_KEY_PREFIX}{project_id}"


def _l1_get(project_id: str) -> ProjectDataResidence | None:
    """Read residence from the in-process LRU cache."""
    with _project_residence_cache_lock:
        return _project_residence_cache.get(project_id)


def _l1_set(project_id: str, residence: ProjectDataResidence) -> None:
    """Write residence to the in-process LRU cache."""
    with _project_residence_cache_lock:
        _project_residence_cache[project_id] = residence


def _l2_get(
    redis_client: redis.Redis, project_id: str
) -> ProjectDataResidence | None:
    """Try to read residence from Redis. Returns None on miss, unknown value, or error."""
    try:
        val = redis_client.get(_residence_cache_key(project_id))
        if val is None:
            return None
        return ProjectDataResidence(val)
    except ValueError:
        # Stale/unknown enum value written by a different code version. Treat
        # as a miss and let ClickHouse re-resolve.
        logger.warning(
            "Unknown project residence value in Redis for project %s: %r",
            project_id,
            val,
        )
        return None
    except Exception:
        logger.exception(
            "Redis L2 cache read failed for project %s", project_id
        )
        return None


def _l2_set(
    redis_client: redis.Redis,
    project_id: str,
    residence: ProjectDataResidence,
) -> None:
    """Try to write residence to Redis with TTL. Logs errors but does not raise."""
    try:
        redis_client.set(
            _residence_cache_key(project_id),
            residence.value,
            ex=REDIS_RESIDENCE_EXPIRY_SECS,
        )
    except Exception:
        logger.exception(
            "Redis L2 cache write failed for project %s", project_id
        )


def _l2_delete(redis_client: redis.Redis, project_id: str) -> None:
    """Try to delete a key from Redis. Logs errors but does not raise."""
    try:
        redis_client.delete(_residence_cache_key(project_id))
    except Exception:
        logger.exception(
            "Redis L2 cache delete failed for project %s", project_id
        )
