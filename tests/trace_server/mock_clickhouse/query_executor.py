"""Query executor for mock ClickHouse backend.

This module handles parsing and executing SQL queries against the mock storage.
It supports a subset of ClickHouse SQL syntax that is used by the trace server.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tests.trace_server.mock_clickhouse.client import MockQueryResult
    from tests.trace_server.mock_clickhouse.storage import MockClickHouseStorage


def _substitute_parameters(query: str, parameters: dict[str, Any]) -> str:
    """Substitute ClickHouse-style parameters in a query.

    ClickHouse uses {param_name:Type} syntax for parameters.
    This function replaces them with Python-style placeholders.

    Args:
        query: SQL query with ClickHouse-style parameters
        parameters: Parameter values

    Returns:
        Query with parameters substituted
    """
    # Pattern matches {param_name:Type} or {param_name}
    pattern = r"\{(\w+)(?::\w+)?\}"

    def replacer(match: re.Match) -> str:
        param_name = match.group(1)
        if param_name not in parameters:
            raise KeyError(f"Parameter '{param_name}' not found in parameters")
        value = parameters[param_name]
        return _format_value(value)

    return re.sub(pattern, replacer, query)


def _format_value(value: Any) -> str:
    """Format a value for SQL substitution."""
    if value is None:
        return "NULL"
    if isinstance(value, str):
        # Escape single quotes
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        return f"'{value.isoformat()}'"
    if isinstance(value, (list, tuple)):
        formatted_items = [_format_value(item) for item in value]
        return f"[{', '.join(formatted_items)}]"
    if isinstance(value, dict):
        return f"'{json.dumps(value)}'"
    return f"'{value!s}'"


class QueryExecutor:
    """Executes SQL queries against mock storage.

    This is a simplified SQL executor that handles the common query patterns
    used by the ClickHouse trace server. It is not a full SQL parser.
    """

    def __init__(self, storage: "MockClickHouseStorage"):
        self._storage = storage

    def execute(
        self, query: str, parameters: dict[str, Any], database: str
    ) -> "MockQueryResult":
        """Execute a query and return results.

        Args:
            query: SQL query string
            parameters: Query parameters
            database: Database name

        Returns:
            MockQueryResult with the query results
        """
        from tests.trace_server.mock_clickhouse.client import (
            MockQueryResult,
            MockQuerySummary,
        )

        # Substitute parameters
        query = _substitute_parameters(query, parameters)

        # Normalize whitespace
        query = " ".join(query.split())

        # Determine query type and execute
        query_upper = query.upper().strip()

        if query_upper.startswith("SELECT"):
            return self._execute_select(query, database)
        elif query_upper.startswith("INSERT"):
            return self._execute_insert(query, database)
        elif query_upper.startswith("WITH"):
            # CTE queries - treat as SELECT
            return self._execute_select(query, database)
        else:
            # For unsupported queries, return empty result
            return MockQueryResult(
                result_rows=[],
                column_names=[],
                summary=MockQuerySummary(),
            )

    def _execute_select(self, query: str, database: str) -> "MockQueryResult":
        """Execute a SELECT query.

        This is a simplified implementation that handles common patterns.
        It does not implement full SQL parsing.
        """
        from tests.trace_server.mock_clickhouse.client import (
            MockQueryResult,
            MockQuerySummary,
        )

        # Extract table name from query
        # This is a simplified approach - look for FROM clause
        from_match = re.search(r"\bFROM\s+(\w+)", query, re.IGNORECASE)
        if not from_match:
            # Could be a SELECT without FROM (e.g., SELECT 1)
            return MockQueryResult(
                result_rows=[],
                column_names=[],
                summary=MockQuerySummary(),
            )

        table_name = from_match.group(1)

        try:
            table = self._storage.get_table(table_name, database)
        except ValueError:
            # Table doesn't exist - return empty result
            return MockQueryResult(
                result_rows=[],
                column_names=[],
                summary=MockQuerySummary(),
            )

        # Get all rows and filter
        rows = self._filter_rows(query, table.rows, table.columns)

        # Apply column selection
        columns, selected_rows = self._select_columns(query, rows, table.columns)

        # Apply ORDER BY first (before LIMIT)
        selected_rows = self._apply_order_by(query, selected_rows, columns)

        # Apply LIMIT after ORDER BY
        selected_rows = self._apply_limit(query, selected_rows)

        return MockQueryResult(
            result_rows=[tuple(row) for row in selected_rows],
            column_names=columns,
            summary=MockQuerySummary(read_rows=len(selected_rows)),
        )

    def _filter_rows(
        self, query: str, rows: list[list[Any]], columns: list[str]
    ) -> list[list[Any]]:
        """Apply WHERE clause filtering (simplified)."""
        # Look for WHERE clause
        where_match = re.search(r"\bWHERE\s+(.+?)(?:\s+ORDER|\s+LIMIT|\s+GROUP|\s*$)", query, re.IGNORECASE | re.DOTALL)
        if not where_match:
            return rows

        where_clause = where_match.group(1).strip()

        # Parse simple equality conditions
        # This is very simplified - only handles basic equality
        filtered = []
        for row in rows:
            if self._evaluate_where(where_clause, row, columns):
                filtered.append(row)

        return filtered

    def _evaluate_where(
        self, where_clause: str, row: list[Any], columns: list[str]
    ) -> bool:
        """Evaluate a WHERE clause for a row (simplified).

        This handles basic patterns like:
        - column = 'value'
        - column = value
        - column IN (value1, value2, ...)
        - column IS NULL / IS NOT NULL
        - AND/OR combinations (basic)
        """
        # Handle AND conditions by splitting
        if " AND " in where_clause.upper():
            parts = re.split(r"\s+AND\s+", where_clause, flags=re.IGNORECASE)
            return all(self._evaluate_where(part.strip(), row, columns) for part in parts)

        # Handle OR conditions
        if " OR " in where_clause.upper():
            parts = re.split(r"\s+OR\s+", where_clause, flags=re.IGNORECASE)
            return any(self._evaluate_where(part.strip(), row, columns) for part in parts)

        # Handle IS NULL
        is_null_match = re.match(r"(\w+)\s+IS\s+NULL", where_clause, re.IGNORECASE)
        if is_null_match:
            col_name = is_null_match.group(1)
            if col_name in columns:
                col_idx = columns.index(col_name)
                return row[col_idx] is None
            return False

        # Handle IS NOT NULL
        is_not_null_match = re.match(r"(\w+)\s+IS\s+NOT\s+NULL", where_clause, re.IGNORECASE)
        if is_not_null_match:
            col_name = is_not_null_match.group(1)
            if col_name in columns:
                col_idx = columns.index(col_name)
                return row[col_idx] is not None
            return False

        # Handle IN clause
        in_match = re.match(r"(\w+)\s+IN\s*\(([^)]+)\)", where_clause, re.IGNORECASE)
        if in_match:
            col_name = in_match.group(1)
            values_str = in_match.group(2)
            if col_name in columns:
                col_idx = columns.index(col_name)
                values = self._parse_in_values(values_str)
                return row[col_idx] in values
            return False

        # Handle NOT IN clause
        not_in_match = re.match(r"(\w+)\s+NOT\s+IN\s*\(([^)]+)\)", where_clause, re.IGNORECASE)
        if not_in_match:
            col_name = not_in_match.group(1)
            values_str = not_in_match.group(2)
            if col_name in columns:
                col_idx = columns.index(col_name)
                values = self._parse_in_values(values_str)
                return row[col_idx] not in values
            return False

        # Handle equality: column = value
        eq_match = re.match(r"(\w+)\s*=\s*(.+)", where_clause)
        if eq_match:
            col_name = eq_match.group(1)
            value_str = eq_match.group(2).strip()
            if col_name in columns:
                col_idx = columns.index(col_name)
                value = self._parse_value(value_str)
                return row[col_idx] == value
            return False

        # Handle inequality: column != value or column <> value
        neq_match = re.match(r"(\w+)\s*(?:!=|<>)\s*(.+)", where_clause)
        if neq_match:
            col_name = neq_match.group(1)
            value_str = neq_match.group(2).strip()
            if col_name in columns:
                col_idx = columns.index(col_name)
                value = self._parse_value(value_str)
                return row[col_idx] != value
            return False

        # Default: accept all rows if we can't parse the condition
        return True

    def _parse_value(self, value_str: str) -> Any:
        """Parse a value from SQL string."""
        value_str = value_str.strip()

        # Handle NULL
        if value_str.upper() == "NULL":
            return None

        # Handle quoted strings
        if (value_str.startswith("'") and value_str.endswith("'")) or (
            value_str.startswith('"') and value_str.endswith('"')
        ):
            return value_str[1:-1].replace("''", "'")

        # Handle numbers
        try:
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            pass

        # Return as-is
        return value_str

    def _parse_in_values(self, values_str: str) -> list[Any]:
        """Parse values from an IN clause."""
        values = []
        # Split by comma, but handle quoted strings
        current = ""
        in_quote = False
        quote_char = None

        for char in values_str:
            if char in ("'", '"') and not in_quote:
                in_quote = True
                quote_char = char
                current += char
            elif char == quote_char and in_quote:
                in_quote = False
                current += char
            elif char == "," and not in_quote:
                if current.strip():
                    values.append(self._parse_value(current.strip()))
                current = ""
            else:
                current += char

        if current.strip():
            values.append(self._parse_value(current.strip()))

        return values

    def _select_columns(
        self, query: str, rows: list[list[Any]], table_columns: list[str]
    ) -> tuple[list[str], list[list[Any]]]:
        """Select columns from rows based on SELECT clause."""
        # Extract SELECT clause
        select_match = re.match(
            r"(?:WITH\s+.+?\s+)?SELECT\s+(.+?)\s+FROM",
            query,
            re.IGNORECASE | re.DOTALL,
        )
        if not select_match:
            return table_columns, rows

        select_clause = select_match.group(1).strip()

        # Handle SELECT *
        if select_clause == "*":
            return table_columns, rows

        # Parse column names (simplified - doesn't handle complex expressions)
        selected_columns = []
        for col_expr in self._split_columns(select_clause):
            col_expr = col_expr.strip()
            # Handle aliased columns: expr AS alias
            alias_match = re.match(r"(.+?)\s+AS\s+(\w+)", col_expr, re.IGNORECASE)
            if alias_match:
                col_name = alias_match.group(2)
            else:
                # Use the expression as the column name
                col_name = col_expr
            selected_columns.append(col_name)

        # For simplicity, if we can't map columns, return all
        # In a full implementation, we'd evaluate expressions
        return selected_columns, rows

    def _split_columns(self, select_clause: str) -> list[str]:
        """Split SELECT clause into individual column expressions."""
        columns = []
        current = ""
        paren_depth = 0

        for char in select_clause:
            if char == "(":
                paren_depth += 1
                current += char
            elif char == ")":
                paren_depth -= 1
                current += char
            elif char == "," and paren_depth == 0:
                if current.strip():
                    columns.append(current.strip())
                current = ""
            else:
                current += char

        if current.strip():
            columns.append(current.strip())

        return columns

    def _apply_limit(self, query: str, rows: list[list[Any]]) -> list[list[Any]]:
        """Apply LIMIT clause."""
        limit_match = re.search(r"\bLIMIT\s+(\d+)", query, re.IGNORECASE)
        if limit_match:
            limit = int(limit_match.group(1))
            return rows[:limit]
        return rows

    def _apply_order_by(
        self, query: str, rows: list[list[Any]], columns: list[str]
    ) -> list[list[Any]]:
        """Apply ORDER BY clause (simplified)."""
        order_match = re.search(
            r"\bORDER\s+BY\s+(\w+)(?:\s+(ASC|DESC))?",
            query,
            re.IGNORECASE,
        )
        if not order_match:
            return rows

        col_name = order_match.group(1)
        direction = order_match.group(2)
        reverse = direction and direction.upper() == "DESC"

        if col_name in columns:
            col_idx = columns.index(col_name)
            return sorted(rows, key=lambda r: (r[col_idx] is None, r[col_idx]), reverse=reverse)

        return rows

    def _execute_insert(self, query: str, database: str) -> "MockQueryResult":
        """Execute an INSERT query."""
        from tests.trace_server.mock_clickhouse.client import (
            MockQueryResult,
            MockQuerySummary,
        )

        # For direct INSERT queries (not through the insert() method)
        # This is a simplified implementation
        return MockQueryResult(
            result_rows=[],
            column_names=[],
            summary=MockQuerySummary(written_rows=0),
        )
