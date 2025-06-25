"""
Object reference query builder for call queries.

This module handles the specialized logic for filtering calls based on object references
in expand columns. It provides functionality to:

1. Detect object reference operands in queries
2. Process object reference conditions into CTEs (Common Table Expressions)
3. Generate optimized SQL for object reference filtering

Key components:
- ObjectRefCondition: Represents a condition that filters on object references
- ObjectRefQueryProcessor: Handles processing of object ref conditions in queries
- CTE building functions for efficient object reference filtering
"""

import typing
from typing import TYPE_CHECKING, Literal, Optional

from pydantic import BaseModel

from weave.trace_server.calls_query_builder.optimization_builder import (
    QueryOptimizationProcessor,
    apply_processor,
)
from weave.trace_server.calls_query_builder.utils import (
    param_slot,
)
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import clickhouse_cast, combine_conditions

if TYPE_CHECKING:
    from weave.trace_server.calls_query_builder.calls_query_builder import (
        ParamBuilder,
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

    @property
    def unique_key(self) -> str:
        """
        Map a unique condition key to the final CTE name.
        Use field_path + operation + value to create unique key for each condition

        Returns:
            str: A unique key identifying this condition

        Examples:
            >>> condition = ObjectRefCondition(field_path="inputs.model", operation_type="eq", value="test", expand_columns=[])
            >>> condition.unique_key
            'inputs.model_eq_test'
        """
        return f"{self.field_path}_{self.operation_type}_{self.value}"

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


class ObjectRefQueryProcessor:
    """
    Processes query operands for object reference conditions.

    This class handles the recursive processing of query operands to identify
    and transform object reference conditions into appropriate SQL.
    """

    def __init__(
        self,
        pb: "ParamBuilder",
        table_alias: str,
        expand_columns: list[str],
        field_to_object_join_alias_map: dict[str, str],
    ):
        self.pb = pb
        self.table_alias = table_alias
        self.expand_columns = expand_columns
        self.field_to_object_join_alias_map = field_to_object_join_alias_map

    def process_operand(self, operand: "tsi_query.Operand") -> str:
        """Recursively process any operand, handling object refs and nested operations."""
        if isinstance(operand, tsi_query.AndOperation):
            conditions = []
            for sub_operand in operand.and_:
                condition_sql = self.process_operand(sub_operand)
                conditions.append(condition_sql)
            return combine_conditions(conditions, "AND")

        elif isinstance(operand, tsi_query.OrOperation):
            conditions = []
            for sub_operand in operand.or_:
                condition_sql = self.process_operand(sub_operand)
                conditions.append(condition_sql)
            return combine_conditions(conditions, "OR")

        elif isinstance(operand, tsi_query.NotOperation):
            inner_sql = self.process_operand(operand.not_[0])
            return f"(NOT ({inner_sql}))"

        else:
            # This is a leaf operand (like EqOperation, GtOperation, etc.)
            return self._process_leaf_operand(operand)

    def _process_leaf_operand(self, operand: "tsi_query.Operand") -> str:
        """Process a leaf operand (non-nested operation)."""
        # Check if this specific operand is an object ref condition
        if is_object_ref_operand(operand, self.expand_columns):
            query_for_condition = tsi_query.Query.model_validate({"$expr": operand})
            object_ref_conditions = process_query_for_object_refs(
                query_for_condition, self.pb, self.table_alias, self.expand_columns
            )
            if len(object_ref_conditions) > 1:
                raise ValueError(
                    f"Leaf operand {operand} has multiple object ref conditions: {object_ref_conditions}"
                )
            return self._handle_single_object_ref_condition(
                operand, object_ref_conditions[0]
            )
        else:
            # Handle as normal condition
            from weave.trace_server.calls_query_builder.calls_query_builder import (
                process_query_to_conditions,
            )

            filter_conditions = process_query_to_conditions(
                tsi_query.Query.model_validate({"$expr": {"$and": [operand]}}),
                self.pb,
                self.table_alias,
            )
            return combine_conditions(filter_conditions.conditions, "AND")

    def _handle_single_object_ref_condition(
        self,
        operand: "tsi_query.Operand",
        condition: ObjectRefCondition,
    ) -> str:
        """Handle a single object reference condition."""
        if condition.unique_key not in self.field_to_object_join_alias_map:
            raise ValueError(
                f"Condition key {condition.unique_key} not found in field_to_object_join_alias_map"
            )

        correct_cte = self.field_to_object_join_alias_map[condition.unique_key]
        # Extract the root field and key from the condition
        expand_match = condition.get_expand_column_match()
        if not expand_match:
            raise ValueError(f"No expand match found for {condition.field_path}")

        root_field = condition.get_root_field()
        field_parts = condition.field_path.split(".")
        expand_parts = expand_match.split(".")
        if len(expand_parts) > 1:
            key = expand_parts[1]
        else:
            object_property_path = condition.get_object_property_path()
            property_parts = object_property_path.split(".")
            key = property_parts[0]

        field_sql = f"any({self.table_alias}.{root_field})"
        json_path_param = self.pb.add_param(f"$.{key}")
        return f"JSON_VALUE({field_sql}, {param_slot(json_path_param, 'String')}) IN (SELECT full_ref FROM {correct_cte})"


class ObjectRefFilterToCTEProcessor(QueryOptimizationProcessor):
    """Processes a calls query to identify and transform object reference conditions"""

    def __init__(self, pb: "ParamBuilder", table_alias: str, expand_columns: list[str]):
        self.pb = pb
        self.table_alias = table_alias
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

    def process_eq(self, operation: tsi_query.EqOperation) -> Optional[str]:
        """Process equality operation for object refs"""
        field_operand = None
        conversion_type = None

        # Handle direct GetFieldOperator
        if isinstance(operation.eq_[0], tsi_query.GetFieldOperator):
            field_operand = operation.eq_[0]
        # Handle ConvertOperation wrapping a GetFieldOperator
        elif isinstance(operation.eq_[0], tsi_query.ConvertOperation) and isinstance(
            operation.eq_[0].convert_.input, tsi_query.GetFieldOperator
        ):
            field_operand = operation.eq_[0].convert_.input
            conversion_type = operation.eq_[0].convert_.to

        if field_operand is not None:
            field_path = field_operand.get_field_
            if self._is_object_ref_field(field_path) and isinstance(
                operation.eq_[1], tsi_query.LiteralOperation
            ):
                obj_condition = ObjectRefCondition(
                    field_path=field_path,
                    operation_type="eq",
                    value=operation.eq_[1].literal_,
                    expand_columns=self.expand_columns,
                    conversion_type=conversion_type,
                )
                self.object_ref_conditions.append(obj_condition)
                return self._create_cte_based_condition(obj_condition)

        return None

    def process_contains(self, operation: tsi_query.ContainsOperation) -> Optional[str]:
        """Process contains operation for object refs"""
        if isinstance(operation.contains_.input, tsi_query.GetFieldOperator):
            field_path = operation.contains_.input.get_field_
            if self._is_object_ref_field(field_path) and isinstance(
                operation.contains_.substr, tsi_query.LiteralOperation
            ):
                obj_condition = ObjectRefCondition(
                    field_path=field_path,
                    operation_type="contains",
                    value=operation.contains_.substr.literal_,
                    expand_columns=self.expand_columns,
                    case_insensitive=operation.contains_.case_insensitive or False,
                )
                self.object_ref_conditions.append(obj_condition)
                return self._create_cte_based_condition(obj_condition)

        return None

    def process_gt(self, operation: tsi_query.GtOperation) -> Optional[str]:
        """Process greater than operation for object refs"""
        field_operand = None
        conversion_type = None

        # Handle direct GetFieldOperator
        if isinstance(operation.gt_[0], tsi_query.GetFieldOperator):
            field_operand = operation.gt_[0]
        # Handle ConvertOperation wrapping a GetFieldOperator
        elif isinstance(operation.gt_[0], tsi_query.ConvertOperation) and isinstance(
            operation.gt_[0].convert_.input, tsi_query.GetFieldOperator
        ):
            field_operand = operation.gt_[0].convert_.input
            conversion_type = operation.gt_[0].convert_.to

        if field_operand is not None:
            field_path = field_operand.get_field_
            if self._is_object_ref_field(field_path) and isinstance(
                operation.gt_[1], tsi_query.LiteralOperation
            ):
                obj_condition = ObjectRefCondition(
                    field_path=field_path,
                    operation_type="gt",
                    value=operation.gt_[1].literal_,
                    expand_columns=self.expand_columns,
                    conversion_type=conversion_type,
                )
                self.object_ref_conditions.append(obj_condition)
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
        elif isinstance(operation.gte_[0], tsi_query.ConvertOperation) and isinstance(
            operation.gte_[0].convert_.input, tsi_query.GetFieldOperator
        ):
            field_operand = operation.gte_[0].convert_.input
            conversion_type = operation.gte_[0].convert_.to

        if field_operand is not None:
            field_path = field_operand.get_field_
            if self._is_object_ref_field(field_path) and isinstance(
                operation.gte_[1], tsi_query.LiteralOperation
            ):
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


def _get_cte_name_for_condition(i: int) -> str:
    """Generate a unique CTE name for this condition"""
    return f"obj_filter_{i}"


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

        field_to_cte_alias_map[condition.unique_key] = current_cte_name

    if not cte_parts:
        return "", {}

    return ",\n".join(cte_parts), field_to_cte_alias_map


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


def process_query_for_object_refs(
    query: tsi_query.Query,
    pb: "ParamBuilder",
    table_alias: str,
    expand_columns: list[str],
) -> list[ObjectRefCondition]:
    """
    Process a query to identify and extract object reference conditions.

    Returns:
        - List of object ref conditions that were extracted
    """
    if not expand_columns:
        return []

    processor = ObjectRefFilterToCTEProcessor(pb, table_alias, expand_columns)
    # We don't need the transformed SQL here, just the extracted conditions
    apply_processor(processor, query.expr_)

    return processor.object_ref_conditions
