import copy
import math
import sqlalchemy
from sqlalchemy import orm

from ..api import op
from .. import weave_types as types
from . import table
from . import graph


class SqlConnectionType(types.Type):
    name = "sqlconnection"


class SqlTableType(types.Type):
    name = "sqltable"


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
        if filter_fn_node.from_op.name == "number-greater":
            return filter_fn_to_sql_filter(
                table, filter_fn_node.from_op.inputs["lhs"]
            ) > filter_fn_to_sql_filter(table, filter_fn_node.from_op.inputs["rhs"])
        if filter_fn_node.from_op.name == "pick":
            return filter_fn_to_sql_filter(
                table, filter_fn_node.from_op.inputs["obj"]
            ).columns[
                filter_fn_to_sql_filter(table, filter_fn_node.from_op.inputs["key"])
            ]
        raise Exception("unhandled op name", filter_fn_node.from_op.name)
    elif isinstance(filter_fn_node, graph.VarNode):
        if filter_fn_node.name == "row":
            return table
        raise Exception("unhandled var name")


class SqlTable(table.Table):
    PAGE_SIZE = 100

    def __init__(self, conn, table):
        self.conn = conn
        self.table = table

        # We always fetch results in pages of PAGE_SIZE, and store the results
        # here in _row_cache.
        self._row_cache = {}
        self._filter_fn = None

    def _to_list_table(self):
        return table.ListTable([self.index(i) for i in range(self.count())])

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

    def count(self):
        return self.query.count()

    def index(self, index):
        row = self._cached_row(index)
        if row is not None:
            return row

        page = math.floor(index / self.PAGE_SIZE)
        page_offset = index % self.PAGE_SIZE

        query = self.query
        results = query.offset(page * self.PAGE_SIZE).limit(SqlTable.PAGE_SIZE)
        # print('RESULTS QUERY', results)
        rows = []
        print("MAKING QUERY for page", page)
        for row in results.all():
            row = {k: getattr(row, k) for k in row.keys()}
            rows.append(row)
        self._row_cache[page] = rows
        try:
            return rows[page_offset]
        except IndexError:
            return None

    def pick(self, key):
        return self._to_list_table().pick(key)

    def map(self, mapFn):
        return self._to_list_table().map(mapFn)

    def filter(self, filterFn):
        new_obj = self.copy()
        new_obj._filter_fn = filterFn
        return new_obj

    def groupby(self, groupByFn):
        return self._to_list_table().groupby(groupByFn)


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
    name="sqlconnection-tables-type",
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
    output_type=types.Table(),
)
def sqlconnection_table(conn, name):
    return conn.table(name)
