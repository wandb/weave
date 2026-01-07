"""Project version types for routing between calls tables."""

import logging
import os
from enum import Enum

logger = logging.getLogger(__name__)

DEFAULT_SERVER_MODE = "auto"

# Project Version Routing Matrix
# ==============================
#
# ┌─────────────────────────┬──────────────────────┬─────────────────────────────┬────────────────────────────────┬──────────────────────┬──────────────────────┐
# │ Project Data Residence  │ AUTO                 │ DUAL_WRITE_READ_MERGED      │ DUAL_WRITE_READ_COMPLETE       │ FORCE_LEGACY         │ OFF                  │
# │ (Physical State)        │ (Read / Write)       │ (Read / Write)              │ (Read / Write)                 │ (Read / Write)       │ (Read / Write)       │
# ├─────────────────────────┼──────────────────────┼─────────────────────────────┼────────────────────────────────┼──────────────────────┼──────────────────────┤
# │ EMPTY                   │ COMPLETE / COMPLETE  │ MERGED / BOTH               │ COMPLETE / BOTH                │ MERGED / MERGED      │ MERGED / MERGED      │
# │ MERGED_ONLY             │ MERGED / MERGED      │ MERGED / MERGED             │ MERGED / MERGED                │ MERGED / MERGED      │ MERGED / MERGED      │
# │ COMPLETE_ONLY           │ COMPLETE / COMPLETE  │ COMPLETE / COMPLETE*        │ COMPLETE / COMPLETE*           │ MERGED / MERGED      │ MERGED / MERGED      │
# │ BOTH                    │ COMPLETE / COMPLETE  │ MERGED / BOTH               │ COMPLETE / BOTH                │ MERGED / MERGED      │ MERGED / MERGED      │
# └─────────────────────────┴──────────────────────┴─────────────────────────────┴────────────────────────────────┴──────────────────────┴──────────────────────┘
#
# * COMPLETE_ONLY in dual-write modes is an edge case that should never occur in production.
#   We never switch from AUTO to dual-write modes. When this edge case occurs, read from where the data actually is (calls_complete).


class ProjectDataResidence(Enum):
    EMPTY = "empty"
    MERGED_ONLY = "merged_only"
    COMPLETE_ONLY = "complete_only"
    BOTH = "both"


class CallsStorageServerMode(str, Enum):
    """Modes for controlling server storage behavior.

    AUTO: Default behavior - uses table to determine routing.
    FORCE_LEGACY: Forces all reads/writes to calls_merged table.
    DUAL_WRITE_READ_MERGED: Dual-write mode - Writes to both tables for new/empty projects,
        reads from calls_merged table.
    DUAL_WRITE_READ_COMPLETE: Dual-write mode - Writes to both tables for new/empty projects,
        reads from calls_complete table (falls back to merged for old projects).
    OFF: Skips DB queries entirely, assumes legacy behavior.
    """

    AUTO = "auto"
    FORCE_LEGACY = "force_legacy"
    DUAL_WRITE_READ_MERGED = "dual_write_read_merged"
    DUAL_WRITE_READ_COMPLETE = "dual_write_read_complete"
    OFF = "off"

    @classmethod
    def from_env(cls) -> "CallsStorageServerMode":
        mode_str = os.getenv("PROJECT_VERSION_MODE", DEFAULT_SERVER_MODE).lower()
        try:
            return cls(mode_str)
        except ValueError:
            logger.warning(
                f"Invalid PROJECT_VERSION_MODE '{mode_str}', defaulting to {DEFAULT_SERVER_MODE}. "
                f"Valid options: {', '.join([m.value for m in cls])}. "
            )
            return cls(DEFAULT_SERVER_MODE)


class ReadTable(str, Enum):
    CALLS_MERGED = "calls_merged"
    CALLS_COMPLETE = "calls_complete"


class WriteTarget(str, Enum):
    CALLS_MERGED = "calls_merged"
    CALLS_COMPLETE = "calls_complete"
    BOTH = "both"


class CallSource(str, Enum):
    """Source of call data being inserted.

    SDK_CALLS_MERGED: Old SDK with single-table writes only (calls_merged).
    SDK_CALLS_COMPLETE: New SDK with dual-write capability.
    SERVER: Server-side sources (OTEL, completions).
    """

    SDK_CALLS_MERGED = "sdk_calls_merged"
    SDK_CALLS_COMPLETE = "sdk_calls_complete"
    SERVER = "server"
