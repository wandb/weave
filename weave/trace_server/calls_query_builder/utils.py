import contextlib
import logging
from collections.abc import Generator

import sqlparse


def param_slot(param_name: str, param_type: str) -> str:
    """Helper function to create a parameter slot for a clickhouse query."""
    return f"{{{param_name}:{param_type}}}"


def safely_format_sql(
    sql: str,
    logger: logging.Logger,
) -> str:
    """Safely format a SQL string with parameters."""
    try:
        return sqlparse.format(sql, reindent=True)
    except:
        logger.info(f"Failed to format SQL: {sql}")
        return sql


# Context for tracking if we're in a NOT operation
class NotContext:
    # Nesting depth
    _depth = 0

    @classmethod
    @contextlib.contextmanager
    def not_context(cls) -> Generator[None, None, None]:
        """Context manager for NOT operations.

        Properly handles nested NOT operations by tracking depth.
        In boolean logic:
        - NOT(expr) flips the result
        - NOT(NOT(expr)) is equivalent to expr
        - NOT(NOT(NOT(expr))) is equivalent to NOT(expr)

        So we only apply special handling when nesting depth is odd.
        """
        cls._depth += 1
        try:
            yield
        finally:
            cls._depth -= 1

    @classmethod
    def is_in_not_context(cls) -> bool:
        """Check if we're in a NOT context with odd nesting depth."""
        return cls._depth % 2 == 1
