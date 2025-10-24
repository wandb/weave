"""Project version types for routing between calls tables."""

from enum import IntEnum


class ProjectVersion(IntEnum):
    """Represents the project version for table routing.

    This enum determines which calls table to use for reads/writes:
    - EMPTY_PROJECT (-1): No calls in either table (new project, can write to either)
    - CALLS_MERGED_VERSION (0): Use calls_merged table (legacy schema)
    - CALLS_COMPLETE_VERSION (1): Use calls_complete table (new schema)

    The enum is designed to be extensible for future migrations.

    Examples:
        >>> version = ProjectVersion.CALLS_COMPLETE_VERSION
        >>> assert version == 1
        >>> version = ProjectVersion.EMPTY_PROJECT
        >>> assert version == -1
    """

    EMPTY_PROJECT = -1
    """No calls in either table - new project."""

    CALLS_MERGED_VERSION = 0
    """Legacy schema using calls_merged table."""

    CALLS_COMPLETE_VERSION = 1
    """New schema using calls_complete table."""
