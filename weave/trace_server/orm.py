"""
A lightweight ORM layer for ClickHouse/SQLite.
Abstracts away some of their differences and allows building up SQL queries in a safe way.
"""

import datetime
import json
import typing

from pydantic import BaseModel
from typing_extensions import TypeAlias

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface import query as tsi_query

DatabaseType = typing.Literal["clickhouse", "sqlite"]


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

    def __init__(
        self,
        prefix: typing.Optional[str] = None,
        database_type: DatabaseType = "clickhouse",
    ):
        global param_builder_count
        param_builder_count += 1
        self._params: dict[str, typing.Any] = {}
        self._prefix = (prefix or f"pb_{param_builder_count}") + "_"
        self._database_type = database_type
        self._param_to_name: dict[typing.Any, str] = {}

    def add_param(self, param_value: typing.Any) -> str:
        param_name = self._prefix + str(len(self._params))

        # Only attempt caching for hashable values
        if isinstance(param_value, typing.Hashable):
            if param_value in self._param_to_name:
                return self._param_to_name[param_value]
            self._param_to_name[param_value] = param_name

        # For non-hashable values, just generate a new param without caching
        self._params[param_name] = param_value
        return param_name

    def add(
        self,
        param_value: typing.Any,
        param_name: typing.Optional[str] = None,
        param_type: typing.Optional[str] = None,
    ) -> str:
        """Returns the placeholder for the target database type.

        e.g. SQLite -> :limit
        e.g. ClickHouse -> {limit:UInt64}
        """
        param_name = param_name or self._prefix + str(len(self._params))
        self._params[param_name] = param_value
        if self._database_type == "clickhouse":
            ptype = param_type or python_value_to_ch_type(param_value)
            return f"{{{param_name}:{ptype}}}"
        return ":" + param_name

    def get_params(self) -> dict[str, typing.Any]:
        return {**self._params}


Value: TypeAlias = typing.Optional[
    typing.Union[
        str, float, datetime.datetime, list[str], list[float], dict[str, typing.Any]
    ]
]
Row: TypeAlias = dict[str, Value]
Rows: TypeAlias = list[Row]


ColumnType = typing.Literal[
    "string",
    "datetime",
    "json",  # Represented as string in ClickHouse
    "float",
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

    def create_sql(self) -> str:
        sql_type = "TEXT"
        sql = f"{self.dbname()} {sql_type}"
        return sql


Columns = list[Column]


class Table:
    name: str
    cols: Columns

    # Fields derived from cols
    col_types: dict[str, ColumnType]
    json_cols: list[str]

    def __init__(self, name: str, cols: typing.Optional[Columns] = None):
        self.name = name
        self.cols = cols or []
        self.col_types = {c.name: c.type for c in self.cols}
        self.json_cols = [c.name for c in self.cols if c.type == "json"]

    def create_sql(self) -> str:
        sql = f"CREATE TABLE IF NOT EXISTS {self.name} (\n"
        sql += ",\n".join("    " + col.create_sql() for col in self.cols)
        sql += "\n)"
        return sql

    def drop_sql(self) -> str:
        return f"DROP TABLE IF EXISTS {self.name}"

    def select(self) -> "Select":
        return Select(self)

    def insert(self, row: typing.Optional[Row] = None) -> "Insert":
        ins = Insert(self)
        if row:
            ins.row(row)
        return ins

    def purge(self) -> "Select":
        return Select(self, action="DELETE")

    def truncate_sql(self, database_type: DatabaseType) -> str:
        if database_type == "clickhouse":
            return f"TRUNCATE TABLE {self.name}"
        if database_type == "sqlite":
            return f"DELETE FROM {self.name}"

    def tuple_to_row(self, tup: tuple, fields: list[str]) -> Row:
        d = {}
        for i, field in enumerate(fields):
            if field.endswith("_dump"):
                field = field[:-5]
            value = tup[i]
            if field in self.col_types and self.col_types[field] == "json":
                d[field] = json.loads(value)
            else:
                d[field] = value
        return d

    def tuples_to_rows(self, tuples: list[tuple], fields: list[str]) -> Rows:
        rows = []
        for t in tuples:
            rows.append(self.tuple_to_row(t, fields))
        return rows


Action = typing.Literal["SELECT", "DELETE"]


class PreparedSelect(BaseModel):
    sql: str
    parameters: dict[str, typing.Any]
    fields: list[str]


class Join:
    join_type: typing.Optional[str]
    table: Table
    query: tsi.Query

    def __init__(
        self, table: Table, query: tsi.Query, join_type: typing.Optional[str] = None
    ):
        self.join_type = join_type
        self.table = table
        self.query = query


class Select:
    table: Table
    all_columns: list[str]
    joins: list[Join]

    action: Action

    _project_id: typing.Optional[str]
    _fields: typing.Optional[list[str]]
    _query: typing.Optional[tsi.Query]
    _order_by: typing.Optional[list[tsi.SortBy]]
    _limit: typing.Optional[int]
    _offset: typing.Optional[int]
    _group_by: typing.Optional[list[str]]

    def __init__(self, table: Table, action: Action = "SELECT"):
        self.table = table
        self.action = action
        self.all_columns = [c.dbname() for c in table.cols]
        self.joins = []

        self._project_id = None
        self._fields = []
        self._query = None
        self._order_by = None
        self._limit = None
        self._offset = None
        self._group_by = None

    def join(
        self, table: Table, query: tsi.Query, join_type: typing.Optional[str] = None
    ) -> "Select":
        self.joins.append(Join(table, query, join_type))
        for col in table.cols:
            self.all_columns.append(col.dbname())
        return self

    def project_id(self, project_id: typing.Optional[str]) -> "Select":
        self._project_id = project_id
        return self

    def fields(self, fields: typing.Optional[list[str]]) -> "Select":
        self._fields = fields
        return self

    def where(self, query: typing.Optional[tsi.Query]) -> "Select":
        self._query = query
        return self

    def order_by(self, order_by: typing.Optional[list[tsi.SortBy]]) -> "Select":
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

    def group_by(self, fields: typing.Optional[list[str]]) -> "Select":
        self._group_by = fields
        return self

    def prepare(
        self,
        database_type: DatabaseType,
        param_builder: typing.Optional[ParamBuilder] = None,
    ) -> PreparedSelect:
        param_builder = param_builder or ParamBuilder(None, database_type)
        assert database_type == param_builder._database_type

        sql = ""
        if self.action == "SELECT":
            fieldnames = self._fields or self.all_columns
            internal_fields = [
                _transform_external_field_to_internal_field(
                    f,
                    self.all_columns,
                    self.table.json_cols,
                    param_builder=param_builder,
                )[0]
                for f in fieldnames
            ]
            joined_fields = ", ".join(internal_fields)
            sql = f"SELECT {joined_fields}\n"
        elif self.action == "DELETE":
            fieldnames = []
            sql = "DELETE "

        sql += f"FROM {self.table.name}"

        # Handle joins
        # Returns {join type} JOIN {table name} ON {join condition}
        for j in self.joins:
            query_conds, fields_used = _process_query_to_conditions(
                j.query, self.all_columns, self.table.json_cols, param_builder
            )
            joined = combine_conditions(query_conds, "AND")
            sql += f"\n{j.join_type + ' ' if j.join_type else ''}JOIN {j.table.name} ON {joined}"

        conditions = []
        if self._project_id:
            param_project_id = param_builder.add(
                self._project_id, "project_id", "String"
            )
            conditions = [f"project_id = {param_project_id}"]
        if self._query:
            query_conds, fields_used = _process_query_to_conditions(
                self._query, self.all_columns, self.table.json_cols, param_builder
            )
            conditions.extend(query_conds)

        joined = combine_conditions(conditions, "AND")
        if joined:
            sql += f"\nWHERE {joined}"

        if self._group_by is not None:
            internal_fields = [
                _transform_external_field_to_internal_field(
                    f,
                    self.all_columns,
                    self.table.json_cols,
                    param_builder=param_builder,
                )[0]
                for f in self._group_by
            ]
            joined_fields = ", ".join(internal_fields)
            sql += f"\nGROUP BY {joined_fields}"

        if self._order_by is not None:
            order_parts = []
            for clause in self._order_by:
                field = clause.field
                direction = clause.direction
                # For each order by field, if it is a dynamic field, we generate
                # 3 order by terms: one for existence, one for float casting, and one for string casting.
                # The effect of this is that we will have stable sorting for nullable, mixed-type fields.
                if _is_dynamic_field(field, self.table.json_cols):
                    # Prioritize existence, then cast to double, then str
                    options = [
                        ("exists", "desc"),
                        ("double", direction),
                        ("string", direction),
                    ]
                else:
                    options = [(field, direction)]

                # For each option, build the order by term
                for cast, direct in options:
                    # Future refactor: this entire section should be moved into its own helper
                    # method and hoisted out of this function
                    (
                        inner_field,
                        _,
                        _,
                    ) = _transform_external_field_to_internal_field(
                        field,
                        self.all_columns,
                        self.table.json_cols,
                        cast,
                        param_builder=param_builder,
                    )
                    order_parts.append(f"{inner_field} {direct}")
            order_by_part = ", ".join(order_parts)
            if order_by_part:
                sql += f"\nORDER BY {order_by_part}"

        if self._limit is not None:
            param_limit = param_builder.add(self._limit, "limit", "UInt64")
            sql += f"\nLIMIT {param_limit}"
        if self._offset is not None:
            param_offset = param_builder.add(self._offset, "offset", "UInt64")
            sql += f"\nOFFSET {param_offset}"

        parameters = param_builder.get_params()
        return PreparedSelect(sql=sql, parameters=parameters, fields=fieldnames)


class PreparedInsert(BaseModel):
    sql: str
    column_names: list[str]
    data: typing.Sequence[typing.Sequence[typing.Any]]


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

    def prepare(self, database_type: DatabaseType) -> PreparedInsert:
        if not self.rows:
            raise ValueError("No rows added for insertion")

        # TODO: Do we want to allow different columns per row?
        first_row = self.rows[0]
        given_column_names = first_row.keys()
        column_names = [self.dbnames.get(k, k) for k in given_column_names]

        data = []
        for row in self.rows:
            r: list[typing.Any] = []
            for field in given_column_names:
                if (
                    field in self.table.col_types
                    and self.table.col_types[field] == "json"
                ):
                    r.append(json.dumps(row[field]))
                else:
                    r.append(row[field])
            data.append(r)

        if database_type == "sqlite":
            sql = f"INSERT INTO {self.table.name} (\n    "
            sql += ", ".join(column_names)
            sql += "\n) VALUES (\n    "
            sql += ", ".join("?" for _ in column_names)
            sql += "\n)"
        elif database_type == "clickhouse":
            # We could implement this, but we don't need to given the ClickHouse Python Client API
            sql = ""
        return PreparedInsert(sql=sql, column_names=column_names, data=data)


def combine_conditions(conditions: list[str], operator: str) -> str:
    if operator not in ("AND", "OR"):
        raise ValueError(f"Invalid operator: {operator}")
    conditions = [c for c in conditions if c is not None and c != ""]
    if not conditions:
        return ""
    if len(conditions) == 1:
        return conditions[0]
    combined = f" {operator} ".join(f"({c})" for c in conditions)
    return f"({combined})"


def python_value_to_ch_type(value: typing.Any) -> str:
    """Helper function to convert python types to clickhouse types."""
    if isinstance(value, str):
        return "String"
    elif isinstance(value, bool):
        return "Bool"
    elif isinstance(value, int):
        return "UInt64"
    elif isinstance(value, float):
        return "Float64"
    elif value is None:
        return "Nullable(String)"
    else:
        raise ValueError(f"Unknown value type: {value}")


def clickhouse_cast(
    inner_sql: str, cast: typing.Optional[tsi_query.CastTo] = None
) -> str:
    """Helper function to cast a sql expression to a clickhouse type."""
    if cast == None:
        return inner_sql
    if cast == "int":
        return f"toInt64OrNull({inner_sql})"
    elif cast == "double":
        return f"toFloat64OrNull({inner_sql})"
    elif cast == "bool":
        return f"toUInt8OrNull({inner_sql})"
    elif cast == "string":
        return f"toString({inner_sql})"
    elif cast == "exists":
        return f"({inner_sql} IS NOT NULL)"
    else:
        raise ValueError(f"Unknown cast: {cast}")


def quote_json_path(path: str) -> str:
    """Helper function to quote a json path for use in a clickhouse query. Moreover,
    this converts index operations from dot notation (conforms to Mongo) to bracket
    notation (required by clickhouse)

    See comments on `GetFieldOperator` for current limitations
    """
    parts = path.split(".")
    return quote_json_path_parts(parts)


def quote_json_path_parts(parts: list[str]) -> str:
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
        if field == prefix:
            field = prefix + "_dump"
        elif field.startswith(prefix + "."):
            json_path = quote_json_path(field[len(prefix + ".") :])
            field = prefix + "_dump"

    # pops of table_prefix
    # necessary for joins, allows table1.field1 and table2.field2
    table_prefix = None
    unprefixed_field = field
    if "." in field:
        table_prefix, field = field.split(".", 1)

    # validate field
    if (
        field not in all_columns
        and field != "*"
        and field.lower() != "count(*)"
        and not any(
            # Checks that a column is in the field, allows prefixed columns to be used
            substr in unprefixed_field.lower()
            for substr in all_columns
        )
    ):
        raise ValueError(f"Unknown field: {field}")

    raw_fields_used.add(unprefixed_field)
    if json_path is not None:
        json_path_param = param_builder.add(json_path, None, "String")
        if cast == "exists":
            field = "(JSON_EXISTS(" + field + ", " + json_path_param + "))"
        else:
            is_sqlite = param_builder._database_type == "sqlite"
            json_func = "json_extract(" if is_sqlite else "JSON_VALUE("
            field = json_func + field + ", " + json_path_param + ")"
            if not is_sqlite:
                field = clickhouse_cast(field, cast or "string")  # type: ignore

    if table_prefix:
        field = f"{table_prefix}.{field}"

    return field, param_builder, raw_fields_used


def _process_query_to_conditions(
    query: tsi.Query,
    all_columns: typing.Sequence[str],
    json_columns: typing.Sequence[str],
    param_builder: typing.Optional[ParamBuilder] = None,
) -> tuple[list[str], set[str]]:
    """Converts a Query to a list of conditions for a clickhouse query."""
    pb = param_builder or ParamBuilder()
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

    def process_operand(operand: tsi_query.Operand) -> str:
        if isinstance(operand, tsi_query.LiteralOperation):
            return pb.add(
                operand.literal_, None, python_value_to_ch_type(operand.literal_)
            )
        elif isinstance(operand, tsi_query.GetFieldOperator):
            (
                field,
                _,
                fields_used,
            ) = _transform_external_field_to_internal_field(
                operand.get_field_, all_columns, json_columns, None, pb
            )
            raw_fields_used.update(fields_used)
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
                tsi_query.GteOperation,
                tsi_query.InOperation,
                tsi_query.ContainsOperation,
            ),
        ):
            return process_operation(operand)
        else:
            raise TypeError(f"Unknown operand type: {operand}")

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
