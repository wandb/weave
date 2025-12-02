import logging
from typing import Any

import ddtrace
from cachetools import LRUCache

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

PER_REPLICA_CACHE_SIZE = 10_000


class TableRoutingResolver:
    """Resolver for determining which table to read from or write to based on project data residence.

    This resolver maintains a cache of project data residence information to avoid
    repeated queries to the database.

    Args:
        ch_client: ClickHouse client instance for querying project data residence.
        cache_size: Size of the in-memory cache (defaults to 10,000).
    """

    def __init__(
        self,
        ch_client: Any,
        cache_size: int = PER_REPLICA_CACHE_SIZE,
    ):
        self._cache: LRUCache[str, ProjectDataResidence] = LRUCache(maxsize=cache_size)
        self._ch_client = ch_client
        self._mode = CallsStorageServerMode.from_env()

    def _get_residence(self, project_id: str) -> ProjectDataResidence:
        cached = self._cache.get(project_id)
        if cached is not None:
            return cached

        residence = get_project_data_residence(project_id, lambda: self._ch_client)

        # Don't cache if project is empty, we could write to either table.
        if residence != ProjectDataResidence.EMPTY:
            self._cache[project_id] = residence

        # TODO: remove me, this is temporary to guage cache size impact
        if root_span := ddtrace.tracer.current_root_span():
            root_span.set_tag("cache_size", len(self._cache))

        return residence

    @ddtrace.tracer.wrap(name="table_routing.resolve_read_table")
    def resolve_read_table(self, project_id: str) -> ReadTable:
        if self._mode == CallsStorageServerMode.OFF:
            return ReadTable.CALLS_MERGED

        residence = self._get_residence(project_id)

        if self._mode == CallsStorageServerMode.FORCE_LEGACY:
            return ReadTable.CALLS_MERGED

        if self._mode == CallsStorageServerMode.AUTO:
            if residence in (
                ProjectDataResidence.COMPLETE_ONLY,
                ProjectDataResidence.BOTH,
            ):
                return ReadTable.CALLS_COMPLETE
            return ReadTable.CALLS_MERGED

        if self._mode == CallsStorageServerMode.DUAL_WRITE:
            # Duel writes shadows w/ calls_complete, we still should be reading from
            # the calls_merged tables.
            return ReadTable.CALLS_MERGED

        return ReadTable.CALLS_MERGED

    @ddtrace.tracer.wrap(name="table_routing.resolve_write_target")
    def resolve_write_target(self, project_id: str) -> WriteTarget:
        if self._mode == CallsStorageServerMode.OFF:
            return WriteTarget.CALLS_MERGED

        residence = self._get_residence(project_id)

        if self._mode == CallsStorageServerMode.FORCE_LEGACY:
            return WriteTarget.CALLS_MERGED

        if self._mode == CallsStorageServerMode.AUTO:
            if residence in (
                ProjectDataResidence.COMPLETE_ONLY,
                ProjectDataResidence.BOTH,
            ):
                return WriteTarget.CALLS_COMPLETE
            return WriteTarget.CALLS_MERGED

        if self._mode == CallsStorageServerMode.DUAL_WRITE:
            return WriteTarget.BOTH

        return WriteTarget.CALLS_MERGED
