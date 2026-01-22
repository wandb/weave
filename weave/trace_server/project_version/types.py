"""Project version types for routing between calls tables."""

import logging
import os
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

DEFAULT_SERVER_MODE = "auto"

# Project Version Routing Matrix
# ==============================
#
# ┌─────────────────────────┬──────────────────────┬──────────────────────┬──────────────────────┐
# │ Project Data Residence  │ AUTO                 │ FORCE_LEGACY         │ OFF                  │
# │ (Physical State)        │ (Read / Write)       │ (Read / Write)       │ (Read / Write)       │
# ├─────────────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
# │ EMPTY                   │ COMPLETE / COMPLETE  │ MERGED / MERGED      │ MERGED / MERGED      │
# │ MERGED_ONLY             │ MERGED / MERGED      │ MERGED / MERGED      │ MERGED / MERGED      │
# │ COMPLETE_ONLY           │ COMPLETE / COMPLETE  │ MERGED / MERGED      │ MERGED / MERGED      │
# │ BOTH                    │ COMPLETE / COMPLETE  │ MERGED / MERGED      │ MERGED / MERGED      │
# └─────────────────────────┴──────────────────────┴──────────────────────┴──────────────────────┘


class ProjectDataResidence(Enum):
    EMPTY = "empty"
    MERGED_ONLY = "merged_only"
    COMPLETE_ONLY = "complete_only"
    BOTH = "both"


class CallsStorageServerMode(str, Enum):
    """Modes for controlling server storage behavior.

    AUTO: Default behavior - uses table to determine routing.
    FORCE_LEGACY: Forces all reads/writes to calls_merged table.
    OFF: Skips DB queries entirely, assumes legacy behavior.
    """

    AUTO = "auto"
    FORCE_LEGACY = "force_legacy"
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


@dataclass(frozen=True)
class TableConfig:
    """Centralized configuration for table-specific SQL generation.

    This dataclass encapsulates all table-specific decisions to avoid spreading
    conditional logic throughout the query builders.

    Attributes:
        read_table: The ReadTable enum value.
        table_name: SQL table name (e.g., "calls_merged", "calls_complete").
        stats_table_name: Associated stats table (e.g., "calls_merged_stats").
        use_aggregation: Whether to use aggregate functions (GROUP BY semantics).
            True for calls_merged (requires aggregation to resolve concurrent writes).
            False for calls_complete (single-row per call, no aggregation needed).
        datetime_filter_field: Column name for datetime-based optimizations.
            "sortable_datetime" for calls_merged, "started_at" for calls_complete.
    """

    read_table: ReadTable
    table_name: str
    stats_table_name: str
    use_aggregation: bool
    datetime_filter_field: str

    @classmethod
    def from_read_table(cls, read_table: ReadTable) -> "TableConfig":
        """Create a TableConfig from a ReadTable enum.

        Args:
            read_table: The table to configure for.

        Returns:
            TableConfig with all derived values populated.

        Examples:
            >>> config = TableConfig.from_read_table(ReadTable.CALLS_MERGED)
            >>> config.use_aggregation
            True
        """
        if read_table == ReadTable.CALLS_MERGED:
            return cls(
                read_table=read_table,
                table_name="calls_merged",
                stats_table_name="calls_merged_stats",
                use_aggregation=True,
                datetime_filter_field="sortable_datetime",
            )
        else:
            return cls(
                read_table=read_table,
                table_name="calls_complete",
                stats_table_name="calls_complete_stats",
                use_aggregation=False,
                datetime_filter_field="started_at",
            )
