import copy
import math
import functools

from ..api import op, weave_class
from .. import decorator_type
from .. import weave_types as types
from . import list_
from . import graph

from ..language_features.tagging import tagged_value_type

try:
    import sqlalchemy
    from sqlalchemy import orm
except ImportError:
    pass


@decorator_type.type("sqlconnection")
class SqlConnection:
    path: str

    @functools.cached_property
    def engine(self):
        return sqlalchemy.create_engine(self.path)

    @functools.cached_property
    def meta(self):
        meta = sqlalchemy.MetaData()
        meta.reflect(self.engine)
        return meta

    def table(self, name):
        return SqlTable(self, name)


def filter_fn_to_sql_filter(table, filter_fn_node):
    if isinstance(filter_fn_node, graph.ConstNode):
        return filter_fn_node.val
    elif isinstance(filter_fn_node, graph.OutputNode):
        op_name = graph.op_full_name(filter_fn_node.from_op)
        if op_name == "number-greater":
            return filter_fn_to_sql_filter(
                table, filter_fn_node.from_op.inputs["lhs"]
            ) > filter_fn_to_sql_filter(table, filter_fn_node.from_op.inputs["rhs"])
        elif op_name == "pick":
            return filter_fn_to_sql_filter(
                table, filter_fn_node.from_op.inputs["obj"]
            ).columns[
                filter_fn_to_sql_filter(table, filter_fn_node.from_op.inputs["key"])
            ]
        elif op_name == "typedDict-pick":
            return filter_fn_to_sql_filter(
                table, filter_fn_node.from_op.inputs["self"]
            ).columns[
                filter_fn_to_sql_filter(table, filter_fn_node.from_op.inputs["key"])
            ]
        raise Exception("unhandled op name", op_name)
    elif isinstance(filter_fn_node, graph.VarNode):
        if filter_fn_node.name == "row":
            return table
        raise Exception("unhandled var name")


def index_output_type(input_types):
    # THIS IS NO GOOD
    # TODO: need to fix Const type so we don't need this.
    self_type = input_types["self"]
    if isinstance(self_type, types.Const):
        return self_type.val_type.object_type
    else:
        return self_type.object_type


def mapped_pick_output_type(input_types):
    if not isinstance(input_types["key"], types.Const):
        return types.List(types.UnknownType())
    key = input_types["key"].val
    prop_type = input_types["self"].object_type.property_types.get(key)
    if prop_type is None:
        return types.Invalid()
    return types.List(prop_type)


class SqlTableType(types.ObjectType):
    _base_type = types.List
    name = "sqltable"

    object_type: types.Type

    def property_types(self):
        return {
            "conn": SqlConnection.WeaveType(),
            "table_name": types.String(),
        }

    def __init__(self, object_type=types.TypedDict({})):
        self.object_type = object_type

    def _to_dict(self):
        return {"objectType": self.object_type.to_dict()}

    @classmethod
    def from_dict(cls, d):
        return cls(types.TypeRegistry.type_from_dict(d["objectType"]))


@weave_class(weave_type=SqlTableType)
class SqlTable:
    PAGE_SIZE = 100

    def __init__(self, conn, table_name):
        self.conn = conn
        self.table_name = table_name

        # We always fetch results in pages of PAGE_SIZE, and store the results
        # here in _row_cache.
        self._row_cache = {}
        self._filter_fn = None

    @functools.cached_property
    def table(self):
        return self.conn.meta.tables[self.table_name]

    def _to_list_table(self):
        self_list = []
        for i in range(self._count()):
            self_list.append(self._index(i))
        return self_list

    def copy(self):
        new_obj = self.__class__(self.conn, self.table_name)
        new_obj._filter_fn = copy.deepcopy(self._filter_fn)
        return new_obj

    def _cached_row(self, index):
        page = math.floor(index / self.PAGE_SIZE)
        page_offset = index % self.PAGE_SIZE
        if page in self._row_cache:
            try:
                return self._row_cache[page][page_offset]
            except IndexError:
                return None
        return None

    @property
    def query(self):
        DBSession = orm.sessionmaker(bind=self.conn.engine)
        session = DBSession()
        query = session.query(self.table)
        if self._filter_fn is not None:
            query = query.filter(filter_fn_to_sql_filter(self.table, self._filter_fn))
        return query

    def _count(self):
        return self.query.count()

    @op()
    def count(self) -> int:
        return self._count()

    def _index(self, index: int):
        row = self._cached_row(index)
        if row is not None:
            return row

        page = math.floor(index / self.PAGE_SIZE)
        page_offset = index % self.PAGE_SIZE

        query = self.query
        results = query.offset(page * self.PAGE_SIZE).limit(SqlTable.PAGE_SIZE)
        # print('RESULTS QUERY', results)
        rows = []
        for row in results.all():
            row = {k: getattr(row, k) for k in row._fields}
            rows.append(row)
        self._row_cache[page] = rows
        try:
            return rows[page_offset]
        except IndexError:
            return None

    @op(name="sqltable-index", output_type=index_output_type)
    def __getitem__(self, index: int):
        return self._index(index)

    @op(output_type=mapped_pick_output_type)
    def pick(self, key: str):
        return list_.general_picker(self._to_list_table(), key)

    @op(
        input_type={
            "map_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: types.List(input_types["self"].object_type),
    )
    def map(self, map_fn):
        return list_.List.map.resolve_fn(self._to_list_table(), map_fn)

    @op(
        input_type={
            "filterFn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: input_types["self"],
    )
    def filter(self, filterFn):
        new_obj = self.copy()
        new_obj._filter_fn = filterFn
        return new_obj

    @op(
        input_type={
            "group_by_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: types.List(
            tagged_value_type.TaggedValueType(
                types.TypedDict(
                    {
                        "groupKey": input_types["group_by_fn"].output_type,
                    }
                ),
                types.List(input_types["self"].object_type),
            )
        ),
    )
    def groupby(self, group_by_fn):
        return list_.List.groupby.resolve_fn(self._to_list_table(), group_by_fn)


SqlTableType.instance_class = SqlTable
SqlTableType.instance_classes = SqlTable


@op(
    name="local-sqlconnection",
    input_type={"path": types.String()},
    output_type=SqlConnection.WeaveType(),  # type: ignore
)
def local_sqlconnection(path):
    return SqlConnection(path)


@op(
    name="sqlconnection-tables",
    input_type={"conn": SqlConnection.WeaveType()},  # type: ignore
    output_type=types.TypedDict({}),
)
def sqlconnection_tables(conn):
    tables = {}
    for table_name in conn.meta.tables.keys():
        tables[table_name] = conn.table(table_name)
    return tables


# @op(
#     name='sqlconnection-schemanames',
#     input_type={
#         'conn': SqlConnectionType()},
#     output_type=types.List(types.String()))
# def sqlconnection_schemanames(conn):
#     return conn.schema_names()

# @op(
#     name='sqlconnection-tablenames',
#     input_type={
#         'conn': SqlConnectionType()},
#     output_type=types.List(types.String()))
# def sqlconnection_tablenames(conn):
#     return conn.table_names()


def _table_to_type(table):
    table_column_types = {}
    for column_name, column in table.columns.items():
        type_class = column.type.__class__.__name__
        if type_class == "VARCHAR" or type_class == "TEXT":
            table_column_type = types.String()
        elif type_class == "INTEGER":
            table_column_type = types.Number()
        table_column_types[column_name] = table_column_type
    return table_column_types


@op(
    name="sqlconnection-tablesType",
    input_type={"conn": SqlConnection.WeaveType()},  # type: ignore
    output_type=types.TypeType(),
)
def sqlconnection_tables_type(conn):
    properties = {}
    for table_name, table in conn.meta.tables.items():
        properties[table_name] = types.List(types.TypedDict(_table_to_type(table)))
    return types.TypedDict(properties).to_json()


@op(
    name="sqlconnection-refine_table",
    hidden=True,
    input_type={"conn": SqlConnection.WeaveType(), "name": types.String()},  # type: ignore
    output_type=types.TypeType(),
)
def refine_sqlconnection_table(conn, name):
    for table_name, table in conn.meta.tables.items():
        if table_name == name:
            return SqlTableType(types.TypedDict(_table_to_type(table)))
    return types.NoneType()


@op(
    name="sqlconnection-table",
    input_type={"conn": SqlConnection.WeaveType(), "name": types.String()},  # type: ignore
    output_type=SqlTableType(types.TypedDict({})),
    refine_output_type=refine_sqlconnection_table,
)
def sqlconnection_table(conn, name):
    return conn.table(name)
