import uuid
from typing import TYPE_CHECKING, Optional, Union

from pydantic import BaseModel

from weave.trace_server.calls_query_builder.utils import (
    _param_slot,
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

DATETIME_OPTIMIZATION_BUFFER = 60 * 1_000  # 60 seconds


def _field_requires_null_check(field: str) -> bool:
    return field in START_ONLY_CALL_FIELDS | END_ONLY_CALL_FIELDS


class QueryOptimizationProcessor:
    def __init__(self, pb: "ParamBuilder", table_alias: str):
        self.pb = pb
        self.table_alias = table_alias

    def process_operand(self, operand: tsi_query.Operand) -> Optional[str]:
        # Can never hit leaf operations before optimizations, always return None
        if isinstance(operand, tsi_query.LiteralOperation):
            return None
        elif isinstance(operand, tsi_query.GetFieldOperator):
            return None
        elif isinstance(operand, tsi_query.ConvertOperation):
            return None
        return apply_processor(self, operand)

    def process_and(self, operation: tsi_query.AndOperation) -> Optional[str]:
        conditions = []
        for op in operation.and_:
            result = self.process_operand(op)
            if result:
                conditions.append(result)

        if conditions:
            return "(" + " AND ".join(conditions) + ")"
        return None

    def process_or(self, operation: tsi_query.OrOperation) -> Optional[str]:
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
        result = self.process_operand(operation.not_[0])
        if result is None:
            return None
        return f"NOT ({result})"

    def process_eq(self, operation: tsi_query.EqOperation) -> Optional[str]:
        return None

    def process_contains(self, operation: tsi_query.ContainsOperation) -> Optional[str]:
        return None

    def process_in(self, operation: tsi_query.InOperation) -> Optional[str]:
        return None

    def process_gt(self, operation: tsi_query.GtOperation) -> Optional[str]:
        return None

    def process_gte(self, operation: tsi_query.GteOperation) -> Optional[str]:
        return None

    def finalize_sql(self, result: Optional[str]) -> Optional[str]:
        """Final step to make valid SQL for the calls query."""
        if result:
            return f"AND {result}"
        return None


class StringOptimizationProcessor(QueryOptimizationProcessor):
    def process_eq(self, operation: tsi_query.EqOperation) -> Optional[str]:
        return _create_like_optimized_eq_condition(operation, self.pb, self.table_alias)

    def process_contains(self, operation: tsi_query.ContainsOperation) -> Optional[str]:
        return _create_like_optimized_contains_condition(
            operation, self.pb, self.table_alias
        )

    def process_in(self, operation: tsi_query.InOperation) -> Optional[str]:
        return _create_like_optimized_in_condition(operation, self.pb, self.table_alias)


class IdOptimizationProcessor(QueryOptimizationProcessor):
    def process_gt(self, operation: tsi_query.GtOperation) -> Optional[str]:
        return _create_datetime_optimization_sql(operation, self.pb, self.table_alias)

    def process_gte(self, operation: tsi_query.GteOperation) -> Optional[str]:
        return _create_datetime_optimization_sql(operation, self.pb, self.table_alias)

    def finalize_sql(self, result: Optional[str]) -> Optional[str]:
        if result:
            with_otel_id_filter = _add_otel_id_filter(self.table_alias, result)
            return super().finalize_sql(with_otel_id_filter)
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
    id_datetime_filters_sql: Optional[str] = None


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

    # Apply ID optimization
    id_processor = IdOptimizationProcessor(param_builder, table_alias)
    id_result = apply_processor(id_processor, and_operation)
    id_result_sql = id_processor.finalize_sql(id_result)

    return OptimizationConditions(
        str_filter_opt_sql=string_result_sql,
        id_datetime_filters_sql=id_result_sql,
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
        return f"lower({field_name}) LIKE {_param_slot(param_name, 'String')}"
    else:
        param_name = pb.add_param(like_pattern)
        return f"{field_name} LIKE {_param_slot(param_name, 'String')}"


def _create_like_optimized_eq_condition(
    operation: tsi_query.EqOperation,
    pb: "ParamBuilder",
    table_alias: str,
) -> Optional[str]:
    """Creates a LIKE-optimized condition for equality operations."""
    # Check both sides for field and literal
    field_operand = None
    literal_operand = None

    if isinstance(operation.eq_[0], tsi_query.GetFieldOperator):
        field_operand = operation.eq_[0]
        literal_operand = operation.eq_[1]
    elif isinstance(operation.eq_[1], tsi_query.GetFieldOperator):
        field_operand = operation.eq_[1]
        literal_operand = operation.eq_[0]
    else:
        return None

    # Return if literal isn't a string
    if not isinstance(literal_operand, tsi_query.LiteralOperation) or not isinstance(
        literal_operand.literal_, str
    ):
        return None

    from weave.trace_server.calls_query_builder.calls_query_builder import (
        get_field_by_name,
    )

    field = get_field_by_name(field_operand.get_field_).field
    literal_value = literal_operand.literal_

    if field not in STRING_FIELDS_TO_OPTIMIZE:
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

    if field not in STRING_FIELDS_TO_OPTIMIZE:
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
    if field not in STRING_FIELDS_TO_OPTIMIZE:
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


def _uuidv7_from_timestamp_zeroed(ms_since_epoch: int) -> str:
    """Creates a UUIDv7 from a timestamp in milliseconds since epoch."""
    if not (0 <= ms_since_epoch < 2**48):
        raise ValueError("Timestamp must be a 48-bit integer (ms since epoch).")

    # Split the 48-bit timestamp
    time_low = (ms_since_epoch >> 16) & 0xFFFFFFFF  # First 32 bits
    time_mid = ms_since_epoch & 0xFFFF  # Next 16 bits

    # Set version (7) in high 4 bits, rest zero
    time_hi_and_version = 0x7 << 12  # Version 7 + 12 zero bits

    # Set variant bits (10xx....) and rest zero
    clock_seq_hi_and_reserved = 0x80  # 10xx xxxx
    clock_seq_low = 0x00
    node = 0x000000000000  # 48 bits of zero

    # Create UUID from fields
    uuid_fields = (
        time_low,
        time_mid,
        time_hi_and_version,
        clock_seq_hi_and_reserved,
        clock_seq_low,
        node,
    )
    return str(uuid.UUID(fields=uuid_fields))


def _add_otel_id_filter(table_alias: str, id_str_sql: str) -> str:
    """Adds a filter for OTEL ids to the given filter."""
    non_uuidv7_condition = f"{table_alias}.id <= 'ffffffffffffffff'"
    return f"({non_uuidv7_condition} OR {id_str_sql})"


def _create_datetime_optimization_sql(
    operation: Union[tsi_query.GtOperation, tsi_query.GteOperation],
    pb: "ParamBuilder",
    table_alias: str,
) -> Optional[str]:
    """Creates SQL for datetime optimization using UUIDv7 timestamp filtering.
    This optimization takes advantage of the fact that UUIDv7 includes a timestamp
    in the first 48 bits. For date range filters, we can create a pre-filter
    condition that checks if the ID falls within the expected UUIDv7 range
    for the given date range.

    To account for ids that are not UUIDv7, we explicitly include any ids that are
    < 'ffffffffffffffff', which should allow all OTEL 8 byte ids to pass through.

    We include a buffer time (DATETIME_OPTIMIZATION_BUFFER) to ensure we don't
    miss records due to slight timing differences.
    """
    # Check both sides for field and literal
    field_operand = None
    literal_operand = None

    field1 = (
        operation.gt_[0]
        if isinstance(operation, tsi_query.GtOperation)
        else operation.gte_[0]
    )
    field2 = (
        operation.gt_[1]
        if isinstance(operation, tsi_query.GtOperation)
        else operation.gte_[1]
    )

    if isinstance(field1, tsi_query.GetFieldOperator) and isinstance(
        field2, tsi_query.LiteralOperation
    ):
        field_operand = field1
        literal_operand = field2
    elif isinstance(field2, tsi_query.GetFieldOperator) and isinstance(
        field1, tsi_query.LiteralOperation
    ):
        field_operand = field2
        literal_operand = field1
    else:
        return None

    field_name = field_operand.get_field_
    if field_name not in ("started_at", "ended_at"):
        return None

    literal_value = literal_operand.literal_

    if not literal_value or not isinstance(literal_value, (int, float)):
        return None

    timestamp = int(literal_value * 1_000)

    # Conservative time buffer, includes more data
    timestamp = timestamp - DATETIME_OPTIMIZATION_BUFFER

    try:
        fake_uuid = _uuidv7_from_timestamp_zeroed(timestamp)
    except ValueError:
        # If the timestamp is broken, skip optimizing that condition
        return None

    # Add the condition
    param_name = pb.add_param(fake_uuid)
    return f"({table_alias}.id > {_param_slot(param_name, 'String')})"
