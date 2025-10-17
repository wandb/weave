"""Helper for selecting the correct calls table based on project version."""

from typing import TYPE_CHECKING, Optional

from weave.trace_server.project_version.types import ProjectVersion

if TYPE_CHECKING:
    from weave.trace_server.project_version.base import ProjectVersionService


def get_calls_table(project_id: str, version_service: "ProjectVersionService", error_if_empty: bool = False) -> Optional[str]:
    """Return the appropriate calls table name based on project version.

    Args:
        project_id: The project ID to look up.
        version_service: Service to resolve the project version.

    Returns:
        "calls_complete" for NEW_VERSION (1) or EMPTY_PROJECT (-1),
        "calls_merged" for OLD_VERSION (0).

        For EMPTY_PROJECT, we default to "calls_complete" (new table) since
        it's a new project with no existing data.

    Examples:
        >>> table = get_calls_table("my-project", version_service)
        >>> assert table in ("calls_merged", "calls_complete")
    """
    version = version_service.get_project_version_sync(project_id)

    # For EMPTY_PROJECT, return None
    # For NEW_VERSION, use calls_complete
    # For OLD_VERSION, use calls_merged
    if version == ProjectVersion.OLD_VERSION:
        return "calls_merged"
    else:
        # Both NEW_VERSION (1) and EMPTY_PROJECT (-1) use calls_complete
        return "calls_complete"
