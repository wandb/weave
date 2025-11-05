"""Project version types for routing between calls tables."""

import logging
import os
from enum import Enum, IntEnum
from typing import Protocol

logger = logging.getLogger(__name__)


DEFAULT_PROJECT_VERSION_MODE = "auto"

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

    """No calls in either table - new project."""
    EMPTY_PROJECT = -1

    """Legacy schema using calls_merged table."""
    CALLS_MERGED_VERSION = 0

    """New schema using calls_complete table."""
    CALLS_COMPLETE_VERSION = 1

class ProjectVersionMode(str, Enum):
    """Modes for controlling project version resolution behavior.

    AUTO: Default behavior - uses table to determine project version.
    CALLS_MERGED: Forces all reads/writes to calls_merged table (queries DB for perf measurement).
    CALLS_MERGED_READ: Forces reads to calls_merged table, writes use determined version.
    OFF: Skips DB queries entirely, returns CALLS_MERGED_VERSION immediately.
    """

    AUTO = "auto"
    CALLS_MERGED = "calls_merged"
    CALLS_MERGED_READ = "calls_merged_read"
    OFF = "off"

    @classmethod
    def from_env(cls) -> "ProjectVersionMode":
        """Read project version mode from environment variable (defaults to AUTO)."""
        mode_str = os.getenv(
            "PROJECT_VERSION_MODE", DEFAULT_PROJECT_VERSION_MODE
        ).lower()
        try:
            return cls(mode_str)
        except ValueError:
            logger.warning(
                f"Invalid PROJECT_VERSION_MODE '{mode_str}', defaulting to 'auto'. "
                f"Valid options: {', '.join([m.value for m in cls])}"
            )
            return cls.AUTO


class Provider(Protocol):
    """Protocol for project version providers.

    Providers resolve project versions and always return a value (EMPTY_PROJECT if no data).
    This is distinct from caches, which return Optional to indicate cache misses.

    Examples:
        >>> class MyProvider:
        ...     def get_project_version_sync(self, project_id: str) -> ProjectVersion:
        ...         # Implementation - always returns a value
        ...         return ProjectVersion.CALLS_COMPLETE_VERSION
    """

    def get_project_version_sync(
        self, project_id: str, is_write: bool = False
    ) -> ProjectVersion:
        """Get project version synchronously.

        Args:
            project_id: The project identifier.
            is_write: Whether this is for a write operation.

        Returns:
            ProjectVersion - always returns a value (EMPTY_PROJECT if no data found).
        """
        ...
