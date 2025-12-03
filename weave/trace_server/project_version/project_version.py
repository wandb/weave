import logging
import threading

import ddtrace
from cachetools import LRUCache
from clickhouse_connect.driver.client import Client as CHClient

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

        # Don't cache if project is empty, we could write to either table.
        if residence != ProjectDataResidence.EMPTY:
            with _project_residence_cache_lock:
                _project_residence_cache[project_id] = residence

        # TODO: remove me, this is temporary to guage cache size impact
        if root_span := ddtrace.tracer.current_root_span():
            root_span.set_tag("cache_size", len(_project_residence_cache))

        return residence

    @ddtrace.tracer.wrap(name="table_routing.resolve_read_table")
    def resolve_read_table(self, project_id: str, ch_client: CHClient) -> ReadTable:
        """Resolve which table to read from for a given project."""
        if self._mode == CallsStorageServerMode.OFF:
            return ReadTable.CALLS_MERGED

        residence = self._get_residence(project_id, ch_client)

        if self._mode == CallsStorageServerMode.FORCE_LEGACY:
            return ReadTable.CALLS_MERGED

        if self._mode == CallsStorageServerMode.DUAL_WRITE_READ_MERGED:
            return ReadTable.CALLS_MERGED

        if self._mode == CallsStorageServerMode.DUAL_WRITE_READ_COMPLETE:
            # Old projects have no data in calls_complete, we need to read from calls_merged
            if residence == ProjectDataResidence.MERGED_ONLY:
                return ReadTable.CALLS_MERGED

            if residence in (
                ProjectDataResidence.COMPLETE_ONLY,
                ProjectDataResidence.BOTH,
                ProjectDataResidence.EMPTY,
            ):
                return ReadTable.CALLS_COMPLETE

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

    @ddtrace.tracer.wrap(name="table_routing.resolve_write_target")
    def resolve_write_target(self, project_id: str, ch_client: CHClient) -> WriteTarget:
        """Resolve which table(s) to write to for a given project."""
        if self._mode == CallsStorageServerMode.OFF:
            return WriteTarget.CALLS_MERGED

        residence = self._get_residence(project_id, ch_client)

        if self._mode == CallsStorageServerMode.FORCE_LEGACY:
            return WriteTarget.CALLS_MERGED

        if self._mode in (
            CallsStorageServerMode.DUAL_WRITE_READ_MERGED,
            CallsStorageServerMode.DUAL_WRITE_READ_COMPLETE,
        ):
            if residence == ProjectDataResidence.MERGED_ONLY:
                # If we are dual writing, but the project only has calls_merged data
                # we DO NOT write to the calls_complete table. We ONLY dual write for
                # new projects where we can guarantee identical data in both tables.
                return WriteTarget.CALLS_MERGED

            if residence in (
                # Technically while dual writing COMPLETE_ONLY should never occur, but just in case
                # we should still to write to both tables
                ProjectDataResidence.COMPLETE_ONLY,
                ProjectDataResidence.BOTH,
                ProjectDataResidence.EMPTY,
            ):
                return WriteTarget.BOTH

        if self._mode == CallsStorageServerMode.AUTO:
            if residence in (
                ProjectDataResidence.COMPLETE_ONLY,
                ProjectDataResidence.BOTH,
                ProjectDataResidence.EMPTY,
            ):
                return WriteTarget.CALLS_COMPLETE
            if residence == ProjectDataResidence.MERGED_ONLY:
                return WriteTarget.CALLS_MERGED

        raise ValueError(f"Invalid mode/residence: {self._mode}/{residence}")
