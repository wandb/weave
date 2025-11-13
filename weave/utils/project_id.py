"""Utilities for working with project IDs."""

import dataclasses


@dataclasses.dataclass(frozen=True)
class ProjectID:
    """Represents an entity and project pair.

    Attributes:
        entity: Entity name.
        project: Project name.

    Examples:
        >>> project_id = ProjectID.from_string("my-entity/my-project")
        >>> project_id.entity
        'my-entity'
        >>> project_id.project
        'my-project'
        >>> project_id.name
        'my-entity/my-project'
        >>> project_id = ProjectID("my-entity", "my-project")
        >>> project_id.name
        'my-entity/my-project'
    """

    entity: str
    project: str

    def __post_init__(self) -> None:
        """Validate entity and project values."""
        if not self.entity:
            raise ValueError("entity must be non-empty")
        if not self.project:
            raise ValueError("project must be non-empty")
        if "/" in self.entity:
            raise ValueError("entity cannot contain '/'")
        if "/" in self.project:
            raise ValueError("project cannot contain '/'")

    @property
    def name(self) -> str:
        """Return the project ID in format "entity/project"."""
        return f"{self.entity}/{self.project}"

    @classmethod
    def from_string(cls, project_id: str) -> "ProjectID":
        """Create ProjectID from a string in format "entity/project".

        Args:
            project_id: Project ID in format "entity/project".

        Returns:
            ProjectID instance.

        Raises:
            ValueError: If project_id is not in the expected format.

        Examples:
            >>> ProjectID.from_string("my-entity/my-project")
            ProjectID(entity='my-entity', project='my-project')
            >>> ProjectID.from_string("invalid")
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
        return cls(entity=entity, project=project)
