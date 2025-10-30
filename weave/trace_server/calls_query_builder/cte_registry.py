"""Registry for managing CTEs in a query.

Ensures all CTEs are collected and rendered at the top level in the correct order.
"""

from dataclasses import dataclass


@dataclass
class CTE:
    """Represents a Common Table Expression."""

    name: str
    sql: str


class CTERegistry:
    """Manages CTEs for a query, ensuring proper ordering and no duplicates."""

    def __init__(self) -> None:
        self._ctes: list[CTE] = []
        self._cte_names: set[str] = set()

    def add_cte(self, name: str, sql: str) -> str:
        """Add a CTE to the registry.

        Args:
            name: CTE name (must be unique)
            sql: CTE SQL (without WITH or AS wrapper)

        Returns:
            The CTE name (for convenience in chaining)

        Raises:
            ValueError: If CTE name already exists
        """
        if name in self._cte_names:
            raise ValueError(f"CTE '{name}' already exists in registry")

        self._ctes.append(CTE(name=name, sql=sql))
        self._cte_names.add(name)
        return name

    def has_ctes(self) -> bool:
        """Check if any CTEs have been registered."""
        return len(self._ctes) > 0

    def render(self) -> str:
        """Render all CTEs with WITH clause.

        Returns:
            Empty string if no CTEs, otherwise "WITH cte1 AS (...), cte2 AS (...)"
        """
        if not self._ctes:
            return ""

        cte_parts = [f"{cte.name} AS (\n{cte.sql}\n)" for cte in self._ctes]
        return "WITH " + ",\n".join(cte_parts) + "\n"

    def get_cte_names(self) -> list[str]:
        """Get list of CTE names in order."""
        return [cte.name for cte in self._ctes]
