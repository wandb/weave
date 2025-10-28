"""Configuration for project version resolution modes."""

import os
from enum import Enum


class ProjectVersionMode(str, Enum):
    """Modes for controlling project version resolution behavior.

    Attributes:
        AUTO: Default behavior - uses table to determine project version.
        CALLS_MERGED: Forces all reads and writes to calls_merged table.
            Returns CALLS_MERGED_VERSION after querying DB (to measure perf impact).
        CALLS_MERGED_READ: Forces all reads to use calls_merged table,
            but allows writes to use the determined version.
        OFF: Skips DB queries entirely and returns CALLS_MERGED_VERSION immediately.

    Examples:
        >>> mode = ProjectVersionMode.from_env()
        >>> assert mode in ProjectVersionMode
    """

    AUTO = "auto"
    """Current behavior using table to determine project version."""

    CALLS_MERGED = "calls_merged"
    """All reads and writes go to old table, query DB to measure perf impact."""

    CALLS_MERGED_READ = "calls_merged_read"
    """Reads use calls_merged table, writes use determined version."""

    OFF = "off"
    """Skip DB and return CALLS_MERGED_VERSION immediately."""

    @classmethod
    def from_env(cls) -> "ProjectVersionMode":
        """Read project version mode from environment variable.

        Returns:
            ProjectVersionMode: The configured mode (defaults to AUTO).

        Examples:
            >>> os.environ["PROJECT_VERSION_MODE"] = "off"
            >>> mode = ProjectVersionMode.from_env()
            >>> assert mode == ProjectVersionMode.OFF
        """
        mode_str = os.getenv("PROJECT_VERSION_MODE", "auto").lower()
        try:
            return cls(mode_str)
        except ValueError:
            # Invalid mode, default to AUTO and log warning
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"Invalid PROJECT_VERSION_MODE '{mode_str}', defaulting to 'auto'. "
                f"Valid options: {', '.join([m.value for m in cls])}"
            )
            return cls.AUTO
