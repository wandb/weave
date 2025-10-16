"""Helper for selecting the correct calls table based on project version."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from weave.trace_server.project_version.base import ProjectVersionService


def get_calls_table(project_id: str, version_service: "ProjectVersionService") -> str:
    """
    Return the appropriate calls table name based on project version.

    Args:
        project_id: The project ID to look up.
        version_service: Service to resolve the project version.

    Returns:
        "calls_merged" for version 0, "calls_complete" for version 1.

    Examples:
        >>> table = get_calls_table("my-project", version_service)
        >>> assert table in ("calls_merged", "calls_complete")
    """
    # Note: This is a synchronous helper that calls async code
    # In practice, this should be called from async context or
    # the version should be pre-fetched
    import asyncio

    try:
        version = asyncio.get_event_loop().run_until_complete(
            version_service.get_project_version(project_id)
        )
    except RuntimeError:
        # If no event loop is running, create a new one
        version = asyncio.run(version_service.get_project_version(project_id))

    return "calls_complete" if version == 1 else "calls_merged"

