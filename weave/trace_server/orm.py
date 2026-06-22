"""A lightweight ORM layer for ClickHouse.
Allows building up SQL queries in a safe way.
"""

import datetime
import json
import re
from collections.abc import Callable, Collection, Hashable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.common_interface import SortBy
from weave.trace_server.interface import query as tsi_query

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
        prefix: str | None = None,
    ):
        global param_builder_count  # noqa: PLW0603
        param_builder_count += 1
        self._params: dict[str, Any] = {}
        self._prefix = (prefix or f"pb_{param_builder_count}") + "_"
        self._param_to_name: dict[Any, str] = {}

    def add_param(self, param_value: Any) -> str:
        param_name = self._prefix + str(len(self._params))

        # Only attempt caching for hashable values
        if isinstance(param_value, Hashable):
            if param_value in self._param_to_name:
                return self._param_to_name[param_value]
            self._param_to_name[param_value] = param_name

        # For non-hashable values, just generate a new param without caching
        self._params[param_name] = param_value
        return param_name

    def add(
        self,
        param_value: Any,
        param_name: str | None = None,
        param_type: str | None = None,
    ) -> str:
        """Returns the ClickHouse placeholder, e.g. {limit:UInt64}."""
        param_name = param_name or self._prefix + str(len(self._params))
        self._params[param_name] = param_value
        ptype = param_type or python_value_to_ch_type(param_value)
        return f"{{{param_name}:{ptype}}}"

    def get_params(self) -> dict[str, Any]:
        return {**self._params}


Value: TypeAlias = (
    str | float | datetime.datetime | list[str] | list[float] | dict[str, Any] | None
)
Row: TypeAlias = dict[str, Value]
Rows: TypeAlias = list[Row]


ColumnType = Literal[
    "string",
    "datetime",
    "json",  # Represented as string in ClickHouse
    "float",
    "array_string",  # Array(String)
    "map_string_string",  # Map(String, String)
    "map_string_float",  # Map(String, Float64)
]


class Column:
    # This is the name of the column from a user perspective.
    name: str

    # If specified, this is the name of the column in the database.
    # Normally we just use name, but sometimes we have an internal convention like
    # a "_dump" suffix that we don't want to expose in the API.
    db_name: str | None
    type: ColumnType
    nullable: bool
    # TODO: Description?
    # TODO: Default?

    def __init__(
        self,
        name: str,
        type: ColumnType,
        nullable: bool = False,
        db_name: str | None = None,
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

    # Fields derived from cols
    col_types: dict[str, ColumnType]
    json_cols: list[str]
    datetime_cols: list[str]
    array_string_cols: list[str]
    map_string_cols: list[str]
    map_float_cols: list[str]

    def __init__(self, name: str, cols: Columns | None = None):
        self.name = name
        self.cols = cols or []
        self.col_types = {c.name: c.type for c in self.cols}
        self.json_cols = [c.name for c in self.cols if c.type == "json"]
        self.datetime_cols = [c.name for c in self.cols if c.type == "datetime"]
        self.array_string_cols = [c.name for c in self.cols if c.type == "array_string"]
        self.map_string_cols = [
            c.name for c in self.cols if c.type == "map_string_string"
        ]
        self.map_float_cols = [
            c.name for c in self.cols if c.type == "map_string_float"
        ]

    def select(self) -> "Select":
        return Select(self)

    def insert(self, row: Row | None = None) -> "Insert":
        ins = Insert(self)
        if row:
            ins.row(row)
        return ins

    def purge(self) -> "Select":
        return Select(self, action="DELETE")

    def tuple_to_row(self, tup: tuple, fields: list[str]) -> Row:
        d = {}
        for i, field in enumerate(fields):
            normalized_field = field[:-5] if field.endswith("_dump") else field
            value = tup[i]
            col_type = self.col_types.get(normalized_field)
            if col_type == "json":
                d[normalized_field] = json.loads(value)
            else:
                # The ClickHouse driver returns Array/Map columns as native
                # list/dict already.
                d[normalized_field] = value
        return d

    def tuples_to_rows(self, tuples: list[tuple], fields: list[str]) -> Rows:
        rows = []
        for t in tuples:
            rows.append(self.tuple_to_row(t, fields))
        return rows


Action = Literal["SELECT", "DELETE"]


@dataclass(slots=True)
class PreparedSelect:
    sql: str
    parameters: dict[str, Any]
    fields: list[str]


@dataclass
class Join:
    table: Table
    query: tsi.Query
    join_type: str | None


class Select:
    table: Table
    all_columns: list[str]
    datetime_columns: list[str]
    joins: list[Join]

    action: Action

    _project_id: str | None
    # Fields from the user that must be transformed to internal field names
    # like "inputs.my_field" or "payload.value"
    _fields: list[str] | None
    # Fields that we have constructed internally, like cost query fields
    _raw_sql_fields: list[str] | None
    _query: tsi.Query | None
    _order_by: list[SortBy] | None
    _limit: int | None
    _offset: int | None
    _group_by: list[str] | None

    def __init__(self, table: Table, action: Action = "SELECT"):
        self.table = table
        self.action = action
        self.all_columns = [c.dbname() for c in table.cols]
        self.datetime_columns = list(table.datetime_cols)
        self.joins = []

        self._project_id = None
        self._fields = []
        self._raw_sql_fields = []
        self._query = None
        self._order_by = None
        self._limit = None
        self._offset = None
        self._group_by = None

    def join(
        self, table: Table, query: tsi.Query, join_type: str | None = None
    ) -> "Select":
        self.joins.append(Join(table, query, join_type))
        for col in table.cols:
            self.all_columns.append(col.dbname())
        self.datetime_columns.extend(table.datetime_cols)
        return self

    def project_id(self, project_id: str | None) -> "Select":
        self._project_id = project_id
        return self

    def fields(self, fields: list[str] | None) -> "Select":
        self._fields = fields
        return self

    def raw_sql_fields(self, raw_fields: list[str] | None) -> "Select":
        """Add raw SQL expressions that don't need external-to-internal field transformation.

        Example: fields like cost query fields that are aggregations and custom-defined

        Using raw_sql_fields cirucumvents some basic field validation, do not use
           user-controlled fields without handling validation before adding.
        """
        self._raw_sql_fields = raw_fields or []
        return self

    def where(self, query: tsi.Query | None) -> "Select":
        self._query = query
        return self

    def order_by(self, order_by: list[SortBy] | None) -> "Select":
        if order_by:
            for o in order_by:
                assert o.direction in {
                    "ASC",
                    "DESC",
                    "asc",
                    "desc",
                }, f"Invalid order_by direction: {o.direction}"
        self._order_by = order_by
        return self

    def limit(self, limit: int | None) -> "Select":
        if limit is not None and limit < 0:
            raise ValueError("Limit must be non-negative")
        self._limit = limit
        return self

    def offset(self, offset: int | None) -> "Select":
        if offset is not None and offset < 0:
            raise ValueError("Offset must be non-negative")
        self._offset = offset
        return self

    def group_by(self, fields: list[str] | None) -> "Select":
        self._group_by = fields
        return self

    def prepare(
        self,
        param_builder: ParamBuilder | None = None,
        table_name: str | None = None,
        cluster_name: str | None = None,
    ) -> PreparedSelect:
        """`table_name` overrides only the FROM (a same-schema physical variant like `<t>_local`), not joins."""
        param_builder = param_builder or ParamBuilder()

        sql = ""
        if self.action == "SELECT":
            fieldnames = self._fields or self.all_columns
            internal_fields = [
                _transform_external_field_to_internal_field(
                    f,
                    all_columns=self.all_columns,
                    json_columns=self.table.json_cols,
                    map_string_columns=self.table.map_string_cols,
                    map_float_columns=self.table.map_float_cols,
                    param_builder=param_builder,
                )[0]
                for f in fieldnames
            ]
            # Add raw SQL fields without transformation
            if self._raw_sql_fields:
                internal_fields.extend(self._raw_sql_fields)
            joined_fields = ", ".join(internal_fields)
            sql = f"SELECT {joined_fields}\n"
        elif self.action == "DELETE":
            fieldnames = []
            sql = "DELETE "

        sql += f"FROM {_format_table_name_with_cluster(table_name or self.table.name, cluster_name)}"

        # Handle joins
        # Returns {join type} JOIN {table name} ON {join condition}
        for j in self.joins:
            query_conds, fields_used = _process_query_to_conditions(
                j.query,
                all_columns=self.all_columns,
                json_columns=self.table.json_cols,
                array_string_columns=self.table.array_string_cols,
                map_string_columns=self.table.map_string_cols,
                map_float_columns=self.table.map_float_cols,
                param_builder=param_builder,
                datetime_columns=self.datetime_columns,
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
                self._query,
                all_columns=self.all_columns,
                json_columns=self.table.json_cols,
                array_string_columns=self.table.array_string_cols,
                map_string_columns=self.table.map_string_cols,
                map_float_columns=self.table.map_float_cols,
                param_builder=param_builder,
                datetime_columns=self.datetime_columns,
            )
            conditions.extend(query_conds)

        joined = combine_conditions(conditions, "AND")
        if joined:
            sql += f"\nWHERE {joined}"

        if self._group_by is not None:
            internal_fields = [
                _transform_external_field_to_internal_field(
                    f,
                    all_columns=self.all_columns,
                    json_columns=self.table.json_cols,
                    map_string_columns=self.table.map_string_cols,
                    map_float_columns=self.table.map_float_cols,
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
                options: list[tuple[tsi_query.CastTo | None, str]]
                if _is_dynamic_field(field, self.table.json_cols):
                    # Prioritize existence, then cast to double, then str
                    options = [
                        ("exists", "desc"),
                        ("double", direction),
                        ("string", direction),
                    ]
                else:
                    # Static columns don't need a cast; the function ignores
                    # the param when no JSON/Map extraction is happening.
                    options = [(None, direction)]

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
                        all_columns=self.all_columns,
                        json_columns=self.table.json_cols,
                        map_string_columns=self.table.map_string_cols,
                        map_float_columns=self.table.map_float_cols,
                        cast=cast,
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


def _format_table_name_with_cluster(table_name: str, cluster_name: str | None) -> str:
    """Append `ON CLUSTER {cluster_name}` to a table reference when clustered.

    Callers pass the already-resolved table name (e.g. `<table>_local` in
    distributed mode); this only appends the cluster clause.
    """
    if cluster_name:
        return f"{table_name} ON CLUSTER {cluster_name}"
    return table_name


@dataclass(slots=True)
class PreparedInsert:
    column_names: list[str]
    data: Sequence[Sequence[Any]]


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

    def prepare(self) -> PreparedInsert:
        """Marshal queued rows for the ClickHouse Python client's insert API.

        No SQL is generated; the client takes column names and row data
        directly. The ClickHouse driver accepts native list/dict for
        Array/Map columns, so only JSON columns need encoding.
        """
        if not self.rows:
            raise ValueError("No rows added for insertion")

        # TODO: Do we want to allow different columns per row?
        first_row = self.rows[0]
        given_column_names = first_row.keys()
        column_names = [self.dbnames.get(k, k) for k in given_column_names]

        data = []
        for row in self.rows:
            r: list[Any] = []
            for field in given_column_names:
                col_type = self.table.col_types.get(field)
                if col_type == "json":
                    r.append(json.dumps(row[field]))
                else:
                    r.append(row[field])
            data.append(r)

        return PreparedInsert(column_names=column_names, data=data)


def combine_conditions(conditions: list[str], operator: str) -> str:
    if operator not in {"AND", "OR"}:
        raise ValueError(f"Invalid operator: {operator}")
    conditions = [c for c in conditions if c is not None and c != ""]
    if not conditions:
        return ""
    if len(conditions) == 1:
        return conditions[0]
    combined = f" {operator} ".join(f"({c})" for c in conditions)
    return f"({combined})"


def python_value_to_ch_type(value: Any) -> str:
    """Helper function to convert python types to clickhouse types."""
    if isinstance(value, str):
        return "String"
    elif isinstance(value, bool):
        return "Bool"
    elif isinstance(value, int):
        return "Int64"
    elif isinstance(value, float):
        return "Float64"
    elif isinstance(value, datetime.datetime):
        return "DateTime64(3)"
    elif value is None:
        return "Nullable(String)"
    else:
        raise ValueError(f"Unknown value type: {value}")


def timestamp_to_datetime_str(timestamp: float) -> str:
    """Convert a unix timestamp to a ClickHouse-compatible datetime string.

    Args:
        timestamp (int | float): Unix timestamp in seconds.

    Returns:
        str: Datetime string in the format `YYYY-MM-DD HH:MM:SS.ffffff`,
            matching the precision of ClickHouse `DateTime64(6)` columns.

    Examples:
        >>> timestamp_to_datetime_str(1709251200)
        '2024-03-01 00:00:00.000000'
    """
    return datetime.datetime.fromtimestamp(
        timestamp, tz=datetime.timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S.%f")


def parse_string_to_utc_timestamp(value: str) -> float | None:
    """Parse a string date or datetime into a UTC unix timestamp (seconds).

    Parsing is delegated to `datetime.datetime.fromisoformat`, which accepts
    both date-only strings (`YYYY-MM-DD`, read as midnight) and full ISO-8601
    datetimes. A trailing `Z` / `z` is treated as UTC, and naive datetimes are
    assumed to be UTC wall time. Unparsable strings return `None`.

    Examples:
        >>> parse_string_to_utc_timestamp("2024-03-01")
        1709251200.0
        >>> parse_string_to_utc_timestamp("2024-03-01T12:00:00Z") == parse_string_to_utc_timestamp(
        ...     "2024-03-01T12:00:00+00:00"
        ... )
        True
        >>> parse_string_to_utc_timestamp("not a date") is None
        True
    """
    s = value.strip()
    if not s:
        return None
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    else:
        dt = dt.astimezone(datetime.timezone.utc)
    return dt.timestamp()


def datetime_literal_to_timestamp(
    literal: tsi_query.LiteralOperation,
) -> float | None:
    """Resolve a datetime filter literal to a UTC unix timestamp (seconds).

    Single source of truth for the literal shapes a datetime comparison accepts,
    shared by the post-aggregation HAVING (`maybe_convert_datetime_operands`) and
    the `sortable_datetime` pre-filter so the two never diverge. Numeric unix
    timestamps pass through; ISO / `YYYY-MM-DD` strings are parsed; bool (an int
    subclass) and non-scalar / unparsable values return None.
    """
    value = literal.literal_
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return parse_string_to_utc_timestamp(value)
    return None


def clickhouse_cast(inner_sql: str, cast: tsi_query.CastTo | None = None) -> str:
    """Helper function to cast a sql expression to a clickhouse type."""
    if cast is None:
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


def clickhouse_cast_json_value(
    json_value_sql: str, cast: tsi_query.CastTo | None = None
) -> str:
    """Apply a cast to a JSON_VALUE result.

    Identical to `clickhouse_cast` except for `bool`: JSON_VALUE returns the
    literal strings `'true'` / `'false'` for JSON booleans, and
    `toUInt8OrNull` would map both to NULL. The multiIf handles those first
    and falls back to numeric coercion for legacy rows storing 1/0.
    """
    if cast == "bool":
        return (
            f"multiIf({json_value_sql} = 'true', 1, "
            f"{json_value_sql} = 'false', 0, "
            f"toUInt8OrNull({json_value_sql}))"
        )
    return clickhouse_cast(json_value_sql, cast)


def split_escaped_field_path(path: str) -> list[str]:
    r"""Split a field path on dots, respecting backslash-escaped dots.

    This function handles field names that contain literal dots by allowing
    them to be escaped with a backslash. This is necessary because JSON keys
    can contain dots, and we need a way to distinguish between:
    - Nested field access: "output.metrics.run" -> ["output", "metrics", "run"]
    - Field with dot in name: "output.metrics\.run" -> ["output", "metrics.run"]

    Args:
        path: The field path string, potentially with escaped dots

    Returns:
        List of field path segments with escape sequences removed

    Examples:
        >>> split_escaped_field_path("output.metrics.run")
        ['output', 'metrics', 'run']
        >>> split_escaped_field_path("output.a\\.b\\.c.d")
        ['output', 'a.b.c', 'd']
    """
    parts = re.split(r"(?<!\\)\.", path)
    # turn '\.' back into '.' inside each segment
    formd_parts = [p.replace(r"\.", ".") for p in parts]
    return formd_parts


def quote_json_path(path: str) -> str:
    """Helper function to quote a json path for use in a clickhouse query. Moreover,
    this converts index operations from dot notation (conforms to Mongo) to bracket
    notation (required by clickhouse).

    See comments on `GetFieldOperator` for current limitations
    """
    parts = split_escaped_field_path(path)
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
    *,
    all_columns: Sequence[str] = (),
    json_columns: Sequence[str] = (),
    map_string_columns: Sequence[str] = (),
    map_float_columns: Sequence[str] = (),
    cast: tsi_query.CastTo | None = None,
    param_builder: ParamBuilder | None = None,
) -> tuple[str, ParamBuilder, set[str]]:
    """Transforms a request for a dot-notation field to a clickhouse field.

    For Map(String, *) columns, a dotted path like `scorer_ratings._rating_`
    resolves to a typed map access (`col['key']`). Bare references to a map
    column pass through to the column itself.
    """
    param_builder = param_builder or ParamBuilder()
    raw_fields_used = set()
    json_path = None
    map_access_key: str | None = None
    for prefix in (*map_string_columns, *map_float_columns):
        if field == prefix:
            # Bare map column — return as-is and let the caller compare it.
            break
        if field.startswith(prefix + "."):
            map_access_key = field[len(prefix) + 1 :]
            raw_fields_used.add(field)
            field = prefix
            break
    for prefix in json_columns:
        if field == prefix:
            field = prefix + "_dump"
        elif field.startswith(prefix + "."):
            json_path = quote_json_path(field[len(prefix) + 1 :])
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
            # Check if field starts with a valid column name as prefix
            unprefixed_field.lower().startswith(col_name.lower() + ".")
            for col_name in all_columns
        )
    ):
        # add back table prefix when erroring
        if table_prefix:
            field = f"{table_prefix}.{field}"
        raise ValueError(f"Unknown field: {field}")

    raw_fields_used.add(unprefixed_field)
    if map_access_key is not None:
        key_param = param_builder.add(map_access_key, None, "String")
        # Missing CH map keys default to 0 / "" — guard with mapContains
        # so absent keys read as NULL.
        field = f"if(mapContains({field}, {key_param}), {field}[{key_param}], NULL)"
        # Pass-through casts (string/exists/None) are always safe.
        # Numeric `OrNull` casts only work on String inputs, so skip them
        # for `Map(String, Float64)` columns where the value is already
        # numeric.
        map_col_was_string = unprefixed_field.split(".", 1)[0] in map_string_columns
        if map_col_was_string or cast in {None, "string", "exists"}:
            field = clickhouse_cast(field, cast)
    elif json_path is not None:
        json_path_param = param_builder.add(json_path, None, "String")
        if cast == "exists":
            field = "(JSON_EXISTS(" + field + ", " + json_path_param + "))"
        else:
            field = "JSON_VALUE(" + field + ", " + json_path_param + ")"
            field = clickhouse_cast_json_value(field, cast or "string")

    if table_prefix:
        field = f"{table_prefix}.{field}"

    return field, param_builder, raw_fields_used


def maybe_convert_datetime_operands(
    operands: Sequence[tsi_query.Operand],
    datetime_columns: Collection[str],
) -> Sequence[tsi_query.Operand]:
    """Normalize a literal compared against a DateTime column to a CH-native string.

    ClickHouse rejects ISO-8601 strings carrying a `T` separator / `Z` suffix
    (e.g. `2026-05-27T17:49:15.491230Z`) when comparing against a `DateTime64`
    column (TYPE_MISMATCH, code 53). Numeric unix timestamps and parseable
    strings are rewritten to the canonical `YYYY-MM-DD HH:MM:SS.ffffff` form,
    which ClickHouse parses against DateTime columns.

    Returns a new sequence with the conversion applied, or the original
    sequence if neither operand is a DateTime field/parseable literal pair.
    """
    if len(operands) != 2:
        return operands

    field_idx = None
    literal_idx = None
    timestamp: float | None = None
    for i, op in enumerate(operands):
        if (
            isinstance(op, tsi_query.GetFieldOperator)
            and op.get_field_ in datetime_columns
        ):
            field_idx = i
        elif isinstance(op, tsi_query.LiteralOperation):
            parsed = datetime_literal_to_timestamp(op)
            if parsed is not None:
                literal_idx = i
                timestamp = parsed

    if field_idx is None or literal_idx is None or timestamp is None:
        return operands

    datetime_str = timestamp_to_datetime_str(timestamp)
    new_operands = list(operands)
    new_operands[literal_idx] = tsi_query.LiteralOperation(**{"$literal": datetime_str})
    return new_operands


def _operand_array_string_column(
    operand: tsi_query.Operand, array_string_columns: Sequence[str]
) -> str | None:
    """Return the column name if `operand` is a bare $getField on an
    Array(String) column, else None. Used by ContainsOperation to switch
    from substring search to array membership.
    """
    if not array_string_columns:
        return None
    if isinstance(operand, tsi_query.GetFieldOperator):
        name = operand.get_field_
        if name in array_string_columns:
            return name
    return None


def _process_query_to_conditions(
    query: tsi.Query,
    *,
    all_columns: Sequence[str] = (),
    json_columns: Sequence[str] = (),
    array_string_columns: Sequence[str] = (),
    map_string_columns: Sequence[str] = (),
    map_float_columns: Sequence[str] = (),
    param_builder: ParamBuilder | None = None,
    field_resolver: Callable[[str, ParamBuilder], tuple[str, set[str]]] | None = None,
    datetime_columns: Collection[str] | None = None,
) -> tuple[list[str], set[str]]:
    """Converts a Query to a list of conditions for a clickhouse query.

    field_resolver, when provided, overrides the default field-to-SQL mapping
    for $getField operators. Used by eval_results to map fields like
    "scores.accuracy" to aggregated expressions (e.g. avg(...)).

    datetime_columns names the top-level columns typed as DateTime so that
    literals compared against them are normalized via
    `maybe_convert_datetime_operands`.
    """
    dt_columns = datetime_columns or ()
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
            lhs_part, rhs_part = process_binary_operands(*operation.eq_)
            cond = f"({lhs_part} = {rhs_part})"
        elif isinstance(operation, tsi_query.GtOperation):
            lhs_part, rhs_part = process_binary_operands(*operation.gt_)
            cond = f"({lhs_part} > {rhs_part})"
        elif isinstance(operation, tsi_query.LtOperation):
            lhs_part, rhs_part = process_binary_operands(*operation.lt_)
            cond = f"({lhs_part} < {rhs_part})"
        elif isinstance(operation, tsi_query.GteOperation):
            lhs_part, rhs_part = process_binary_operands(*operation.gte_)
            cond = f"({lhs_part} >= {rhs_part})"
        elif isinstance(operation, tsi_query.LteOperation):
            lhs_part, rhs_part = process_binary_operands(*operation.lte_)
            cond = f"({lhs_part} <= {rhs_part})"
        elif isinstance(operation, tsi_query.InOperation):
            lhs_part = process_operand(
                operation.in_[0],
                cast=tsi_query.infer_shared_literal_filter_cast(operation.in_[1]),
            )
            rhs_part = ",".join(process_operand(op) for op in operation.in_[1])
            cond = f"({lhs_part} IN ({rhs_part}))"
        elif isinstance(operation, tsi_query.ContainsOperation):
            # If LHS is a bare Array(String) column, treat $contains as array
            # membership, not substring search — `has(col, value)`. Falls back
            # to the string-contains behavior for every other operand shape.
            array_col = _operand_array_string_column(
                operation.contains_.input, array_string_columns
            )
            if array_col is not None:
                rhs_part = process_operand(operation.contains_.substr)
                raw_fields_used.add(array_col)
                if operation.contains_.case_insensitive:
                    cond = (
                        f"arrayExists(x -> lower(x) = lower({rhs_part}), {array_col})"
                    )
                else:
                    cond = f"has({array_col}, {rhs_part})"
            else:
                lhs_part = process_operand(operation.contains_.input)
                rhs_part = process_operand(operation.contains_.substr)
                position_operation = "position"
                if operation.contains_.case_insensitive:
                    position_operation = "positionCaseInsensitive"
                cond = f"{position_operation}({lhs_part}, {rhs_part}) > 0"
        else:
            raise TypeError(f"Unknown operation type: {operation}")

        return cond

    def process_binary_operands(
        lhs: tsi_query.Operand, rhs: tsi_query.Operand
    ) -> tuple[str, str]:
        # Normalize datetime literals before cast inference: a literal compared
        # against a DateTime column becomes a CH-native datetime string, so the
        # peer-literal cast below correctly sees a string (not a numeric).
        lhs, rhs = maybe_convert_datetime_operands((lhs, rhs), dt_columns)
        # Each side's cast is inferred from the peer literal: a numeric RHS
        # tells us to cast the LHS field, and vice versa. Without this, a
        # JSON_VALUE-extracted field comes through as a String while the
        # literal is bound as Bool/Int64/Float64, and ClickHouse refuses
        # the comparison (NO_COMMON_TYPE).
        lhs_cast = tsi_query.infer_literal_filter_cast(rhs)
        rhs_cast = tsi_query.infer_literal_filter_cast(lhs)
        return process_operand(lhs, cast=lhs_cast), process_operand(rhs, cast=rhs_cast)

    def process_operand(
        operand: tsi_query.Operand, cast: tsi_query.CastTo | None = None
    ) -> str:
        if isinstance(operand, tsi_query.LiteralOperation):
            return pb.add(
                operand.literal_, None, python_value_to_ch_type(operand.literal_)
            )
        elif isinstance(operand, tsi_query.GetFieldOperator):
            if field_resolver is not None:
                field, fields_used = field_resolver(operand.get_field_, pb)
                # The default `_transform_external_field_to_internal_field`
                # path applies the inferred cast inside JSON extraction; the
                # field_resolver path replaces that with caller-controlled
                # SQL, so the cast has to be reapplied here for the typed
                # comparison to type-check in CH.
                if cast is not None:
                    field = clickhouse_cast_json_value(field, cast)
            else:
                (
                    field,
                    _,
                    fields_used,
                ) = _transform_external_field_to_internal_field(
                    operand.get_field_,
                    all_columns=all_columns,
                    json_columns=json_columns,
                    map_string_columns=map_string_columns,
                    map_float_columns=map_float_columns,
                    cast=cast,
                    param_builder=pb,
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

    return conditions, raw_fields_used


def _is_dynamic_field(field: str, json_columns: list[str]) -> bool:
    """Dynamic fields are fields that are arbitrary values produced by the user."""
    if field in json_columns:
        return True
    for col in json_columns:
        if field.startswith(col + "."):
            return True
    return False
