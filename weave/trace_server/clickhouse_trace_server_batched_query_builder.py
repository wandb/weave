import typing


from . import clickhouse_trace_server_batched_schema as schema


from .trace_server_interface_util import (
    WILDCARD_ARTIFACT_VERSION_AND_PATH,
)
from . import trace_server_interface as tsi
from .interface import query as tsi_query


param_builder_count = 0


class ParamBuilder:
    def __init__(self, prefix: typing.Optional[str] = None):
        global param_builder_count
        param_builder_count += 1
        self._params: typing.Dict[str, typing.Any] = {}
        self._prefix = (prefix or f"pb_{param_builder_count}") + "_"

    def add_param(self, param_value: typing.Any) -> str:
        param_name = self._prefix + str(len(self._params))
        self._params[param_name] = param_value
        return param_name

    def get_params(self) -> typing.Dict[str, typing.Any]:
        return {**self._params}


def _python_value_to_ch_type(value: typing.Any) -> str:
    if isinstance(value, str):
        return "String"
    elif isinstance(value, int):
        return "UInt64"
    elif isinstance(value, float):
        return "Float64"
    elif isinstance(value, bool):
        return "UInt8"
    elif value is None:
        return "Nullable(String)"
    else:
        raise ValueError(f"Unknown value type: {value}")


def _param_slot(param_name: str, param_type: str) -> str:
    return f"{{{param_name}:{param_type}}}"


def _quote_json_path(path: str) -> str:
    parts = path.split(".")
    parts_final = []
    for part in parts:
        try:
            int(part)
            parts_final.append("[" + part + "]")
        except ValueError:
            parts_final.append('."' + part + '"')
    return "$" + "".join(parts_final)


def transform_external_calls_field_to_internal_calls_field(
    field: str,
    cast: typing.Optional[str] = None,
    param_builder: typing.Optional[ParamBuilder] = None,
) -> tuple[str, ParamBuilder, set[str]]:
    param_builder = param_builder or ParamBuilder()
    raw_fields_used = set()
    json_path = None
    if field == "inputs" or field.startswith("inputs."):
        if field == "inputs":
            json_path = "$"
        else:
            json_path = _quote_json_path(field[len("inputs.") :])
        field = "inputs_dump"
    elif field == "output" or field.startswith("output."):
        if field == "output":
            json_path = "$"
        else:
            json_path = _quote_json_path(field[len("output.") :])
        field = "output_dump"
    elif field == "attributes" or field.startswith("attributes."):
        if field == "attributes":
            json_path = "$"
        else:
            json_path = _quote_json_path(field[len("attributes.") :])
        field = "attributes_dump"
    elif field == "summary" or field.startswith("summary."):
        if field == "summary":
            json_path = "$"
        else:
            json_path = _quote_json_path(field[len("summary.") :])
        field = "summary_dump"
    else:
        assert (
            field in schema.all_call_select_columns
        ), f"Invalid order_by field: {field}"

    # validate field
    if field not in schema.all_call_select_columns:
        raise ValueError(f"Unknown field: {field}")

    raw_fields_used.add(field)
    if json_path is not None:
        json_path_param_name = param_builder.add_param(json_path)
        if cast == "exists":
            field = (
                "(JSON_EXISTS(" + field + ", {" + json_path_param_name + ":String}))"
            )
        else:
            method = "toString"
            if cast is not None:
                if cast == "int":
                    method = "toInt64OrNull"
                elif cast == "float":
                    method = "toFloat64OrNull"
                elif cast == "bool":
                    method = "toUInt8OrNull"
                elif cast == "str":
                    method = "toString"
                else:
                    raise ValueError(f"Unknown cast: {cast}")
            field = (
                method
                + "(JSON_VALUE("
                + field
                + ", {"
                + json_path_param_name
                + ":String}))"
            )

    return field, param_builder, raw_fields_used


def process_calls_filter_to_conditions(
    filter: tsi._CallsFilter,
    param_builder: typing.Optional[ParamBuilder] = None,
) -> tuple[list[str], ParamBuilder, set[str]]:
    param_builder = param_builder or ParamBuilder()
    conditions = []
    raw_fields_used = set()

    if filter.op_names:
        # We will build up (0 or 1) + N conditions for the op_version_refs
        # If there are any non-wildcarded names, then we at least have an IN condition
        # If there are any wildcarded names, then we have a LIKE condition for each

        or_conditions: typing.List[str] = []

        non_wildcarded_names: typing.List[str] = []
        wildcarded_names: typing.List[str] = []
        for name in filter.op_names:
            if name.endswith(WILDCARD_ARTIFACT_VERSION_AND_PATH):
                wildcarded_names.append(name)
            else:
                non_wildcarded_names.append(name)

        if non_wildcarded_names:
            or_conditions.append(
                f"op_name IN {_param_slot(param_builder.add_param(non_wildcarded_names), 'Array(String)')}"
            )
            raw_fields_used.add("op_name")

        for name in wildcarded_names:
            like_name = name[: -len(WILDCARD_ARTIFACT_VERSION_AND_PATH)] + ":%"
            or_conditions.append(
                f"op_name LIKE {_param_slot(param_builder.add_param(like_name), 'String')}"
            )
            raw_fields_used.add("op_name")

        if or_conditions:
            conditions.append(combine_conditions(or_conditions, "OR"))

    if filter.input_refs:
        conditions.append(
            f"hasAny(input_refs, {_param_slot(param_builder.add_param(filter.input_refs), 'Array(String)')})"
        )
        raw_fields_used.add("input_refs")

    if filter.output_refs:
        conditions.append(
            f"hasAny(output_refs, {_param_slot(param_builder.add_param(filter.output_refs), 'Array(String)')})"
        )
        raw_fields_used.add("output_refs")

    if filter.parent_ids:
        conditions.append(
            f"parent_id IN {_param_slot(param_builder.add_param(filter.parent_ids), 'Array(String)')}"
        )
        raw_fields_used.add("parent_id")

    if filter.trace_ids:
        conditions.append(
            f"trace_id IN {_param_slot(param_builder.add_param(filter.trace_ids), 'Array(String)')}"
        )
        raw_fields_used.add("trace_id")

    if filter.call_ids:
        conditions.append(
            f"id IN {_param_slot(param_builder.add_param(filter.call_ids), 'Array(String)')}"
        )
        raw_fields_used.add("id")

    if filter.trace_roots_only:
        conditions.append("parent_id IS NULL")
        raw_fields_used.add("parent_id")

    if filter.wb_user_ids:
        conditions.append(
            f"wb_user_id IN {_param_slot(param_builder.add_param(filter.wb_user_ids), 'Array(String)')})"
        )
        raw_fields_used.add("wb_user_id")

    if filter.wb_run_ids:
        conditions.append(
            f"wb_run_id IN {_param_slot(param_builder.add_param(filter.wb_run_ids), 'Array(String)')})"
        )
        raw_fields_used.add("wb_run_id")

    return conditions, param_builder, raw_fields_used


def process_calls_query_to_conditions(
    query: tsi.Query, param_builder: typing.Optional[ParamBuilder] = None
) -> tuple[list[str], ParamBuilder, set[str]]:
    param_builder = param_builder or ParamBuilder()
    conditions = []
    raw_fields_used = set()
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
            lhs_part = process_operand(operation.eq_[0])
            rhs_part = process_operand(operation.eq_[1])
            cond = f"({lhs_part} = {rhs_part})"
        elif isinstance(operation, tsi_query.GtOperation):
            lhs_part = process_operand(operation.gt_[0])
            rhs_part = process_operand(operation.gt_[1])
            cond = f"({lhs_part} > {rhs_part})"
        elif isinstance(operation, tsi_query.GteOperation):
            lhs_part = process_operand(operation.gte_[0])
            rhs_part = process_operand(operation.gte_[1])
            cond = f"({lhs_part} >= {rhs_part})"
        elif isinstance(operation, tsi_query.SubstrOperation):
            lhs_part = process_operand(operation.substr_[0])
            rhs_part = process_operand(operation.substr_[1])
            cond = f"position({lhs_part}, {rhs_part}) > 0"
        else:
            raise ValueError(f"Unknown operation type: {operation}")

        return cond

    def process_operand(operand: tsi_query.Operand) -> str:
        if isinstance(operand, tsi_query.LiteralOperation):
            return _param_slot(
                param_builder.add_param(operand.literal_),  # type: ignore
                _python_value_to_ch_type(operand.literal_),
            )
        elif isinstance(operand, tsi_query.GetFieldOperator):
            (
                field,
                _,
                fields_used,
            ) = transform_external_calls_field_to_internal_calls_field(
                operand.get_field_, None, param_builder
            )
            raw_fields_used.update(fields_used)
            return field
        elif isinstance(operand, tsi_query.ConvertOperation):
            field = process_operand(operand.convert_.input)
            convert_to = operand.convert_.to
            if convert_to == "int":
                method = "toInt64OrNull"
            elif convert_to == "double":
                method = "toFloat64OrNull"
            elif convert_to == "bool":
                method = "toUInt8OrNull"
            elif convert_to == "string":
                method = "toString"
            else:
                raise ValueError(f"Unknown cast: {convert_to}")
            return f"{method}({field})"
        elif isinstance(
            operand,
            (
                tsi_query.AndOperation,
                tsi_query.OrOperation,
                tsi_query.NotOperation,
                tsi_query.EqOperation,
                tsi_query.GtOperation,
                tsi_query.GteOperation,
                tsi_query.SubstrOperation,
            ),
        ):
            return process_operation(operand)
        else:
            raise ValueError(f"Unknown operand type: {operand}")

    filter_cond = process_operation(query.expr_)

    conditions.append(filter_cond)

    return conditions, param_builder, raw_fields_used


def combine_conditions(conditions: typing.List[str], operator: str) -> str:
    if operator not in ("AND", "OR"):
        raise ValueError(f"Invalid operator: {operator}")
    combined = f" {operator} ".join([f"({c})" for c in conditions])
    return f"({combined})"
