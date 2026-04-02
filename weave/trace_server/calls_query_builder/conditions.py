"""Condition processing for the calls query builder.

Converts trace_server_interface Query AST (mongo-style expressions)
into ClickHouse SQL WHERE/HAVING conditions.
"""

from collections.abc import Sequence

from pydantic import BaseModel

from weave.trace_server import ch_sentinel_values
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.fields import (
    DATETIME_COLUMN_FIELDS,
    DISALLOWED_FILTERING_FIELDS,
    CallsMergedAggField,
    CallsMergedDynamicField,
    CallsMergedFeedbackPayloadField,
    CallsMergedField,
    CallsMergedQueueItemField,
    CallsMergedSummaryField,
    get_field_by_name,
)
from weave.trace_server.calls_query_builder.utils import (
    param_slot,
    timestamp_to_datetime_str,
)
from weave.trace_server.errors import InvalidFieldError
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import (
    ParamBuilder,
    clickhouse_cast,
    python_value_to_ch_type,
)
from weave.trace_server.project_version.types import ReadTable


class FilterToConditions(BaseModel):
    conditions: list[str]
    fields_used: list[CallsMergedField]


def _maybe_convert_datetime_operands(
    operands: Sequence["tsi_query.Operand"],
) -> Sequence["tsi_query.Operand"]:
    """Convert numeric literals to datetime strings when compared against DateTime columns.

    When a numeric literal (int/float unix timestamp) is being compared against a
    DateTime column field (started_at, ended_at, deleted_at), convert it to a datetime
    string so ClickHouse can properly use primary key / ORDER BY indexes on DateTime64
    columns.

    Returns a new list of operands with conversions applied, or the original sequence if
    no conversion is needed.

    Examples:
        >>> ops = _maybe_convert_datetime_operands([
        ...     tsi_query.GetFieldOperator(**{"$getField": "started_at"}),
        ...     tsi_query.LiteralOperation(**{"$literal": 1770052073.869}),
        ... ])
        >>> isinstance(ops[1].literal_, str)
        True
    """
    if len(operands) != 2:
        return operands

    field_idx = None
    literal_idx = None

    for i, op in enumerate(operands):
        if (
            isinstance(op, tsi_query.GetFieldOperator)
            and op.get_field_ in DATETIME_COLUMN_FIELDS
        ):
            field_idx = i
        elif isinstance(op, tsi_query.LiteralOperation) and isinstance(
            op.literal_, (int, float)
        ):
            literal_idx = i

    if field_idx is None or literal_idx is None:
        return operands

    # Convert numeric timestamp to datetime string for proper DateTime64 comparison
    timestamp = operands[literal_idx].literal_
    assert isinstance(timestamp, (int, float))
    datetime_str = timestamp_to_datetime_str(timestamp)

    new_operands = list(operands)
    new_operands[literal_idx] = tsi_query.LiteralOperation(**{"$literal": datetime_str})
    return new_operands


def _extract_field_name(operand: "tsi_query.Operand") -> str | None:
    """Extract the top-level field name from a GetFieldOperator, if present."""
    if isinstance(operand, tsi_query.GetFieldOperator):
        return operand.get_field_
    return None


def process_query_to_conditions(
    query: tsi.Query,
    param_builder: ParamBuilder,
    table_alias: str,
    use_agg_fn: bool = True,
    read_table: "ReadTable" = ReadTable.CALLS_MERGED,
) -> FilterToConditions:
    """Converts a Query to a list of conditions for a clickhouse query."""
    conditions = []
    raw_fields_used: dict[str, CallsMergedField] = {}
    use_sentinels = read_table == ReadTable.CALLS_COMPLETE

    # This is the mongo-style query
    def process_operation(operation: tsi_query.Operation) -> str:
        cond = None

        if isinstance(operation, tsi_query.AndOperation):
            if len(operation.and_) == 0:
                raise ValueError("Empty AND operation")
            elif len(operation.and_) == 1:
                return process_operand(operation.and_[0])
            parts = [process_operand(op) for op in operation.and_]
            cond = f"({' AND '.join(parts)})"
        elif isinstance(operation, tsi_query.OrOperation):
            if len(operation.or_) == 0:
                raise ValueError("Empty OR operation")
            elif len(operation.or_) == 1:
                return process_operand(operation.or_[0])
            parts = [process_operand(op) for op in operation.or_]
            cond = f"({' OR '.join(parts)})"
        elif isinstance(operation, tsi_query.NotOperation):
            operand_part = process_operand(operation.not_[0])
            cond = f"(NOT ({operand_part}))"
        elif isinstance(operation, tsi_query.EqOperation):
            ops = _maybe_convert_datetime_operands(operation.eq_)
            lhs_part = process_operand(ops[0])
            if (
                isinstance(ops[1], tsi_query.LiteralOperation)
                and ops[1].literal_ is None
            ):
                # For calls_complete, sentinel fields use equality checks
                # against the sentinel value instead of IS NULL.
                field_name = _extract_field_name(ops[0])
                sentinel = (
                    ch_sentinel_values.get_sentinel_value(field_name)
                    if use_sentinels and field_name
                    else None
                )
                if sentinel is not None:
                    assert field_name is not None
                    sentinel_type = ch_sentinel_values.sentinel_ch_type(field_name)
                    sentinel_slot = param_builder.add(
                        sentinel, param_type=sentinel_type
                    )
                    cond = f"({lhs_part} = {sentinel_slot})"
                else:
                    cond = f"({lhs_part} IS NULL)"
            else:
                rhs_part = process_operand(ops[1])
                cond = f"({lhs_part} = {rhs_part})"
        elif isinstance(operation, tsi_query.GtOperation):
            ops = _maybe_convert_datetime_operands(operation.gt_)
            lhs_part = process_operand(ops[0])
            rhs_part = process_operand(ops[1])
            cond = f"({lhs_part} > {rhs_part})"
        elif isinstance(operation, tsi_query.LtOperation):
            ops = _maybe_convert_datetime_operands(operation.lt_)
            lhs_part = process_operand(ops[0])
            rhs_part = process_operand(ops[1])
            cond = f"({lhs_part} < {rhs_part})"
        elif isinstance(operation, tsi_query.GteOperation):
            ops = _maybe_convert_datetime_operands(operation.gte_)
            lhs_part = process_operand(ops[0])
            rhs_part = process_operand(ops[1])
            cond = f"({lhs_part} >= {rhs_part})"
        elif isinstance(operation, tsi_query.LteOperation):
            ops = _maybe_convert_datetime_operands(operation.lte_)
            lhs_part = process_operand(ops[0])
            rhs_part = process_operand(ops[1])
            cond = f"({lhs_part} <= {rhs_part})"
        elif isinstance(operation, tsi_query.InOperation):
            lhs_part = process_operand(operation.in_[0])
            rhs_part = ",".join(process_operand(op) for op in operation.in_[1])
            cond = f"({lhs_part} IN ({rhs_part}))"
        elif isinstance(operation, tsi_query.ContainsOperation):
            lhs_part = process_operand(operation.contains_.input)
            rhs_part = process_operand(operation.contains_.substr)
            position_operation = "position"
            if operation.contains_.case_insensitive:
                position_operation = "positionCaseInsensitive"
            cond = f"{position_operation}({lhs_part}, {rhs_part}) > 0"
        else:
            raise TypeError(f"Unknown operation type: {operation}")

        return cond

    def process_operand(operand: "tsi_query.Operand") -> str:
        if isinstance(operand, tsi_query.LiteralOperation):
            return param_slot(
                param_builder.add_param(operand.literal_),  # type: ignore
                python_value_to_ch_type(operand.literal_),
            )
        elif isinstance(operand, tsi_query.GetFieldOperator):
            if operand.get_field_ in DISALLOWED_FILTERING_FIELDS:
                raise InvalidFieldError(f"Field {operand.get_field_} is not allowed")

            structured_field = get_field_by_name(operand.get_field_)

            if isinstance(structured_field, CallsMergedSummaryField):
                field = structured_field.as_sql(
                    param_builder,
                    table_alias,
                    use_agg_fn=use_agg_fn,
                    read_table=read_table,
                )
            elif isinstance(
                structured_field,
                (
                    CallsMergedDynamicField,
                    CallsMergedAggField,
                    CallsMergedFeedbackPayloadField,
                    CallsMergedQueueItemField,
                ),
            ):
                field = structured_field.as_sql(
                    param_builder, table_alias, use_agg_fn=use_agg_fn
                )
            else:
                field = structured_field.as_sql(param_builder, table_alias)
            raw_fields_used[structured_field.field] = structured_field
            return field
        elif isinstance(operand, tsi_query.ConvertOperation):
            field = process_operand(operand.convert_.input)
            return clickhouse_cast(field, operand.convert_.to)
        elif isinstance(
            operand,
            (
                tsi_query.AndOperation,
                tsi_query.OrOperation,
                tsi_query.NotOperation,
                tsi_query.EqOperation,
                tsi_query.GtOperation,
                tsi_query.LtOperation,
                tsi_query.GteOperation,
                tsi_query.LteOperation,
                tsi_query.InOperation,
                tsi_query.ContainsOperation,
            ),
        ):
            return process_operation(operand)
        else:
            raise TypeError(f"Unknown operand type: {operand}")

    filter_cond = process_operation(query.expr_)

    conditions.append(filter_cond)

    return FilterToConditions(
        conditions=conditions, fields_used=list(raw_fields_used.values())
    )
