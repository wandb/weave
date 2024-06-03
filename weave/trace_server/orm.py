"""
A lightweight ORM layer for ClickHouse. Allows building up SQL queries in a safe way.
"""

import datetime
import json
import typing
from typing_extensions import TypeAlias

from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.summary import QuerySummary

from . import trace_server_interface as tsi
from .errors import RequestTooLarge
from .interface import query as tsi_query


param_builder_count = 0


class ParamBuilder:
    """ParamBuilder helps with the construction of parameterized clickhouse queries.
    It is used in a number of functions/routines that build queries to ensure that
    the queries are parameterized and safe from injection attacks. Specifically, a caller
    would use it as follows:

    ```
    pb = ParamBuilder()
    param_name = pb.add_param("some_value")
    query = f"SELECT * FROM some_table WHERE some_column = {{{param_name}:String}}"
    parameters = pb.get_params()
    # Execute the query with the parameters
    ```

    With queries that have many construction phases, it is recommended to use the
    same ParamBuilder instance to ensure that the parameter names are unique across
    the query.
    """

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


Value: TypeAlias = typing.Optional[
    typing.Union[str, float, datetime.datetime, list[str], list[float]]
]
Row: TypeAlias = dict[str, Value]


ColumnType = typing.Literal[
    "string",
    "datetime",
    "json",  # Represented as string in ClickHouse
]


class Column:
    # This is the name of the column from a user perspective.
    name: str

    # If specified, this is the name of the column in the database.
    # Normally we just use name, but sometimes we have an internal convention like
    # a "_dump" suffix that we don't want to expose in the API.
    db_name: typing.Optional[str]
    type: ColumnType
    nullable: bool
    # TODO: Description?
    # TODO: Default?

    def __init__(
        self,
        name: str,
        type: ColumnType,
        nullable: bool = False,
        db_name: typing.Optional[str] = None,
    ) -> None:
        self.name = name
        self.db_name = db_name
        self.type = type
        self.nullable = nullable

    def dbname(self) -> str:
        return self.db_name or self.name


Columns = list[Column]


class Table:
    name: str
    cols: Columns

    def __init__(self, name: str, cols: typing.Optional[Columns] = None):
        self.name = name
        self.cols = cols or []

    def select(self) -> "Select":
        return Select(self)

    def insert(self, row: typing.Optional[Row] = None) -> "Insert":
        ins = Insert(self)
        if row:
            ins.row(row)
        return ins

    def purge(self) -> "Select":
        return Select(self, action="DELETE")

    def truncate(self, client: CHClient) -> None:
        statement = f"TRUNCATE TABLE {self.name}"
        res = client.query(statement)


Action = typing.Literal["SELECT", "DELETE"]


class Select:
    table: Table
    all_columns: list[str]
    json_columns: list[str]
    col_types: dict[str, ColumnType]
    db_names: dict[str, str]

    action: Action
    param_builder: ParamBuilder

    _project_id: typing.Optional[str]
    _fields: typing.Optional[list[str]]
    _query: typing.Optional[tsi.Query]
    _order_by: typing.Optional[typing.List[tsi._SortBy]]
    _limit: typing.Optional[int]
    _offset: typing.Optional[int]

    def __init__(self, table: Table, action: Action = "SELECT"):
        self.table = table
        self.action = action
        self.all_columns = [c.dbname() for c in table.cols]
        self.json_columns = [c.name for c in table.cols if c.type == "json"]
        self.col_types = {c.name: c.type for c in table.cols}
        self.db_names = {c.name: c.db_name for c in table.cols if c.db_name}

        self.param_builder = ParamBuilder()

        self._project_id = None
        self._fields = []
        self._query = None
        self._order_by = None
        self._limit = None
        self._offset = None

    def project_id(self, project_id: typing.Optional[str]) -> "Select":
        self._project_id = project_id
        return self

    def fields(self, fields: typing.Optional[list[str]]) -> "Select":
        self._fields = fields
        return self

    def where(self, query: typing.Optional[tsi.Query]) -> "Select":
        self._query = query
        return self

    def order_by(self, order_by: typing.Optional[typing.List[tsi._SortBy]]) -> "Select":
        if order_by:
            for o in order_by:
                assert o.direction in (
                    "ASC",
                    "DESC",
                    "asc",
                    "desc",
                ), f"Invalid order_by direction: {o.direction}"
        self._order_by = order_by
        return self

    def limit(self, limit: typing.Optional[int]) -> "Select":
        if limit is not None and limit < 0:
            raise ValueError("Limit must be non-negative")
        self._limit = limit
        return self

    def offset(self, offset: typing.Optional[int]) -> "Select":
        if offset is not None and offset < 0:
            raise ValueError("Offset must be non-negative")
        self._offset = offset
        return self

    def prepare(self) -> typing.Tuple[str, typing.Dict[str, typing.Any], list[str]]:
        sql = ""
        if self.action == "SELECT":
            fieldnames = self._fields or self.all_columns
            internal_fields = [
                _transform_external_field_to_internal_field(
                    f,
                    self.all_columns,
                    self.json_columns,
                    param_builder=self.param_builder,
                )[0]
                for f in fieldnames
            ]
            joined_fields = ", ".join(internal_fields)
            sql = f"SELECT {joined_fields}\n"
        elif self.action == "DELETE":
            fieldnames = []
            sql = "DELETE "

        sql += f"FROM {self.table.name}"

        name_project_id = self.param_builder.add_param(self._project_id)
        conditions = [f"project_id = {{{name_project_id}:String}}"]
        if self._query:
            query_conds, fields_used = _process_query_to_conditions(
                self._query, self.all_columns, self.json_columns, self.param_builder
            )
            conditions.extend(query_conds)

        joined = _combine_conditions(conditions, "AND")
        if joined:
            sql += f"\nWHERE {joined}"

        if self._order_by is not None:
            order_parts = []
            for clause in self._order_by:
                field = clause.field
                direction = clause.direction
                # For each order by field, if it is a dynamic field, we generate
                # 3 order by terms: one for existence, one for float casting, and one for string casting.
                # The effect of this is that we will have stable sorting for nullable, mixed-type fields.
                if _is_dynamic_field(field, self.json_columns):
                    # Prioritize existence, then cast to float, then str
                    options = [
                        ("exists", "desc"),
                        ("float", direction),
                        ("str", direction),
                    ]
                else:
                    options = [(field, direction)]

                # For each option, build the order by term
                for cast, direct in options:
                    # Future refactor: this entire section should be moved into its own helper
                    # method and hoisted out of this function
                    (inner_field, _, _,) = _transform_external_field_to_internal_field(
                        field,
                        self.all_columns,
                        self.json_columns,
                        cast,
                        param_builder=self.param_builder,
                    )
                    order_parts.append(f"{inner_field} {direct}")
            order_by_part = ", ".join(order_parts)
            if order_by_part:
                sql += f"\nORDER BY {order_by_part}"

        if self._limit is not None:
            name_limit = self.param_builder.add_param(self._limit)
            sql += f"\nLIMIT {{{name_limit}:UInt64}}"
        if self._offset is not None:
            name_offset = self.param_builder.add_param(self._offset)
            sql += f"\nOFFSET {{{name_offset}:UInt64}}"

        parameters = self.param_builder.get_params()
        return sql, parameters, fieldnames

    def execute(self, client: CHClient) -> list[Row]:
        """Run the select."""
        sql, parameters, fieldnames = self.prepare()
        res = client.query(sql, parameters=parameters)
        col_types = {c.name: c.type for c in self.table.cols}
        dicts = []
        for row in res.result_rows:
            d = {}
            for i, field in enumerate(fieldnames):
                if field.endswith("_dump"):
                    field = field[:-5]
                value = row[i]
                if field in col_types and col_types[field] == "json":
                    d[field] = json.loads(value)
                else:
                    d[field] = value
            dicts.append(d)
        return dicts


class Insert:
    table: Table
    dbnames: dict[str, str]
    rows: list[Row]

    def __init__(self, table: Table) -> None:
        self.table = table
        self.dbnames = {c.name: c.db_name for c in table.cols if c.db_name}
        self.rows = []

    def row(self, row: Row) -> None:
        """Queue a row for insertion."""
        self.rows.append(row)

    def execute(self, client: CHClient) -> None:
        """Insert the queued rows."""
        # TODO: Bring over batch insert capability.
        for row in self.rows:
            column_names = []
            for key in row.keys():
                column_names.append(self.dbnames.get(key, key))
            data = [list(row.values())]
            self._insert(client, self.table.name, data, column_names)

    def _insert(
        self,
        ch_client: CHClient,
        table: str,
        data: typing.Sequence[typing.Sequence[typing.Any]],
        column_names: list[str],
        settings: typing.Optional[dict[str, typing.Any]] = None,
    ) -> QuerySummary:
        try:
            return ch_client.insert(
                table, data=data, column_names=column_names, settings=settings
            )
        except ValueError as e:
            if "negative shift count" in str(e):
                # clickhouse_connect raises a weird error message like
                # File "/Users/shawn/.pyenv/versions/3.10.13/envs/weave-public-editable/lib/python3.10/site-packages/clickhouse_connect/driver/
                # │insert.py", line 120, in _calc_block_size
                # │    return 1 << (21 - int(log(row_size, 2)))
                # │ValueError: negative shift count
                # when we try to insert something that's too large.
                raise RequestTooLarge("Could not insert record")
            raise


def _combine_conditions(conditions: typing.List[str], operator: str) -> str:
    if operator not in ("AND", "OR"):
        raise ValueError(f"Invalid operator: {operator}")
    if not conditions:
        return ""
    if len(conditions) == 1:
        return conditions[0]
    combined = f" {operator} ".join(f"({c})" for c in conditions)
    return f"({combined})"


def _python_value_to_ch_type(value: typing.Any) -> str:
    """Helper function to convert python types to clickhouse types."""
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
    """Helper function to create a parameter slot for a clickhouse query."""
    return f"{{{param_name}:{param_type}}}"


def _quote_json_path(path: str) -> str:
    """Helper function to quote a json path for use in a clickhouse query. Moreover,
    this converts index operations from dot notation (conforms to Mongo) to bracket
    notation (required by clickhouse)

    See comments on `GetFieldOperator` for current limitations
    """
    parts = path.split(".")
    parts_final = []
    for part in parts:
        try:
            int(part)
            parts_final.append("[" + part + "]")
        except ValueError:
            parts_final.append('."' + part + '"')
    return "$" + "".join(parts_final)


def _transform_external_field_to_internal_field(
    field: str,
    all_columns: typing.Sequence[str],
    json_columns: typing.Sequence[str],
    cast: typing.Optional[str] = None,
    param_builder: typing.Optional[ParamBuilder] = None,
) -> tuple[str, ParamBuilder, set[str]]:
    """Transforms a request for a dot-notation field to a clickhouse field."""
    param_builder = param_builder or ParamBuilder()
    raw_fields_used = set()
    json_path = None
    for prefix in json_columns:
        if field == prefix or field.startswith(prefix + "."):
            if field == prefix:
                json_path = "$"
            else:
                json_path = _quote_json_path(field[len(prefix + ".") :])
            field = prefix + "_dump"
            break

    # validate field
    if field not in all_columns:
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


def _process_query_to_conditions(
    query: tsi.Query,
    all_columns: typing.Sequence[str],
    json_columns: typing.Sequence[str],
    param_builder: typing.Optional[ParamBuilder] = None,
) -> tuple[list[str], set[str]]:
    """Converts a Query to a list of conditions for a clickhouse query."""
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
        elif isinstance(operation, tsi_query.ContainsOperation):
            lhs_part = process_operand(operation.contains_.input)
            rhs_part = process_operand(operation.contains_.substr)
            position_operation = "position"
            if operation.contains_.case_insensitive:
                position_operation = "positionCaseInsensitive"
            cond = f"{position_operation}({lhs_part}, {rhs_part}) > 0"
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
            (field, _, fields_used,) = _transform_external_field_to_internal_field(
                operand.get_field_, all_columns, json_columns, None, param_builder
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
                tsi_query.ContainsOperation,
            ),
        ):
            return process_operation(operand)
        else:
            raise ValueError(f"Unknown operand type: {operand}")

    filter_cond = process_operation(query.expr_)

    conditions.append(filter_cond)

    return conditions, raw_fields_used


def _is_dynamic_field(field: str, json_columns: list[str]) -> bool:
    """Dynamic fields are fields that are arbitrary values produced by the user."""
    if field in json_columns:
        return True
    for col in json_columns:
        if field.startswith(col + "."):
            return True
    return False
