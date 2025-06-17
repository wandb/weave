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
import typing
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal, Optional, Union

from pydantic import BaseModel

from weave.trace_server.calls_query_builder.utils import (
    NotContext,
    param_slot,
)
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import clickhouse_cast

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

        Ignores leaf operations like Literal and GetField.

        Args:
            operand: The operand to process

        Returns:
            SQL condition string or None if optimization is not possible
        """
        if isinstance(operand, tsi_query.LiteralOperation):
            return self.process_literal(operand)
        elif isinstance(operand, tsi_query.GetFieldOperator):
            return self.process_get_field(operand)
        elif isinstance(operand, tsi_query.ConvertOperation):
            return self.process_convert(operand)
        return apply_processor(self, operand)

    def process_literal(self, operand: tsi_query.LiteralOperation) -> Optional[str]:
        """Process literal operand"""
        return None

    def process_get_field(self, operand: tsi_query.GetFieldOperator) -> Optional[str]:
        """Process get field operand"""
        return None

    def process_convert(self, operand: tsi_query.ConvertOperation) -> Optional[str]:
        """Process convert operand"""
        field = self.process_operand(operand.convert_.input)
        if field is None:
            return None
        return clickhouse_cast(field, operand.convert_.to)

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

        Note: If any condition in an OR cannot be processed, the entire OR
        cannot be processed, so we return None.
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


class ObjectRefCondition(BaseModel):
    """Represents a condition that filters on object references"""

    field_path: str  # e.g., "inputs.model.config.temperature"
    operation_type: str  # "eq", "contains", "gt", "gte", "in"
    value: typing.Union[
        str, int, float, bool, list, dict, None
    ]  # Allow dict for literal operations
    expand_columns: list[str]
    case_insensitive: bool = False
    conversion_type: Optional[Literal["double", "string", "int", "bool", "exists"]] = (
        None
    )

    def get_expand_column_match(self, shortest: bool = True) -> Optional[str]:
        """Find the matching expand column for this field path.

        Args:
            shortest (bool): If True, returns the shortest matching expand column.
                If False, returns the longest matching expand column.

        Returns:
            Optional[str]: The matching expand column or None if no match found.

        Examples:
            >>> condition = ObjectRefCondition(field_path="inputs.model.config.temperature", expand_columns=["inputs", "inputs.model"])
            >>> condition.get_expand_column_match(shortest=True)
            'inputs'
            >>> condition.get_expand_column_match(shortest=False)
            'inputs.model'
        """
        for expand_col in sorted(self.expand_columns, key=len, reverse=not shortest):
            if self.field_path.startswith(expand_col + "."):
                return expand_col
        return None

    def get_object_property_path(self) -> str:
        """Get the property path within the object (after the shortest expand column)
        this represents the path that contains object references that need to be expanded
        e.g. "inputs.model.config.temperature" -> "config.temperature"

        where expand_columns = ["inputs.model", "inputs.model.config"]
        """
        expand_match = self.get_expand_column_match()
        if expand_match:
            return self.field_path[len(expand_match) + 1 :]  # +1 for the dot
        return self.field_path

    def get_leaf_object_property_path(self) -> str:
        """Get the property path within the object (after the longest expand column)
        this represents the path that **doesn't** contain object references
        e.g. "inputs.model.config.temperature.val" -> "temperature.val"

        where expand_columns = ["inputs.model", "inputs.model.config"]
        """
        expand_match = self.get_expand_column_match(shortest=False)
        if expand_match:
            return self.field_path[len(expand_match) + 1 :]  # +1 for the dot
        return self.field_path

    def get_root_field(self) -> str:
        """Get the root field name (e.g., 'inputs_dump' from 'inputs.model.config.temperature')"""
        field_parts = self.field_path.split(".")
        root = field_parts[0] + "_dump"
        return root

    def as_sql(
        self,
        pb: "ParamBuilder",
        object_table_alias: str,
        table_alias: str = "calls_merged",
    ) -> str:
        """Generate the SQL for this object ref condition"""
        root_field = self.get_root_field()
        expand_match = self.get_expand_column_match()

        if not expand_match:
            raise ValueError(f"No expand column match found for {self.field_path}")

        # The key is the first property after the expand column
        object_property_path = self.get_object_property_path()
        property_parts = object_property_path.split(".")
        key = property_parts[0]

        # Parameterize the JSON path
        json_path_param = pb.add_param(f"$.{key}")

        # Build the SQL condition
        field_sql = f"any({table_alias}.{root_field})"
        ref_subquery = f"IN (SELECT full_ref FROM {object_table_alias})"

        return f"JSON_VALUE({field_sql}, {param_slot(json_path_param, 'String')}) {ref_subquery}"


def _get_cte_name_for_condition(i: int) -> str:
    """Generate a unique CTE name for this condition"""
    return f"obj_filter_{i}"


class ObjectRefFilterToCTEProcessor(QueryOptimizationProcessor):
    """Processes a calls query to identify and transform object reference conditions"""

    def __init__(self, pb: "ParamBuilder", table_alias: str, expand_columns: list[str]):
        super().__init__(pb, table_alias)
        self.expand_columns = expand_columns
        self.object_ref_conditions: list[ObjectRefCondition] = []
        self.field_to_cte_map: dict[str, str] = {}  # Maps field paths to CTE names

    def _is_object_ref_field(self, field_path: str) -> bool:
        """Check if this field path is an object ref based on expand_columns"""
        for expand_col in self.expand_columns:
            if field_path.startswith(expand_col + "."):
                return True
        return False

    def _create_cte_based_condition(self, condition: ObjectRefCondition) -> str:
        """Create a SQL condition that uses the CTE for this object ref"""
        expand_match = condition.get_expand_column_match()
        if not expand_match:
            raise ValueError(f"No expand column match found for {condition.field_path}")

        # Get the root field (e.g., 'inputs_dump')
        root_field = condition.get_root_field()

        # Get the key from the expand column, not the object property path
        # For "inputs.model" expand column, we want "model" (the part after "inputs.")
        field_parts = condition.field_path.split(".")
        expand_parts = expand_match.split(".")

        # The key should be the part of the expand column after the root field
        # e.g., for "inputs.model" expand column, key should be "model"
        if len(expand_parts) > 1:
            key = expand_parts[1]
        else:
            # This shouldn't happen if expand_match is valid, but fallback to first part
            object_property_path = condition.get_object_property_path()
            property_parts = object_property_path.split(".")
            key = property_parts[0]

        # Parameterize the JSON path
        json_path_param = self.pb.add_param(f"$.{key}")

        # Get the CTE name for this condition
        index = self.object_ref_conditions.index(condition)
        cte_name = _get_cte_name_for_condition(index)

        # Create the SQL condition
        field_sql = f"any({self.table_alias}.{root_field})"
        return f"JSON_VALUE({field_sql}, {param_slot(json_path_param, 'String')}) IN (SELECT full_ref FROM {cte_name})"

    def process_get_field(self, operand: tsi_query.GetFieldOperator) -> Optional[str]:
        """Check if this field reference is an object ref - if so, we can't process it normally"""
        field_path = operand.get_field_

        if self._is_object_ref_field(field_path):
            # Return None to indicate we can't process this normally
            return None

        # Not an object ref, let the parent handle it
        return super().process_get_field(operand)

    def process_eq(self, operation: tsi_query.EqOperation) -> Optional[str]:
        """Process equality operation for object refs"""
        field_operand = None
        conversion_type = None

        # Handle direct GetFieldOperator
        if isinstance(operation.eq_[0], tsi_query.GetFieldOperator):
            field_operand = operation.eq_[0]
        # Handle ConvertOperation wrapping a GetFieldOperator
        elif isinstance(operation.eq_[0], tsi_query.ConvertOperation):
            if isinstance(operation.eq_[0].convert_.input, tsi_query.GetFieldOperator):
                field_operand = operation.eq_[0].convert_.input
                conversion_type = operation.eq_[0].convert_.to

        if field_operand is not None:
            field_path = field_operand.get_field_
            if self._is_object_ref_field(field_path):
                if isinstance(operation.eq_[1], tsi_query.LiteralOperation):
                    obj_condition = ObjectRefCondition(
                        field_path=field_path,
                        operation_type="eq",
                        value=operation.eq_[1].literal_,
                        expand_columns=self.expand_columns,
                        conversion_type=conversion_type,
                    )
                    self.object_ref_conditions.append(obj_condition)

                    # Return the CTE-based condition
                    return self._create_cte_based_condition(obj_condition)

        return None

    def process_contains(self, operation: tsi_query.ContainsOperation) -> Optional[str]:
        """Process contains operation for object refs"""
        if isinstance(operation.contains_.input, tsi_query.GetFieldOperator):
            field_path = operation.contains_.input.get_field_
            if self._is_object_ref_field(field_path):
                if isinstance(operation.contains_.substr, tsi_query.LiteralOperation):
                    obj_condition = ObjectRefCondition(
                        field_path=field_path,
                        operation_type="contains",
                        value=operation.contains_.substr.literal_,
                        expand_columns=self.expand_columns,
                        case_insensitive=operation.contains_.case_insensitive or False,
                    )
                    self.object_ref_conditions.append(obj_condition)

                    # Return the CTE-based condition
                    return self._create_cte_based_condition(obj_condition)

        # Fall back to default (which will return None since we don't implement contains normally)
        return None

    def process_gt(self, operation: tsi_query.GtOperation) -> Optional[str]:
        """Process greater than operation for object refs"""
        field_operand = None
        conversion_type = None

        # Handle direct GetFieldOperator
        if isinstance(operation.gt_[0], tsi_query.GetFieldOperator):
            field_operand = operation.gt_[0]
        # Handle ConvertOperation wrapping a GetFieldOperator
        elif isinstance(operation.gt_[0], tsi_query.ConvertOperation):
            if isinstance(operation.gt_[0].convert_.input, tsi_query.GetFieldOperator):
                field_operand = operation.gt_[0].convert_.input
                conversion_type = operation.gt_[0].convert_.to

        if field_operand is not None:
            field_path = field_operand.get_field_
            if self._is_object_ref_field(field_path):
                if isinstance(operation.gt_[1], tsi_query.LiteralOperation):
                    obj_condition = ObjectRefCondition(
                        field_path=field_path,
                        operation_type="gt",
                        value=operation.gt_[1].literal_,
                        expand_columns=self.expand_columns,
                        conversion_type=conversion_type,
                    )
                    self.object_ref_conditions.append(obj_condition)

                    # Return the CTE-based condition
                    return self._create_cte_based_condition(obj_condition)

        return None

    def process_gte(self, operation: tsi_query.GteOperation) -> Optional[str]:
        """Process greater than or equal operation for object refs"""
        field_operand = None
        conversion_type = None

        # Handle direct GetFieldOperator
        if isinstance(operation.gte_[0], tsi_query.GetFieldOperator):
            field_operand = operation.gte_[0]
        # Handle ConvertOperation wrapping a GetFieldOperator
        elif isinstance(operation.gte_[0], tsi_query.ConvertOperation):
            if isinstance(operation.gte_[0].convert_.input, tsi_query.GetFieldOperator):
                field_operand = operation.gte_[0].convert_.input
                conversion_type = operation.gte_[0].convert_.to

        if field_operand is not None:
            field_path = field_operand.get_field_
            if self._is_object_ref_field(field_path):
                if isinstance(operation.gte_[1], tsi_query.LiteralOperation):
                    obj_condition = ObjectRefCondition(
                        field_path=field_path,
                        operation_type="gte",
                        value=operation.gte_[1].literal_,
                        expand_columns=self.expand_columns,
                        conversion_type=conversion_type,
                    )
                    self.object_ref_conditions.append(obj_condition)

                    # Return the CTE-based condition
                    return self._create_cte_based_condition(obj_condition)

        return None

    def process_in(self, operation: tsi_query.InOperation) -> Optional[str]:
        """Process in operation for object refs"""
        if isinstance(operation.in_[0], tsi_query.GetFieldOperator):
            field_path = operation.in_[0].get_field_
            if self._is_object_ref_field(field_path):
                # Extract literal values from the list
                values = []
                for operand in operation.in_[1]:
                    if isinstance(operand, tsi_query.LiteralOperation):
                        values.append(operand.literal_)
                    else:
                        return None  # Can't handle non-literal values in IN

                obj_condition = ObjectRefCondition(
                    field_path=field_path,
                    operation_type="in",
                    value=values,
                    expand_columns=self.expand_columns,
                )
                self.object_ref_conditions.append(obj_condition)

                # Return the CTE-based condition
                return self._create_cte_based_condition(obj_condition)

        return None


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


class OperationHandlerBase:
    """
    Base class for handling common patterns in query operation processing.

    This class provides shared functionality for extracting fields and literals
    from binary operations, reducing code duplication across different processors.
    """

    @staticmethod
    def extract_field_and_literal(
        operation: Union[
            tsi_query.EqOperation,
            tsi_query.GtOperation,
            tsi_query.GteOperation,
            tsi_query.ContainsOperation,
            tsi_query.InOperation,
        ],
    ) -> tuple[
        Optional[tsi_query.GetFieldOperator], Optional[tsi_query.LiteralOperation]
    ]:
        """
        Extract field and literal operands from a binary operation.

        Args:
            operation: The binary operation to extract operands from

        Returns:
            tuple[Optional[GetFieldOperator], Optional[LiteralOperation]]:
                A tuple of (field_operand, literal_operand) or (None, None) if invalid.

        Examples:
            >>> op = EqOperation(eq_=[GetFieldOperator(get_field_="test"), LiteralOperation(literal_="value")])
            >>> field_op, literal_op = OperationHandlerBase.extract_field_and_literal(op)
            >>> field_op.get_field_
            'test'
            >>> literal_op.literal_
            'value'
        """
        # Handle different operation types
        if hasattr(operation, "eq_"):
            ops = operation.eq_
        elif hasattr(operation, "gt_"):
            ops = operation.gt_
        elif hasattr(operation, "gte_"):
            ops = operation.gte_
        elif hasattr(operation, "contains_"):
            # Contains operation has a different structure
            if isinstance(operation.contains_.input, tsi_query.GetFieldOperator):
                field_operand = operation.contains_.input
                literal_operand = operation.contains_.substr
                if isinstance(literal_operand, tsi_query.LiteralOperation):
                    return field_operand, literal_operand
            return None, None
        elif hasattr(operation, "in_"):
            # IN operation has a different structure
            if len(operation.in_) >= 2 and isinstance(
                operation.in_[0], tsi_query.GetFieldOperator
            ):
                field_operand = operation.in_[0]
                # For IN operations, we don't extract a single literal but validate the structure
                # The caller should handle the list of values separately
                return field_operand, None
            return None, None
        else:
            return None, None

        if len(ops) != 2:
            return None, None

        field_operand_res = None
        literal_operand = None

        if isinstance(ops[0], tsi_query.GetFieldOperator):
            field_operand_res = ops[0]
            literal_operand = ops[1]
        elif isinstance(ops[1], tsi_query.GetFieldOperator):
            field_operand_res = ops[1]
            literal_operand = ops[0]

        if not isinstance(literal_operand, tsi_query.LiteralOperation):
            return None, None

        return field_operand_res, literal_operand

    @staticmethod
    def create_like_condition(
        field: str,
        like_pattern: str,
        pb: "ParamBuilder",
        table_alias: str,
        case_insensitive: bool = False,
    ) -> str:
        """
        Creates a LIKE condition for a JSON field.

        Args:
            field: The field name to apply the LIKE condition to
            like_pattern: The pattern to match against
            pb: Parameter builder for SQL parameters
            table_alias: Table alias to use in the condition
            case_insensitive: Whether to perform case-insensitive matching

        Returns:
            str: SQL LIKE condition

        Examples:
            >>> OperationHandlerBase.create_like_condition("inputs_dump", "%test%", pb, "calls")
            'calls.inputs_dump LIKE {param_slot}'
        """
        field_name = f"{table_alias}.{field}"

        if case_insensitive:
            param_name = pb.add_param(like_pattern.lower())
            return f"lower({field_name}) LIKE {param_slot(param_name, 'String')}"
        else:
            param_name = pb.add_param(like_pattern)
            return f"{field_name} LIKE {param_slot(param_name, 'String')}"


def _create_like_optimized_eq_condition(
    operation: tsi_query.EqOperation,
    pb: "ParamBuilder",
    table_alias: str,
) -> Optional[str]:
    """Creates a LIKE-optimized condition for equality operations."""
    field_operand, literal_operand = OperationHandlerBase.extract_field_and_literal(
        operation
    )
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

    like_condition = OperationHandlerBase.create_like_condition(
        field, like_pattern, pb, table_alias
    )
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

    like_condition = OperationHandlerBase.create_like_condition(
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
        like_condition = OperationHandlerBase.create_like_condition(
            field, like_pattern, pb, table_alias
        )
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
    field_operand, literal_operand = OperationHandlerBase.extract_field_and_literal(
        operation
    )
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


def process_query_for_object_refs(
    query: tsi_query.Query,
    pb: "ParamBuilder",
    table_alias: str,
    expand_columns: list[str],
) -> tuple[Optional[str], list[ObjectRefCondition]]:
    """
    Process a query to identify and extract object reference conditions.

    Returns:
        - Transformed SQL condition that uses CTEs (or None if no object refs)
        - List of object ref conditions that were extracted
    """
    if not expand_columns:
        return None, []

    processor = ObjectRefFilterToCTEProcessor(pb, table_alias, expand_columns)
    transformed_sql = apply_processor(processor, query.expr_)

    return transformed_sql, processor.object_ref_conditions


class ObjectRefConditionHandler:
    """
    Handles the creation of SQL conditions for object reference filtering.

    This class encapsulates the logic for building SQL conditions for different
    operation types while reducing code duplication.
    """

    def __init__(self, pb: "ParamBuilder", json_path_param: str):
        self.pb = pb
        self.json_path_param = json_path_param

    def _create_json_extract_expression(
        self, conversion_type: Optional[tsi_query.CastTo] = None
    ) -> str:
        """
        Creates a JSON_VALUE expression with optional type conversion.

        Args:
            conversion_type: Optional type to convert the extracted value to

        Returns:
            str: The JSON extraction expression

        Examples:
            >>> handler._create_json_extract_expression()
            'JSON_VALUE(val_dump, {param_slot})'
            >>> handler._create_json_extract_expression('double')
            'toFloat64(JSON_VALUE(val_dump, {param_slot}))'
        """
        json_extract = (
            f"JSON_VALUE(val_dump, {param_slot(self.json_path_param, 'String')})"
        )

        if conversion_type:
            from weave.trace_server.orm import clickhouse_cast

            return clickhouse_cast(json_extract, conversion_type)

        return json_extract

    def _create_filter_param(self, value: typing.Any) -> tuple[str, str]:
        """
        Creates a filter parameter and determines its type.

        Args:
            value: The value to create a parameter for

        Returns:
            tuple[str, str]: A tuple of (parameter_name, parameter_type)

        Examples:
            >>> handler._create_filter_param("test")
            ('param_1', 'String')
            >>> handler._create_filter_param(42)
            ('param_2', 'Int64')
        """
        from weave.trace_server.orm import python_value_to_ch_type

        filter_param = self.pb.add_param(value)
        filter_type = python_value_to_ch_type(value)
        return filter_param, filter_type

    def handle_eq_operation(self, condition: ObjectRefCondition) -> str:
        """
        Handle equality operations for object references.

        Args:
            condition: The object reference condition

        Returns:
            str: SQL condition for equality comparison
        """
        filter_param, filter_type = self._create_filter_param(condition.value)
        json_extract = self._create_json_extract_expression(condition.conversion_type)

        return f"{json_extract} = {param_slot(filter_param, filter_type)}"

    def handle_contains_operation(self, condition: ObjectRefCondition) -> str:
        """
        Handle contains operations for object references.

        Args:
            condition: The object reference condition

        Returns:
            str: SQL condition for contains comparison
        """
        filter_param = self.pb.add_param(f"%{condition.value}%")
        json_extract = self._create_json_extract_expression()

        if condition.case_insensitive:
            return f"lower({json_extract}) LIKE lower({param_slot(filter_param, 'String')})"
        else:
            return f"{json_extract} LIKE {param_slot(filter_param, 'String')}"

    def handle_comparison_operation(
        self, condition: ObjectRefCondition, operator: str
    ) -> str:
        """
        Handle gt/gte operations for object references.

        Args:
            condition: The object reference condition
            operator: The comparison operator ('>' or '>=')

        Returns:
            str: SQL condition for comparison
        """
        filter_param, filter_type = self._create_filter_param(condition.value)
        json_extract = self._create_json_extract_expression(condition.conversion_type)

        return f"{json_extract} {operator} {param_slot(filter_param, filter_type)}"

    def handle_in_operation(self, condition: ObjectRefCondition) -> str:
        """
        Handle IN operations for object references.

        Args:
            condition: The object reference condition

        Returns:
            str: SQL condition for IN comparison
        """
        if not isinstance(condition.value, list):
            raise TypeError("IN operation requires a list value")

        if not condition.value:
            return "1=0"  # Empty IN list matches nothing

        from weave.trace_server.orm import python_value_to_ch_type

        filter_param = self.pb.add_param(condition.value)
        filter_type = f"Array({python_value_to_ch_type(condition.value[0])})"
        json_extract = self._create_json_extract_expression(condition.conversion_type)

        return f"{json_extract} IN {param_slot(filter_param, filter_type)}"


def build_object_ref_ctes(
    pb: "ParamBuilder", project_id: str, object_ref_conditions: list[ObjectRefCondition]
) -> tuple[str, dict[str, str]]:
    """
    Build CTEs (Common Table Expressions) for object reference filtering.

    Args:
        pb: Parameter builder for SQL parameters
        project_id: Project ID for filtering
        object_ref_conditions: List of object reference conditions to build CTEs for

    Returns:
        - CTE SQL string
        - Dictionary mapping field paths to CTE alias names
    """
    if not object_ref_conditions:
        return "", {}

    project_param = pb.add_param(project_id)
    cte_parts = []
    field_to_cte_alias_map = {}
    cte_counter = 0

    for condition in object_ref_conditions:
        # Get the expand column match and property path
        expand_match = condition.get_expand_column_match()
        if not expand_match:
            continue

        object_property_path = condition.get_object_property_path()
        leaf_property = condition.get_leaf_object_property_path()
        # the number of refs in the path:
        intermediate_parts = object_property_path.replace(leaf_property, "").split(".")

        # Build the leaf-level CTE (filters on the actual property value)
        leaf_cte_name = f"obj_filter_{cte_counter}"
        cte_counter += 1

        # Parameterize the JSON path
        json_path_param = pb.add_param(f"$.{leaf_property}")

        # Create condition handler and generate the appropriate SQL condition
        handler = ObjectRefConditionHandler(pb, json_path_param)

        if condition.operation_type == "eq":
            val_condition = handler.handle_eq_operation(condition)
        elif condition.operation_type == "contains":
            val_condition = handler.handle_contains_operation(condition)
        elif condition.operation_type == "gt":
            val_condition = handler.handle_comparison_operation(condition, ">")
        elif condition.operation_type == "gte":
            val_condition = handler.handle_comparison_operation(condition, ">=")
        elif condition.operation_type == "in":
            val_condition = handler.handle_in_operation(condition)
        else:
            continue

        # Build the leaf CTE
        leaf_cte = f"""
        {leaf_cte_name} AS (
            SELECT
                object_id,
                digest,
                concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS full_ref
            FROM object_versions
            WHERE project_id = {param_slot(project_param, "String")}
                AND {val_condition}
            GROUP BY project_id, object_id, digest
        )"""

        cte_parts.append(leaf_cte)
        current_cte_name = leaf_cte_name

        # If we have nested properties, build intermediate CTEs
        if len(intermediate_parts) > 1:
            # Work backwards from the leaf to build the chain
            remaining_properties = intermediate_parts[:-1]  # All but the last property
            for prop in reversed(remaining_properties):
                intermediate_cte_name = f"obj_filter_{cte_counter}"
                cte_counter += 1

                # Parameterize the JSON path for this property
                prop_json_path_param = pb.add_param(f"$.{prop}")

                intermediate_cte = f"""
                {intermediate_cte_name} AS (
                    SELECT
                        object_id,
                        digest,
                        concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS full_ref
                    FROM object_versions
                    WHERE project_id = {param_slot(project_param, "String")}
                    AND JSON_VALUE(val_dump, {param_slot(prop_json_path_param, 'String')}) IN (
                        SELECT full_ref
                        FROM {current_cte_name}
                    )
                    GROUP BY project_id, object_id, digest
                )"""
                cte_parts.append(intermediate_cte)
                current_cte_name = intermediate_cte_name

        condition_key = _make_condition_key(condition)
        field_to_cte_alias_map[condition_key] = current_cte_name

    if not cte_parts:
        return "", {}

    return ",\n".join(cte_parts), field_to_cte_alias_map


def _make_condition_key(condition: ObjectRefCondition) -> str:
    """Map a unique condition key to the final CTE name.
    Use field_path + operation + value to create unique key for each condition
    """
    return f"{condition.field_path}_{condition.operation_type}_{condition.value}"


def is_object_ref_operand(
    operand: "tsi_query.Operand", expand_columns: list[str]
) -> bool:
    """Check if an operand references object fields based on expand_columns"""
    if not expand_columns:
        return False

    def check_field_operator(field_op: "tsi_query.GetFieldOperator") -> bool:
        field_path = field_op.get_field_
        for expand_col in expand_columns:
            if field_path.startswith(expand_col + "."):
                return True
        return False

    # Check all GetFieldOperator operands in the expression tree
    def check_operand_recursive(op: "tsi_query.Operand") -> bool:
        if isinstance(op, tsi_query.GetFieldOperator):
            return check_field_operator(op)
        elif isinstance(op, tsi_query.AndOperation):
            return any(check_operand_recursive(sub_op) for sub_op in op.and_)
        elif isinstance(op, tsi_query.OrOperation):
            return any(check_operand_recursive(sub_op) for sub_op in op.or_)
        elif isinstance(op, tsi_query.NotOperation):
            return any(check_operand_recursive(sub_op) for sub_op in op.not_)
        elif isinstance(op, tsi_query.EqOperation):
            return any(check_operand_recursive(sub_op) for sub_op in op.eq_)
        elif isinstance(op, tsi_query.GtOperation):
            return any(check_operand_recursive(sub_op) for sub_op in op.gt_)
        elif isinstance(op, tsi_query.GteOperation):
            return any(check_operand_recursive(sub_op) for sub_op in op.gte_)
        elif isinstance(op, tsi_query.InOperation):
            return check_operand_recursive(
                op.in_[0]
            )  # Only check the field being compared
        elif isinstance(op, tsi_query.ContainsOperation):
            return check_operand_recursive(op.contains_.input)
        elif isinstance(op, tsi_query.ConvertOperation):
            return check_operand_recursive(op.convert_.input)
        return False

    return check_operand_recursive(operand)
