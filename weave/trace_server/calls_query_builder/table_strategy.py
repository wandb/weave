"""Table strategy for multi-table query support."""

from abc import ABC, abstractmethod

from weave.trace_server.project_version.types import ReadTable


class TableStrategy(ABC):
    """Strategy for table-specific query generation behavior.

    Each table backend (calls_merged, calls_complete) implements this interface
    to define how queries should be generated for that table.
    """

    @property
    @abstractmethod
    def table_name(self) -> str:
        """Physical table name in database."""
        ...

    @property
    @abstractmethod
    def read_table_enum(self) -> ReadTable:
        """ReadTable enum value for this strategy."""
        ...

    @abstractmethod
    def requires_grouping(self) -> bool:
        """Whether this table requires GROUP BY in queries.

        This is the fundamental difference between table types:
        - calls_merged: True (multiple rows per call, must aggregate)
        - calls_complete: False (one row per call, already aggregated)

        This determines whether to add GROUP BY, use HAVING vs WHERE for
        post-aggregation filters, and whether fields need aggregation functions.
        """
        ...


class CallsMergedStrategy(TableStrategy):
    """Strategy for calls_merged table (legacy aggregated view)."""

    @property
    def table_name(self) -> str:
        return "calls_merged"

    @property
    def read_table_enum(self) -> ReadTable:
        return ReadTable.CALLS_MERGED

    def requires_grouping(self) -> bool:
        return True


class CallsCompleteStrategy(TableStrategy):
    """Strategy for calls_complete table (new single-row-per-call)."""

    @property
    def table_name(self) -> str:
        return "calls_complete"

    @property
    def read_table_enum(self) -> ReadTable:
        return ReadTable.CALLS_COMPLETE

    def requires_grouping(self) -> bool:
        return False


def get_table_strategy(read_table: ReadTable) -> TableStrategy:
    """Factory function to get appropriate strategy for a read table."""
    if read_table == ReadTable.CALLS_MERGED:
        return CallsMergedStrategy()
    elif read_table == ReadTable.CALLS_COMPLETE:
        return CallsCompleteStrategy()
    else:
        raise ValueError(f"Unknown read table: {read_table}")
