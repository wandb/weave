# Clickhouse Trace Server

from contextlib import contextmanager
import datetime
import json
import typing

from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.query import QueryResult
import clickhouse_connect
from pydantic import BaseModel

from . import environment as wf_env
from . import clickhouse_trace_server_migrator as wf_migrator

from .trace_server_interface_util import (
    extract_refs_from_values,
    decode_b64_to_bytes,
    encode_bytes_as_b64,
    generate_id,
    version_hash_for_object,
    WILDCARD_ARTIFACT_VERSION_AND_PATH,
)
from . import trace_server_interface as tsi


MAX_FLUSH_COUNT = 10000
MAX_FLUSH_AGE = 15


class NotFoundError(Exception):
    pass


class CallStartCHInsertable(BaseModel):
    project_id: str
    id: str
    trace_id: str
    parent_id: typing.Optional[str] = None
    name: str
    start_datetime: datetime.datetime
    attributes_dump: str
    inputs_dump: str
    input_refs: typing.List[str]
    output_refs: typing.List[str] = []  # sadly, this is required

    wb_user_id: typing.Optional[str] = None
    wb_run_id: typing.Optional[str] = None


class CallEndCHInsertable(BaseModel):
    project_id: str
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
    project_id: str
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

    wb_user_id: typing.Optional[str] = None
    wb_run_id: typing.Optional[str] = None


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
    ch_client: CHClient

    def __init__(
        self,
        *,
        host: str,
        port: int = 8123,
        user: str = "default",
        password: str = "",
        database: str = "default",
        use_async_insert: bool = False,
    ):
        super().__init__()
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self.ch_client = self._mint_client()
        self._flush_immediately = True
        self._call_batch: typing.List[typing.List[typing.Any]] = []
        self._use_async_insert = use_async_insert

    @classmethod
    def from_env(cls, use_async_insert: bool = False) -> "ClickHouseTraceServer":
        return cls(
            host=wf_env.wf_clickhouse_host(),
            port=wf_env.wf_clickhouse_port(),
            user=wf_env.wf_clickhouse_user(),
            password=wf_env.wf_clickhouse_pass(),
            database=wf_env.wf_clickhouse_database(),
            use_async_insert=use_async_insert,
        )

    @contextmanager
    def call_batch(self) -> typing.Iterator[None]:
        # Not thread safe - do not use across threads
        self._flush_immediately = False
        try:
            yield
            self._flush_calls()
        finally:
            self._call_batch = []
            self._flush_immediately = True

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

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        conditions = []
        parameters: typing.Dict[str, typing.Union[typing.List[str], str]] = {}
        if req.filter:
            if req.filter.op_version_refs:
                # We will build up (0 or 1) + N conditions for the op_version_refs
                # If there are any non-wildcarded names, then we at least have an IN condition
                # If there are any wildcarded names, then we have a LIKE condition for each

                or_conditions: typing.List[str] = []

                non_wildcarded_names: typing.List[str] = []
                wildcarded_names: typing.List[str] = []
                for name in req.filter.op_version_refs:
                    if name.endswith(WILDCARD_ARTIFACT_VERSION_AND_PATH):
                        wildcarded_names.append(name)
                    else:
                        non_wildcarded_names.append(name)

                if non_wildcarded_names:
                    or_conditions.append(
                        "name IN {non_wildcarded_names: Array(String)}"
                    )
                    parameters["non_wildcarded_names"] = non_wildcarded_names

                for name_ndx, name in enumerate(wildcarded_names):
                    param_name = "wildcarded_name_" + str(name_ndx)
                    or_conditions.append("name LIKE {" + param_name + ": String}")
                    like_name = name[: -len(WILDCARD_ARTIFACT_VERSION_AND_PATH)] + "%"
                    parameters[param_name] = like_name

                if or_conditions:
                    conditions.append("(" + " OR ".join(or_conditions) + ")")

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

            if req.filter.wb_user_ids:
                conditions.append("wb_user_id IN {wb_user_ids: Array(String)}")
                parameters["wb_user_ids"] = req.filter.wb_user_ids

            if req.filter.wb_run_ids:
                conditions.append("wb_run_id IN {wb_run_ids: Array(String)}")
                parameters["wb_run_ids"] = req.filter.wb_run_ids

        ch_call_dicts = self._select_calls_query_raw(
            req.project_id,
            conditions=conditions,
            parameters=parameters,
            limit=req.limit,
        )
        calls = [
            _ch_call_dict_to_call_schema_dict(ch_dict) for ch_dict in ch_call_dicts
        ]
        return tsi.CallsQueryRes(calls=calls)

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
    def _mint_client(self) -> CHClient:
        client = clickhouse_connect.get_client(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
        )
        # Safely create the database if it does not exist
        client.command(f"CREATE DATABASE IF NOT EXISTS {self._database}")
        client.database = self._database
        return client

    def __del__(self) -> None:
        self.ch_client.close()

    def _insert_call_batch(self, batch: typing.List) -> None:
        if batch:
            settings = {}
            if self._use_async_insert:
                settings["async_insert"] = 1
                settings["wait_for_async_insert"] = 0
            self.ch_client.insert(
                "calls_raw",
                data=batch,
                column_names=all_call_insert_columns,
                settings=settings,
            )

    def _insert_obj_batch(self, batch: typing.List) -> None:
        if batch:
            settings = {}
            if self._use_async_insert:
                settings["async_insert"] = 1
                settings["wait_for_async_insert"] = 0
            self.ch_client.insert(
                "objects_raw",
                data=batch,
                column_names=all_obj_insert_columns,
                settings=settings,
            )

    def _call_read(self, req: tsi.CallReadReq) -> SelectableCHCallSchema:
        # Generate and run the query to get the call from the database
        ch_calls = self._select_calls_query(
            req.project_id,
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
        project_id: str,
        columns: typing.Optional[typing.List[str]] = None,
        conditions: typing.Optional[typing.List[str]] = None,
        order_by: typing.Optional[typing.List[typing.Tuple[str, str]]] = None,
        offset: typing.Optional[int] = None,
        limit: typing.Optional[int] = None,
        parameters: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.List[SelectableCHCallSchema]:
        dicts = self._select_calls_query_raw(
            project_id,
            columns=columns,
            conditions=conditions,
            order_by=order_by,
            offset=offset,
            limit=limit,
            parameters=parameters,
        )
        calls = []
        for row in dicts:
            calls.append(_raw_call_dict_to_ch_call(row))
        return calls

    def _select_calls_query_raw(
        self,
        project_id: str,
        columns: typing.Optional[typing.List[str]] = None,
        conditions: typing.Optional[typing.List[str]] = None,
        order_by: typing.Optional[typing.List[typing.Tuple[str, str]]] = None,
        offset: typing.Optional[int] = None,
        limit: typing.Optional[int] = None,
        parameters: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.List[typing.Dict]:
        if not parameters:
            parameters = {}
        parameters = typing.cast(typing.Dict[str, typing.Any], parameters)

        parameters["project_id"] = project_id
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
            if col in ["project_id", "id"]:
                merged_cols.append(f"{col} AS {col}")
            elif col in ["input_refs", "output_refs"]:
                merged_cols.append(f"array_concat_agg({col}) AS {col}")
            else:
                merged_cols.append(f"any({col}) AS {col}")
        select_columns_part = ", ".join(merged_cols)

        if not conditions:
            conditions = ["1 = 1"]

        conditions_part = " AND ".join(conditions)

        order_by_part = "ORDER BY start_datetime ASC"
        # if order_by != None:
        #     order_by = typing.cast(typing.List[typing.Tuple[str, str]], order_by)
        #     for field, direction in order_by:
        #         assert (
        #             field in all_call_select_columns
        #         ), f"Invalid order_by field: {field}"
        #         assert direction in [
        #             "ASC",
        #             "DESC",
        #         ], f"Invalid order_by direction: {direction}"
        #     order_by_part = ", ".join(
        #         [f"{field} {direction}" for field, direction in order_by]
        #     )
        #     order_by_part = f"ORDER BY {order_by_part}"

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
            WHERE project_id = {{project_id: String}}
            GROUP BY project_id, id
            HAVING {conditions_part}
            {order_by_part}
            {limit_part}
            {offset_part}
        """,
            parameters,
        )

        dicts = []
        for row in raw_res.result_rows:
            dicts.append(dict(zip(columns, row)))
        return dicts

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
        migrator = wf_migrator.ClickHouseTraceServerMigrator(self._mint_client())
        migrator.apply_migrations(self._database)

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
        self._call_batch.append(row)
        if self._flush_immediately:
            self._flush_calls()

    def _flush_calls(self) -> None:
        self._insert_call_batch(self._call_batch)
        self._call_batch = []

    def _insert_obj(self, ch_obj: ObjCHInsertable) -> None:
        parameters = ch_obj.model_dump()
        row = []
        for key in all_obj_insert_columns:
            row.append(parameters.get(key, None))

        self._insert_obj_batch([row])


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


def _ensure_datetimes_have_tz(
    dt: typing.Optional[datetime.datetime] = None,
) -> typing.Optional[datetime.datetime]:
    # https://github.com/ClickHouse/clickhouse-connect/issues/210
    # Clickhouse does not support timezone-aware datetimes. You can specify the
    # desired timezone at query time. However according to the issue above,
    # clickhouse will produce a timezone-naive datetime when the preferred
    # timezone is UTC. This is a problem because it does not match the ISO8601
    # standard as datetimes are to be interpreted locally unless specified
    # otherwise. This function ensures that the datetime has a timezone, and if
    # it does not, it adds the UTC timezone to correctly convey that the
    # datetime is in UTC for the caller.
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt


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
        project_id=ch_call.project_id,
        id=ch_call.id,
        trace_id=ch_call.trace_id,
        parent_id=ch_call.parent_id,
        name=ch_call.name,
        start_datetime=_ensure_datetimes_have_tz(ch_call.start_datetime),
        end_datetime=_ensure_datetimes_have_tz(ch_call.end_datetime),
        attributes=_dict_dump_to_dict(ch_call.attributes_dump),
        inputs=_dict_dump_to_dict(ch_call.inputs_dump),
        outputs=_nullable_dict_dump_to_dict(ch_call.outputs_dump),
        summary=_nullable_dict_dump_to_dict(ch_call.summary_dump),
        exception=ch_call.exception,
        wb_run_id=ch_call.wb_run_id,
        wb_user_id=ch_call.wb_user_id,
    )


# Keep in sync with `_ch_call_to_call_schema`. This copy is for performance
def _ch_call_dict_to_call_schema_dict(ch_call_dict: typing.Dict) -> typing.Dict:
    return dict(
        project_id=ch_call_dict.get("project_id"),
        id=ch_call_dict.get("id"),
        trace_id=ch_call_dict.get("trace_id"),
        parent_id=ch_call_dict.get("parent_id"),
        name=ch_call_dict.get("name"),
        start_datetime=_ensure_datetimes_have_tz(ch_call_dict.get("start_datetime")),
        end_datetime=_ensure_datetimes_have_tz(ch_call_dict.get("end_datetime")),
        attributes=_dict_dump_to_dict(ch_call_dict.get("attributes_dump")),
        inputs=_dict_dump_to_dict(ch_call_dict.get("inputs_dump")),
        outputs=_nullable_dict_dump_to_dict(ch_call_dict.get("outputs_dump")),
        summary=_nullable_dict_dump_to_dict(ch_call_dict.get("summary_dump")),
        exception=ch_call_dict.get("exception"),
        wb_run_id=ch_call_dict.get("wb_run_id"),
        wb_user_id=ch_call_dict.get("wb_user_id"),
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
        created_datetime=_ensure_datetimes_have_tz(ch_obj.created_datetime),
        version_index=ch_obj.version_index,
    )


def _start_call_for_insert_to_ch_insertable_start_call(
    start_call: tsi.StartedCallSchemaForInsert,
) -> CallStartCHInsertable:
    # Note: it is technically possible for the user to mess up and provide the
    # wrong trace id (one that does not match the parent_id)!
    call_id = start_call.id or generate_id()
    trace_id = start_call.trace_id or generate_id()
    return CallStartCHInsertable(
        project_id=start_call.project_id,
        id=call_id,
        trace_id=trace_id,
        parent_id=start_call.parent_id,
        name=start_call.name,
        start_datetime=start_call.start_datetime,
        attributes_dump=_dict_value_to_dump(start_call.attributes),
        inputs_dump=_dict_value_to_dump(start_call.inputs),
        input_refs=extract_refs_from_values(list(start_call.inputs.values())),
        wb_run_id=start_call.wb_run_id,
        wb_user_id=start_call.wb_user_id,
    )


def _end_call_for_insert_to_ch_insertable_end_call(
    end_call: tsi.EndedCallSchemaForInsert,
) -> CallEndCHInsertable:
    # Note: it is technically possible for the user to mess up and provide the
    # wrong trace id (one that does not match the parent_id)!
    return CallEndCHInsertable(
        project_id=end_call.project_id,
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
