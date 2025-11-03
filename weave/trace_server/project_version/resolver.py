"""Concrete project version resolver with explicit provider order."""

import asyncio
import logging
import threading
from typing import Any, Optional

from cachetools import LRUCache

from weave.trace_server.project_version.base import ProjectVersionService
from weave.trace_server.project_version.clickhouse_provider import (
    ClickHouseProjectVersionProvider,
)
from weave.trace_server.project_version.types import ProjectVersionMode
from weave.trace_server.project_version.types import ProjectVersion

PER_REPLICA_CACHE_SIZE = 10_000

logger = logging.getLogger(__name__)


class ProjectVersionResolver(ProjectVersionService):
    """Resolves project versions by trying providers in explicit order.

    Provider order (fastest to slowest):
        1. In-memory cache
        2. ClickHouse (checks for calls_complete rows)

    Args:
        ch_client: ClickHouse client.

    Examples:
        >>> resolver = ProjectVersionResolver(
        ...     ch_client=clickhouse_client,
        ... )
        >>> version = await resolver.get_project_version("my-project")
    """

    def __init__(
        self,
        ch_client: Any,
    ):
        self._clickhouse_provider = ClickHouseProjectVersionProvider(
            ch_client=ch_client
        )
        self._cache: LRUCache[str, ProjectVersion] = LRUCache[str, ProjectVersion](
            maxsize=PER_REPLICA_CACHE_SIZE
        )
        self._mode = ProjectVersionMode.from_env()

    def _apply_mode(
        self, resolved_version: ProjectVersion, is_write: bool
    ) -> ProjectVersion:
        """Apply mode-specific overrides to resolved version.

        Modes that skip DB queries return early in get_project_version.
        This method only handles modes that override the resolved result.
        """
        if self._mode == ProjectVersionMode.CALLS_MERGED:
            return ProjectVersion.CALLS_MERGED_VERSION
        return resolved_version

    async def _resolve_version(self, project_id: str) -> ProjectVersion:
        """Resolve version through provider chain, without mode overrides."""
        cached = self._cache.get(project_id)
        if cached is not None:
            return cached

        version = await self._clickhouse_provider.get_project_version(project_id)
        if version != ProjectVersion.EMPTY_PROJECT:
            self._cache[project_id] = version

        return version

    async def get_project_version(
        self, project_id: str, is_write: bool = False
    ) -> ProjectVersion:
        """Resolve project version through explicit provider checks.

        Args:
            project_id: The project identifier.
            is_write: Whether this is for a write operation.

        Returns:
            ProjectVersion enum.
        """
        if self._mode == ProjectVersionMode.OFF:
            return ProjectVersion.CALLS_MERGED_VERSION

        if self._mode == ProjectVersionMode.CALLS_MERGED_READ and not is_write:
            return ProjectVersion.CALLS_MERGED_VERSION

        version = await self._resolve_version(project_id)
        return self._apply_mode(version, is_write)

    def get_project_version_sync(
        self, project_id: str, is_write: bool = False
    ) -> ProjectVersion:
        """Get the project version synchronously.

        Args:
            project_id: The project identifier.
            is_write: Whether this is for a write operation.

        Returns:
            ProjectVersion enum.
        """
        if self._mode == ProjectVersionMode.OFF:
            return ProjectVersion.CALLS_MERGED_VERSION

        if self._mode == ProjectVersionMode.CALLS_MERGED_READ and not is_write:
            return ProjectVersion.CALLS_MERGED_VERSION

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is None:
            return asyncio.run(self.get_project_version(project_id, is_write=is_write))

        result: list[ProjectVersion] = []
        exception: list[Exception] = []

        def run_in_new_loop() -> None:
            try:
                result.append(
                    asyncio.run(self.get_project_version(project_id, is_write=is_write))
                )
            except Exception as e:
                exception.append(e)

        thread = threading.Thread(target=run_in_new_loop)
        thread.start()
        thread.join()

        if exception:
            raise exception[0]

        return result[0]
