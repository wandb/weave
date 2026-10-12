"""Common Table Expression (CTE) definitions for query building."""

from pydantic import BaseModel, Field


class CTE(BaseModel):
    """Represents a single Common Table Expression (CTE)."""

    name: str
    sql: str

    def to_sql(self) -> str:
        """Format this CTE for inclusion in a WITH clause."""
        return f"{self.name} AS ({self.sql})"


class CTECollection(BaseModel):
    """Manages a collection of CTEs for a query.

    CTEs are rendered in the order they are added.
    """

    ctes: list[CTE] = Field(default_factory=list)

    def add_cte(self, name: str, sql: str) -> None:
        """Add a CTE to the collection."""
        self.ctes.append(CTE(name=name, sql=sql))

    def has_ctes(self) -> bool:
        """Check if there are any CTEs."""
        return len(self.ctes) > 0

    def to_sql(self) -> str:
        """Convert all CTEs to SQL WITH clause.

        Returns empty string if no CTEs, otherwise returns 'WITH cte1 AS (...), cte2 AS (...)'.
        """
        if not self.ctes:
            return ""

        cte_sqls = [cte.to_sql() for cte in self.ctes]
        return "WITH " + ",\n".join(cte_sqls)
