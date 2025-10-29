"""Configuration for project version resolution modes."""

import logging
import os
from enum import Enum

logger = logging.getLogger(__name__)


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
        mode_str = os.getenv("PROJECT_VERSION_MODE", "auto").lower()
        try:
            return cls(mode_str)
        except ValueError:
            logger.warning(
                f"Invalid PROJECT_VERSION_MODE '{mode_str}', defaulting to 'auto'. "
                f"Valid options: {', '.join([m.value for m in cls])}"
            )
            return cls.AUTO
