"""Gorilla config-based project version provider."""

from typing import Any, Optional


class GorillaProjectVersionProvider:
    """
    Reads project version from Gorilla MySQL config via gRPC/HTTP.

    Args:
        gorilla_client: Client for querying Gorilla project config.

    Raises:
        Exception: If Gorilla is unavailable or project not found.

    Examples:
        >>> gorilla_provider = GorillaProjectVersionProvider(
        ...     gorilla_client=wb_gql_client
        ... )
        >>> version = await gorilla_provider.get_project_version("proj-123")
    """

    def __init__(
        self,
        gorilla_client: Optional[Any],
    ):
        self._gorilla = gorilla_client

    async def get_project_version(self, project_id: str) -> int:
        """
        Query Gorilla config for project version.

        Raises:
            Exception: If Gorilla is unavailable or config not found.
        """
        if self._gorilla is None:
            raise ValueError("Gorilla client is unavailable")

        config = self._gorilla.get_project_config(project_id)
        return config.get("weaveProjectVersion", 0)

