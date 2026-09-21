"""Utilities for working with project IDs."""


def to_project_id(entity: str, project: str) -> str:
    """Format entity and project as 'entity/project'.

    Args:
        entity: Entity name.
        project: Project name.

    Returns:
        Project ID in format "entity/project".

    Raises:
        ValueError: If entity or project is empty or contains '/'.

    Examples:
        >>> to_project_id("my-entity", "my-project")
        'my-entity/my-project'
        >>> to_project_id("", "my-project")
        Traceback (most recent call last):
        ...
        ValueError: entity must be non-empty
    """
    if not entity:
        raise ValueError("entity must be non-empty")
    if not project:
        raise ValueError("project must be non-empty")
    if "/" in entity:
        raise ValueError("entity cannot contain '/'")
    if "/" in project:
        raise ValueError("project cannot contain '/'")
    return f"{entity}/{project}"


def from_project_id(project_id: str) -> tuple[str, str]:
    """Parse 'entity/project' string into (entity, project) tuple.

    Args:
        project_id: Project ID in format "entity/project".

    Returns:
        Tuple of (entity, project).

    Raises:
        ValueError: If project_id is not in the expected format or contains invalid values.

    Examples:
        >>> from_project_id("my-entity/my-project")
        ('my-entity', 'my-project')
        >>> from_project_id("invalid")
        Traceback (most recent call last):
        ...
        ValueError: Invalid project_id format: invalid. Expected 'entity/project'
    """
    try:
        entity, project = project_id.split("/", 1)
    except ValueError as e:
        raise ValueError(
            f"Invalid project_id format: {project_id}. Expected 'entity/project'"
        ) from e
    if not entity:
        raise ValueError("entity must be non-empty")
    if not project:
        raise ValueError("project must be non-empty")
    if "/" in entity:
        raise ValueError("entity cannot contain '/'")
    if "/" in project:
        raise ValueError("project cannot contain '/'")
    return entity, project
