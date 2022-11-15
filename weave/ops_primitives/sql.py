import copy
import math
import sqlalchemy
import typing
from sqlalchemy import orm

from ..api import op, weave_class
from .. import weave_types as types
from . import list_
from . import graph


class SqlConnectionType(types.Type):
    name = "sqlconnection"


class SqlTableType(types.Type):
    name = "sqltable"

    object_type: types.Type

    def __init__(self, object_type=types.TypedDict({})):
        self.object_type = object_type

    def __str__(self):
        return "<SqlTableType %s>" % self.object_type

    def _to_dict(self):
        return {"objectType": self.object_type.to_dict()}

    @classmethod
    def from_dict(cls, d):
        return cls(types.TypeRegistry.type_from_dict(d["objectType"]))


class SqlConnection(object):
    def __init__(self, engine):
        self.engine = engine
        self.meta = sqlalchemy.MetaData(engine)
        self.meta.reflect(engine)

    def table(self, name):
        return SqlTable(self, self.meta.tables[name])


SqlConnectionType.instance_class = SqlConnection
SqlConnectionType.instance_classes = SqlConnection


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


def pick_output_type(input_types):
    if not isinstance(input_types["key"], types.Const):
        return types.UnknownType()
    key = input_types["key"].val
    prop_type = input_types["self"].object_type.property_types.get(key)
    if prop_type is None:
        return types.Invalid()
    return prop_type


@weave_class(weave_type=SqlTableType)
class SqlTable:
    PAGE_SIZE = 100

    def __init__(self, conn, table):
        self.conn = conn
        self.table = table

        # We always fetch results in pages of PAGE_SIZE, and store the results
        # here in _row_cache.
        self._row_cache = {}
        self._filter_fn = None

    def _to_list_table(self):
        self_list = []
        for i in range(self._count()):
            self_list.append(self._index(i))
        return self_list

    def copy(self):
        new_obj = self.__class__(self.conn, self.table)
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
            row = {k: getattr(row, k) for k in row.keys()}
            rows.append(row)
        self._row_cache[page] = rows
        try:
            return rows[page_offset]
        except IndexError:
            return None

    @op(name="sqltable-index", output_type=index_output_type)
    def __getitem__(self, index: int):
        return self._index(index)

    @op(output_type=pick_output_type)
    def pick(self, key: str):
        return list_.general_picker(self._to_list_table(), key)

    @op(output_type=lambda input_types: types.List(input_types["self"].object_type))
    def map(self, map_fn: typing.Any):
        return list_.List.map.resolve_fn(self._to_list_table(), map_fn)

    @op(
        input_type={
            "filter_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: input_types["self"],
    )
    def filter(self, filter_fn):
        new_obj = self.copy()
        new_obj._filter_fn = filter_fn
        return new_obj

    @op(
        input_type={
            "group_by_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: types.List(
            list_.GroupResultType(input_types["self"].object_type)
        ),
    )
    def groupby(self, group_by_fn):
        return list_.List.groupby.resolve_fn(self._to_list_table(), group_by_fn)


SqlTableType.instance_class = SqlTable
SqlTableType.instance_classes = SqlTable


@op(
    name="local-sqlconnection",
    input_type={"path": types.String()},
    output_type=SqlConnectionType(),
)
def local_sqlconnection(path):
    return SqlConnection(sqlalchemy.create_engine(path))


@op(
    name="sqlconnection-tables",
    input_type={"conn": SqlConnectionType()},
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


@op(
    name="sqlconnection-tablesType",
    input_type={"conn": SqlConnectionType()},
    output_type=types.Type(),
)
def sqlconnection_tables_type(conn):
    properties = {}
    for table_name, table in conn.meta.tables.items():
        table_column_types = {}
        for column_name, column in table.columns.items():
            type_class = column.type.__class__.__name__
            if type_class == "VARCHAR":
                table_column_type = types.String()
            elif type_class == "INTEGER":
                table_column_type = types.Number()
            table_column_types[column_name] = table_column_type
        properties[table_name] = types.List(types.TypedDict(table_column_types))
    return types.TypedDict(properties).to_json()


@op(
    name="sqlconnection-table",
    input_type={"conn": SqlConnectionType(), "name": types.String()},
    output_type=SqlTableType(types.TypedDict({})),
)
def sqlconnection_table(conn, name):
    return conn.table(name)
