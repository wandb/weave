"""Base interface and composition for project version resolution."""

import asyncio
from typing import Protocol, Union

from weave.trace_server.project_version.types import ProjectVersion


class ProjectVersionService(Protocol):
    """Resolves the schema version for a given project.

    Returns:
        ProjectVersion: Enum value indicating which table to use:
            - OLD_VERSION (0): Legacy schema (calls_merged)
            - NEW_VERSION (1): New schema (calls_complete)
            - EMPTY_PROJECT (-1): No calls in either table

    Examples:
        >>> service = InMemoryProjectVersionCache(...)
        >>> version = await service.get_project_version("my-project")
        >>> assert version in (ProjectVersion.OLD_VERSION, ProjectVersion.NEW_VERSION, ProjectVersion.EMPTY_PROJECT)
    """

    async def get_project_version(self, project_id: str) -> Union[ProjectVersion, int]:
        """Get the project version for routing decisions.

        Returns:
            Union[ProjectVersion, int]: ProjectVersion enum or int for backwards compatibility.
        """
        ...

    def get_project_version_sync(self, project_id: str) -> Union[ProjectVersion, int]:
        """Get the project version for routing decisions.

        Returns:
            Union[ProjectVersion, int]: ProjectVersion enum or int for backwards compatibility.
        """
        return asyncio.get_event_loop().run_until_complete(
            self.get_project_version(project_id)
        )
