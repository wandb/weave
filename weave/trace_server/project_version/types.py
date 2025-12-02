"""Project version types for routing between calls tables."""

import logging
import os
from enum import Enum

logger = logging.getLogger(__name__)

DEFAULT_SERVER_MODE = "force_legacy"

# Project Version Routing Matrix
# ==============================
#
# ┌─────────────────────────┬──────────────────────┬──────────────────────┬──────────────────────┬──────────────────────┐
# │ Project Data Residence  │ AUTO                 │ DUAL_WRITE           │ FORCE_LEGACY         │ OFF                  │
# │ (Physical State)        │ (Read / Write)       │ (Read / Write)       │ (Read / Write)       │ (Read / Write)       │
# ├─────────────────────────┼──────────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
# │ EMPTY                   │ MERGED / MERGED      │ MERGED / BOTH        │ MERGED / MERGED      │ MERGED / MERGED      │
# │ MERGED_ONLY             │ MERGED / MERGED      │ MERGED / BOTH        │ MERGED / MERGED      │ MERGED / MERGED      │
# │ COMPLETE_ONLY           │ COMPLETE / COMPLETE  │ MERGED / BOTH        │ MERGED / MERGED      │ MERGED / MERGED      │
# │ BOTH                    │ COMPLETE / COMPLETE  │ MERGED / BOTH        │ MERGED / MERGED      │ MERGED / MERGED      │
# └─────────────────────────┴──────────────────────┴──────────────────────┴──────────────────────┴──────────────────────┘


class ProjectDataResidence(Enum):
    EMPTY = "empty"
    MERGED_ONLY = "merged_only"
    COMPLETE_ONLY = "complete_only"
    BOTH = "both"


class CallsStorageServerMode(str, Enum):
    """Modes for controlling server storage behavior.

    AUTO: Default behavior - uses table to determine routing.
    FORCE_LEGACY: Forces all reads/writes to calls_merged table.
    DUAL_WRITE: Dual-write mode - Writes to both tables, reads from calls_merged.
    OFF: Skips DB queries entirely, assumes legacy behavior.
    """

    AUTO = "auto"
    FORCE_LEGACY = "force_legacy"
    DUAL_WRITE = "dual_write"
    OFF = "off"

    @classmethod
    def from_env(cls) -> "CallsStorageServerMode":
        mode_str = os.getenv("PROJECT_VERSION_MODE", DEFAULT_SERVER_MODE).lower()
        try:
            return cls(mode_str)
        except ValueError:
            logger.warning(
                f"Invalid PROJECT_VERSION_MODE '{mode_str}', defaulting to 'auto'. "
                f"Valid options: {', '.join([m.value for m in cls])}"
            )
            return cls(DEFAULT_SERVER_MODE)


class ReadTable(str, Enum):
    CALLS_MERGED = "calls_merged"
    CALLS_COMPLETE = "calls_complete"


class WriteTarget(str, Enum):
    CALLS_MERGED = "calls_merged"
    CALLS_COMPLETE = "calls_complete"
    BOTH = "both"
