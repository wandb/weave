# Clickhouse Trace Server

import datetime
import json
import queue
import time
import typing
import uuid

from clickhouse_connect.driver.client import Client
from clickhouse_connect.driver.query import QueryResult
import clickhouse_connect
from pydantic import BaseModel, model_validator


from .trace_server_interface_util import version_hash_for_object
from . import trace_server_interface as tsi
from .flushing_buffer import InMemAutoFlushingBuffer, InMemFlushableBuffer


MAX_FLUSH_COUNT = 10000
MAX_FLUSH_AGE = 15


class NotFoundError(Exception):
    pass


class InsertableCHCallSchema(BaseModel):
    entity: str
    project: str
    id: str
    trace_id: str
    parent_id: typing.Optional[str] = None
    name: str
    status_code: tsi.StatusCodeEnum
    start_time: datetime.datetime
    end_time: typing.Optional[datetime.datetime] = None
    attributes: typing.Optional[str] = None
    inputs: typing.Optional[str] = None
    outputs: typing.Optional[str] = None
    summary: typing.Optional[str] = None
    exception: typing.Optional[str] = None
    created_at: typing.Optional[datetime.datetime] = None

    input_refs: typing.List[str]
    output_refs: typing.List[str]

    @model_validator(mode="after")
    def enforce_db_level_business_rules(self):
        # Running State
        if self.status_code == "UNSET":
            assert (
                self.end_time is None
            ), "end_time must be None if status_code is UNSET"
            assert self.outputs is None, "outputs must be None if status_code is UNSET"
            assert (
                self.exception is None
            ), "exception must be None if status_code is UNSET"

        # Finished State
        elif self.status_code == "OK":
            assert self.end_time, "end_time must be set if status_code is OK"
            # Sometimes the finish update is so fast & the server time is not the same as the client time
            # So, we need to make sure that the end_time is greater than the start_time
            # if self.end_time < self.start_time:
            #     self.end_time = self.start_time
            assert (
                self.end_time >= self.start_time
            ), f"end_time {self.end_time} must be greater than start_time {self.start_time}"
            assert self.exception is None, "exception must be None if status_code is OK"

        # Error State
        elif self.status_code == "ERROR":
            assert self.end_time, "end_time must be set if status_code is ERROR"
            # Sometimes the finish update is so fast & the server time is not the same as the client time
            # So, we need to make sure that the end_time is greater than the start_time
            # if self.end_time < self.start_time:
            #     self.end_time = self.start_time
            assert (
                self.end_time >= self.start_time
            ), f"end_time {self.end_time} must be greater than start_time {self.start_time}"
            assert self.exception, "exception must be set if status_code is ERROR"
            assert self.outputs is None, "outputs must be None if status_code is ERROR"

        # Invalid State
        else:
            raise ValueError(f"Invalid status_code: {self.status_code}")

        return self


class UpdateableCHCallSchema(BaseModel):
    entity: str
    project: str
    id: str
    trace_id: typing.Optional[str] = None
    parent_id: typing.Optional[str] = None
    name: typing.Optional[str] = None
    status_code: typing.Optional[tsi.StatusCodeEnum] = None
    start_time: typing.Optional[datetime.datetime] = None
    end_time: typing.Optional[datetime.datetime] = None
    attributes: typing.Optional[str] = None
    inputs: typing.Optional[str] = None
    outputs: typing.Optional[str] = None
    summary: typing.Optional[str] = None
    exception: typing.Optional[str] = None
    created_at: typing.Optional[datetime.datetime] = None

    input_refs: typing.List[str]
    output_refs: typing.List[str]


# Very critical that this matches the calls table schema! This should
# essentially be the DB version of CallSchema with the addition of the
# created_at and updated_at fields
class SelectableCHCallSchema(BaseModel):
    entity: str
    project: str
    id: str

    name: str

    trace_id: str
    parent_id: typing.Optional[str] = None

    status_code: tsi.StatusCodeEnum
    start_time: datetime.datetime
    end_time: typing.Optional[datetime.datetime] = None
    exception: typing.Optional[str] = None

    attributes: typing.Optional[str] = None
    inputs: typing.Optional[str] = None
    outputs: typing.Optional[str] = None
    summary: typing.Optional[str] = None

    updated_at: datetime.datetime
    created_at: datetime.datetime

    input_refs: typing.List[str]
    output_refs: typing.List[str]


class InsertableCHObjSchema(BaseModel):
    entity: str
    project: str
    name: str
    version_hash: str

    is_op: bool

    type_dict_dump: str
    # val_dict_dump: str
    encoded_file_map: typing.Dict[str, bytes] = {}
    metadata_dict_dump: typing.Optional[str] = None


class SelectableCHObjSchema(BaseModel):
    entity: str
    project: str
    name: str
    version_hash: str

    is_op: bool

    type_dict_dump: str
    # val_dict_dump: str
    encoded_file_map: typing.Dict[str, bytes] = {}
    metadata_dict_dump: typing.Optional[str] = None

    created_at: datetime.datetime
    updated_at: datetime.datetime


# Listing of all columns to protect against SQL injection

call_columns: typing.Dict[str, str] = {
    "entity": "String",
    "project": "String",
    "id": "String",
    "trace_id": "Nullable(String)",
    "parent_id": "Nullable(String)",
    "name": "Nullable(String)",
    "status_code": "Nullable(Enum8('UNSET' = 0, 'OK' = 1, 'ERROR' = 2))",
    "start_time": "Nullable(DateTime64(3))",
    "end_time": "Nullable(DateTime64(3))",
    "attributes": "Nullable(String)",
    "inputs": "Nullable(String)",
    "outputs": "Nullable(String)",
    "summary": "Nullable(String)",
    "exception": "Nullable(String)",
    "created_at": "DateTime64(3)",
    "updated_at": "DateTime64(3)",
    "input_refs": "Array(String)",
    "output_refs": "Array(String)",
}
all_call_columns = list(call_columns.keys())

# Super hack since the insert method is buggy in clickhouse. TODO: make this more maintainable
cpy = call_columns.copy()
cpy["created_at"] = "Nullable(" + cpy["created_at"] + ")"
cpy["updated_at"] = "Nullable(" + cpy["updated_at"] + ")"
all_call_column_type_names_with_defaults_nullable = list(cpy.values())


# Listing of required columns that are expected to be returned regardless of the caller's columns request
required_call_columns = [
    "entity",
    "project",
    "id",
    "created_at",
    "updated_at",
    "trace_id",
    "parent_id",
    "name",
    "status_code",
    "start_time",
    "end_time",
    "exception",
]

all_obj_columns = [
    "entity",
    "project",
    "name",
    "version_hash",
    "is_op",
    "type_dict_dump",
    # "val_dict_dump",
    "encoded_file_map",
    "metadata_dict_dump",
    "created_at",
    "updated_at",
]

required_obj_columns = [
    "entity",
    "project",
    "name",
    "version_hash",
    "is_op",
    "type_dict_dump",
    # "val_dict_dump",
    # "encoded_file_map",
    # "metadata_dict_dump",
    "created_at",
    "updated_at",
]


all_obj_insert_columns = [
    "entity",
    "project",
    "name",
    "version_hash",
    "is_op",
    "type_dict_dump",
    # "val_dict_dump",
    "encoded_file_map",
    "metadata_dict_dump",
]


class ClickHouseTraceServer(tsi.TraceServerInterface):
    ch_client: Client
    call_insert_buffer: InMemFlushableBuffer

    def __init__(self, host: str, port: int = 8123, should_batch: bool = True):
        super().__init__()
        self.ch_client = clickhouse_connect.get_client(host=host, port=port)
        self.ch_call_insert_thread_client = clickhouse_connect.get_client(
            host=host, port=port
        )
        self.ch_obj_insert_thread_client = clickhouse_connect.get_client(
            host=host, port=port
        )
        # self._print_status()
        self.call_insert_buffer = InMemAutoFlushingBuffer(
            MAX_FLUSH_COUNT, MAX_FLUSH_AGE, self._flush_call_insert_buffer
        )
        self.obj_insert_buffer = InMemAutoFlushingBuffer(
            MAX_FLUSH_COUNT, MAX_FLUSH_AGE, self._flush_obj_insert_buffer
        )
        self.should_batch = should_batch

    # Creates a new call
    def call_create(self, req: tsi.CallCreateReq) -> tsi.CallCreateRes:
        # Converts the user-provided call details into a clickhouse schema.
        # This does validation and conversion of the input data as well
        # as enforcing business rules and defaults
        ch_call = _partial_call_schema_to_ch_call(req.call)

        # Inserts the call into the clickhouse database, verifying that
        # the call does not already exist
        self._insert_call(ch_call)

        # Returns the id of the newly created call
        # Nothing to return in a buffered/async world
        # return tsi.CallCreateRes(entity=ch_call.entity, project=ch_call.project, id=ch_call.id)
        return tsi.CallCreateRes()

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        # Return the marshaled response
        return tsi.CallReadRes(call=_ch_call_to_call_schema(self._call_read(req)))

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        # Two problems: finish time is going to be delayed, and multiple updates of the
        # same call will be lost clobbered.
        self._execute_update(req)

        # Returns the id of the newly created call
        # Nothing to return in a buffered/async world
        # return tsi.CallCreateRes(entity=req.entity, project=req.project, id=id)
        return tsi.CallCreateRes()

    def call_delete(self, req: tsi.CallDeleteReq) -> tsi.CallDeleteRes:
        raise NotImplementedError()

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallQueryRes:
        conditions = []
        parameters = {}
        if req.filter:
            if req.filter.names:
                conditions.append("name IN {names: Array(String)}")
                parameters["names"] = req.filter.names

            if req.filter.input_object_version_refs:
                parameters["input_refs"] = req.filter.input_object_version_refs
                conditions.append("hasAny(input_refs, {input_refs: Array(String)})")

            if req.filter.output_object_version_refs:
                parameters["output_refs"] = req.filter.output_object_version_refs
                conditions.append("hasAny(output_refs, {output_refs: Array(String)})")

            if req.filter.parent_ids:
                conditions.append("parent_id IN {parent_ids: Array(String)}")
                parameters["parent_ids"] = req.filter.parent_ids

            if req.filter.trace_ids:
                conditions.append("trace_id IN {trace_ids: Array(String)}")
                parameters["trace_ids"] = req.filter.trace_ids

            if req.filter.call_ids:
                conditions.append("id IN {call_ids: Array(String)}")
                parameters["call_ids"] = req.filter.call_ids

            if req.filter.trace_roots_only:
                conditions.append("parent_id IS NULL")

        ch_calls = self._select_calls_query(
            req.entity,
            req.project,
            columns=req.columns,
            conditions=conditions,
            order_by=req.order_by,
            # Skipping limit and offset for now so we aren't tempted to use them.
            # We should have a better way to paginate
            # offset=req.offset,
            # limit=req.limit,
            parameters=parameters,
        )
        calls = [_ch_call_to_call_schema(call) for call in ch_calls]
        return tsi.CallQueryRes(calls=calls)

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        ch_obj = _partial_obj_schema_to_ch_obj(req.op_obj, True)
        self._insert_obj(ch_obj)
        return tsi.ObjCreateRes()

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        return tsi.OpReadRes(op_obj=_ch_obj_to_obj_schema(self._obj_read(req, True)))

    def op_update(self, req: tsi.OpUpdateReq) -> tsi.OpUpdateRes:
        raise NotImplementedError()

    def op_delete(self, req: tsi.OpDeleteReq) -> tsi.OpDeleteRes:
        raise NotImplementedError()

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        raise NotImplementedError()

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        ch_obj = _partial_obj_schema_to_ch_obj(req.obj)
        self._insert_obj(ch_obj)
        return tsi.ObjCreateRes()

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return tsi.ObjReadRes(obj=_ch_obj_to_obj_schema(self._obj_read(req)))

    def obj_update(self, req: tsi.ObjUpdateReq) -> tsi.ObjUpdateRes:
        raise NotImplementedError()

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        raise NotImplementedError()

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        conditions = []
        # parameters = {}
        if req.filter:
            raise NotImplementedError()
        conditions.append("is_op == 0")

        ch_objs = self._select_objs_query(
            req.entity,
            req.project,
            # columns=None,
            conditions=conditions,
            # order_by=None,
            # Skipping limit and offset for now so we aren't tempted to use them.
            # We should have a better way to paginate
            # offset=req.offset,
            # limit=req.limit,
            # parameters=parameters,
        )
        objs = [_ch_obj_to_obj_schema(call) for call in ch_objs]
        return tsi.ObjQueryRes(objs=objs)

    # Private Methods
    def __del__(self):
        self.call_insert_buffer.flush()
        self.ch_client.close()
        self.ch_call_insert_thread_client.close()

    def _flush_call_insert_buffer(self, buffer: typing.List):
        buffer_len = len(buffer)
        if buffer_len:
            flush_id = _generate_id()
            start_time = time.time()
            print("(" + flush_id + ") Flushing " + str(buffer_len) + " calls.")
            self.ch_call_insert_thread_client.insert(
                "calls_raw",
                data=buffer,
                column_names=all_call_columns,
                column_type_names=all_call_column_type_names_with_defaults_nullable,
            )
            print(
                "("
                + flush_id
                + ") Call flush complete in "
                + str(time.time() - start_time)
                + " seconds."
            )

    def _flush_obj_insert_buffer(self, buffer: typing.List):
        buffer_len = len(buffer)
        if buffer_len:
            flush_id = _generate_id()
            start_time = time.time()
            print("(" + flush_id + ") Flushing " + str(buffer_len) + " objects.")
            self.ch_obj_insert_thread_client.insert(
                "objects",
                data=buffer,
                column_names=all_obj_insert_columns,
                # column_type_names=all_obj_column_type_names_with_defaults_nullable,
            )
            print(
                "("
                + flush_id
                + ") Object flush complete in "
                + str(time.time() - start_time)
                + " seconds."
            )

    def _call_read(self, req: tsi.CallReadReq) -> SelectableCHCallSchema:
        # Generate and run the query to get the call from the database
        ch_calls = self._select_calls_query(
            req.entity,
            req.project,
            columns=req.columns,
            conditions=["id = {id: String}"],
            limit=1,
            parameters={"id": req.id},
        )

        # If the call is not found, raise a NotFoundError
        if not ch_calls:
            raise NotFoundError(f"Call with id {req.id} not found")

        return ch_calls[0]

    def _select_calls_query(
        self,
        entity: str,
        project: str,
        columns: typing.Optional[typing.List[str]] = None,
        conditions: typing.Optional[typing.List[str]] = None,
        order_by: typing.Optional[typing.List[typing.Tuple[str, str]]] = None,
        offset: typing.Optional[int] = None,
        limit: typing.Optional[int] = None,
        parameters: typing.Dict[str, typing.Any] = None,
    ) -> typing.List[SelectableCHCallSchema]:

        if not parameters:
            parameters = {}

        parameters["entity_scope"] = entity
        parameters["project_scope"] = project
        if columns == None:
            columns = all_call_columns

        remaining_columns = set(columns) - set(required_call_columns)
        columns = required_call_columns + list(remaining_columns)

        # Stop injection
        assert (
            set(columns) - set(all_call_columns) == set()
        ), f"Invalid columns: {columns}"
        merged_cols = []
        for col in columns:
            if col in ["entity", "project", "id"]:
                merged_cols.append(f"{col} AS {col}")
            else:
                 merged_cols.append(f"anyLast({col}) AS {col}")
        select_columns_part = ", ".join(merged_cols)

        if not conditions:
            conditions = ["1 = 1"]

        # conditions.append(
        #     "entity = {entity_scope: String} AND project = {project_scope: String}"
        # )

        conditions_part = " AND ".join(conditions)

        order_by_part = ""
        if order_by == None:
            order_by = []
        order_by = list(order_by) + [("updated_at", "DESC")]
        for field, direction in order_by:
            assert field in all_call_columns, f"Invalid order_by field: {field}"
            assert direction in [
                "ASC",
                "DESC",
            ], f"Invalid order_by direction: {direction}"
        order_by_part = ", ".join(
            [f"{field} {direction}" for field, direction in order_by]
        )
        order_by_part = f"ORDER BY {order_by_part}"

        offset_part = ""
        if offset != None:
            offset_part = f"OFFSET {offset}"

        limit_part = ""
        if limit != None:
            limit_part = f"LIMIT {limit}"

        raw_res = self._query(
            f"""
            SELECT {select_columns_part}
            FROM calls_agg
            WHERE entity = {{entity_scope: String}} AND project = {{project_scope: String}}
            GROUP BY entity, project, id
            HAVING {conditions_part}
            {order_by_part}
            {limit_part}
            {offset_part}
        """,
            parameters,
        )
        # print(raw_res.result_rows)
        calls = []
        for row in raw_res.result_rows:
            calls.append(_raw_call_dict_to_ch_call(dict(zip(columns, row))))
        return _deduplicate_calls(calls)

    def _obj_read(
        self, req: tsi.ObjReadReq, only_ops: bool = False
    ) -> SelectableCHObjSchema:
        conditions = ["name = {name: String}", "version_hash = {version_hash: String}"]
        if only_ops:
            conditions.append("is_op = 1")
        else:
            conditions.append("is_op = 0")
        ch_objs = self._select_objs_query(
            req.entity,
            req.project,
            columns=all_obj_columns,
            # columns=req.columns,
            conditions=conditions,
            limit=1,
            parameters={"name": req.name, "version_hash": req.version_hash},
        )

        # If the call is not found, raise a NotFoundError
        if not ch_objs:
            raise NotFoundError(f"Obj with id {req.id} not found")

        return ch_objs[0]

    def _select_objs_query(
        self,
        entity: str,
        project: str,
        columns: typing.Optional[typing.List[str]] = None,
        conditions: typing.Optional[typing.List[str]] = None,
        # order_by: typing.Optional[typing.List[typing.Tuple[str, str]]] = None,
        # offset: typing.Optional[int] = None,
        limit: typing.Optional[int] = None,
        parameters: typing.Dict[str, typing.Any] = None,
    ) -> typing.List[SelectableCHObjSchema]:

        if not parameters:
            parameters = {}

        parameters["entity_scope"] = entity
        parameters["project_scope"] = project
        if columns == None:
            columns = all_obj_columns

        remaining_columns = set(columns) - set(required_obj_columns)
        columns = required_obj_columns + list(remaining_columns)
        # # Stop injection
        assert (
            set(columns) - set(all_obj_columns) == set()
        ), f"Invalid columns: {columns}"
        select_columns_part = ", ".join(columns)
        merged_cols = []
        for col in columns:
            if col in ["entity", "project", "name", "version_hash"]:
                merged_cols.append(f"{col} AS {col}")
            else:
                merged_cols.append(f"anyLast({col}) AS {col}")
        select_columns_part = ", ".join(merged_cols)



        if not conditions:
            conditions = ['1 = 1']

        # conditions.append(
        #     "entity = {entity_scope: String} AND project = {project_scope: String}"
        # )

        conditions_part = " AND ".join(conditions)

        # order_by_part = ""
        # if order_by == None:
        #     order_by = []
        # order_by = list(order_by) + [("updated_at", "DESC")]
        # for field, direction in order_by:
        #     assert field in all_call_columns, f"Invalid order_by field: {field}"
        #     assert direction in [
        #         "ASC",
        #         "DESC",
        #     ], f"Invalid order_by direction: {direction}"
        # order_by_part = ", ".join(
        #     [f"{field} {direction}" for field, direction in order_by]
        # )
        # order_by_part = f"ORDER BY {order_by_part}"

        # offset_part = ""
        # if offset != None:
        #     offset_part = f"OFFSET {offset}"

        limit_part = ""
        if limit != None:
            limit_part = f"LIMIT {limit}"

        # raw_res = self._query(
        #     f"""
        #     SELECT {select_columns_part}
        #     FROM calls_agg
        #     WHERE entity = {{entity_scope: String}} AND project = {{project_scope: String}}
        #     GROUP BY entity, project, id
        #     HAVING {conditions_part}
        #     {order_by_part}
        #     {limit_part}
        #     {offset_part}
        # """,
        #     parameters,
        # )

        raw_res = self._query(
            f"""
            SELECT {select_columns_part}
            FROM objects
            WHERE entity = {{entity_scope: String}} AND project = {{project_scope: String}}
            GROUP BY entity, project, name, version_hash
            HAVING {conditions_part}
            {limit_part}
        """,
            parameters,
            column_formats={"encoded_file_map": {"string": "bytes"}},
        )
        # # print(raw_res.result_rows)
        objs = []
        for row in raw_res.result_rows:
            objs.append(_raw_obj_dict_to_ch_obj(dict(zip(columns, row))))
        return objs

    def _execute_update(self, req: tsi.CallUpdateReq) -> None:
        # raw_read_res = self._call_read(tsi.CallReadReq(entity=req.entity, project=req.project, id=req.id))
        # read_res = _ch_call_to_call_schema(raw_read_res)

        # Builds a new call schema with the updated fields
        ch_call = _partial_call_schema_to_ch_call_update(
            tsi.PartialCallForCreationSchema(
                entity=req.entity,
                project=req.project,
                id=req.id,
                trace_id=None,
                parent_id=None,
                name=None,
                status_code=req.fields.status_code,
                start_time_s=None,
                end_time_s=req.fields.end_time_s,
                attributes=None,
                inputs=None,
                outputs=req.fields.outputs,
                summary=req.fields.summary,
                exception=req.fields.exception,
            )
        )

        self._insert_call(ch_call)

        # Returns the id of the newly created call
        # Nothing to return in a buffered/async world
        # return tsi.CallCreateRes(entity=req.entity, project=req.project, id=id)

    def _print_status(self):
        tables = self.ch_client.command("SHOW TABLES")
        # tables = self.ch_client.command("SHOW VIEW")
        print("Current Tables: \n" + tables + "\n")

    def _run_migrations(self):
        print("Running migrations")
        self.ch_client.command("DROP TABLE IF EXISTS objects")
        self.ch_client.command("DROP TABLE IF EXISTS calls")
        self.ch_client.command("DROP TABLE IF EXISTS calls_raw")
        self.ch_client.command("DROP TABLE IF EXISTS calls_agg")
        self.ch_client.command(
            """
        CREATE TABLE IF NOT EXISTS
        objects (
            entity String,
            project String,
            name String,
            version_hash String,

            is_op UInt8,

            type_dict_dump String,
            # val_dict_dump String,
            encoded_file_map Map(String, String),
            metadata_dict_dump String NULL,

            created_at DateTime64(3) DEFAULT now64(3),
            updated_at DateTime64(3) DEFAULT now64(3)
        )
        ENGINE = ReplacingMergeTree
        ORDER BY (entity, project, name, version_hash)
        PRIMARY KEY (entity, project, name, version_hash)
        """
        )
        self.ch_client.command(
            """
        CREATE TABLE IF NOT EXISTS
        calls_raw (
            entity String,
            project String,
            id String,
            trace_id String NULL,
            parent_id String NULL,
            name String NULL,
            status_code String NULL,
            start_time Nullable(DateTime64(3)) ,
            end_time Nullable(DateTime64(3)) ,
            attributes String NULL,
            inputs String NULL,
            outputs String NULL,
            summary String NULL,
            exception String NULL,
            created_at DateTime64(3) DEFAULT now64(3),
            updated_at DateTime64(3) DEFAULT now64(3),
            input_refs Array(String),
            output_refs Array(String)
        )
        ENGINE = MergeTree
        ORDER BY (entity, project, id)
        """
        )
        self.ch_client.command(
            """
        CREATE MATERIALIZED VIEW IF NOT EXISTS
        calls_agg (
            entity String,
            project String,
            id String,
            trace_id SimpleAggregateFunction(any, String) NULL,
            parent_id SimpleAggregateFunction(any, String) NULL,
            name SimpleAggregateFunction(any, String) NULL,
            status_code SimpleAggregateFunction(anyLast, String) NULL,
            start_time SimpleAggregateFunction(anyLast, Nullable(DateTime64(3))),
            end_time SimpleAggregateFunction(anyLast, Nullable(DateTime64(3))),
            attributes SimpleAggregateFunction(anyLast, String) NULL,
            inputs SimpleAggregateFunction(anyLast, String) NULL,
            outputs SimpleAggregateFunction(anyLast, String) NULL,
            summary SimpleAggregateFunction(anyLast, String) NULL,
            exception SimpleAggregateFunction(anyLast, String) NULL,
            created_at SimpleAggregateFunction(any, DateTime64(3)),
            updated_at SimpleAggregateFunction(anyLast, DateTime64(3)),
            input_refs SimpleAggregateFunction(array_concat_agg, Array(String)),
            output_refs SimpleAggregateFunction(array_concat_agg, Array(String))
        )
        ENGINE = AggregatingMergeTree()
        ORDER BY (entity, project, id)
        AS SELECT
            entity,
            project,
            id,
            anySimpleState(trace_id) as trace_id,
            anySimpleState(parent_id) as parent_id,
            anySimpleState(name) as name,
            anyLastSimpleState(status_code) as status_code,
            anyLastSimpleState(start_time) as start_time,
            anyLastSimpleState(end_time) as end_time,
            anyLastSimpleState(attributes) as attributes,
            anyLastSimpleState(inputs) as inputs,
            anyLastSimpleState(outputs) as outputs,
            anyLastSimpleState(summary) as summary,
            anyLastSimpleState(exception) as exception,
            anySimpleState(created_at) as created_at,
            anyLastSimpleState(updated_at) as updated_at,
            anyLastSimpleState(input_refs) as input_refs,
            anyLastSimpleState(output_refs) as output_refs
        FROM calls_raw
        GROUP BY entity, project, id
        """
        )

    def _query(
        self,
        query: str,
        parameters: typing.Dict[str, typing.Any],
        column_formats: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> QueryResult:
        print("Running query: " + query + " with parameters: " + str(parameters))
        parameters = _process_parameters(parameters)
        res = self.ch_client.query(
            query, parameters=parameters, column_formats=column_formats, use_none=True
        )
        print("Summary: " + json.dumps(res.summary, indent=2))
        return res

    def _insert_call(self, ch_call: UpdateableCHCallSchema) -> None:
        parameters = ch_call.model_dump()
        row = []
        for key in all_call_columns:
            row.append(parameters.get(key, None))

        if self.should_batch:
            self.call_insert_buffer.insert(row=row)
        else:
            self._flush_call_insert_buffer([row])

    def _insert_obj(self, ch_obj: InsertableCHObjSchema) -> None:
        parameters = ch_obj.model_dump()
        row = []
        for key in all_obj_insert_columns:
            row.append(parameters.get(key, None))

        if self.should_batch:
            self.obj_insert_buffer.insert(row=row)
        else:
            self._flush_obj_insert_buffer([row])


def _prepare_nullable_dict_value(
    value: typing.Optional[dict] = None,
) -> typing.Optional[str]:
    # TODO
    return json.dumps(value) if value else None


def _utc_sec_to_datetime(s_time: float) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(s_time)


def _generate_id() -> str:
    return str(uuid.uuid4())


def _xor(a, b, field_name: str):
    if a and b:
        raise ValueError(f"{field_name} already set to {a}")
    return a or b


def _datetime_to_sec_float(val: datetime.datetime) -> float:
    return val.timestamp()


def _nullable_datetime_to_sec_float(
    val: typing.Optional[datetime.datetime],
) -> typing.Optional[float]:
    return _datetime_to_sec_float(val) if val else None


def _nullable_dict_dump_to_dict(
    val: str,
) -> typing.Optional[typing.Dict[str, typing.Any]]:
    return json.loads(val) if val else None


def _raw_call_dict_to_ch_call(
    call: typing.Dict[str, typing.Any]
) -> SelectableCHCallSchema:
    return SelectableCHCallSchema.model_validate(call)


def _raw_obj_dict_to_ch_obj(obj: typing.Dict[str, typing.Any]) -> SelectableCHObjSchema:
    if obj["encoded_file_map"]:
        obj["encoded_file_map"] = {
            k.decode("utf-8"): v for k, v in obj["encoded_file_map"].items()
        }
    return SelectableCHObjSchema.model_validate(obj)


def _ch_call_to_call_schema(ch_call: SelectableCHCallSchema) -> tsi.CallSchema:
    return tsi.CallSchema(
        # `entity` should always be present
        entity=ch_call.entity,
        # `project`` should always be present
        project=ch_call.project,
        # `id`` should always be present
        id=ch_call.id,
        # `trace_id` should always be present
        trace_id=ch_call.trace_id,
        # `parent_id` may be null (represented as `\\N`)
        parent_id=ch_call.parent_id,
        # `name` should always be present
        name=ch_call.name,
        # `status_code` should always be present
        status_code=ch_call.status_code,
        # `start_time` should always be present
        start_time_s=_nullable_datetime_to_sec_float(ch_call.start_time),
        # `end_time` may be null (represented as `\\N`)
        end_time_s=_nullable_datetime_to_sec_float(ch_call.end_time),
        # `attributes` may be null (represented as `\\N`)
        attributes=_nullable_dict_dump_to_dict(ch_call.attributes),
        # `inputs` may be null (represented as `\\N`)
        inputs=_nullable_dict_dump_to_dict(ch_call.inputs),
        # `outputs` may be null (represented as `\\N`)
        outputs=_nullable_dict_dump_to_dict(ch_call.outputs),
        # `summary` may be null (represented as `\\N`)
        summary=_nullable_dict_dump_to_dict(ch_call.summary),
        # `summary` may be null (represented as `\\N`)
        exception=ch_call.exception,
    )


def _ch_obj_to_obj_schema(ch_obj: SelectableCHObjSchema) -> tsi.ObjSchema:
    return tsi.ObjSchema(
        # `entity` should always be present
        entity=ch_obj.entity,
        # `project`` should always be present
        project=ch_obj.project,
        # `name`` should always be present
        name=ch_obj.name,
        # `version_hash`` should always be present
        version_hash=ch_obj.version_hash,
        # `is_op`` should always be present
        is_op=ch_obj.is_op,
        # `type_dict`` should always be present
        type_dict=json.loads(ch_obj.type_dict_dump),
        # `val_dict`` should always be present
        # val_dict=json.loads(ch_obj.val_dict_dump),
        # `encoded_file_map`` should always be present
        encoded_file_map=ch_obj.encoded_file_map,
        # `metadata_dict`` may be null (represented as `\\N`)
        metadata_dict=json.loads(ch_obj.metadata_dict_dump)
        if ch_obj.metadata_dict_dump
        else None,
        # `created_at`` should always be present
        created_at_s=_datetime_to_sec_float(ch_obj.created_at),
    )


def extract_refs_from_values(vals: typing.Optional[typing.List[typing.Any]]) -> typing.List[str]:
    refs = []
    if vals:
        for val in vals:
            if isinstance(val, str) and val.startswith("wandb-trace://"):
                refs.append(val)
                # parts = val[len("wandb-trace://") :].split("/")
                # entity = parts[0]
                # project = parts[1]
                # noun = parts[2]
                # name_and_version = parts[3]
                # name, version = name_and_version.split(":")
                # refs.append((entity, project, noun, name, version))
    print(refs)
    return refs


def _partial_call_schema_to_ch_call(
    partial_call: tsi.PartialCallForCreationSchema,
) -> InsertableCHCallSchema:
    id = partial_call.id or _generate_id()
    trace_id = partial_call.trace_id or _generate_id()
    # Default Rules
    status_code = (
        partial_call.status_code.value if partial_call.status_code else "UNSET"
    )
    start_time = (
        _utc_sec_to_datetime(partial_call.start_time_s)
        if partial_call.start_time_s
        else datetime.datetime.now()
    )
    end_time = (
        _utc_sec_to_datetime(partial_call.end_time_s)
        if partial_call.end_time_s
        else None
    )

    if status_code == "UNSET":
        # Case 1: We have an exception, then we are in an error state
        if partial_call.exception:
            status_code = "ERROR"

        # Case 2: We have an exception, then we are in an error state
        elif partial_call.outputs or partial_call.summary:
            status_code = "OK"

    if status_code != "UNSET" and not partial_call.end_time_s:
        end_time = datetime.datetime.now()

    input_refs = []
    output_refs = []
    if partial_call.inputs:
        input_refs = extract_refs_from_values(list(partial_call.inputs.values()))
    if partial_call.outputs:
        output_refs = extract_refs_from_values(list(partial_call.outputs.values()))

    return InsertableCHCallSchema(
        entity=partial_call.entity,
        project=partial_call.project,
        id=id,
        trace_id=trace_id,
        parent_id=partial_call.parent_id,
        name=partial_call.name,
        status_code=status_code,
        start_time=start_time,
        end_time=end_time,
        attributes=_prepare_nullable_dict_value(partial_call.attributes),
        inputs=_prepare_nullable_dict_value(partial_call.inputs),
        outputs=_prepare_nullable_dict_value(partial_call.outputs),
        summary=_prepare_nullable_dict_value(partial_call.summary),
        exception=partial_call.exception,

        input_refs=input_refs,
        output_refs=output_refs,
    )


def _partial_call_schema_to_ch_call_update(
    partial_call: tsi.PartialCallForCreationSchema,
) -> UpdateableCHCallSchema:
    status_code = partial_call.status_code.value if partial_call.status_code else None
    start_time = partial_call.start_time_s
    end_time = partial_call.end_time_s
    id = partial_call.id
    trace_id = partial_call.trace_id

    if status_code == "UNSET" or status_code == None:
        # Case 1: We have an exception, then we are in an error state
        if partial_call.exception:
            status_code = "ERROR"

        # Case 2: We have an exception, then we are in an error state
        elif partial_call.outputs or partial_call.summary or partial_call.end_time_s:
            status_code = "OK"

    if (
        not (status_code == "UNSET" or status_code == None)
        and not partial_call.end_time_s
    ):
        end_time = datetime.datetime.now()

    input_refs = []
    output_refs = []
    if partial_call.inputs:
        input_refs = extract_refs_from_values(list(partial_call.inputs.values()))
    if partial_call.outputs:
        output_refs = extract_refs_from_values(list(partial_call.outputs.values()))

    return UpdateableCHCallSchema(
        entity=partial_call.entity,
        project=partial_call.project,
        id=id,
        trace_id=trace_id,
        parent_id=partial_call.parent_id,
        name=partial_call.name,
        status_code=status_code,
        start_time=start_time,
        end_time=end_time,
        attributes=_prepare_nullable_dict_value(partial_call.attributes),
        inputs=_prepare_nullable_dict_value(partial_call.inputs),
        outputs=_prepare_nullable_dict_value(partial_call.outputs),
        summary=_prepare_nullable_dict_value(partial_call.summary),
        exception=partial_call.exception,

        input_refs=input_refs,
        output_refs=output_refs,
    )


def _deduplicate_calls(
    calls: typing.List[SelectableCHCallSchema],
) -> typing.List[SelectableCHCallSchema]:
    latest_calls = {}
    for call in calls:
        call_id = f"{call.entity}/{call.project}/{call.id}"
        if not call.updated_at:
            raise ValueError(f"Call {call_id} has no updated_at")
        if (
            call_id not in latest_calls
            or latest_calls[call_id].updated_at < call.updated_at
        ):
            latest_calls[call_id] = call
    return list(latest_calls.values())


def _process_parameters(
    parameters: typing.Dict[str, typing.Any]
) -> typing.Dict[str, typing.Any]:
    # Special processing for datetimes! For some reason, the clickhouse connect
    # client truncates the datetime to the nearest second, so we need to convert
    # the datetime to a float which is then converted back to a datetime in the
    # clickhouse query
    parameters = parameters.copy()
    for key, value in parameters.items():
        if isinstance(value, datetime.datetime):
            parameters[key] = value.timestamp()
    return parameters


def _partial_obj_schema_to_ch_obj(
    partial_obj: tsi.PartialObjForCreationSchema,
    is_op: bool = False,
) -> InsertableCHObjSchema:
    version_hash = version_hash_for_object(partial_obj)

    return InsertableCHObjSchema(
        entity=partial_obj.entity,
        project=partial_obj.project,
        name=partial_obj.name,
        version_hash=version_hash,
        is_op=is_op,
        type_dict_dump=json.dumps(partial_obj.type_dict),
        # val_dict_dump=json.dumps(partial_obj.val_dict),
        encoded_file_map=partial_obj.encoded_file_map or {},
        metadata_dict_dump=json.dumps(partial_obj.metadata_dict),
    )
