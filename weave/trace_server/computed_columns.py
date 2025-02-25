"""
Computed columns module for trace server implementations.

This module provides a unified way to define and use computed columns
that are derived from other columns rather than being direct database columns.
These computed columns can be used in queries, filters, and order-by clauses
across different database backends (currently SQLite and ClickHouse).
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DbEngine(str, Enum):
    """Supported database engines."""

    SQLITE = "sqlite"
    CLICKHOUSE = "clickhouse"


class ComputedColumn(BaseModel):
    """
    Definition of a computed column that can be used in queries.

    A computed column is derived from other columns using a SQL expression
    that is specific to each database engine.
    """

    name: str = Field(..., description="Name of the computed column")
    description: str = Field(
        ..., description="Description of what this column represents"
    )

    # SQL snippets for each database engine - using names without leading underscores
    sqlite_sql: Optional[str] = Field(None, description="SQL snippet for SQLite")
    clickhouse_sql: Optional[str] = Field(
        None, description="SQL snippet for ClickHouse"
    )

    # Optional additional configuration
    sortable: bool = Field(
        True, description="Whether this column can be used in ORDER BY"
    )
    filterable: bool = Field(
        True, description="Whether this column can be used in WHERE/HAVING"
    )

    def get_sql(self, engine: DbEngine, table_alias: Optional[str] = None) -> str:
        """
        Get the SQL snippet for this computed column for the specified database engine.

        Args:
            engine: The database engine to get the SQL for
            table_alias: Optional table alias to use in the SQL

        Returns:
            SQL snippet for the computed column
        """
        if engine == DbEngine.SQLITE:
            sql = self.sqlite_sql
        elif engine == DbEngine.CLICKHOUSE:
            sql = self.clickhouse_sql
        else:
            raise ValueError(f"Unsupported database engine: {engine}")

        if sql is None:
            raise NotImplementedError(
                f"SQL for {self.name} not implemented for {engine}"
            )

        # Apply table alias if provided and needed
        if table_alias:
            # Replace column references with table-qualified references
            # This is a simple implementation that assumes columns are referenced directly
            # A more robust implementation might use a SQL parser
            for col in ["exception", "ended_at"]:
                sql = sql.replace(f"{col} ", f"{table_alias}.{col} ")
                sql = sql.replace(f"{col}\n", f"{table_alias}.{col}\n")

            # For ClickHouse, we need to handle the any() function
            if engine == DbEngine.CLICKHOUSE:
                for col in ["exception", "ended_at"]:
                    sql = sql.replace(f"any({col})", f"any({table_alias}.{col})")

        return sql


class ComputedColumnsRegistry:
    """Registry of computed columns that can be used in queries."""

    def __init__(self) -> None:
        self._columns: dict[str, ComputedColumn] = {}
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Initialize the default computed columns."""
        # Status column - computed from exception and ended_at
        status = ComputedColumn(
            name="status",
            description="Status of the call (error, success, or running)",
            sqlite_sql="""
                CASE
                    WHEN exception IS NOT NULL THEN 1
                    WHEN ended_at IS NOT NULL THEN 2
                    ELSE 3
                END
            """,
            clickhouse_sql="""
                CASE
                    WHEN any(exception) IS NOT NULL THEN 1
                    WHEN any(ended_at) IS NOT NULL THEN 2
                    ELSE 3
                END
            """,
        )
        self.register(status)

    def register(self, column: ComputedColumn) -> None:
        """Register a computed column."""
        self._columns[column.name] = column

    def get(self, name: str) -> Optional[ComputedColumn]:
        """Get a computed column by name."""
        return self._columns.get(name)

    def contains(self, name: str) -> bool:
        """Check if a column name is a computed column."""
        return name in self._columns

    def list_columns(self) -> list[str]:
        """List all registered computed column names."""
        return list(self._columns.keys())


# Global instance of the registry
computed_columns = ComputedColumnsRegistry()


def is_computed_column(column_name: str) -> bool:
    """Check if a column name is a computed column."""
    return computed_columns.contains(column_name)


def get_computed_column_sql(
    column_name: str, engine: DbEngine, table_alias: Optional[str] = None
) -> str:
    """
    Get the SQL for a computed column.

    Args:
        column_name: Name of the column
        engine: Database engine to get SQL for
        table_alias: Optional table alias to use in the SQL

    Returns:
        SQL snippet for the computed column

    Raises:
        KeyError: If the column name is not a registered computed column
    """
    column = computed_columns.get(column_name)
    if column is None:
        raise KeyError(f"Unknown computed column: {column_name}")
    return column.get_sql(engine, table_alias)
