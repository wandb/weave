"""Project version types for routing between calls tables."""

import logging
import os
from enum import Enum, IntEnum

logger = logging.getLogger(__name__)

# Default should eventually be 'auto' but for added security during
# rollout, the default should be 'calls_merged' which still queries
# the db but always returns 'calls_merged' no matter what
DEFAULT_PROJECT_VERSION_MODE = "calls_merged"


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
