"""
Query optimization framework for call queries.

Optimizes complex queries on call data before expensive database aggregation (groupby).
Optimizations should be conservative, not guaranteed to full filter down but should
   be a superset of results.

Key strategies:
1. String optimization - Uses LIKE patterns for string fields
2. ID-based optimization - Uses sortable_datetime column for datetime filtering

Optimization SQL is applied before GROUP BY, reducing memory usage and
improving performance for complex conditions.
"""

import datetime
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Union, Any

from pydantic import BaseModel

from weave.trace_server.calls_query_builder.utils import (
    NotContext,
    param_slot,
)
from weave.trace_server.interface import query as tsi_query

if TYPE_CHECKING:
    from weave.trace_server.calls_query_builder.calls_query_builder import (
        Condition,
        ParamBuilder,
    )

START_ONLY_CALL_FIELDS = {"started_at", "inputs_dump", "attributes_dump"}
END_ONLY_CALL_FIELDS = {"ended_at", "output_dump", "summary_dump"}
STRING_FIELDS_TO_OPTIMIZE = {"inputs_dump", "output_dump", "attributes_dump"}
DATETIME_FIELDS_TO_OPTIMIZE = {"started_at"}

DATETIME_BUFFER_TIME_SECONDS = 60 * 5  # 5 minutes


def _field_requires_null_check(field: str) -> bool:
    """Returns whether a string is a start or end field

    Start and end fields require appending a NULL to all conditional
    checks when operating on the calls_merged table, as unmerged
    call starts and ends can be valid results without inputs/output
    """
    return field in START_ONLY_CALL_FIELDS | END_ONLY_CALL_FIELDS


def _can_optimize_string_field(field: str) -> bool:
    """Returns whether a field can be optimized for string search."""
    return field in STRING_FIELDS_TO_OPTIMIZE


def _can_optimize_datetime_field(field: str) -> bool:
    """Returns whether a field can be optimized for datetime filtering.

    Currently this is only the started_at field, which can be converted
    to the `sortable_datetime` column.
    """
    return field in DATETIME_FIELDS_TO_OPTIMIZE


class QueryOptimizationProcessor(ABC):
    """
    Abstract base class for query optimization processors.

    This class defines the interface for optimization processors that convert
    query operations into optimized SQL conditions. Subclasses should implement
    specific strategies for different types of data or operations.
    """

    def __init__(self, pb: "ParamBuilder", table_alias: str):
        self.pb = pb
        self.table_alias = table_alias

    def process_operand(self, operand: tsi_query.Operand) -> Optional[str]:
        """
        Process an operand and convert it to an optimized SQL condition if possible.

        Ignores leaf operations like Literal, GetField, and Convert.

        Args:
            operand: The operand to process

        Returns:
            SQL condition string or None if optimization is not possible
        """
        if isinstance(operand, tsi_query.LiteralOperation):
            return None
        elif isinstance(operand, tsi_query.GetFieldOperator):
            return None
        elif isinstance(operand, tsi_query.ConvertOperation):
            return None
        return apply_processor(self, operand)

    def process_and(self, operation: tsi_query.AndOperation) -> Optional[str]:
        """Process AND operations into optimized SQL."""
        conditions = []
        for op in operation.and_:
            result = self.process_operand(op)
            if result:
                conditions.append(result)

        if conditions:
            return "(" + " AND ".join(conditions) + ")"
        return None

    def process_or(self, operation: tsi_query.OrOperation) -> Optional[str]:
        """
        Process OR operations into optimized SQL.

        Note: If any condition in an OR cannot be optimized, the entire OR
        cannot be optimized, so we return None.
        """
        conditions = []
        for op in operation.or_:
            result = self.process_operand(op)
            if result is None:
                # If any or condition can't be optimized, return
                # TODO: this should return the non optimized,
                # non aggreagated condition when available
                return None
            conditions.append(result)

        if conditions:
            return "(" + " OR ".join(conditions) + ")"
        return None

    def process_not(self, operation: tsi_query.NotOperation) -> Optional[str]:
        """Process NOT operations into optimized SQL."""
        if len(operation.not_) != 1:
            return None

        with NotContext.not_context():
            result = self.process_operand(operation.not_[0])

        if result is None:
            return None
        return f"NOT ({result})"

    @abstractmethod
    def process_eq(self, operation: tsi_query.EqOperation) -> Optional[str]:
        """Process equality operation."""
        pass

    @abstractmethod
    def process_contains(self, operation: tsi_query.ContainsOperation) -> Optional[str]:
        """Process contains operation."""
        pass

    @abstractmethod
    def process_in(self, operation: tsi_query.InOperation) -> Optional[str]:
        """Process in operation."""
        pass

    @abstractmethod
    def process_gt(self, operation: tsi_query.GtOperation) -> Optional[str]:
        """Process greater than operation."""
        pass

    @abstractmethod
    def process_gte(self, operation: tsi_query.GteOperation) -> Optional[str]:
        """Process greater than or equal operation."""
        pass

    def finalize_sql(self, result: Optional[str]) -> Optional[str]:
        """
        Final step to make valid SQL for the calls query.

        This method can be overridden by subclasses to apply additional
        transformations to the final SQL condition.

        Args:
            result: The SQL condition to finalize

        Returns:
            The finalized SQL condition or None if no condition
        """
        if result:
            return f"AND {result}"
        return None


class StringOptimizationProcessor(QueryOptimizationProcessor):
    """
    Optimization processor for string operations.

    This processor creates LIKE-based SQL conditions to optimize queries
    on string fields before aggregation, reducing memory pressure.
    """

    def process_eq(self, operation: tsi_query.EqOperation) -> Optional[str]:
        """
        Process equality operation on string fields.

        Creates SQL condition using LIKE patterns for strings in JSON fields.
        """
        return _create_like_optimized_eq_condition(operation, self.pb, self.table_alias)

    def process_contains(self, operation: tsi_query.ContainsOperation) -> Optional[str]:
        """
        Process contains operation on string fields.

        Creates SQL condition using LIKE patterns for substrings in JSON fields.
        """
        return _create_like_optimized_contains_condition(
            operation, self.pb, self.table_alias
        )

    def process_in(self, operation: tsi_query.InOperation) -> Optional[str]:
        """
        Process IN operation on string fields.

        Creates SQL conditions using LIKE patterns for multiple string values.
        """
        return _create_like_optimized_in_condition(operation, self.pb, self.table_alias)

    def process_gt(self, operation: tsi_query.GtOperation) -> Optional[str]:
        """Not implemented for string optimization."""
        return None

    def process_gte(self, operation: tsi_query.GteOperation) -> Optional[str]:
        """Not implemented for string optimization."""
        return None


class SortableDatetimeOptimizationProcessor(QueryOptimizationProcessor):
    """
    Optimization processor for sortable_datetime operations.

    This processor creates SQL conditions that filter based on the
    `sortable_datetime` column, which can significantly reduce the dataset before
    doing more complex operations after aggregation.
    """

    def process_eq(self, operation: tsi_query.EqOperation) -> Optional[str]:
        """Not implemented for sortable_datetime optimization."""
        return None

    def process_contains(self, operation: tsi_query.ContainsOperation) -> Optional[str]:
        """Not implemented for sortable_datetime optimization."""
        return None

    def process_in(self, operation: tsi_query.InOperation) -> Optional[str]:
        """Not implemented for sortable_datetime optimization."""
        return None

    def process_gt(self, operation: tsi_query.GtOperation) -> Optional[str]:
        """
        Process GT operation on sortable_datetime fields using sortable_datetime optimization.

        Creates SQL condition that filters started_at with the sortable_datetime column.
        """
        return _create_datetime_optimization_sql(
            operation, self.pb, self.table_alias, ">"
        )

    def process_gte(self, operation: tsi_query.GteOperation) -> Optional[str]:
        """
        Process GTE operation on sortable_datetime fields using sortable_datetime optimization.

        Creates SQL condition that filters started_at with the sortable_datetime column.
        """
        return _create_datetime_optimization_sql(
            operation, self.pb, self.table_alias, ">="
        )


def apply_processor(
    processor: QueryOptimizationProcessor, operation: tsi_query.Operation
) -> Optional[str]:
    if isinstance(operation, tsi_query.AndOperation):
        return processor.process_and(operation)
    elif isinstance(operation, tsi_query.OrOperation):
        return processor.process_or(operation)
    elif isinstance(operation, tsi_query.NotOperation):
        return processor.process_not(operation)
    elif isinstance(operation, tsi_query.EqOperation):
        return processor.process_eq(operation)
    elif isinstance(operation, tsi_query.ContainsOperation):
        return processor.process_contains(operation)
    elif isinstance(operation, tsi_query.InOperation):
        return processor.process_in(operation)
    elif isinstance(operation, tsi_query.GtOperation):
        return processor.process_gt(operation)
    elif isinstance(operation, tsi_query.GteOperation):
        return processor.process_gte(operation)
    return None


class OptimizationConditions(BaseModel):
    str_filter_opt_sql: Optional[str] = None
    sortable_datetime_filters_sql: Optional[str] = None


def process_query_to_optimization_sql(
    conditions: list["Condition"],
    param_builder: "ParamBuilder",
    table_alias: str,
) -> OptimizationConditions:
    """Converts a list of conditions to optimization conditions for a clickhouse query.

    This function creates SQL conditions that can be applied before the GROUP BY
    to filter out rows that definitely won't match the heavy conditions. These
    conditions MUST be identical or less restrictive than the conditions in the
    `conditions` list which will appear in HAVING after group by.

    For fields that may only exist in start or end parts, we add special handling
    to avoid filtering out rows where the field is NULL (as they might be part of
    a valid call when combined with other parts).

    Performance note: This optimization is critical for queries with heavy fields,
    as it can significantly reduce peak memory by filtering before aggregation.
    """
    if not conditions:
        return OptimizationConditions()

    # Create a single AND operation from all conditions
    and_operation = tsi_query.AndOperation(**{"$and": [c.operand for c in conditions]})

    # Apply string optimization
    string_processor = StringOptimizationProcessor(param_builder, table_alias)
    string_result = apply_processor(string_processor, and_operation)
    string_result_sql = string_processor.finalize_sql(string_result)

    # Apply sortable_datetime optimization
    sortable_datetime_processor = SortableDatetimeOptimizationProcessor(
        param_builder, table_alias
    )
    sortable_datetime_result = apply_processor(
        sortable_datetime_processor, and_operation
    )
    sortable_datetime_result_sql = sortable_datetime_processor.finalize_sql(
        sortable_datetime_result
    )

    return OptimizationConditions(
        str_filter_opt_sql=string_result_sql,
        sortable_datetime_filters_sql=sortable_datetime_result_sql,
    )


def _create_like_condition(
    field: str,
    like_pattern: str,
    pb: "ParamBuilder",
    table_alias: str,
    case_insensitive: bool = False,
) -> str:
    """Creates a LIKE condition for a JSON field."""
    field_name = f"{table_alias}.{field}"

    if case_insensitive:
        param_name = pb.add_param(like_pattern.lower())
        return f"lower({field_name}) LIKE {param_slot(param_name, 'String')}"
    else:
        param_name = pb.add_param(like_pattern)
        return f"{field_name} LIKE {param_slot(param_name, 'String')}"


def _extract_field_and_literal(
    operation: Union[
        tsi_query.EqOperation, tsi_query.GtOperation, tsi_query.GteOperation
    ],
) -> tuple[Optional[tsi_query.GetFieldOperator], Optional[tsi_query.LiteralOperation]]:
    """Extract field and literal operands from a binary operation.

    Returns a tuple of (field_operand, literal_operand) or (None, None) if invalid.
    """
    ops = (
        operation.eq_
        if hasattr(operation, "eq_")
        else (operation.gt_ if hasattr(operation, "gt_") else operation.gte_)
    )

    if len(ops) != 2:
        return None, None

    field_operand = None
    literal_operand = None

    if isinstance(ops[0], tsi_query.GetFieldOperator):
        field_operand = ops[0]
        literal_operand = ops[1]
    elif isinstance(ops[1], tsi_query.GetFieldOperator):
        field_operand = ops[1]
        literal_operand = ops[0]

    if not isinstance(literal_operand, tsi_query.LiteralOperation):
        return None, None

    return field_operand, literal_operand


def _create_like_optimized_eq_condition(
    operation: tsi_query.EqOperation,
    pb: "ParamBuilder",
    table_alias: str,
) -> Optional[str]:
    """Creates a LIKE-optimized condition for equality operations."""
    field_operand, literal_operand = _extract_field_and_literal(operation)
    if field_operand is None or literal_operand is None:
        return None

    # Return if literal isn't a string
    if not isinstance(literal_operand.literal_, str):
        return None

    from weave.trace_server.calls_query_builder.calls_query_builder import (
        get_field_by_name,
    )

    field = get_field_by_name(field_operand.get_field_).field
    literal_value = literal_operand.literal_

    if not _can_optimize_string_field(field):
        return None

    if not literal_value:
        # Empty string is not a valid value for LIKE optimization
        return None

    # Boolean literals are not wrapped in quotes in JSON payloads
    if literal_value in ("true", "false"):
        like_pattern = f"%{literal_value}%"
    else:
        like_pattern = f'%"{literal_value}"%'

    like_condition = _create_like_condition(field, like_pattern, pb, table_alias)
    if _field_requires_null_check(field):
        return f"({like_condition} OR {table_alias}.{field} IS NULL)"
    return like_condition


def _create_like_optimized_contains_condition(
    operation: tsi_query.ContainsOperation,
    pb: "ParamBuilder",
    table_alias: str,
) -> Optional[str]:
    """Creates a LIKE-optimized condition for contains operations."""
    # Check if the input is a GetField operation on a JSON field
    if not isinstance(operation.contains_.input, tsi_query.GetFieldOperator):
        return None
    # Return if substr isn't a string literal
    if not isinstance(
        operation.contains_.substr, tsi_query.LiteralOperation
    ) or not isinstance(operation.contains_.substr.literal_, str):
        return None

    from weave.trace_server.calls_query_builder.calls_query_builder import (
        get_field_by_name,
    )

    field = get_field_by_name(operation.contains_.input.get_field_).field
    substr_value = operation.contains_.substr.literal_
    if not substr_value:
        # Empty string is not a valid value for LIKE optimization
        return None

    if not _can_optimize_string_field(field):
        return None

    case_insensitive = operation.contains_.case_insensitive or False
    like_pattern = f'%"%{substr_value}%"%'

    like_condition = _create_like_condition(
        field, like_pattern, pb, table_alias, case_insensitive
    )
    if _field_requires_null_check(field):
        return f"({like_condition} OR {table_alias}.{field} IS NULL)"
    return like_condition


def _create_like_optimized_in_condition(
    operation: tsi_query.InOperation,
    pb: "ParamBuilder",
    table_alias: str,
) -> Optional[str]:
    """Creates a LIKE-optimized condition for in operations."""
    # Check if the left side is a GetField operation on a JSON field
    if not isinstance(operation.in_[0], tsi_query.GetFieldOperator):
        return None
    # Return if right-side isn't non-empty list
    if (
        len(operation.in_) != 2
        or not isinstance(operation.in_[1], list)
        or len(operation.in_[1]) == 0
    ):
        return None

    from weave.trace_server.calls_query_builder.calls_query_builder import (
        get_field_by_name,
    )

    field = get_field_by_name(operation.in_[0].get_field_).field
    if not _can_optimize_string_field(field):
        return None

    # Create OR conditions for each value
    like_conditions: list[str] = []

    for value_operand in operation.in_[1]:
        if (
            not isinstance(value_operand, tsi_query.LiteralOperation)
            or not isinstance(value_operand.literal_, str)
            or not value_operand.literal_
        ):
            return None

        like_pattern = f'%"{value_operand.literal_}"%'
        like_condition = _create_like_condition(field, like_pattern, pb, table_alias)
        like_conditions.append(like_condition)

    or_sql = "(" + " OR ".join(like_conditions) + ")"
    if _field_requires_null_check(field):
        return f"({or_sql} OR {table_alias}.{field} IS NULL)"
    return or_sql


def _timestamp_to_datetime_str(timestamp: int) -> str:
    """Converts a timestamp to a datetime string."""
    return datetime.datetime.fromtimestamp(
        timestamp, tz=datetime.timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S.%f")


def _create_datetime_optimization_sql(
    operation: Union[tsi_query.GtOperation, tsi_query.GteOperation],
    pb: "ParamBuilder",
    table_alias: str,
    op_str: str,
) -> Optional[str]:
    """Creates SQL for datetime optimization using indexed sortable_datetime column.

    Applies a buffer to the timestamp to make the filter more permissive:
    - For normal context: Subtracts buffer from timestamp
    - For NOT context: Adds buffer to timestamp
    """
    field_operand, literal_operand = _extract_field_and_literal(operation)
    if field_operand is None or literal_operand is None:
        return None

    field_name = field_operand.get_field_
    if not _can_optimize_datetime_field(field_name):
        return None

    literal_value = literal_operand.literal_

    if not literal_value or not isinstance(literal_value, (int, float)):
        return None

    # convert timestamp to datetime_str
    timestamp = int(literal_value)

    # Apply buffer in appropriate direction based on context
    buffer_seconds = int(DATETIME_BUFFER_TIME_SECONDS)
    if NotContext.is_in_not_context():
        # For NOT context, add buffer to make filter more permissive
        timestamp += buffer_seconds
    else:
        # For normal context, subtract buffer to make filter more permissive
        timestamp -= buffer_seconds

    datetime_str = _timestamp_to_datetime_str(timestamp)

    param_name = pb.add_param(datetime_str)
    return (
        f"{table_alias}.sortable_datetime {op_str} {param_slot(param_name, 'String')}"
    )


class ObjectReferenceProcessor(ABC):
    """Base processor for handling object reference operations."""

    @abstractmethod
    def process_condition(
        self,
        field_path: str,
        operation: Union[
            tsi_query.EqOperation,
            tsi_query.ContainsOperation,
            tsi_query.GtOperation,
            tsi_query.GteOperation,
        ],
        pb: "ParamBuilder",
    ) -> tuple[str, str, Any]:
        """Process condition and return operator, field, and value."""
        pass


class EqObjectReferenceProcessor(ObjectReferenceProcessor):
    """Process equality operations for object references."""

    def process_condition(
        self, field_path: str, operation: tsi_query.EqOperation, pb: "ParamBuilder"
    ) -> tuple[str, str, Any]:
        """Convert equality operation to SQL operator, field, and value."""
        field_operand, literal_operand = _extract_field_and_literal(operation)
        if field_operand is None or literal_operand is None:
            raise ValueError(f"Invalid field or literal operand for {field_path}")

        return "=", field_operand.get_field_, literal_operand.literal_


class ContainsObjectReferenceProcessor(ObjectReferenceProcessor):
    """Process contains operations for object references."""

    def process_condition(
        self,
        field_path: str,
        operation: tsi_query.ContainsOperation,
        pb: "ParamBuilder",
    ) -> tuple[str, str, Any]:
        """Convert contains operation to SQL operator, field, and value."""
        if not isinstance(operation.contains_.input, tsi_query.GetFieldOperator):
            raise ValueError(f"Contains input must be a field for {field_path}")

        if not isinstance(operation.contains_.substr, tsi_query.LiteralOperation):
            raise ValueError(f"Contains substr must be a literal for {field_path}")

        get_field = operation.contains_.input.get_field_
        val = operation.contains_.substr.literal_
        val = f"%{val}%"

        return "LIKE", get_field, val


class GtObjectReferenceProcessor(ObjectReferenceProcessor):
    """Process greater than operations for object references."""

    def process_condition(
        self, field_path: str, operation: tsi_query.GtOperation, pb: "ParamBuilder"
    ) -> tuple[str, str, Any]:
        """Convert greater than operation to SQL operator, field, and value."""
        field_operand, literal_operand = _extract_field_and_literal(operation)
        if field_operand is None or literal_operand is None:
            raise ValueError(f"Invalid field or literal operand for {field_path}")

        return ">", field_operand.get_field_, literal_operand.literal_


class GteObjectReferenceProcessor(ObjectReferenceProcessor):
    """Process greater than or equal operations for object references."""

    def process_condition(
        self, field_path: str, operation: tsi_query.GteOperation, pb: "ParamBuilder"
    ) -> tuple[str, str, Any]:
        """Convert greater than or equal operation to SQL operator, field, and value."""
        field_operand, literal_operand = _extract_field_and_literal(operation)
        if field_operand is None or literal_operand is None:
            raise ValueError(f"Invalid field or literal operand for {field_path}")

        return ">=", field_operand.get_field_, literal_operand.literal_


# Mapping of operation types to their processors
OBJECT_REFERENCE_PROCESSORS = {
    tsi_query.EqOperation: EqObjectReferenceProcessor(),
    tsi_query.ContainsOperation: ContainsObjectReferenceProcessor(),
    tsi_query.GtOperation: GtObjectReferenceProcessor(),
    tsi_query.GteOperation: GteObjectReferenceProcessor(),
}


def _field_is_expanded_column(field: Any, expand_columns: list[str]) -> bool:
    """
    Check if a field is part of the expanded columns or is a child of an expanded path.
    """
    field_path = ".".join([field.field.field.split("_")[0]] + field.field.extra_path)
    return _is_expanded_column(field_path, expand_columns)


def _is_expanded_column(field_path: str, expand_columns: list[str]) -> bool:
    """
    Check if a field path is part of the expanded columns or is a child of an expanded path.

    Args:
        field_path: The field path to check, e.g. "inputs.model.name"
        expand_columns: List of expanded column paths, e.g. ["inputs.model", "output.values"]

    Returns:
        True if the field path is covered by an expanded column, False otherwise
    """
    if not expand_columns:
        return True  # If no explicit columns to expand, treat all as expandable

    parts = field_path.split(".")
    if len(parts) < 2:
        return False

    field_prefix = ".".join(parts[:2])  # e.g., "inputs.model"

    for expand_path in expand_columns:
        if expand_path == field_prefix or field_path.startswith(expand_path + "."):
            return True
    return False


def build_object_ref_conditions(
    pb: "ParamBuilder",
    project_id: str,
    table_alias: str,
    object_mapping: dict[str, tuple[Condition, bool]],
) -> dict[str, Any]:
    """
    Builds SQL components for filtering based on object references.

    This function processes various condition types (eq, contains, gt, gte)
    and creates the appropriate SQL for filtering object references.

    Args:
        pb: ParamBuilder for parameter management
        project_id: Project ID for the query
        table_alias: The alias of the table being queried
        object_mapping: A mapping from field path to condition objects
                        e.g. {"inputs.model.name.str": Condition}
        expand_columns: List of column paths that should be treated as references
                        to the objects table, e.g. ["inputs.model", "output.values"]

    Returns:
        Dictionary with cte_parts and filter_sql
    """
    project_param = pb.add_param(project_id)
    if not object_mapping:
        return {"cte_parts": [], "filter_sql": ""}

    # Start building the CTEs from the deepest leaf values
    cte_parts = []
    filter_conditions = []

    # Process object mapping conditions
    for i, (path_str, (filter_condition, is_object_order_by)) in enumerate(
        object_mapping.items()
    ):
        path_parts = path_str.split(".")
        root_field = path_parts[0] + "_dump"
        # The property within the root field (model, name, etc.)
        property_path = path_parts[1:]

        # Process the operation based on its type
        operation = filter_condition.operand
        operation_type = type(operation)
        processor = OBJECT_REFERENCE_PROCESSORS.get(operation_type)

        if processor is None:
            # Skip if we don't have a processor for this operation type
            continue

        try:
            # Cast operation to the specific type that the processor expects
            if isinstance(
                operation,
                (
                    tsi_query.EqOperation,
                    tsi_query.ContainsOperation,
                    tsi_query.GtOperation,
                    tsi_query.GteOperation,
                ),
            ):
                op_str, _, val = processor.process_condition(path_str, operation, pb)
            else:
                continue
        except ValueError as e:
            # Skip if we can't process the condition
            print(f"Skipping {path_str} because of {e}")
            continue

        # Convert filter value to appropriate parameter
        from weave.trace_server.orm import python_value_to_ch_type

        filter_param = pb.add_param(val)
        filter_type = python_value_to_ch_type(val)

        # Simple case: direct field in the table (inputs.model = value)
        if len(property_path) == 1:
            field_access = (
                f"JSON_VALUE({table_alias}.{root_field}, '$.{property_path[0]}')"
            )
            condition = (
                f"{field_access} {op_str} {param_slot(filter_param, filter_type)}"
            )
            filter_conditions.append(condition)
            continue

        # Complex case: requires object table joins
        cte_name = f"obj_filter_{i}"

        # The leaf level query directly checks the property value
        leaf_property = property_path[-1]
        val_dump_select = "val_dump," if is_object_order_by else ""
        val_dump_condition = f"JSON_VALUE(val_dump, '$.{leaf_property}') {op_str} {param_slot(filter_param, filter_type)}"
        if is_object_order_by:
            val_dump_condition = (
                f"JSONType(JSON_VALUE(val_dump, '$.{leaf_property}')) != 'Null'"
            )

        leaf_cte = f"""
        {cte_name} AS (
            SELECT
                object_id,
                digest,
                {val_dump_select}
                concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS full_ref
            FROM object_versions
            WHERE project_id = {param_slot(project_param, "String")}
                AND {val_dump_condition}
            GROUP BY project_id, object_id, digest
        )"""
        cte_parts.append(leaf_cte)

        # If we have more than two levels of nesting, we need intermediate CTEs
        current_cte_name = cte_name
        if len(property_path) > 2:
            # ['model', 'config', 'sensitivity'] -> ['sensitivity', 'config]
            properties = reversed(property_path[1:-1])
            for j, prop in enumerate(properties):
                intermediate_cte_name = f"{cte_name}_level_{j}"

                intermediate_cte = f"""
                {intermediate_cte_name} AS (
                    SELECT 
                        ov.object_id, 
                        ov.digest,
                        concat('weave-trace-internal:///', ov.project_id, '/object/', ov.object_id, ':', ov.digest) AS full_ref
                    FROM object_versions ov
                    WHERE ov.project_id = {param_slot(project_param, "String")}
                    AND JSON_VALUE(ov.val_dump, '$.{prop}') IN (
                        SELECT full_ref 
                        FROM {current_cte_name}
                    )
                    GROUP BY ov.project_id, ov.object_id, ov.digest
                )"""
                cte_parts.append(intermediate_cte)
                current_cte_name = intermediate_cte_name

        # Connect to the main query - if we have only inputs.x.y, then we join directly to inputs.x
        field_access = f"JSON_VALUE({table_alias}.{root_field}, '$.{property_path[0]}')"
        condition = f"""
        {field_access} IN (
            SELECT full_ref 
            FROM {current_cte_name}
        )"""
        filter_conditions.append(condition)

    # Return the CTEs and filter condition
    if not cte_parts and not filter_conditions:
        return {"cte_parts": [], "filter_sql": ""}

    # Add the object_conditions CTE to gather all conditions
    conditions_sql = ""
    if filter_conditions:
        conditions_sql = " AND (" + " AND ".join(filter_conditions) + ")"

    # Return components separately
    return {
        "cte_parts": cte_parts,
        "filter_sql": conditions_sql,
    }
