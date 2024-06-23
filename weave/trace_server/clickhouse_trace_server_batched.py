# Clickhouse Trace Server

# A note on query structure:
# There are four major kinds of things that we query:
# - calls,
# - object_versions,
# - tables
# - files
#
# calls are identified by ID.
#
# object_versions, tables, and files are identified by digest. For these kinds of
# things, we dedupe at merge time using Clickhouse's ReplacingMergeTree, but we also
# need to dedupe at query time.
#
# Previously, we did query time deduping in *_deduped VIEWs. But it turns out
# clickhouse doesn't push down the project_id predicate into those views, so we were
# always scanning whole tables.
#
# Now, we've just written the what were views before into this file directly as
# subqueries, and put the project_id predicate in the innermost subquery, which fixes
# the problem.


import dataclasses
import datetime
import hashlib
import json
import logging
import threading
import typing
from collections import defaultdict
from contextlib import contextmanager
from zoneinfo import ZoneInfo

import clickhouse_connect
import emoji
from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.query import QueryResult
from clickhouse_connect.driver.summary import QuerySummary
from pydantic import BaseModel

from weave.trace_server.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
    combine_conditions,
)

from . import clickhouse_trace_server_migrator as wf_migrator
from . import environment as wf_env
from . import refs_internal
from . import trace_server_interface as tsi
from .emoji_util import detone_emojis
from .errors import InvalidRequest, RequestTooLarge
from .feedback import (
    TABLE_FEEDBACK,
    validate_feedback_create_req,
    validate_feedback_purge_req,
)
from .orm import ParamBuilder, Row
from .trace_server_interface_util import (
    assert_non_null_wb_user_id,
    bytes_digest,
    extract_refs_from_values,
    generate_id,
    str_digest,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_FLUSH_COUNT = 10000
MAX_FLUSH_AGE = 15

FILE_CHUNK_SIZE = 100000

MAX_DELETE_CALLS_COUNT = 100


class NotFoundError(Exception):
    pass


class CallStartCHInsertable(BaseModel):
    project_id: str
    id: str
    trace_id: str
    parent_id: typing.Optional[str] = None
    op_name: str
    started_at: datetime.datetime
    attributes_dump: str
    inputs_dump: str
    input_refs: typing.List[str]
    output_refs: typing.List[str] = []  # sadly, this is required
    display_name: typing.Optional[str] = None

    wb_user_id: typing.Optional[str] = None
    wb_run_id: typing.Optional[str] = None


class CallEndCHInsertable(BaseModel):
    project_id: str
    id: str
    ended_at: datetime.datetime
    exception: typing.Optional[str] = None
    summary_dump: str
    output_dump: str
    input_refs: typing.List[str] = []  # sadly, this is required
    output_refs: typing.List[str]


class CallDeleteCHInsertable(BaseModel):
    project_id: str
    id: str
    wb_user_id: str

    deleted_at: datetime.datetime

    # required types
    input_refs: typing.List[str] = []
    output_refs: typing.List[str] = []


class CallUpdateCHInsertable(BaseModel):
    project_id: str
    id: str
    wb_user_id: str

    # update types
    display_name: typing.Optional[str] = None

    # required types
    input_refs: typing.List[str] = []
    output_refs: typing.List[str] = []


CallCHInsertable = typing.Union[
    CallStartCHInsertable,
    CallEndCHInsertable,
    CallDeleteCHInsertable,
    CallUpdateCHInsertable,
]


# Very critical that this matches the calls table schema! This should
# essentially be the DB version of CallSchema with the addition of the
# created_at and updated_at fields
class SelectableCHCallSchema(BaseModel):
    project_id: str
    id: str

    op_name: str
    display_name: typing.Optional[str] = None

    trace_id: str
    parent_id: typing.Optional[str] = None

    started_at: datetime.datetime
    ended_at: typing.Optional[datetime.datetime] = None
    exception: typing.Optional[str] = None

    attributes_dump: str
    inputs_dump: str
    output_dump: typing.Optional[str] = None
    summary_dump: typing.Optional[str] = None

    input_refs: typing.List[str]
    output_refs: typing.List[str]

    wb_user_id: typing.Optional[str] = None
    wb_run_id: typing.Optional[str] = None

    deleted_at: typing.Optional[datetime.datetime] = None


all_call_insert_columns = list(
    CallStartCHInsertable.model_fields.keys()
    | CallEndCHInsertable.model_fields.keys()
    | CallDeleteCHInsertable.model_fields.keys()
    | CallUpdateCHInsertable.model_fields.keys()
)

all_call_select_columns = list(SelectableCHCallSchema.model_fields.keys())
all_call_json_columns = ("inputs", "output", "attributes", "summary")


# Let's just make everything required for now ... can optimize when we implement column selection
required_call_columns = list(set(all_call_select_columns) - set([]))


# Columns in the calls_merged table with special aggregation functions:
call_select_raw_columns = ["id", "project_id"]  # no aggregation
call_select_arrays_columns = ["input_refs", "output_refs"]  # array_concat_agg
call_select_argmax_columns = ["display_name"]  # argMaxMerge
# all others use `any`


class ObjCHInsertable(BaseModel):
    project_id: str
    kind: str
    base_object_class: typing.Optional[str]
    object_id: str
    refs: typing.List[str]
    val_dump: str
    digest: str


class SelectableCHObjSchema(BaseModel):
    project_id: str
    object_id: str
    created_at: datetime.datetime
    refs: typing.List[str]
    val_dump: str
    kind: str
    base_object_class: typing.Optional[str]
    digest: str
    version_index: int
    is_latest: int


all_obj_select_columns = list(SelectableCHObjSchema.model_fields.keys())
all_obj_insert_columns = list(ObjCHInsertable.model_fields.keys())

# Let's just make everything required for now ... can optimize when we implement column selection
required_obj_select_columns = list(set(all_obj_select_columns) - set([]))


class ClickHouseTraceServer(tsi.TraceServerInterface):
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
        self._thread_local = threading.local()
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
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
        res = self.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=req.project_id,
                filter=tsi._CallsFilter(
                    call_ids=[req.id],
                ),
                limit=1,
            )
        )
        return tsi.CallReadRes(call=next(res))

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        stream = self.calls_query_stream(req)
        return tsi.CallsQueryRes(calls=list(stream))

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        """Returns a stats object for the given query. This is useful for counts or other
        aggregate statistics that are not directly queryable from the calls themselves.
        """
        cq = CallsQuery(project_id=req.project_id)

        cq.add_field("id")
        if req.filter is not None:
            cq.set_hardcoded_filter(HardCodedFilter(filter=req.filter))
        if req.query is not None:
            cq.add_condition(req.query.expr_)

        pb = ParamBuilder()
        inner_query = cq.as_sql(pb)
        raw_res = self._query(
            f"SELECT count() FROM ({inner_query})",
            pb.get_params(),
        )
        rows = raw_res.result_rows
        count = 0
        if rows and len(rows) == 1 and len(rows[0]) == 1:
            count = rows[0][0]
        return tsi.CallsQueryStatsRes(count=count)

    def calls_query_stream(
        self, req: tsi.CallsQueryReq
    ) -> typing.Iterator[tsi.CallSchema]:
        """Returns a stream of calls that match the given query."""
        cq = CallsQuery(project_id=req.project_id)

        # TODO (Perf): By allowing a sub-selection of columns
        # we will gain increased performance by not having to
        # fetch all columns from the database. Currently all use
        # cases call for every column to be fetched, so we have not
        # implemented this yet.
        columns = all_call_select_columns
        for col in columns:
            cq.add_field(col)
        if req.filter is not None:
            cq.set_hardcoded_filter(HardCodedFilter(filter=req.filter))
        if req.query is not None:
            cq.add_condition(req.query.expr_)

        # Sort with empty list results in no sorting
        if req.sort_by is not None:
            for sort_by in req.sort_by:
                cq.add_order(sort_by.field, sort_by.direction)
        else:
            cq.add_order("started_at", "asc")
        if req.limit is not None:
            cq.set_limit(req.limit)
        if req.offset is not None:
            cq.set_offset(req.offset)

        pb = ParamBuilder()
        raw_res = self._query_stream(
            cq.as_sql(pb),
            pb.get_params(),
        )

        for row in raw_res:
            yield tsi.CallSchema.model_validate(
                _ch_call_dict_to_call_schema_dict(dict(zip(columns, row)))
            )

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        assert_non_null_wb_user_id(req)
        if len(req.call_ids) > MAX_DELETE_CALLS_COUNT:
            raise RequestTooLarge(
                f"Cannot delete more than {MAX_DELETE_CALLS_COUNT} calls at once"
            )

        # Note: i think this project condition is redundant
        proj_cond = "calls_merged.project_id = {project_id: String}"
        proj_params = {"project_id": req.project_id}

        # get all parents
        parents = list(
            self.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=req.project_id,
                    filter=tsi._CallsFilter(
                        call_ids=req.call_ids,
                    ),
                )
            )
        )

        # get all calls with trace_ids matching parents
        all_calls = list(
            self.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=req.project_id,
                    filter=tsi._CallsFilter(
                        trace_ids=[p.trace_id for p in parents],
                    ),
                )
            )
        )

        all_descendants = find_call_descendants(
            root_ids=req.call_ids,
            all_calls=all_calls,
        )

        deleted_at = datetime.datetime.now()
        insertables = [
            CallDeleteCHInsertable(
                project_id=req.project_id,
                id=call_id,
                wb_user_id=req.wb_user_id,
                deleted_at=deleted_at,
            )
            for call_id in all_descendants
        ]

        with self.call_batch():
            for insertable in insertables:
                self._insert_call(insertable)

        return tsi.CallsDeleteRes()

    def _ensure_valid_update_field(self, req: tsi.CallUpdateReq) -> None:
        valid_update_fields = ["display_name"]
        for field in valid_update_fields:
            if getattr(req, field, None) is not None:
                return

        raise ValueError(
            f"One of [{', '.join(valid_update_fields)}] is required for call update"
        )

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        assert_non_null_wb_user_id(req)
        self._ensure_valid_update_field(req)
        renamed_insertable = CallUpdateCHInsertable(
            project_id=req.project_id,
            id=req.call_id,
            wb_user_id=req.wb_user_id,
            display_name=req.display_name,
        )
        self._insert_call(renamed_insertable)

        return tsi.CallUpdateRes()

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        raise NotImplementedError()

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        conds = [
            "object_id = {name: String}",
            "digest = {version_hash: String}",
            "is_op = 1",
        ]
        parameters = {"name": req.name, "digest": req.digest}
        objs = self._select_objs_query(
            req.project_id, conditions=conds, parameters=parameters
        )
        if len(objs) == 0:
            raise NotFoundError(f"Obj {req.name}:{req.digest} not found")

        return tsi.OpReadRes(op_obj=_ch_obj_to_obj_schema(objs[0]))

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        parameters = {}
        conds: typing.List[str] = ["is_op = 1"]
        if req.filter:
            if req.filter.op_names:
                conds.append("object_id IN {op_names: Array(String)}")
                parameters["op_names"] = req.filter.op_names

            if req.filter.latest_only:
                conds.append("is_latest = 1")

        ch_objs = self._select_objs_query(
            req.project_id,
            conditions=conds,
        )
        objs = [_ch_obj_to_obj_schema(call) for call in ch_objs]
        return tsi.OpQueryRes(op_objs=objs)

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        json_val = json.dumps(req.obj.val)
        digest = str_digest(json_val)

        req_obj = req.obj
        ch_obj = ObjCHInsertable(
            project_id=req_obj.project_id,
            object_id=req_obj.object_id,
            kind=get_kind(req.obj.val),
            base_object_class=get_base_object_class(req.obj.val),
            refs=extract_refs_from_values(req.obj.val),
            val_dump=json_val,
            digest=digest,
        )

        self._insert(
            "object_versions",
            data=[list(ch_obj.model_dump().values())],
            column_names=list(ch_obj.model_fields.keys()),
        )
        return tsi.ObjCreateRes(digest=digest)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        conds = ["object_id = {object_id: String}"]
        parameters: typing.Dict[str, typing.Union[str, int]] = {
            "object_id": req.object_id
        }
        if req.digest == "latest":
            conds.append("is_latest = 1")
        else:
            (is_version, version_index) = _digest_is_version_like(req.digest)
            if is_version:
                conds.append("version_index = {version_index: UInt64}")
                parameters["version_index"] = version_index
            else:
                conds.append("digest = {version_digest: String}")
                parameters["version_digest"] = req.digest
        objs = self._select_objs_query(
            req.project_id, conditions=conds, parameters=parameters
        )
        if len(objs) == 0:
            raise NotFoundError(f"Obj {req.object_id}:{req.digest} not found")

        return tsi.ObjReadRes(obj=_ch_obj_to_obj_schema(objs[0]))

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        conds: list[str] = []
        parameters = {}
        if req.filter:
            if req.filter.is_op is not None:
                if req.filter.is_op:
                    conds.append("is_op = 1")
                else:
                    conds.append("is_op = 0")
            if req.filter.object_ids:
                conds.append("object_id IN {object_ids: Array(String)}")
                parameters["object_ids"] = req.filter.object_ids
            if req.filter.latest_only:
                conds.append("is_latest = 1")
            if req.filter.base_object_classes:
                conds.append(
                    "base_object_class IN {base_object_classes: Array(String)}"
                )
                parameters["base_object_classes"] = req.filter.base_object_classes

        objs = self._select_objs_query(
            req.project_id,
            conditions=conds,
            parameters=parameters,
        )

        return tsi.ObjQueryRes(objs=[_ch_obj_to_obj_schema(obj) for obj in objs])

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        insert_rows = []
        for r in req.table.rows:
            if not isinstance(r, dict):
                raise ValueError(
                    f"""Validation Error: Encountered a non-dictionary row when creating a table. Please ensure that all rows are dictionaries. Violating row:\n{r}."""
                )
            row_json = json.dumps(r)
            row_digest = str_digest(row_json)
            insert_rows.append(
                (
                    req.table.project_id,
                    row_digest,
                    extract_refs_from_values(r),
                    row_json,
                )
            )

        self._insert(
            "table_rows",
            data=insert_rows,
            column_names=["project_id", "digest", "refs", "val_dump"],
        )

        row_digests = [r[1] for r in insert_rows]

        table_hasher = hashlib.sha256()
        for row_digest in row_digests:
            table_hasher.update(row_digest.encode())
        digest = table_hasher.hexdigest()

        self._insert(
            "tables",
            data=[(req.table.project_id, digest, row_digests)],
            column_names=["project_id", "digest", "row_digests"],
        )
        return tsi.TableCreateRes(digest=digest)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        conds = []
        parameters = {}
        if req.filter:
            if req.filter.row_digests:
                conds.append("tr.digest IN {row_digets: Array(String)}")
                parameters["row_digests"] = req.filter.row_digests
        else:
            conds.append("1 = 1")
        rows = self._table_query(
            req.project_id,
            req.digest,
            conditions=conds,
            limit=req.limit,
            offset=req.offset,
        )
        return tsi.TableQueryRes(rows=rows)

    def _table_query(
        self,
        project_id: str,
        digest: str,
        conditions: typing.Optional[typing.List[str]] = None,
        limit: typing.Optional[int] = None,
        offset: typing.Optional[int] = None,
        parameters: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.List[tsi.TableRowSchema]:
        conds = ["project_id = {project_id: String}"]
        if conditions:
            conds.extend(conditions)

        predicate = combine_conditions(conds, "AND")
        # The subqueries are for deduplication of table rows and tables by digest.
        # It might be more efficient to do deduplication of table rows
        # in the outer query instead of the right side of the JOIN clause here,
        # that hasn't been tested yet.
        query = f"""
                SELECT tr.digest, tr.val_dump
                FROM (
                    SELECT project_id, row_digest
                    FROM (
                        SELECT *
                        FROM (
                                SELECT *,
                                    row_number() OVER (PARTITION BY project_id, digest) AS rn
                                FROM tables
                                WHERE project_id = {{project_id:String}} AND digest = {{digest:String}}
                            )
                        WHERE rn = 1
                        ORDER BY project_id, digest
                    )
                    ARRAY JOIN row_digests AS row_digest
                    WHERE digest = {{digest:String}}
                ) AS t
                JOIN (
                    SELECT project_id, digest, val_dump
                    FROM (
                            SELECT *,
                                row_number() OVER (PARTITION BY project_id, digest) AS rn
                            FROM table_rows
                            WHERE project_id = {{project_id:String}}
                        )
                    WHERE rn = 1
                    ORDER BY project_id, digest
                ) tr ON t.project_id = tr.project_id AND t.row_digest = tr.digest
                WHERE {predicate}
            """
        if parameters is None:
            parameters = {}
        if limit:
            query += " LIMIT {limit: UInt64}"
            parameters["limit"] = limit
        if offset:
            query += " OFFSET {offset: UInt64}"
            parameters["offset"] = offset

        query_result = self.ch_client.query(
            query,
            parameters={
                "project_id": project_id,
                "digest": digest,
                **parameters,
            },
        )

        return [
            tsi.TableRowSchema(digest=r[0], val=json.loads(r[1]))
            for r in query_result.result_rows
        ]

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        # TODO: This reads one ref at a time, it should read them in batches
        # where it can. Like it should group by object that we need to read.
        # And it should also batch into table refs (like when we are reading a bunch
        # of rows from a single Dataset)
        if len(req.refs) > 1000:
            raise ValueError("Too many refs")

        parsed_raw_refs = [refs_internal.parse_internal_uri(r) for r in req.refs]
        if any(isinstance(r, refs_internal.InternalTableRef) for r in parsed_raw_refs):
            raise ValueError("Table refs not supported")
        parsed_refs = typing.cast(
            typing.List[refs_internal.InternalObjectRef], parsed_raw_refs
        )

        root_val_cache: typing.Dict[str, typing.Any] = {}

        def make_ref_cache_key(ref: refs_internal.InternalObjectRef) -> str:
            return f"{ref.project_id}/{ref.name}/{ref.version}"

        def make_obj_cache_key(obj: SelectableCHObjSchema) -> str:
            return f"{obj.project_id}/{obj.object_id}/{obj.digest}"

        def get_object_refs_root_val(
            refs: list[refs_internal.InternalObjectRef],
        ) -> typing.Any:
            conds = []
            parameters = {}
            for ref_index, ref in enumerate(refs):
                if ref.version == "latest":
                    raise ValueError("Reading refs with `latest` is not supported")

                cache_key = make_ref_cache_key(ref)

                if cache_key in root_val_cache:
                    continue

                object_id_param_key = "object_id_" + str(ref_index)
                version_param_key = "version_" + str(ref_index)
                conds.append(
                    f"object_id = {{{object_id_param_key}: String}} AND digest = {{{version_param_key}: String}}"
                )
                parameters[object_id_param_key] = ref.name
                parameters[version_param_key] = ref.version

            if len(conds) > 0:
                conditions = [combine_conditions(conds, "OR")]
                objs = self._select_objs_query(
                    ref.project_id, conditions=conditions, parameters=parameters
                )
                for obj in objs:
                    root_val_cache[make_obj_cache_key(obj)] = json.loads(obj.val_dump)

            return [root_val_cache[make_ref_cache_key(ref)] for ref in refs]

        # Represents work left to do for resolving a ref
        @dataclasses.dataclass
        class PartialRefResult:
            remaining_extra: list[str]
            # unresolved_obj_ref and unresolved_table_ref are mutually exclusive
            unresolved_obj_ref: typing.Optional[refs_internal.InternalObjectRef]
            unresolved_table_ref: typing.Optional[refs_internal.InternalTableRef]
            val: typing.Any

        def resolve_extra(extra: list[str], val: typing.Any) -> typing.Any:
            for extra_index in range(0, len(extra), 2):
                op, arg = extra[extra_index], extra[extra_index + 1]
                if isinstance(val, str) and val.startswith(
                    refs_internal.WEAVE_INTERNAL_SCHEME + "://"
                ):
                    parsed_ref = refs_internal.parse_internal_uri(val)
                    if isinstance(parsed_ref, refs_internal.InternalObjectRef):
                        return PartialRefResult(
                            remaining_extra=extra[extra_index:],
                            unresolved_obj_ref=parsed_ref,
                            unresolved_table_ref=None,
                            val=val,
                        )
                    elif isinstance(parsed_ref, refs_internal.InternalTableRef):
                        return PartialRefResult(
                            remaining_extra=extra[extra_index:],
                            unresolved_obj_ref=None,
                            unresolved_table_ref=parsed_ref,
                            val=val,
                        )
                if val is None:
                    return PartialRefResult(
                        remaining_extra=[],
                        unresolved_obj_ref=None,
                        unresolved_table_ref=None,
                        val=None,
                    )
                if op == refs_internal.DICT_KEY_EDGE_NAME:
                    val = val.get(arg)
                elif op == refs_internal.OBJECT_ATTR_EDGE_NAME:
                    val = val.get(arg)
                elif op == refs_internal.LIST_INDEX_EDGE_NAME:
                    index = int(arg)
                    if index >= len(val):
                        return None
                    val = val[index]
                else:
                    raise ValueError(f"Unknown ref type: {extra[extra_index]}")
            return PartialRefResult(
                remaining_extra=[],
                unresolved_obj_ref=None,
                unresolved_table_ref=None,
                val=val,
            )

        # Initialize the results with the parsed refs
        extra_results = [
            PartialRefResult(
                remaining_extra=[],
                unresolved_obj_ref=ref,
                unresolved_table_ref=None,
                val=None,
            )
            for ref in parsed_refs
        ]

        # Loop until there is nothing left to resolve
        while (
            any(r.unresolved_obj_ref is not None for r in extra_results)
            or any(r.unresolved_table_ref is not None for r in extra_results)
            or any(r.remaining_extra for r in extra_results)
        ):
            # Resolve any unresolved object refs
            needed_extra_results: list[typing.Tuple[int, PartialRefResult]] = []
            for i, extra_result in enumerate(extra_results):
                if extra_result.unresolved_obj_ref is not None:
                    needed_extra_results.append((i, extra_result))

            if len(needed_extra_results) > 0:
                refs: list[refs_internal.InternalObjectRef] = []
                for i, extra_result in needed_extra_results:
                    if extra_result.unresolved_obj_ref is None:
                        raise ValueError("Expected unresolved obj ref")
                    refs.append(extra_result.unresolved_obj_ref)
                obj_roots = get_object_refs_root_val(refs)
                for (i, extra_result), obj_root in zip(needed_extra_results, obj_roots):
                    if extra_result.unresolved_obj_ref is None:
                        raise ValueError("Expected unresolved obj ref")
                    extra_results[i] = PartialRefResult(
                        remaining_extra=extra_result.unresolved_obj_ref.extra,
                        val=obj_root,
                        unresolved_obj_ref=None,
                        unresolved_table_ref=None,
                    )

            # Resolve any unresolved table refs
            # First batch the table queries by project_id and table digest
            table_queries: dict[
                typing.Tuple[str, str], list[typing.Tuple[int, str]]
            ] = {}
            for i, extra_result in enumerate(extra_results):
                if extra_result.unresolved_table_ref is not None:
                    table_ref = extra_result.unresolved_table_ref
                    if not extra_result.remaining_extra:
                        raise ValueError("Table refs must have id extra")
                    op, row_digest = (
                        extra_result.remaining_extra[0],
                        extra_result.remaining_extra[1],
                    )
                    if op != refs_internal.TABLE_ROW_ID_EDGE_NAME:
                        raise ValueError("Table refs must have id extra")
                    table_queries.setdefault(
                        (table_ref.project_id, table_ref.digest), []
                    ).append((i, row_digest))
            # Make the queries
            for (project_id, digest), index_digests in table_queries.items():
                row_digests = [d for i, d in index_digests]
                rows = self._table_query(
                    project_id=project_id,
                    digest=digest,
                    conditions=["digest IN {digests: Array(String)}"],
                    parameters={"digests": row_digests},
                )
                # Unpack the results into the target rows
                row_digest_vals = {r.digest: r.val for r in rows}
                for index, row_digest in index_digests:
                    extra_results[index] = PartialRefResult(
                        remaining_extra=extra_results[index].remaining_extra[2:],
                        val=row_digest_vals[row_digest],
                        unresolved_obj_ref=None,
                        unresolved_table_ref=None,
                    )

            # Resolve any remaining extras, possibly producing more unresolved refs
            for i, extra_result in enumerate(extra_results):
                if extra_result.remaining_extra:
                    extra_results[i] = resolve_extra(
                        extra_result.remaining_extra, extra_result.val
                    )

        return tsi.RefsReadBatchRes(vals=[r.val for r in extra_results])

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        digest = bytes_digest(req.content)
        chunks = [
            req.content[i : i + FILE_CHUNK_SIZE]
            for i in range(0, len(req.content), FILE_CHUNK_SIZE)
        ]
        self._insert(
            "files",
            data=[
                (
                    req.project_id,
                    digest,
                    i,
                    len(chunks),
                    req.name,
                    chunk,
                )
                for i, chunk in enumerate(chunks)
            ],
            column_names=[
                "project_id",
                "digest",
                "chunk_index",
                "n_chunks",
                "name",
                "val_bytes",
            ],
        )
        return tsi.FileCreateRes(digest=digest)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        # The subquery is responsible for deduplication of file chunks by digest
        query_result = self.ch_client.query(
            """
            SELECT n_chunks, val_bytes
            FROM (
                SELECT *
                FROM (
                        SELECT *,
                            row_number() OVER (PARTITION BY project_id, digest, chunk_index) AS rn
                        FROM files
                        WHERE project_id = {project_id:String} AND digest = {digest:String}
                    )
                WHERE rn = 1
                ORDER BY project_id, digest, chunk_index
            )
            WHERE project_id = {project_id:String} AND digest = {digest:String}""",
            parameters={"project_id": req.project_id, "digest": req.digest},
            column_formats={"val_bytes": "bytes"},
        )
        n_chunks = query_result.result_rows[0][0]
        chunks = [r[1] for r in query_result.result_rows]
        if len(chunks) != n_chunks:
            raise ValueError("Missing chunks")
        return tsi.FileContentReadRes(content=b"".join(chunks))

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        assert_non_null_wb_user_id(req)
        validate_feedback_create_req(req)

        # Augment emoji with alias.
        res_payload = {}
        if req.feedback_type == "wandb.reaction.1":
            em = req.payload["emoji"]
            if emoji.emoji_count(em) != 1:
                raise InvalidRequest(
                    "Value of emoji key in payload must be exactly one emoji"
                )
            req.payload["alias"] = emoji.demojize(em)
            detoned = detone_emojis(em)
            req.payload["detoned"] = detoned
            req.payload["detoned_alias"] = emoji.demojize(detoned)
            res_payload = req.payload

        feedback_id = generate_id()
        created_at = datetime.datetime.now(ZoneInfo("UTC"))
        # TODO: Any validation on weave_ref?
        payload = _dict_value_to_dump(req.payload)
        MAX_PAYLOAD = 1024
        if len(payload) > MAX_PAYLOAD:
            raise InvalidRequest("Feedback payload too large")
        row: Row = {
            "id": feedback_id,
            "project_id": req.project_id,
            "weave_ref": req.weave_ref,
            "wb_user_id": req.wb_user_id,
            "creator": req.creator,
            "feedback_type": req.feedback_type,
            "payload": req.payload,
            "created_at": created_at,
        }
        prepared = TABLE_FEEDBACK.insert(row).prepare(database_type="clickhouse")
        self._insert(TABLE_FEEDBACK.name, prepared.data, prepared.column_names)
        return tsi.FeedbackCreateRes(
            id=feedback_id,
            created_at=created_at,
            wb_user_id=req.wb_user_id,
            payload=res_payload,
        )

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        query = TABLE_FEEDBACK.select()
        query = query.project_id(req.project_id)
        query = query.fields(req.fields)
        query = query.where(req.query)
        query = query.order_by(req.sort_by)
        query = query.limit(req.limit).offset(req.offset)
        prepared = query.prepare(database_type="clickhouse")
        query_result = self.ch_client.query(prepared.sql, prepared.parameters)
        result = TABLE_FEEDBACK.tuples_to_rows(
            query_result.result_rows, prepared.fields
        )
        return tsi.FeedbackQueryRes(result=result)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        # TODO: Instead of passing conditions to DELETE FROM,
        #       should we select matching ids, and then DELETE FROM WHERE id IN (...)?
        #       This would allow us to return the number of rows deleted, and complain
        #       if too many things would be deleted.
        validate_feedback_purge_req(req)
        query = TABLE_FEEDBACK.purge()
        query = query.project_id(req.project_id)
        query = query.where(req.query)
        prepared = query.prepare(database_type="clickhouse")
        self.ch_client.query(prepared.sql, prepared.parameters)
        return tsi.FeedbackPurgeRes()

    # Private Methods
    @property
    def ch_client(self) -> CHClient:
        if not hasattr(self._thread_local, "ch_client"):
            self._thread_local.ch_client = self._mint_client()
        return self._thread_local.ch_client

    def _mint_client(self) -> CHClient:
        client = clickhouse_connect.get_client(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            secure=self._port == 8443,
        )
        # Safely create the database if it does not exist
        client.command(f"CREATE DATABASE IF NOT EXISTS {self._database}")
        client.database = self._database
        return client

    # def __del__(self) -> None:
    #     self.ch_client.close()

    def _insert_call_batch(self, batch: typing.List) -> None:
        if batch:
            settings = {}
            if self._use_async_insert:
                settings["async_insert"] = 1
                settings["wait_for_async_insert"] = 0
            self._insert(
                "call_parts",
                data=batch,
                column_names=all_call_insert_columns,
                settings=settings,
            )

    def _select_objs_query(
        self,
        project_id: str,
        conditions: typing.Optional[typing.List[str]] = None,
        limit: typing.Optional[int] = None,
        parameters: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.List[SelectableCHObjSchema]:
        if not conditions:
            conditions = ["1 = 1"]

        conditions_part = combine_conditions(conditions, "AND")

        limit_part = ""
        if limit != None:
            limit_part = f"LIMIT {limit}"

        if parameters is None:
            parameters = {}
        # The subquery is for deduplication of object versions by digest
        query_result = self._query_stream(
            f"""
            SELECT
                project_id,
                object_id,
                created_at,
                kind,
                base_object_class,
                refs,
                val_dump,
                digest,
                is_op,
                _version_index_plus_1,
                version_index,
                version_count,
                is_latest
            FROM (
                SELECT project_id,
                    object_id,
                    created_at,
                    kind,
                    base_object_class,
                    refs,
                    val_dump,
                    digest,
                    if (kind = 'op', 1, 0) AS is_op,
                    row_number() OVER (
                        PARTITION BY project_id,
                        kind,
                        object_id
                        ORDER BY created_at ASC
                    ) AS _version_index_plus_1,
                    _version_index_plus_1 - 1 AS version_index,
                    count(*) OVER (PARTITION BY project_id, kind, object_id) as version_count,
                    if(_version_index_plus_1 = version_count, 1, 0) AS is_latest
                FROM (
                    SELECT *,
                        row_number() OVER (
                            PARTITION BY project_id,
                            kind,
                            object_id,
                            digest
                            ORDER BY created_at ASC
                        ) AS rn
                    FROM object_versions
                    WHERE project_id = {{project_id: String}}
                )
                WHERE rn = 1
            )
            WHERE project_id = {{project_id: String}} AND
                {conditions_part}
            {limit_part}
        """,
            {"project_id": project_id, **parameters},
        )
        result: typing.List[SelectableCHObjSchema] = []
        for row in query_result:
            result.append(
                SelectableCHObjSchema.model_validate(
                    dict(
                        zip(
                            [
                                "project_id",
                                "object_id",
                                "created_at",
                                "kind",
                                "base_object_class",
                                "refs",
                                "val_dump",
                                "digest",
                                "is_op",
                                "_version_index_plus_1",
                                "version_index",
                                "version_count",
                                "is_latest",
                            ],
                            row,
                        )
                    )
                )
            )

        return result

    def _run_migrations(self) -> None:
        logger.info("Running migrations")
        migrator = wf_migrator.ClickHouseTraceServerMigrator(self._mint_client())
        migrator.apply_migrations(self._database)

    def _query_stream(
        self,
        query: str,
        parameters: typing.Dict[str, typing.Any],
        column_formats: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.Iterator[QueryResult]:
        """Streams the results of a query from the database."""
        summary = None
        parameters = _process_parameters(parameters)
        with self.ch_client.query_rows_stream(
            query, parameters=parameters, column_formats=column_formats, use_none=True
        ) as stream:
            if isinstance(stream.source, QueryResult):
                summary = stream.source.summary
            logger.info(
                "clickhouse_stream_query",
                extra={
                    "query": query,
                    "parameters": parameters,
                    "summary": summary,
                },
            )
            for row in stream:
                yield row

    def _query(
        self,
        query: str,
        parameters: typing.Dict[str, typing.Any],
        column_formats: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> QueryResult:
        """Directly queries the database and returns the result."""
        parameters = _process_parameters(parameters)
        res = self.ch_client.query(
            query, parameters=parameters, column_formats=column_formats, use_none=True
        )
        logger.info(
            "clickhouse_query",
            extra={
                "query": query,
                "parameters": parameters,
                "summary": res.summary,
            },
        )
        return res

    def _insert(
        self,
        table: str,
        data: typing.Sequence[typing.Sequence[typing.Any]],
        column_names: typing.List[str],
        settings: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> QuerySummary:
        try:
            return self.ch_client.insert(
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


def _dict_value_to_dump(
    value: dict,
) -> str:
    if not isinstance(value, dict):
        raise ValueError(f"Value is not a dict: {value}")
    return json.dumps(value)


def _any_value_to_dump(
    value: typing.Any,
) -> str:
    return json.dumps(value)


def _dict_dump_to_dict(val: str) -> typing.Dict[str, typing.Any]:
    res = json.loads(val)
    if not isinstance(res, dict):
        raise ValueError(f"Value is not a dict: {val}")
    return res


def _any_dump_to_any(val: str) -> typing.Any:
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


def _nullable_any_dump_to_any(
    val: typing.Optional[str],
) -> typing.Optional[typing.Any]:
    return _any_dump_to_any(val) if val else None


def _raw_call_dict_to_ch_call(
    call: typing.Dict[str, typing.Any],
) -> SelectableCHCallSchema:
    return SelectableCHCallSchema.model_validate(call)


def _empty_str_to_none(val: typing.Optional[str]) -> typing.Optional[str]:
    return val if val != "" else None


def _ch_call_to_call_schema(ch_call: SelectableCHCallSchema) -> tsi.CallSchema:
    return tsi.CallSchema(
        project_id=ch_call.project_id,
        id=ch_call.id,
        trace_id=ch_call.trace_id,
        parent_id=ch_call.parent_id,
        op_name=ch_call.op_name,
        started_at=_ensure_datetimes_have_tz(ch_call.started_at),
        ended_at=_ensure_datetimes_have_tz(ch_call.ended_at),
        attributes=_dict_dump_to_dict(ch_call.attributes_dump),
        inputs=_dict_dump_to_dict(ch_call.inputs_dump),
        output=_nullable_any_dump_to_any(ch_call.output_dump),
        summary=_nullable_dict_dump_to_dict(ch_call.summary_dump),
        exception=ch_call.exception,
        wb_run_id=ch_call.wb_run_id,
        wb_user_id=ch_call.wb_user_id,
        display_name=_empty_str_to_none(ch_call.display_name),
    )


# Keep in sync with `_ch_call_to_call_schema`. This copy is for performance
def _ch_call_dict_to_call_schema_dict(ch_call_dict: typing.Dict) -> typing.Dict:
    return dict(
        project_id=ch_call_dict.get("project_id"),
        id=ch_call_dict.get("id"),
        trace_id=ch_call_dict.get("trace_id"),
        parent_id=ch_call_dict.get("parent_id"),
        op_name=ch_call_dict.get("op_name"),
        started_at=_ensure_datetimes_have_tz(ch_call_dict.get("started_at")),
        ended_at=_ensure_datetimes_have_tz(ch_call_dict.get("ended_at")),
        attributes=_dict_dump_to_dict(ch_call_dict["attributes_dump"]),
        inputs=_dict_dump_to_dict(ch_call_dict["inputs_dump"]),
        output=_nullable_any_dump_to_any(ch_call_dict.get("output_dump")),
        summary=_nullable_dict_dump_to_dict(ch_call_dict.get("summary_dump")),
        exception=ch_call_dict.get("exception"),
        wb_run_id=ch_call_dict.get("wb_run_id"),
        wb_user_id=ch_call_dict.get("wb_user_id"),
        display_name=_empty_str_to_none(ch_call_dict.get("display_name")),
    )


def _ch_obj_to_obj_schema(ch_obj: SelectableCHObjSchema) -> tsi.ObjSchema:
    return tsi.ObjSchema(
        project_id=ch_obj.project_id,
        object_id=ch_obj.object_id,
        created_at=_ensure_datetimes_have_tz(ch_obj.created_at),
        version_index=ch_obj.version_index,
        is_latest=ch_obj.is_latest,
        digest=ch_obj.digest,
        kind=ch_obj.kind,
        base_object_class=ch_obj.base_object_class,
        val=json.loads(ch_obj.val_dump),
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
        op_name=start_call.op_name,
        started_at=start_call.started_at,
        attributes_dump=_dict_value_to_dump(start_call.attributes),
        inputs_dump=_dict_value_to_dump(start_call.inputs),
        input_refs=extract_refs_from_values(start_call.inputs),
        wb_run_id=start_call.wb_run_id,
        wb_user_id=start_call.wb_user_id,
        display_name=start_call.display_name,
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
        ended_at=end_call.ended_at,
        summary_dump=_dict_value_to_dump(end_call.summary),
        output_dump=_any_value_to_dump(end_call.output),
        output_refs=extract_refs_from_values(end_call.output),
    )


def _process_parameters(
    parameters: typing.Dict[str, typing.Any],
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


# def _partial_obj_schema_to_ch_obj(
#     partial_obj: tsi.ObjSchemaForInsert,
# ) -> ObjCHInsertable:
#     version_hash = version_hash_for_object(partial_obj)

#     return ObjCHInsertable(
#         id=uuid.uuid4(),
#         project_id=partial_obj.project_id,
#         name=partial_obj.name,
#         type="unknown",
#         refs=[],
#         val=json.dumps(partial_obj.val),
#     )


def get_type(val: typing.Any) -> str:
    if val == None:
        return "none"
    elif isinstance(val, dict):
        if "_type" in val:
            if "weave_type" in val:
                return val["weave_type"]["type"]
            return val["_type"]
        return "dict"
    elif isinstance(val, list):
        return "list"
    return "unknown"


def get_kind(val: typing.Any) -> str:
    val_type = get_type(val)
    if val_type == "Op":
        return "op"
    return "object"


def get_base_object_class(val: typing.Any) -> typing.Optional[str]:
    if isinstance(val, dict):
        if "_bases" in val:
            if isinstance(val["_bases"], list):
                if len(val["_bases"]) >= 2:
                    if val["_bases"][-1] == "BaseModel":
                        if val["_bases"][-2] == "Object":
                            if len(val["_bases"]) > 2:
                                return val["_bases"][-3]
                            elif "_class_name" in val:
                                return val["_class_name"]
    return None


def _digest_is_version_like(digest: str) -> typing.Tuple[bool, int]:
    if not digest.startswith("v"):
        return (False, -1)
    try:
        return (True, int(digest[1:]))
    except ValueError:
        return (False, -1)


def find_call_descendants(
    root_ids: typing.List[str],
    all_calls: typing.List[SelectableCHCallSchema],
) -> typing.List[str]:
    # make a map of call_id to children list
    children_map = defaultdict(list)
    for call in all_calls:
        if call.parent_id is not None:
            children_map[call.parent_id].append(call.id)

    # do DFS to get all descendants
    def find_all_descendants(root_ids: typing.List[str]) -> typing.Set[str]:
        descendants = set()
        stack = root_ids

        while stack:
            current_id = stack.pop()
            if current_id not in descendants:
                descendants.add(current_id)
                stack += children_map.get(current_id, [])

        return descendants

    # Find descendants for each initial id
    descendants = find_all_descendants(root_ids)

    return list(descendants)
