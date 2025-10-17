"""Project version types for routing between calls tables."""

from enum import IntEnum


class ProjectVersion(IntEnum):
    """Represents the project version for table routing.

    This enum determines which calls table to use for reads/writes:
    - OLD_VERSION (0): Use calls_merged table (legacy schema)
    - NEW_VERSION (1): Use calls_complete table (new schema)
    - EMPTY_PROJECT (-1): No calls in either table (new project, can write to either)

    Examples:
        >>> version = ProjectVersion.NEW_VERSION
        >>> assert version == 1
        >>> version = ProjectVersion.EMPTY_PROJECT
        >>> assert version == -1
    """

    OLD_VERSION = 0
    """Legacy schema using calls_merged table."""

    NEW_VERSION = 1
    """New schema using calls_complete table."""

    EMPTY_PROJECT = -1
    """No calls in either table - new project."""
