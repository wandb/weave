import logging
import threading

import ddtrace
from cachetools import LRUCache
from clickhouse_connect.driver.client import Client as CHClient

from weave.trace_server.datadog import set_current_span_dd_tags, set_root_span_dd_tags
from weave.trace_server.project_version.clickhouse_project_version import (
    get_project_data_residence,
)
from weave.trace_server.project_version.types import (
    CallSource,
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

    def update_cache(
        self, project_id: str, residence: ProjectDataResidence | None
    ) -> None:
        """Update the residence cache for a project with a known state."""
        with _project_residence_cache_lock:
            if residence is None:
                _project_residence_cache.pop(project_id, None)
            else:
                _project_residence_cache[project_id] = residence

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

        set_current_span_dd_tags({"cache_size": len(_project_residence_cache)})

        return residence

    @ddtrace.tracer.wrap(name="table_routing.resolve_read_table")
    def resolve_read_table(self, project_id: str, ch_client: CHClient) -> ReadTable:
        """Resolve which table to read from for a given project."""
        if self._mode == CallsStorageServerMode.OFF:
            return ReadTable.CALLS_MERGED

        residence = self._get_residence(project_id, ch_client)

        set_current_span_dd_tags({"residence": residence.value})
        set_root_span_dd_tags(
            {
                "table_routing.resolve_read_table.residence": residence.value,
                "table_routing.resolve_read_table.mode": self._mode.value,
            }
        )

        if self._mode == CallsStorageServerMode.FORCE_LEGACY:
            return ReadTable.CALLS_MERGED

        if self._mode == CallsStorageServerMode.DUAL_WRITE_READ_MERGED:
            # Edge case: COMPLETE_ONLY shouldn't happen in dual-write mode
            # but if it does, read from where the data actually is
            if residence == ProjectDataResidence.COMPLETE_ONLY:
                return ReadTable.CALLS_COMPLETE
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
    def resolve_write_target(
        self,
        project_id: str,
        ch_client: CHClient,
        source: CallSource,
    ) -> WriteTarget:
        """Resolve which table(s) to write to for a given project.

        Args:
            project_id: The project ID
            ch_client: ClickHouse client
            source: Source of the data. Supported values:
                - "sdk_calls_merged": Old SDK using call_start/call_end (calls_merged only)
                - "sdk_calls_complete": New SDK using calls_start_batch/calls_end_batch (dual-write capable)
                - "server": Server-side operations (OTEL, completions) - external sources

        Returns:
            WriteTarget indicating which table(s) to write to
        """
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

            # INVARIANT: If data exists in both tables, always write to both tables
            # regardless of source to maintain data consistency
            if residence == ProjectDataResidence.BOTH:
                return WriteTarget.BOTH

            # EMPTY projects: behavior depends on SDK capability
            if residence == ProjectDataResidence.EMPTY:
                if source == CallSource.SDK_CALLS_MERGED:
                    # Old SDK: don't initiate dual-write even in dual-write mode
                    return WriteTarget.CALLS_MERGED
                elif source == CallSource.SERVER:
                    # Server sources: don't initiate dual-write (safe rollout)
                    return WriteTarget.CALLS_MERGED
                elif source == CallSource.SDK_CALLS_COMPLETE:
                    # New SDK: initiate dual-write
                    return WriteTarget.BOTH
                else:
                    raise ValueError(f"Invalid source: {source}")

            # COMPLETE_ONLY projects: behavior depends on SDK capability
            # This is an edge error case, we should never be in dual write mode and
            # see projects that only have calls_complete data. Rather than error
            # only return complete_only, let caller deal with erroring.
            if residence == ProjectDataResidence.COMPLETE_ONLY:
                return WriteTarget.CALLS_COMPLETE

        if self._mode == CallsStorageServerMode.AUTO:
            if residence in (
                ProjectDataResidence.COMPLETE_ONLY,
                ProjectDataResidence.BOTH,
            ):
                return WriteTarget.CALLS_COMPLETE
            if residence == ProjectDataResidence.MERGED_ONLY:
                return WriteTarget.CALLS_MERGED

            # EMPTY projects: behavior depends on SDK capability
            if residence == ProjectDataResidence.EMPTY:
                if source == CallSource.SDK_CALLS_MERGED:
                    return WriteTarget.CALLS_MERGED
                elif source == CallSource.SERVER:
                    return WriteTarget.CALLS_COMPLETE
                elif source == CallSource.SDK_CALLS_COMPLETE:
                    return WriteTarget.CALLS_COMPLETE
                else:
                    raise ValueError(f"Invalid source: {source}")

        raise ValueError(f"Invalid mode/residence: {self._mode}/{residence}")
