"""Gorilla config-based project version provider."""

from typing import Optional, Union

from gql import gql
from src import auth_types, id_converters, wb_gql_client

from weave.trace_server.project_version.types import ProjectVersion

_set_project_version_mutation = gql(
    """
    mutation SetWeaveProjectVersion(
        $entityName: String!,
        $projectName: String!,
        $version: Int!
    ) {
        setWeaveProjectVersion(
            input: {
                entityName: $entityName,
                projectName: $projectName,
                version: $version
            }
        ) {
            project {
                internalId
                weaveProjectVersion
            }
        }
    }
    """
)


class GorillaProjectVersionProvider:
    """Reads project version from request context (populated during auth).

    This provider leverages the project context that's already populated
    during authentication, avoiding duplicate queries to Gorilla.

    Args:
        auth_params (Optional[auth_types.AuthParams]): Auth params for mutations

    Examples:
        >>> provider = GorillaProjectVersionProvider()
        >>> version = provider.get_project_version("entity/project")
        >>> assert version in (0, 1) or version is None
    """

    def __init__(self, auth_params: Optional[auth_types.AuthParams] = None):
        """Initialize provider with optional auth params for mutations.

        Args:
            auth_params (Optional[auth_types.AuthParams]): Required for set operations
        """
        self._auth_params = auth_params

    async def get_project_version(
        self, project_id: str
    ) -> Optional[Union[ProjectVersion, int]]:
        """Get project version from current request context.

        Args:
            project_id (str): External project ID (entity/project format)

        Returns:
            Optional[Union[ProjectVersion, int]]: 0 for legacy, 1 for new schema, None if not set.
            Note: Gorilla never stores EMPTY_PROJECT (-1), only OLD_VERSION (0) or NEW_VERSION (1).

        Examples:
            >>> provider = GorillaProjectVersionProvider()
            >>> version = await provider.get_project_version("myentity/myproject")
        """
        # Import here to avoid circular dependency
        from src.trace_server import get_project_context

        context = get_project_context()
        if context is None:
            # Context not available - this shouldn't happen after auth
            return None

        # Verify this is the right project
        if context.project_id != project_id:
            return None

        return context.weave_project_version

    async def set_project_version(self, project_id: str, version: int) -> None:
        """Set the project version for a given project via Gorilla mutation.

        Args:
            project_id (str): External project ID (entity/project format)
            version (int): Version to set (0 or 1). Note: -1 (EMPTY_PROJECT) should not be passed here.

        Raises:
            ValueError: If auth params not available or invalid version

        Examples:
            >>> provider = GorillaProjectVersionProvider(auth_params)
            >>> await provider.set_project_version("myentity/myproject", 1)
        """
        if self._auth_params is None:
            raise ValueError("Auth params required for setting project version")

        if version not in (0, 1):
            raise ValueError(
                f"Invalid version {version}, must be 0 or 1. "
                "EMPTY_PROJECT (-1) should not be persisted to Gorilla."
            )

        entity, project = id_converters.extract_ext_project_id_to_parts(project_id)

        wb_gql_client.execute_with_retry_cached(
            self._auth_params,
            _set_project_version_mutation,
            variable_values={
                "entityName": entity,
                "projectName": project,
                "version": version,
            },
        )
