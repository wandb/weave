"""Base interface and composition for project version resolution."""

from typing import Protocol


class ProjectVersionService(Protocol):
    """Resolves the schema version for a given project.

    Returns:
        int: 0 for legacy schema (calls_merged), 1 for new schema (calls_complete).

    Examples:
        >>> service = InMemoryProjectVersionCache(...)
        >>> version = await service.get_project_version("my-project")
        >>> assert version in (0, 1)
    """

    async def get_project_version(self, project_id: str) -> int:
        """Get the project version for routing decisions."""
        ...
