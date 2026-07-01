import logging
import threading

from cachetools import LRUCache, TTLCache
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
from weave.trace_server.tracing import _tracer

logger = logging.getLogger(__name__)

PROJECT_RESIDENCE_CACHE_SIZE = 10_000
# Populated residence is treated as immutable (assumes data never migrates
# between tables post-write) and cached without expiry. EMPTY is cached (read
# path only, short TTL) so cold projects stop re-probing CH. Writes best-effort
# evict it, but the TTL is the real staleness bound: a read racing a write's
# probe->insert can re-cache EMPTY on any replica, including the writer. Worst
# case is a <=TTL transient empty read, never wrong data.
EMPTY_RESIDENCE_CACHE_TTL_SECS = 10

# Global caches shared across all resolvers and threads, keyed by project_id.
_project_residence_cache: LRUCache[str, ProjectDataResidence] = LRUCache(
    maxsize=PROJECT_RESIDENCE_CACHE_SIZE
)
_empty_residence_cache: TTLCache[str, ProjectDataResidence] = TTLCache(
    maxsize=PROJECT_RESIDENCE_CACHE_SIZE, ttl=EMPTY_RESIDENCE_CACHE_TTL_SECS
)
_project_residence_cache_lock = threading.Lock()


def reset_project_residence_cache() -> None:
    """Clear the cached project data residence entries."""
    with _project_residence_cache_lock:
        _project_residence_cache.clear()
        _empty_residence_cache.clear()


class TableRoutingResolver:
    """Resolver for determining which table to read from or write to based on project data residence.

    Uses a global cache of project data residence information shared across all threads.
    """

    def __init__(self) -> None:
        self._mode = CallsStorageServerMode.from_env()

    def _get_residence(
        self, project_id: str, ch_client: CHClient, *, cache_empty: bool = True
    ) -> ProjectDataResidence:
        # cache_empty=False on write paths: EMPTY must be ground-truth (a stale
        # EMPTY would misroute a V1 write into calls_merged past an upgrade error),
        # so skip the read cache and evict any entry instead of populating it.
        with _project_residence_cache_lock:
            cached = _project_residence_cache.get(project_id)
            if cached is None and cache_empty:
                cached = _empty_residence_cache.get(project_id)
        if cached is not None:
            return cached

        # Only span the cache-miss path. Cache-hit calls are extremely high
        # volume and produce noisy DD spans with no useful information.
        with _tracer.start_as_current_span("table_routing.fetch_residence"):
            residence = get_project_data_residence(project_id, ch_client)

            set_root_span_dd_tags({"project_version.fetch_residence": residence.value})

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

            # Populated residence -> long-lived cache. EMPTY -> short-TTL read cache;
            # a write resolution instead evicts any read-cached EMPTY so a post-write
            # read re-probes (best-effort; a racing read can re-cache it, TTL is the bound).
            with _project_residence_cache_lock:
                if residence != ProjectDataResidence.EMPTY:
                    _project_residence_cache[project_id] = residence
                elif cache_empty:
                    _empty_residence_cache[project_id] = residence
                else:
                    _empty_residence_cache.pop(project_id, None)

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

        residence = self._get_residence(project_id, ch_client, cache_empty=False)
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

        residence = self._get_residence(project_id, ch_client, cache_empty=False)
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
