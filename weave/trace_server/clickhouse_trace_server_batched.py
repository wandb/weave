# Clickhouse Trace Server

import datetime
import json
import os
import time
import typing

from clickhouse_connect.driver.client import Client
from clickhouse_connect.driver.query import QueryResult
import clickhouse_connect
from pydantic import BaseModel


from .trace_server_interface_util import (
    ARTIFACT_REF_SCHEME,
    TRACE_REF_SCHEME,
    decode_b64_to_bytes,
    encode_bytes_as_b64,
    generate_id,
    version_hash_for_object,
)
from . import trace_server_interface as tsi
from .flushing_buffer import InMemAutoFlushingBuffer, InMemFlushableBuffer


MAX_FLUSH_COUNT = 10000
MAX_FLUSH_AGE = 15


class NotFoundError(Exception):
    pass


class CallStartCHInsertable(BaseModel):
    entity: str
    project: str
    id: str
    trace_id: str
    parent_id: typing.Optional[str] = None
    name: str
    start_datetime: datetime.datetime
    attributes_dump: str
    inputs_dump: str
    input_refs: typing.List[str]
    output_refs: typing.List[str] = []  # sadly, this is required


class CallEndCHInsertable(BaseModel):
    entity: str
    project: str
    id: str
    end_datetime: datetime.datetime
    exception: typing.Optional[str] = None
    summary_dump: str
    outputs_dump: str
    input_refs: typing.List[str] = []  # sadly, this is required
    output_refs: typing.List[str]


CallCHInsertable = typing.Union[CallStartCHInsertable, CallEndCHInsertable]


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

    start_datetime: datetime.datetime
    end_datetime: typing.Optional[datetime.datetime] = None
    exception: typing.Optional[str] = None

    attributes_dump: str
    inputs_dump: str
    outputs_dump: typing.Optional[str] = None
    summary_dump: typing.Optional[str] = None

    input_refs: typing.List[str]
    output_refs: typing.List[str]


all_call_insert_columns = list(
    CallStartCHInsertable.model_fields.keys() | CallEndCHInsertable.model_fields.keys()
)

all_call_select_columns = list(SelectableCHCallSchema.model_fields.keys())

# Let's just make everything required for now ... can optimize when we implement column selection
required_call_columns = list(set(all_call_select_columns) - set([]))


class ObjCHInsertable(BaseModel):
    entity: str
    project: str
    is_op: bool
    name: str
    version_hash: str
    created_datetime: datetime.datetime

    type_dict_dump: str
    bytes_file_map: typing.Dict[str, bytes]
    metadata_dict_dump: str


class SelectableCHObjSchema(BaseModel):
    entity: str
    project: str
    is_op: bool
    name: str
    version_hash: str
    created_datetime: datetime.datetime
    version_index: int

    type_dict_dump: str
    bytes_file_map: typing.Dict[str, bytes]
    metadata_dict_dump: str


all_obj_select_columns = list(SelectableCHObjSchema.model_fields.keys())
all_obj_insert_columns = list(ObjCHInsertable.model_fields.keys())

# Let's just make everything required for now ... can optimize when we implement column selection
required_obj_select_columns = list(set(all_obj_select_columns) - set([]))


class ClickHouseTraceServer(tsi.TraceServerInterface):
    ch_client: Client
    call_insert_buffer: InMemFlushableBuffer

    def __init__(self, host: str, port: int = 8123, user="default", password="", should_batch: bool = True):
        super().__init__()
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self.ch_client = self._mint_client()
        self.ch_call_insert_thread_client = self._mint_client()
        self.ch_obj_insert_thread_client = self._mint_client()
        self.call_insert_buffer = InMemAutoFlushingBuffer(
            MAX_FLUSH_COUNT, MAX_FLUSH_AGE, self._flush_call_insert_buffer
        )
        self.obj_insert_buffer = InMemAutoFlushingBuffer(
            MAX_FLUSH_COUNT, MAX_FLUSH_AGE, self._flush_obj_insert_buffer
        )
        self.should_batch = should_batch

    @classmethod
    def from_env(cls, should_batch = True) -> "ClickHouseTraceServer":
        host = os.environ.get("WF_CLICKHOUSE_HOST", "localhost")
        port = int(os.environ.get("WF_CLICKHOUSE_PORT", 8123))
        user = os.environ.get("WF_CLICKHOUSE_USER", "default")
        password = os.environ.get("WF_CLICKHOUSE_PASS", "")
        return cls(host, port, user, password, should_batch)


    # Creates a new call
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        # Converts the user-provided call details into a clickhouse schema.
        # This does validation and conversion of the input data as well
        # as enforcing business rules and defaults
        ch_call = _start_call_for_insert_to_ch_insertable_start_call(req.start)

        # Inserts the call into the clickhouse database, verifying that
        # the call does not already exist
        self._insert_call(ch_call)

        # Returns the id of the newly created call
        return tsi.CallStartRes(
            id=ch_call.id,
            trace_id=ch_call.trace_id,
        )

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        # Converts the user-provided call details into a clickhouse schema.
        # This does validation and conversion of the input data as well
        # as enforcing business rules and defaults
        ch_call = _end_call_for_insert_to_ch_insertable_end_call(req.end)

        # Inserts the call into the clickhouse database, verifying that
        # the call does not already exist
        self._insert_call(ch_call)

        # Returns the id of the newly created call
        return tsi.CallEndRes()

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        # Return the marshaled response
        return tsi.CallReadRes(call=_ch_call_to_call_schema(self._call_read(req)))

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallQueryRes:
        conditions = []
        parameters = {}
        if req.filter:
            if req.filter.op_version_refs:
                for name in req.filter.op_version_refs:
                    if "*" in name:
                        raise NotImplementedError("Wildcard not yet supported")
                conditions.append("name IN {names: Array(String)}")
                parameters["names"] = req.filter.op_version_refs

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
            conditions=conditions,
            parameters=parameters,
        )
        calls = [_ch_call_to_call_schema(call) for call in ch_calls]
        return tsi.CallQueryRes(calls=calls)

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        ch_obj = _partial_obj_schema_to_ch_obj(req.op_obj, is_op=True)
        self._insert_obj(ch_obj)
        return tsi.OpCreateRes(version_hash=ch_obj.version_hash)

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        return tsi.OpReadRes(
            op_obj=_ch_obj_to_obj_schema(self._obj_read(req, op_only=True))
        )

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        conditions: typing.List[str] = []
        parameters: typing.Dict[str, typing.Any] = {}
        if req.filter:
            if req.filter.op_names:
                raise NotImplementedError()
            if req.filter.latest_only:
                raise NotImplementedError()
        conditions.append("is_op == 1")

        ch_objs = self._select_objs_query(
            req.entity,
            req.project,
            conditions=conditions,
            parameters=parameters,
        )
        objs = [_ch_obj_to_obj_schema(call) for call in ch_objs]
        return tsi.OpQueryRes(op_objs=objs)

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        ch_obj = _partial_obj_schema_to_ch_obj(req.obj, is_op=False)
        self._insert_obj(ch_obj)
        return tsi.ObjCreateRes(version_hash=ch_obj.version_hash)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return tsi.ObjReadRes(
            obj=_ch_obj_to_obj_schema(self._obj_read(req, op_only=False))
        )

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        conditions: typing.List[str] = []
        parameters: typing.Dict[str, typing.Any] = {}
        if req.filter:
            if req.filter.object_names:
                raise NotImplementedError()
            if req.filter.latest_only:
                raise NotImplementedError()
        conditions.append("is_op == 0")

        ch_objs = self._select_objs_query(
            req.entity,
            req.project,
            conditions=conditions,
            parameters=parameters,
        )
        objs = [_ch_obj_to_obj_schema(call) for call in ch_objs]
        return tsi.ObjQueryRes(objs=objs)

    # Private Methods
    def _mint_client(self) -> str:
        return  clickhouse_connect.get_client(host=self._host, port=self._port, user=self._user, password=self._password)


    def __del__(self) -> None:
        self.call_insert_buffer.flush()
        self.ch_client.close()
        self.ch_call_insert_thread_client.close()

    def _flush_call_insert_buffer(self, buffer: typing.List) -> None:
        buffer_len = len(buffer)
        if buffer_len:
            flush_id = generate_id()
            start_time = time.time()
            print("(" + flush_id + ") Flushing " + str(buffer_len) + " calls.")
            self.ch_call_insert_thread_client.insert(
                "calls_raw",
                data=buffer,
                column_names=all_call_insert_columns,
            )
            print(
                "("
                + flush_id
                + ") Call flush complete in "
                + str(time.time() - start_time)
                + " seconds."
            )

    def _flush_obj_insert_buffer(self, buffer: typing.List) -> None:
        buffer_len = len(buffer)
        if buffer_len:
            flush_id = generate_id()
            start_time = time.time()
            print("(" + flush_id + ") Flushing " + str(buffer_len) + " objects.")
            self.ch_obj_insert_thread_client.insert(
                "objects_raw",
                data=buffer,
                column_names=all_obj_insert_columns,
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
        parameters: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.List[SelectableCHCallSchema]:

        if not parameters:
            parameters = {}
        parameters = typing.cast(typing.Dict[str, typing.Any], parameters)

        parameters["entity_scope"] = entity
        parameters["project_scope"] = project
        if columns == None:
            columns = all_call_select_columns
        columns = typing.cast(typing.List[str], columns)

        remaining_columns = set(columns) - set(required_call_columns)
        columns = required_call_columns + list(remaining_columns)

        # Stop injection
        assert (
            set(columns) - set(all_call_select_columns) == set()
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

        conditions_part = " AND ".join(conditions)

        order_by_part = ""
        if order_by != None:
            order_by = typing.cast(typing.List[typing.Tuple[str, str]], order_by)
            for field, direction in order_by:
                assert (
                    field in all_call_select_columns
                ), f"Invalid order_by field: {field}"
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
            FROM calls_merged
            WHERE entity = {{entity_scope: String}} AND project = {{project_scope: String}}
            GROUP BY entity, project, id
            HAVING {conditions_part}
            {order_by_part}
            {limit_part}
            {offset_part}
        """,
            parameters,
        )

        calls = []
        for row in raw_res.result_rows:
            calls.append(_raw_call_dict_to_ch_call(dict(zip(columns, row))))
        return calls

    def _obj_read(self, req: tsi.ObjReadReq, op_only: bool) -> SelectableCHObjSchema:
        conditions = ["name = {name: String}", "version_hash = {version_hash: String}"]

        if op_only:
            conditions.append("is_op == 1")
        else:
            conditions.append("is_op == 0")

        ch_objs = self._select_objs_query(
            req.entity,
            req.project,
            columns=all_obj_select_columns,
            conditions=conditions,
            limit=1,
            parameters={"name": req.name, "version_hash": req.version_hash},
        )

        # If the obj is not found, raise a NotFoundError
        if not ch_objs:
            raise NotFoundError(f"Obj with id {req.id} not found")

        return ch_objs[0]

    def _select_objs_query(
        self,
        entity: str,
        project: str,
        columns: typing.Optional[typing.List[str]] = None,
        conditions: typing.Optional[typing.List[str]] = None,
        limit: typing.Optional[int] = None,
        parameters: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.List[SelectableCHObjSchema]:

        if not parameters:
            parameters = {}
        parameters = typing.cast(typing.Dict[str, typing.Any], parameters)

        parameters["entity_scope"] = entity
        parameters["project_scope"] = project
        if columns == None:
            columns = all_obj_select_columns
        columns = typing.cast(typing.List[str], columns)

        remaining_columns = set(columns) - set(required_obj_select_columns)
        columns = required_obj_select_columns + list(remaining_columns)
        # # Stop injection
        assert (
            set(columns) - set(all_obj_select_columns) == set()
        ), f"Invalid columns: {columns}"
        select_columns_part = ", ".join(columns)

        if not conditions:
            conditions = ["1 = 1"]

        conditions_part = " AND ".join(conditions)

        limit_part = ""
        if limit != None:
            limit_part = f"LIMIT {limit}"

        raw_res = self._query(
            f"""
            SELECT {select_columns_part}
            FROM objects_versioned
            WHERE entity = {{entity_scope: String}} AND project = {{project_scope: String}}
            AND {conditions_part}
            {limit_part}
        """,
            parameters,
            column_formats={"bytes_file_map": {"string": "bytes"}},
        )

        objs = []
        for row in raw_res.result_rows:
            objs.append(_raw_obj_dict_to_ch_obj(dict(zip(columns, row))))
        return objs

    def _run_migrations(self) -> None:
        print("Running migrations")
        # res = self.ch_client.command("SHOW TABLES")
        # if isinstance(res, str):
        #     table_names = res.split("\n")
        #     for table_name in table_names:
        #         if not table_name.startswith("."):
        #             self.ch_client.command("DROP TABLE IF EXISTS " + table_name)

        self.ch_client.command(
            """
        CREATE TABLE IF NOT EXISTS
        objects_raw (
            entity String,
            project String,
            is_op UInt8,
            name String,
            version_hash String,
            created_datetime DateTime64(3),

            type_dict_dump String,
            bytes_file_map Map(String, String),
            metadata_dict_dump String,

            db_row_created_at DateTime64(3) DEFAULT now64(3)

        )
        ENGINE = MergeTree
        ORDER BY (entity, project, is_op, name, version_hash)
        """
        )

        self.ch_client.command(
            """
        CREATE TABLE IF NOT EXISTS
        objects_deduplicated (
            entity String,
            project String,
            is_op UInt8,
            name String,
            version_hash String,
            created_datetime SimpleAggregateFunction(min, DateTime64(3)),

            type_dict_dump SimpleAggregateFunction(any, String),
            bytes_file_map SimpleAggregateFunction(any, Map(String, String)),

            # Note: if we ever want to support updates, this needs to be moved to a more robust handling
            metadata_dict_dump SimpleAggregateFunction(any, String),
        )
        ENGINE = AggregatingMergeTree
        ORDER BY (entity, project, is_op, name, version_hash)
        """
        )

        self.ch_client.command(
            """
        CREATE MATERIALIZED VIEW IF NOT EXISTS objects_deduplicated_view TO objects_deduplicated
        AS
        SELECT
            entity,
            project,
            is_op,
            name,
            version_hash,
            minSimpleState(created_datetime) as created_datetime,

            anySimpleState(type_dict_dump) as type_dict_dump,
            anySimpleState(bytes_file_map) as bytes_file_map,
            anySimpleState(metadata_dict_dump) as metadata_dict_dump
            
        FROM objects_raw
        GROUP BY entity, project, is_op, name, version_hash
        """
        )

        # The following view is just to workout version indexing and latest keys
        self.ch_client.command(
            """
        CREATE VIEW IF NOT EXISTS objects_versioned
        AS
        SELECT
            entity,
            project,
            is_op,
            name,
            version_hash,
            min(objects_deduplicated.created_datetime) as created_datetime,
            any(type_dict_dump) as type_dict_dump,
            any(bytes_file_map) as bytes_file_map,
            any(metadata_dict_dump) as metadata_dict_dump,
            row_number() OVER w1 as version_index,
            1 == count(*) OVER w1 as is_latest
        FROM objects_deduplicated
        GROUP BY entity, project, is_op, name, version_hash
        WINDOW
            w1 AS (PARTITION BY entity, project, is_op, name ORDER BY min(objects_deduplicated.created_datetime) ASC Rows BETWEEN CURRENT ROW AND 1 FOLLOWING)
        """
        )

        self.ch_client.command(
            """
            CREATE TABLE IF NOT EXISTS
            calls_raw (
                # Identity Fields
                entity String,
                project String,
                id String,

                # Start Fields (All fields except parent_id are required when starting
                # a call. However, to support a fast "update" we need to allow nulls)
                trace_id String NULL,
                parent_id String NULL, # This field is actually nullable
                name String NULL,
                start_datetime DateTime64(3) NULL,
                attributes_dump String NULL,
                inputs_dump String NULL,
                input_refs Array(String), # Empty array treated as null

                # End Fields (All fields are required when ending
                # a call. However, to support a fast "update" we need to allow nulls)
                end_datetime DateTime64(3) NULL,
                outputs_dump String NULL,
                summary_dump String NULL,
                exception String NULL,
                output_refs Array(String), # Empty array treated as null

                # Bookkeeping
                db_row_created_at DateTime64(3) DEFAULT now64(3)
            )
            ENGINE = MergeTree
            ORDER BY (entity, project, id)
        """
        )
        self.ch_client.command(
            """
            CREATE TABLE IF NOT EXISTS calls_merged
            (
                entity String,
                project String,
                id String,
                # While these fields are all marked as null, the practical expectation
                # is that they will be non-null except for parent_id. The problem is that
                # clickhouse might not aggregate the data immediately, so we need to allow
                # for nulls in the interim.
                trace_id SimpleAggregateFunction(any, String) NULL,
                parent_id SimpleAggregateFunction(any, String) NULL,
                name SimpleAggregateFunction(any, String) NULL,
                start_datetime SimpleAggregateFunction(any, DateTime64(3)) NULL,
                attributes_dump SimpleAggregateFunction(any, String) NULL,
                inputs_dump SimpleAggregateFunction(any, String) NULL,
                input_refs SimpleAggregateFunction(array_concat_agg, Array(String)),
                end_datetime SimpleAggregateFunction(any, DateTime64(3)) NULL,
                outputs_dump SimpleAggregateFunction(any, String) NULL,
                summary_dump SimpleAggregateFunction(any, String) NULL,
                exception SimpleAggregateFunction(any, String) NULL,
                output_refs SimpleAggregateFunction(array_concat_agg, Array(String))
            )
            ENGINE = AggregatingMergeTree
            ORDER BY (entity, project, id)
        """
        )
        self.ch_client.command(
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS calls_merged_view TO calls_merged
            AS
            SELECT
                entity,
                project,
                id,
                anySimpleState(trace_id) as trace_id,
                anySimpleState(parent_id) as parent_id,
                anySimpleState(name) as name,
                anySimpleState(start_datetime) as start_datetime,
                anySimpleState(attributes_dump) as attributes_dump,
                anySimpleState(inputs_dump) as inputs_dump,
                array_concat_aggSimpleState(input_refs) as input_refs,
                anySimpleState(end_datetime) as end_datetime,
                anySimpleState(outputs_dump) as outputs_dump,
                anySimpleState(summary_dump) as summary_dump,
                anySimpleState(exception) as exception,
                array_concat_aggSimpleState(output_refs) as output_refs
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

    def _insert_call(self, ch_call: CallCHInsertable) -> None:
        parameters = ch_call.model_dump()
        row = []
        for key in all_call_insert_columns:
            row.append(parameters.get(key, None))

        if self.should_batch:
            self.call_insert_buffer.insert(row=row)
        else:
            self._flush_call_insert_buffer([row])

    def _insert_obj(self, ch_obj: ObjCHInsertable) -> None:
        parameters = ch_obj.model_dump()
        row = []
        for key in all_obj_insert_columns:
            row.append(parameters.get(key, None))

        if self.should_batch:
            self.obj_insert_buffer.insert(row=row)
        else:
            self._flush_obj_insert_buffer([row])


def _dict_value_to_dump(
    value: dict,
) -> str:
    cpy = value.copy()
    if cpy:
        keys = list(cpy.keys())
        cpy["_keys"] = keys
    return json.dumps(cpy)


def _dict_dump_to_dict(val: str) -> typing.Dict[str, typing.Any]:
    return json.loads(val)


def _nullable_dict_dump_to_dict(
    val: typing.Optional[str],
) -> typing.Optional[typing.Dict[str, typing.Any]]:
    return _dict_dump_to_dict(val) if val else None


def _raw_call_dict_to_ch_call(
    call: typing.Dict[str, typing.Any]
) -> SelectableCHCallSchema:
    return SelectableCHCallSchema.model_validate(call)


def _raw_obj_dict_to_ch_obj(obj: typing.Dict[str, typing.Any]) -> SelectableCHObjSchema:
    if obj["bytes_file_map"]:
        obj["bytes_file_map"] = {
            k.decode("utf-8"): v for k, v in obj["bytes_file_map"].items()
        }
    return SelectableCHObjSchema.model_validate(obj)


def _ch_call_to_call_schema(ch_call: SelectableCHCallSchema) -> tsi.CallSchema:
    return tsi.CallSchema(
        entity=ch_call.entity,
        project=ch_call.project,
        id=ch_call.id,
        trace_id=ch_call.trace_id,
        parent_id=ch_call.parent_id,
        name=ch_call.name,
        start_datetime=ch_call.start_datetime,
        end_datetime=ch_call.end_datetime,
        attributes=_dict_dump_to_dict(ch_call.attributes_dump),
        inputs=_dict_dump_to_dict(ch_call.inputs_dump),
        outputs=_nullable_dict_dump_to_dict(ch_call.outputs_dump),
        summary=_nullable_dict_dump_to_dict(ch_call.summary_dump),
        exception=ch_call.exception,
    )


def _ch_obj_to_obj_schema(ch_obj: SelectableCHObjSchema) -> tsi.ObjSchema:
    return tsi.ObjSchema(
        entity=ch_obj.entity,
        project=ch_obj.project,
        name=ch_obj.name,
        version_hash=ch_obj.version_hash,
        type_dict=_dict_dump_to_dict(ch_obj.type_dict_dump),
        b64_file_map=encode_bytes_as_b64(ch_obj.bytes_file_map),
        metadata_dict=_dict_dump_to_dict(ch_obj.metadata_dict_dump),
        created_datetime=ch_obj.created_datetime,
        version_index=ch_obj.version_index,
    )


valid_schemes = [TRACE_REF_SCHEME, ARTIFACT_REF_SCHEME]


def extract_refs_from_values(
    vals: typing.Optional[typing.List[typing.Any]],
) -> typing.List[str]:
    refs = []
    if vals:
        for val in vals:
            if isinstance(val, str) and any(
                val.startswith(scheme + "://") for scheme in valid_schemes
            ):
                refs.append(val)
    return refs


def _start_call_for_insert_to_ch_insertable_start_call(
    start_call: tsi.StartedCallSchemaForInsert,
) -> CallStartCHInsertable:
    # Note: it is technically possible for the user to mess up and provide the
    # wrong trace id (one that does not match the parent_id)!
    call_id = start_call.id or generate_id()
    trace_id = start_call.trace_id or generate_id()
    return CallStartCHInsertable(
        entity=start_call.entity,
        project=start_call.project,
        id=call_id,
        trace_id=trace_id,
        parent_id=start_call.parent_id,
        name=start_call.name,
        start_datetime=start_call.start_datetime,
        attributes_dump=_dict_value_to_dump(start_call.attributes),
        inputs_dump=_dict_value_to_dump(start_call.inputs),
        input_refs=extract_refs_from_values(list(start_call.inputs.values())),
    )


def _end_call_for_insert_to_ch_insertable_end_call(
    end_call: tsi.EndedCallSchemaForInsert,
) -> CallEndCHInsertable:
    # Note: it is technically possible for the user to mess up and provide the
    # wrong trace id (one that does not match the parent_id)!
    return CallEndCHInsertable(
        entity=end_call.entity,
        project=end_call.project,
        id=end_call.id,
        exception=end_call.exception,
        end_datetime=end_call.end_datetime,
        summary_dump=_dict_value_to_dump(end_call.summary),
        outputs_dump=_dict_value_to_dump(end_call.outputs),
        output_refs=extract_refs_from_values(list(end_call.outputs.values())),
    )


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
    partial_obj: tsi.ObjSchemaForInsert,
    is_op: bool,
) -> ObjCHInsertable:
    version_hash = version_hash_for_object(partial_obj)

    return ObjCHInsertable(
        entity=partial_obj.entity,
        project=partial_obj.project,
        name=partial_obj.name,
        version_hash=version_hash,
        is_op=is_op,
        type_dict_dump=_dict_value_to_dump(partial_obj.type_dict),
        bytes_file_map=decode_b64_to_bytes(partial_obj.b64_file_map or {}),
        metadata_dict_dump=_dict_value_to_dump(partial_obj.metadata_dict),
        created_datetime=partial_obj.created_datetime,
    )
