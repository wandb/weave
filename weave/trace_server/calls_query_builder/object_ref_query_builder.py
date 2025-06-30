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

from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from weave.trace_server.calls_query_builder.optimization_builder import (
    QueryOptimizationProcessor,
    apply_processor,
)
from weave.trace_server.calls_query_builder.utils import (
    json_dump_field_as_sql,
    param_slot,
)
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import clickhouse_cast, combine_conditions, quote_json_path

if TYPE_CHECKING:
    from weave.trace_server.calls_query_builder.calls_query_builder import (
        Condition,
        OrderField,
        ParamBuilder,
    )


class ObjectRefCondition:
    """Base class for object reference conditions"""

    def __init__(
        self,
        field_path: str,
        expand_columns: list[str],
        case_insensitive: bool = False,
        conversion_type: Optional[
            Literal["double", "string", "int", "bool", "exists"]
        ] = None,
    ):
        self.field_path = field_path
        self.expand_columns = expand_columns
        self.case_insensitive = case_insensitive
        self.conversion_type = conversion_type

    @property
    def is_table_rows_condition(self) -> bool:
        # TODO: is this the only time this is an actual table join condition??
        if (
            self.field_path.startswith("inputs.example")
            and "inputs.example" in self.expand_columns
        ):
            return True
        return False

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

    def get_intermediate_object_refs(self) -> list[str]:
        """
        Get the intermediate object reference property paths between the shortest and longest expand columns.

        Args:
            condition: The object reference condition

        Returns:
            List of property paths for intermediate object references based on expand columns

        Examples:
            >>> # For path "inputs.a.b.c.d.e" with expand_columns ["inputs.a.b", "inputs.a.b.c.d"]
            >>> # We have segments: ["inputs.a.b", "c.d", "e"]
            >>> # intermediate refs = ["c.d"] (the property path between the two expand columns)
        """
        # Get all matching expand columns for this field path, sorted by length
        matching_columns = []
        for expand_col in self.expand_columns:
            if self.field_path.startswith(expand_col + "."):
                matching_columns.append(expand_col)

        if len(matching_columns) <= 1:
            # No intermediate refs if we only have 0 or 1 expand column
            return []

        # Sort by length to get shortest to longest
        matching_columns.sort(key=len)

        # Calculate intermediate property paths between consecutive expand columns
        intermediate_refs = []
        for i in range(len(matching_columns) - 1):
            current_expand = matching_columns[i]
            next_expand = matching_columns[i + 1]

            # The intermediate property is the part of next_expand that comes after current_expand
            if next_expand.startswith(current_expand + "."):
                intermediate_prop = next_expand[len(current_expand) + 1 :]
                intermediate_refs.append(intermediate_prop)

        return intermediate_refs

    def get_accessor_key(self) -> str:
        """
        Get the JSON accessor key for this objects *first* ref

        This extracts the key that should be used in JSON_VALUE operations to access
        the object reference within the root field's JSON structure. This is non trivial
        because we don't know where refs stop and nested json begins.

        Returns:
            str: The key to use for JSON access

        Examples:
            >>> # json: {"inputs": {"model": <ref>}}, {"config": {"temperature": "hot"}}
            >>> # For field_path="inputs.model.config.temperature" with expand_columns=["inputs.model"]
            >>> condition = ObjectRefCondition(field_path="inputs.model.config.temperature", expand_columns=["inputs.model"], ...)
            >>> condition.get_accessor_key()
            'model'

            >>> # json: {"inputs": {"a": {"b": <ref>}}}
            >>> # For field_path="inputs.a.b.c.d.e" with expand_columns=["inputs.a.b"]
            >>> condition = ObjectRefCondition(field_path="inputs.a.b.c.d.e", expand_columns=["inputs.a.b"], ...)
            >>> condition.get_accessor_key()
            'a.b'
        """
        expand_match = self.get_expand_column_match()
        if not expand_match:
            raise ValueError(f"No expand column match found for {self.field_path}")

        expand_parts = expand_match.split(".")
        if len(expand_parts) > 1:
            return ".".join(expand_parts[1:])

        object_property_path = self.get_object_property_path()
        property_parts = object_property_path.split(".")
        return property_parts[0]

    @property
    def unique_key(self) -> str:
        """
        Map a unique condition key to the final CTE name.
        Must be implemented by child classes.

        Returns:
            str: A unique key identifying this condition
        """
        raise NotImplementedError("Child classes must implement unique_key property")


class ObjectRefFilterCondition(ObjectRefCondition):
    """Represents a condition that filters on object references"""

    def __init__(
        self,
        field_path: str,
        operation_type: str,
        value: Union[str, int, float, bool, list, dict, None],
        expand_columns: list[str],
        case_insensitive: bool = False,
        conversion_type: Optional[
            Literal["double", "string", "int", "bool", "exists"]
        ] = None,
    ):
        super().__init__(field_path, expand_columns, case_insensitive, conversion_type)
        self.operation_type = operation_type
        self.value = value

    @property
    def unique_key(self) -> str:
        """
        Map a unique condition key to the final CTE name.
        Use field_path + operation + value to create unique key for each condition

        Returns:
            str: A unique key identifying this condition
        """
        return f"{self.field_path}_{self.operation_type}_{self.value}"


class ObjectRefOrderCondition(ObjectRefCondition):
    """Represents an order condition on object references"""

    def __init__(
        self,
        field_path: str,
        expand_columns: list[str],
        case_insensitive: bool = False,
        conversion_type: Optional[
            Literal["double", "string", "int", "bool", "exists"]
        ] = None,
    ):
        super().__init__(field_path, expand_columns, case_insensitive, conversion_type)

    @property
    def unique_key(self) -> str:
        """
        Map a unique condition key to the final CTE name.
        For ordering, we only need the field path since we include all objects.

        Returns:
            str: A unique key identifying this condition
        """
        return f"order_{self.field_path}"


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

    def _create_filter_param(self, value: Any) -> tuple[str, str]:
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

    def handle_comparison_operation(
        self, condition: ObjectRefFilterCondition, operator: str
    ) -> str:
        """
        Handle simple binary operations (=, >, >=) for object references.

        Args:
            condition: The object reference filter condition
            operator: The SQL operator to use ("=", ">", ">=")

        Returns:
            str: SQL condition for the operation
        """
        filter_param, filter_type = self._create_filter_param(condition.value)
        json_extract = self._create_json_extract_expression(condition.conversion_type)

        return f"{json_extract} {operator} {param_slot(filter_param, filter_type)}"

    def handle_contains_operation(self, condition: ObjectRefFilterCondition) -> str:
        """
        Handle contains operations for object references.

        Args:
            condition: The object reference filter condition

        Returns:
            str: SQL condition for contains comparison
        """
        filter_param = self.pb.add_param(f"%{condition.value}%")
        json_extract = self._create_json_extract_expression()

        if condition.case_insensitive:
            return f"lower({json_extract}) LIKE lower({param_slot(filter_param, 'String')})"
        else:
            return f"{json_extract} LIKE {param_slot(filter_param, 'String')}"

    def handle_in_operation(self, condition: ObjectRefFilterCondition) -> str:
        """
        Handle IN operations for object references.

        Args:
            condition: The object reference filter condition

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

        # Extract the root field and accessor key from the condition
        root_field = condition.get_root_field()
        key = condition.get_accessor_key()

        key_parts = key.split(".") if key else []
        field_sql = f"any({self.table_alias}.{root_field})"
        json_extract_sql = json_dump_field_as_sql(
            self.pb, self.table_alias, field_sql, key_parts, use_agg_fn=False
        )
        if condition.is_table_rows_condition:
            json_extract_sql = f"regexpExtract({json_extract_sql}, '/([^/]+)$', 1)"
        return f"{json_extract_sql} IN (SELECT full_ref FROM {correct_cte})"


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

    def _extract_field_operand(
        self, operand: "tsi_query.Operand"
    ) -> tuple[Optional["tsi_query.GetFieldOperator"], Optional[str]]:
        """
        Extract field operand and conversion type from an operand.

        Returns:
            tuple: (field_operand, conversion_type) or (None, None) if not extractable
        """
        # Handle direct GetFieldOperator
        if isinstance(operand, tsi_query.GetFieldOperator):
            return operand, None
        # Handle ConvertOperation wrapping a GetFieldOperator
        elif isinstance(operand, tsi_query.ConvertOperation) and isinstance(
            operand.convert_.input, tsi_query.GetFieldOperator
        ):
            return operand.convert_.input, operand.convert_.to

        return None, None

    def _process_binary_operation(
        self,
        operands: tuple["tsi_query.Operand", "tsi_query.Operand"],
        operation_type: str,
        **kwargs: Any,
    ) -> Optional[str]:
        """
        Process binary operations (eq, gt, gte) with common logic.

        Args:
            operands: Tuple of operands from the operation
            operation_type: Type of operation ("eq", "gt", "gte")
            **kwargs: Additional arguments for ObjectRefCondition

        Returns:
            Optional[str]: CTE-based condition or None if not processable
        """
        if len(operands) < 2:
            return None

        field_operand, conversion_type = self._extract_field_operand(operands[0])

        if field_operand is not None:
            field_path = field_operand.get_field_
            if self._is_object_ref_field(field_path) and isinstance(
                operands[1], tsi_query.LiteralOperation
            ):
                # Only include conversion_type if it's a valid CastTo type
                condition_kwargs = {**kwargs}
                if conversion_type in {"double", "string", "int", "bool", "exists"}:
                    condition_kwargs["conversion_type"] = conversion_type

                obj_condition = ObjectRefFilterCondition(
                    field_path=field_path,
                    operation_type=operation_type,
                    value=operands[1].literal_,
                    expand_columns=self.expand_columns,
                    **condition_kwargs,
                )
                self.object_ref_conditions.append(obj_condition)

        return None

    def process_or(self, operation: tsi_query.OrOperation) -> Optional[str]:
        """Process OR operations to extract object reference conditions from all operands."""
        # Unlike the parent class, we need to process ALL operands to extract conditions,
        # regardless of whether they can be "optimized" or not
        for op in operation.or_:
            self.process_operand(op)

        return None

    def process_eq(self, operation: tsi_query.EqOperation) -> Optional[str]:
        """Process equality operation for object refs"""
        return self._process_binary_operation(operation.eq_, "eq")

    def process_contains(self, operation: tsi_query.ContainsOperation) -> Optional[str]:
        """Process contains operation for object refs"""
        if isinstance(operation.contains_.input, tsi_query.GetFieldOperator):
            field_path = operation.contains_.input.get_field_
            if self._is_object_ref_field(field_path) and isinstance(
                operation.contains_.substr, tsi_query.LiteralOperation
            ):
                obj_condition = ObjectRefFilterCondition(
                    field_path=field_path,
                    operation_type="contains",
                    value=operation.contains_.substr.literal_,
                    expand_columns=self.expand_columns,
                    case_insensitive=operation.contains_.case_insensitive or False,
                )
                self.object_ref_conditions.append(obj_condition)

        return None

    def process_gt(self, operation: tsi_query.GtOperation) -> Optional[str]:
        """Process greater than operation for object refs"""
        return self._process_binary_operation(operation.gt_, "gt")

    def process_gte(self, operation: tsi_query.GteOperation) -> Optional[str]:
        """Process greater than or equal operation for object refs"""
        return self._process_binary_operation(operation.gte_, "gte")

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

                obj_condition = ObjectRefFilterCondition(
                    field_path=field_path,
                    operation_type="in",
                    value=values,
                    expand_columns=self.expand_columns,
                )
                self.object_ref_conditions.append(obj_condition)
        return None


def _get_cte_name_for_condition(i: int) -> str:
    """Generate a unique CTE name for this condition"""
    return f"obj_filter_{i}"


def build_object_ref_ctes(
    pb: "ParamBuilder",
    project_id: str,
    object_ref_conditions: list[ObjectRefCondition],
) -> tuple[str, dict[str, str]]:
    """
    Build CTEs (Common Table Expressions) for object reference filtering and ordering.

    For ordering conditions, this function creates a chain of CTEs where:
    1. The leaf CTE selects the actual value to order by from the deepest object
    2. Each intermediate CTE propagates this value up the reference chain
    3. The final CTE contains the top-level object reference with the leaf value

    This ensures that when ordering by nested object properties (e.g., inputs.model.config.temperature),
    we sort by the actual temperature value rather than the object reference itself.

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

    # Deduplicate conditions based on unique_key
    unique_conditions: dict[str, ObjectRefCondition] = {}
    for condition in object_ref_conditions:
        unique_key = condition.unique_key
        if unique_key not in unique_conditions:
            unique_conditions[unique_key] = condition

    for condition in unique_conditions.values():
        # Get the expand column match and property path
        expand_match = condition.get_expand_column_match()
        if not expand_match:
            continue

        # Build the leaf-level CTE (filters on the actual property value)
        leaf_cte_name = f"obj_filter_{cte_counter}"
        cte_counter += 1

        leaf_property = condition.get_leaf_object_property_path()
        json_path_param = pb.add_param(quote_json_path(leaf_property))

        # Create condition handler and generate the appropriate SQL condition
        handler = ObjectRefConditionHandler(pb, json_path_param)

        # For filters, don't select object value. Only needed when ordering
        val_dump_select = ""
        val_condition: Optional[str] = None
        if isinstance(condition, ObjectRefOrderCondition):
            # For ordering, select the actual leaf value that we want to order by
            # This value will be propagated through intermediate CTEs to the final result
            json_extract_sql = json_dump_field_as_sql(
                pb,
                "object_versions",
                "any(val_dump)",
                leaf_property.split("."),
            )
            val_dump_select = f"{json_extract_sql} AS object_val_dump,"
        elif isinstance(condition, ObjectRefFilterCondition):
            if condition.operation_type == "eq":
                val_condition = handler.handle_comparison_operation(condition, "=")
            elif condition.operation_type == "contains":
                val_condition = handler.handle_contains_operation(condition)
            elif condition.operation_type == "gt":
                val_condition = handler.handle_comparison_operation(condition, ">")
            elif condition.operation_type == "gte":
                val_condition = handler.handle_comparison_operation(condition, ">=")
            elif condition.operation_type == "in":
                val_condition = handler.handle_in_operation(condition)
        val_condition_sql = f"AND {val_condition}" if val_condition else ""

        # Build the leaf CTE
        if condition.is_table_rows_condition:
            leaf_cte = f"""
            {leaf_cte_name} AS (
                SELECT distinct(digest) as full_ref
                FROM table_rows
                WHERE project_id = {param_slot(project_param, "String")}
                {val_condition_sql}
            )
            """
        else:
            leaf_cte = f"""
            {leaf_cte_name} AS (
                SELECT
                    object_id,
                    digest,
                    {val_dump_select}
                    concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS full_ref
                FROM object_versions
                WHERE project_id = {param_slot(project_param, "String")}
                    {val_condition_sql}
                GROUP BY project_id, object_id, digest
            )"""

        cte_parts.append(leaf_cte)
        current_cte_name = leaf_cte_name

        intermediate_refs = condition.get_intermediate_object_refs()
        # If we have intermediate object references, build CTEs for them
        if intermediate_refs:
            # Work backwards to build the chain
            for ref_property in reversed(intermediate_refs):
                intermediate_cte_name = f"obj_filter_{cte_counter}"
                cte_counter += 1

                prop_json_path_param = pb.add_param(quote_json_path(ref_property))

                # For intermediate CTEs, we need to propagate the object_val_dump from the previous CTE
                # rather than selecting it from the current object's val_dump
                intermediate_val_dump_select, join_clause_for_ordering = "", ""
                if isinstance(condition, ObjectRefOrderCondition):
                    # Select the object_val_dump from the previous CTE to propagate the leaf value
                    intermediate_val_dump_select = (
                        "any(prev.object_val_dump) AS object_val_dump,"
                    )
                    join_clause_for_ordering = f"JOIN {current_cte_name} prev ON JSON_VALUE(ov.val_dump, {param_slot(prop_json_path_param, 'String')}) = prev.full_ref"

                intermediate_cte = f"""
                {intermediate_cte_name} AS (
                    SELECT
                        ov.object_id,
                        ov.digest,
                        {intermediate_val_dump_select}
                        concat('weave-trace-internal:///', ov.project_id, '/object/', ov.object_id, ':', ov.digest) AS full_ref
                    FROM object_versions ov
                    {join_clause_for_ordering}
                    WHERE ov.project_id = {param_slot(project_param, "String")}
                        AND JSON_VALUE(ov.val_dump, {param_slot(prop_json_path_param, 'String')}) IN (
                            SELECT full_ref FROM {current_cte_name}
                        )
                    GROUP BY ov.project_id, ov.object_id, ov.digest
                )"""
                cte_parts.append(intermediate_cte)
                current_cte_name = intermediate_cte_name

        field_to_cte_alias_map[condition.unique_key] = current_cte_name

    if not cte_parts:
        return "", {}

    return ",\n".join(cte_parts), field_to_cte_alias_map


def has_object_ref_field(field_path: str, expand_columns: list[str]) -> bool:
    """
    Check if an order field references object fields based on expand_columns.

    Args:
        field_path: The field path to check (e.g., "inputs.model.temperature")
        expand_columns: List of expand column patterns to match against

    Returns:
        bool: True if the field path references object fields
    """
    if not expand_columns:
        return False

    return any(field_path.startswith(expand_col + ".") for expand_col in expand_columns)


def is_object_ref_operand(
    operand: "tsi_query.Operand", expand_columns: list[str]
) -> bool:
    """
    Check if an operand references object fields based on expand_columns.

    Args:
        operand: The operand to check
        expand_columns: List of expand column patterns to match against

    Returns:
        bool: True if the operand references object fields
    """
    if not expand_columns:
        return False

    # Check all GetFieldOperator operands in the expression tree
    def check_operand_recursive(op: "tsi_query.Operand") -> bool:
        if isinstance(op, tsi_query.GetFieldOperator):
            return has_object_ref_field(op.get_field_, expand_columns)
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


def get_object_ref_conditions(
    conditions: list["Condition"],
    order_fields: list["OrderField"],
    expand_columns: list[str],
) -> list[ObjectRefCondition]:
    """
    Get all object reference conditions from a list of conditions.

    Args:
        conditions: List of conditions to process
        expand_columns: List of expand columns to match against

    Returns:
        List of object reference conditions
    """
    if not expand_columns:
        return []

    all_object_ref_conditions: list[ObjectRefCondition] = []
    for condition in conditions:
        object_ref_conditions = condition.get_object_ref_conditions(expand_columns)
        all_object_ref_conditions.extend(object_ref_conditions)

    for order_field in order_fields:
        field_path = order_field.raw_field_path
        is_obj_ref = has_object_ref_field(field_path, expand_columns)
        if is_obj_ref:
            obj_order_condition = ObjectRefOrderCondition(
                field_path=field_path,
                expand_columns=expand_columns,
            )
            all_object_ref_conditions.append(obj_order_condition)

    return all_object_ref_conditions
