"""Project version types for routing between calls tables."""

import logging
import os
from enum import Enum, IntEnum

logger = logging.getLogger(__name__)

# Project Version Mode Behavior Matrix
# =====================================
# ┌─────────────────────────┬────────────────────────┬─────────────────────────┬────────────────────────┐
# │ Calls Present In        │ AUTO                   │ FORCE_ONLY_CALLS_MERGED │ OFF (no db query)      │
# ├─────────────────────────┼────────────────────────┼─────────────────────────┼────────────────────────┤
# │ Neither table (empty)   │ EMPTY_PROJECT          │ CALLS_MERGED_VERSION    │ CALLS_MERGED_VERSION   │
# │ calls_merged only       │ CALLS_MERGED_VERSION   │ CALLS_MERGED_VERSION    │ CALLS_MERGED_VERSION   │
# │ calls_complete only     │ CALLS_COMPLETE_VERSION │ CALLS_MERGED_VERSION    │ CALLS_MERGED_VERSION   │
# │ Both tables             │ CALLS_MERGED_VERSION   │ CALLS_MERGED_VERSION    │ CALLS_MERGED_VERSION   │
# └─────────────────────────┴────────────────────────┴─────────────────────────┴────────────────────────┘
#
# Rollout stage 1: do the db query for latency impact, always return `calls_merged` table
DEFAULT_PROJECT_VERSION_MODE = "force_only_calls_merged"


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
    FORCE_ONLY_CALLS_MERGED: Forces all reads/writes to calls_merged table (queries DB for perf measurement).
    DUAL_WRITE: Dual-write mode - Writes to both tables, prefers reads from calls_complete table.
        Only initial write to calls_complete if project is empty.
    OFF: Skips DB queries entirely, returns CALLS_MERGED_VERSION immediately.
    """

    AUTO = "auto"
    FORCE_ONLY_CALLS_MERGED = "force_only_calls_merged"
    DUAL_WRITE = "dual_write"
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
            return cls(DEFAULT_PROJECT_VERSION_MODE)
