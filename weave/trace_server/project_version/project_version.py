import logging
import threading
from collections.abc import Callable
from typing import Any, Optional

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

_resolver: Optional["TableRoutingResolver"] = None
_resolver_lock = threading.Lock()


def init_resolver(
    ch_client_factory: Callable[[], Any],
    cache_size: int = PER_REPLICA_CACHE_SIZE,
) -> None:
    """Initialize the project version resolver.

    Call this once at application startup. Subsequent calls are ignored
    (the first initialization wins).

    Args:
        ch_client_factory: Callable that returns a ClickHouse client.
        cache_size: Size of the in-memory cache (defaults to 10,000).
    """
    global _resolver
    with _resolver_lock:
        if _resolver is None:
            _resolver = TableRoutingResolver(
                ch_client_factory=ch_client_factory,
                cache_size=cache_size,
            )


def resolve_read_table(project_id: str) -> ReadTable:
    if _resolver is None:
        raise RuntimeError("init_resolver() must be called before resolve_read_table()")
    return _resolver.resolve_read_table(project_id)


def resolve_write_target(project_id: str) -> WriteTarget:
    if _resolver is None:
        raise RuntimeError(
            "init_resolver() must be called before resolve_write_target()"
        )
    return _resolver.resolve_write_target(project_id)


class TableRoutingResolver:
    def __init__(
        self,
        ch_client_factory: Callable[[], Any],
        cache_size: int = PER_REPLICA_CACHE_SIZE,
    ):
        self._cache: LRUCache[str, ProjectDataResidence] = LRUCache(maxsize=cache_size)
        self._ch_client_factory = ch_client_factory
        self._mode = CallsStorageServerMode.from_env()

    def _get_residence(self, project_id: str) -> ProjectDataResidence:
        cached = self._cache.get(project_id)
        if cached is not None:
            return cached

        residence = get_project_data_residence(project_id, self._ch_client_factory)

        # Don't cache if project is empty, we could write to either table.
        if residence != ProjectDataResidence.EMPTY:
            self._cache[project_id] = residence

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
            # Duel writes shadows to calls_complete, we still should be reading from
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
