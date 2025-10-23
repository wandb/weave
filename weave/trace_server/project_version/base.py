"""Base interface and composition for project version resolution."""

from typing import Protocol

from weave.trace_server.project_version.types import ProjectVersion


class ProjectVersionService(Protocol):
    """Resolves the schema version for a given project.

    Returns:
        ProjectVersion: Enum value indicating which table to use:
            - EMPTY_PROJECT (-1): No calls in either table
            - CALLS_MERGED_VERSION (0): Legacy schema (calls_merged)
            - CALLS_COMPLETE_VERSION (1): New schema (calls_complete)

    Examples:
        >>> service = ClickHouseProjectVersionProvider(...)
        >>> version = await service.get_project_version("my-project")
        >>> assert version in (ProjectVersion.CALLS_MERGED_VERSION, ProjectVersion.CALLS_COMPLETE_VERSION, ProjectVersion.EMPTY_PROJECT)
    """

    async def get_project_version(self, project_id: str) -> ProjectVersion:
        """Get the project version for routing decisions.

        Returns:
            Union[ProjectVersion, int]: ProjectVersion enum or int for backwards compatibility.
        """
        ...

    def get_project_version_sync(self, project_id: str) -> ProjectVersion:
        """Get the project version for routing decisions.

        Returns:
            Union[ProjectVersion, int]: ProjectVersion enum or int for backwards compatibility.
        """
        ...
