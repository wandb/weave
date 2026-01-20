import logging
import threading

import ddtrace
from cachetools import LRUCache
from clickhouse_connect.driver.client import Client as CHClient

from weave.trace_server.datadog import set_current_span_dd_tags
from weave.trace_server.project_version.clickhouse_project_version import (
    get_project_data_residence,
)
from weave.trace_server.project_version.types import (
    CallsStorageServerMode,
    ProjectDataResidence,
    ReadTable,
    WriteTarget,
)

logger = logging.getLogger(__name__)

PROJECT_RESIDENCE_CACHE_SIZE = 10_000

# Global cache shared across all resolvers
_project_residence_cache: LRUCache[str, ProjectDataResidence] = LRUCache(
    maxsize=PROJECT_RESIDENCE_CACHE_SIZE
)
_project_residence_cache_lock = threading.Lock()


def reset_project_residence_cache() -> None:
    """Clear the cached project data residence entries.

    Examples:
        >>> reset_project_residence_cache()

    """
    with _project_residence_cache_lock:
        _project_residence_cache.clear()


class TableRoutingResolver:
    """Resolver for determining which table to read from or write to based on project data residence.

    Uses a global cache of project data residence information shared across all threads.
    """

    def __init__(self) -> None:
        self._mode = CallsStorageServerMode.from_env()

    def _get_residence(
        self, project_id: str, ch_client: CHClient
    ) -> ProjectDataResidence:
        with _project_residence_cache_lock:
            cached = _project_residence_cache.get(project_id)
        if cached is not None:
            return cached

        residence = get_project_data_residence(project_id, ch_client)

        # Log warning if we detect dual residency - data should only ever be in
        # calls_merged OR calls_complete, not both. This is handled gracefully but
        # indicates an unexpected state that should be investigated.
        if residence == ProjectDataResidence.BOTH:
            logger.warning(f"Detected dual call residency for project {project_id}. ")
            set_current_span_dd_tags(
                {
                    "project_version.dual_residency": "true",
                    "project_version.dual_residency.project_id": project_id,
                }
            )

        # Don't cache if project is empty, we could write to either table.
        if residence != ProjectDataResidence.EMPTY:
            with _project_residence_cache_lock:
                _project_residence_cache[project_id] = residence

        return residence

    @ddtrace.tracer.wrap(name="table_routing.resolve_read_table")
    def resolve_read_table(self, project_id: str, ch_client: CHClient) -> ReadTable:
        """Resolve which table to read from for a given project."""
        if self._mode == CallsStorageServerMode.OFF:
            return ReadTable.CALLS_MERGED

        residence = self._get_residence(project_id, ch_client)
        set_current_span_dd_tags({"project_version.residence": residence.value})

        if self._mode == CallsStorageServerMode.FORCE_LEGACY:
            return ReadTable.CALLS_MERGED

        if self._mode == CallsStorageServerMode.AUTO:
            if residence in (
                ProjectDataResidence.COMPLETE_ONLY,
                ProjectDataResidence.BOTH,
                ProjectDataResidence.EMPTY,
            ):
                return ReadTable.CALLS_COMPLETE
            if residence == ProjectDataResidence.MERGED_ONLY:
                return ReadTable.CALLS_MERGED

        raise ValueError(f"Invalid mode/residence: {self._mode}/{residence}")

    @ddtrace.tracer.wrap(name="table_routing.resolve_v1_write_target")
    def resolve_v1_write_target(
        self,
        project_id: str,
        ch_client: CHClient,
    ) -> WriteTarget:
        """Resolve write target for V1 (legacy) API calls.

        V1 writes go to MERGED unless project only has COMPLETE data.
        In the COMPLETE_ONLY case, the caller should raise an error.

        Args:
            project_id: The internal project ID.
            ch_client: ClickHouse client instance.

        Returns:
            WriteTarget indicating which table to write to.
        """
        if self._mode == CallsStorageServerMode.OFF:
            return WriteTarget.CALLS_MERGED

        residence = self._get_residence(project_id, ch_client)
        set_current_span_dd_tags({"project_version.residence": residence.value})

        if self._mode == CallsStorageServerMode.FORCE_LEGACY:
            return WriteTarget.CALLS_MERGED

        if self._mode == CallsStorageServerMode.AUTO:
            # V1 writes go to MERGED unless project only has COMPLETE data
            if residence == ProjectDataResidence.COMPLETE_ONLY:
                return WriteTarget.CALLS_COMPLETE
            return WriteTarget.CALLS_MERGED

        raise ValueError(f"Invalid mode/residence: {self._mode}/{residence}")

    @ddtrace.tracer.wrap(name="table_routing.resolve_v2_write_target")
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
        if self._mode == CallsStorageServerMode.OFF:
            return WriteTarget.CALLS_MERGED

        residence = self._get_residence(project_id, ch_client)
        set_current_span_dd_tags({"project_version.residence": residence.value})

        if self._mode == CallsStorageServerMode.FORCE_LEGACY:
            return WriteTarget.CALLS_MERGED

        if self._mode == CallsStorageServerMode.AUTO:
            # V2 writes go to MERGED if there is already calls_merged data
            if residence == ProjectDataResidence.MERGED_ONLY:
                return WriteTarget.CALLS_MERGED
            return WriteTarget.CALLS_COMPLETE

        raise ValueError(f"Invalid mode/residence: {self._mode}/{residence}")
