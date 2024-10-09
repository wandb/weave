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
from collections import defaultdict
from contextlib import contextmanager
from typing import (
    Any,
    Dict,
    Iterator,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    cast,
)
from zoneinfo import ZoneInfo

import clickhouse_connect
import emoji
from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.query import QueryResult
from clickhouse_connect.driver.summary import QuerySummary

from weave.trace_server import clickhouse_trace_server_migrator as wf_migrator
from weave.trace_server import environment as wf_env
from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
    OrderField,
    QueryBuilderDynamicField,
    QueryBuilderField,
    combine_conditions,
)
from weave.trace_server.clickhouse_schema import (
    CallDeleteCHInsertable,
    CallEndCHInsertable,
    CallStartCHInsertable,
    CallUpdateCHInsertable,
    ObjCHInsertable,
    SelectableCHCallSchema,
    SelectableCHObjSchema,
)
from weave.trace_server.emoji_util import detone_emojis
from weave.trace_server.errors import InsertTooLarge, InvalidRequest, RequestTooLarge
from weave.trace_server.feedback import (
    TABLE_FEEDBACK,
    validate_feedback_create_req,
    validate_feedback_purge_req,
)
from weave.trace_server.ids import generate_id
from weave.trace_server.orm import ParamBuilder, Row
from weave.trace_server.table_query_builder import (
    ROW_ORDER_COLUMN_NAME,
    TABLE_ROWS_ALIAS,
    VAL_DUMP_COLUMN_NAME,
    make_natural_sort_table_query,
    make_standard_table_query,
)
from weave.trace_server.token_costs import (
    LLM_TOKEN_PRICES_TABLE,
    validate_cost_purge_req,
)
from weave.trace_server.trace_server_common import (
    LRUCache,
    digest_is_version_like,
    empty_str_to_none,
    get_nested_key,
    hydrate_calls_with_feedback,
    make_derived_summary_fields,
    make_feedback_query_req,
    set_nested_key,
)
from weave.trace_server.trace_server_interface_util import (
    assert_non_null_wb_user_id,
    bytes_digest,
    extract_refs_from_values,
    str_digest,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_FLUSH_COUNT = 10000
MAX_FLUSH_AGE = 15

FILE_CHUNK_SIZE = 100000

MAX_DELETE_CALLS_COUNT = 100
MAX_CALLS_STREAM_BATCH_SIZE = 500


class NotFoundError(Exception):
    pass


CallCHInsertable = Union[
    CallStartCHInsertable,
    CallEndCHInsertable,
    CallDeleteCHInsertable,
    CallUpdateCHInsertable,
]


all_call_insert_columns = list(
    CallStartCHInsertable.model_fields.keys()
    | CallEndCHInsertable.model_fields.keys()
    | CallDeleteCHInsertable.model_fields.keys()
    | CallUpdateCHInsertable.model_fields.keys()
)

all_call_select_columns = list(SelectableCHCallSchema.model_fields.keys())
all_call_json_columns = ("inputs", "output", "attributes", "summary")
required_call_columns = ["id", "project_id", "trace_id", "op_name", "started_at"]


# Columns in the calls_merged table with special aggregation functions:
call_select_raw_columns = ["id", "project_id"]  # no aggregation
call_select_arrays_columns = ["input_refs", "output_refs"]  # array_concat_agg
call_select_argmax_columns = ["display_name"]  # argMaxMerge
# all others use `any`


all_obj_select_columns = list(SelectableCHObjSchema.model_fields.keys())
all_obj_insert_columns = list(ObjCHInsertable.model_fields.keys())

# Let's just make everything required for now ... can optimize when we implement column selection
required_obj_select_columns = list(set(all_obj_select_columns) - set([]))

ObjRefListType = list[ri.InternalObjectRef]


CLICKHOUSE_SINGLE_ROW_INSERT_BYTES_LIMIT = 3.5 * 1024 * 1024  # 3.5 MiB
ENTITY_TOO_LARGE_PAYLOAD = '{"_weave": {"error":"<EXCEEDS_LIMITS>"}}'


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
        self._call_batch: list[list[Any]] = []
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
    def call_batch(self) -> Iterator[None]:
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
                filter=tsi.CallsFilter(
                    call_ids=[req.id],
                ),
                limit=1,
                include_costs=req.include_costs,
            )
        )
        try:
            _call = next(res)
        except StopIteration:
            _call = None
        return tsi.CallReadRes(call=_call)

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

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        """Returns a stream of calls that match the given query."""
        cq = CallsQuery(
            project_id=req.project_id, include_costs=req.include_costs or False
        )
        columns = all_call_select_columns
        if req.columns:
            # Set columns to user-requested columns, w/ required columns
            # These are all formatted by the CallsQuery, which prevents injection
            # and other attack vectors.
            columns = list(set(required_call_columns + req.columns))
            # TODO: add support for json extract fields
            # Split out any nested column requests
            columns = [col.split(".")[0] for col in columns]

        # We put summary_dump last so that when we compute the costs and summary its in the right place
        if req.include_costs:
            summary_columns = ["summary", "summary_dump"]
            columns = [
                *[col for col in columns if col not in summary_columns],
                "summary_dump",
            ]
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

        select_columns = [c.field for c in cq.select_fields]

        if not req.expand_columns and not req.include_feedback:
            for row in raw_res:
                yield tsi.CallSchema.model_validate(
                    _ch_call_dict_to_call_schema_dict(dict(zip(select_columns, row)))
                )

        else:
            expand_columns = req.expand_columns or []
            ref_cache = LRUCache(max_size=1000)

            batch_size = 10
            batch = []
            for row in raw_res:
                call_dict = _ch_call_dict_to_call_schema_dict(
                    dict(zip(select_columns, row))
                )
                batch.append(call_dict)

                if len(batch) >= batch_size:
                    hydrated_batch = self._hydrate_calls(
                        req.project_id,
                        batch,
                        expand_columns,
                        req.include_feedback or False,
                        ref_cache,
                    )
                    for call in hydrated_batch:
                        yield tsi.CallSchema.model_validate(call)

                    # *** Dynamic increase from 10 to 500 ***
                    batch_size = min(MAX_CALLS_STREAM_BATCH_SIZE, batch_size * 10)
                    batch = []

            hydrated_batch = self._hydrate_calls(
                req.project_id,
                batch,
                expand_columns,
                req.include_feedback or False,
                ref_cache,
            )
            for call in hydrated_batch:
                yield tsi.CallSchema.model_validate(call)

    def _hydrate_calls(
        self,
        project_id: str,
        calls: list[dict[str, Any]],
        expand_columns: list[str],
        include_feedback: bool,
        ref_cache: LRUCache,
    ) -> list[dict[str, Any]]:
        if len(calls) == 0:
            return calls

        self._expand_call_refs(project_id, calls, expand_columns, ref_cache)
        if include_feedback:
            feedback_query_req = make_feedback_query_req(project_id, calls)
            feedback = self.feedback_query(feedback_query_req)
            hydrate_calls_with_feedback(calls, feedback)

        return calls

    def _get_refs_to_resolve(
        self, calls: list[dict[str, Any]], expand_columns: list[str]
    ) -> Dict[tuple[int, str], ri.InternalObjectRef]:
        refs_to_resolve: Dict[tuple[int, str], ri.InternalObjectRef] = {}
        for i, call in enumerate(calls):
            for col in expand_columns:
                if col in call:
                    val = call[col]
                else:
                    val = get_nested_key(call, col)
                    if not val:
                        continue

                if not ri.any_will_be_interpreted_as_ref_str(val):
                    continue

                ref = ri.parse_internal_uri(val)
                if not isinstance(ref, ri.InternalObjectRef):
                    continue

                refs_to_resolve[(i, col)] = ref
        return refs_to_resolve

    def _expand_call_refs(
        self,
        project_id: str,
        calls: list[dict[str, Any]],
        expand_columns: list[str],
        ref_cache: LRUCache,
    ) -> None:
        # format expand columns by depth, iterate through each batch in order
        expand_column_by_depth = defaultdict(list)
        for col in expand_columns:
            expand_column_by_depth[col.count(".")].append(col)

        for depth in sorted(expand_column_by_depth.keys()):
            refs_to_resolve = self._get_refs_to_resolve(
                calls, expand_column_by_depth[depth]
            )
            if not refs_to_resolve:
                continue

            vals = self._refs_read_batch_within_project(
                project_id, list(refs_to_resolve.values()), ref_cache
            )
            for ((i, col), ref), val in zip(refs_to_resolve.items(), vals):
                if isinstance(val, dict) and "_ref" not in val:
                    val["_ref"] = ref.uri()
                set_nested_key(calls[i], col, val)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        assert_non_null_wb_user_id(req)
        if len(req.call_ids) > MAX_DELETE_CALLS_COUNT:
            raise RequestTooLarge(
                f"Cannot delete more than {MAX_DELETE_CALLS_COUNT} calls at once"
            )

        # get all parents
        parents = list(
            self.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=req.project_id,
                    filter=tsi.CallsFilter(
                        call_ids=req.call_ids,
                    ),
                    # request minimal columns
                    columns=["id", "parent_id"],
                )
            )
        )

        # get all calls with trace_ids matching parents
        all_calls = list(
            self.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=req.project_id,
                    filter=tsi.CallsFilter(
                        trace_ids=[p.trace_id for p in parents],
                    ),
                    # request minimal columns
                    columns=["id", "parent_id"],
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
            "is_op = 1",
            "digest = {digest: String}",
        ]
        object_id_conditions = ["object_id = {object_id: String}"]
        parameters = {"name": req.name, "digest": req.digest}
        objs = self._select_objs_query(
            req.project_id,
            conditions=conds,
            object_id_conditions=object_id_conditions,
            parameters=parameters,
        )
        if len(objs) == 0:
            raise NotFoundError(f"Obj {req.name}:{req.digest} not found")

        return tsi.OpReadRes(op_obj=_ch_obj_to_obj_schema(objs[0]))

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        parameters = {}
        conds: list[str] = ["is_op = 1"]
        object_id_conditions: list[str] = []
        if req.filter:
            if req.filter.op_names:
                object_id_conditions.append("object_id IN {op_names: Array(String)}")
                parameters["op_names"] = req.filter.op_names
            if req.filter.latest_only:
                conds.append("is_latest = 1")

        ch_objs = self._select_objs_query(
            req.project_id,
            conditions=conds,
            object_id_conditions=object_id_conditions,
            parameters=parameters,
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
        conds: list[str] = []
        object_id_conditions = ["object_id = {object_id: String}"]
        parameters: Dict[str, Union[str, int]] = {"object_id": req.object_id}
        if req.digest == "latest":
            conds.append("is_latest = 1")
        else:
            (is_version, version_index) = digest_is_version_like(req.digest)
            if is_version:
                conds.append("version_index = {version_index: UInt64}")
                parameters["version_index"] = version_index
            else:
                conds.append("digest = {version_digest: String}")
                parameters["version_digest"] = req.digest
        objs = self._select_objs_query(
            req.project_id,
            conditions=conds,
            object_id_conditions=object_id_conditions,
            parameters=parameters,
        )
        if len(objs) == 0:
            raise NotFoundError(f"Obj {req.object_id}:{req.digest} not found")

        return tsi.ObjReadRes(obj=_ch_obj_to_obj_schema(objs[0]))

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        conds: list[str] = []
        object_id_conditions: list[str] = []
        parameters = {}
        if req.filter:
            if req.filter.is_op is not None:
                if req.filter.is_op:
                    conds.append("is_op = 1")
                else:
                    conds.append("is_op = 0")
            if req.filter.object_ids:
                object_id_conditions.append("object_id IN {object_ids: Array(String)}")
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
            object_id_conditions=object_id_conditions,
            parameters=parameters,
            metadata_only=req.metadata_only,
            limit=req.limit,
            offset=req.offset,
            sort_by=req.sort_by,
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
        return tsi.TableCreateRes(digest=digest, row_digests=row_digests)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        query = """
            SELECT *
            FROM (
                    SELECT *,
                        row_number() OVER (PARTITION BY project_id, digest) AS rn
                    FROM tables
                    WHERE project_id = {project_id:String} AND digest = {digest:String}
                )
            WHERE rn = 1
            ORDER BY project_id, digest
        """

        row_digest_result_query = self.ch_client.query(
            query,
            parameters={
                "project_id": req.project_id,
                "digest": req.base_digest,
            },
        )

        if len(row_digest_result_query.result_rows) == 0:
            raise NotFoundError(f"Table {req.project_id}:{req.base_digest} not found")

        final_row_digests: list[str] = row_digest_result_query.result_rows[0][2]
        new_rows_needed_to_insert = []
        known_digests = set(final_row_digests)

        def add_new_row_needed_to_insert(row_data: Any) -> str:
            if not isinstance(row_data, dict):
                raise ValueError("All rows must be dictionaries")
            row_json = json.dumps(row_data)
            row_digest = str_digest(row_json)
            if row_digest not in known_digests:
                new_rows_needed_to_insert.append(
                    (
                        req.project_id,
                        row_digest,
                        extract_refs_from_values(row_data),
                        row_json,
                    )
                )
                known_digests.add(row_digest)
            return row_digest

        updated_digests = []
        for update in req.updates:
            if isinstance(update, tsi.TableAppendSpec):
                new_digest = add_new_row_needed_to_insert(update.append.row)
                final_row_digests.append(new_digest)
                updated_digests.append(new_digest)
            elif isinstance(update, tsi.TablePopSpec):
                if update.pop.index >= len(final_row_digests) or update.pop.index < 0:
                    raise ValueError("Index out of range")
                popped_digest = final_row_digests.pop(update.pop.index)
                updated_digests.append(popped_digest)
            elif isinstance(update, tsi.TableInsertSpec):
                if (
                    update.insert.index > len(final_row_digests)
                    or update.insert.index < 0
                ):
                    raise ValueError("Index out of range")
                new_digest = add_new_row_needed_to_insert(update.insert.row)
                final_row_digests.insert(update.insert.index, new_digest)
                updated_digests.append(new_digest)
            else:
                raise ValueError("Unrecognized update", update)

        if new_rows_needed_to_insert:
            self._insert(
                "table_rows",
                data=new_rows_needed_to_insert,
                column_names=["project_id", "digest", "refs", "val_dump"],
            )

        table_hasher = hashlib.sha256()
        for row_digest in final_row_digests:
            table_hasher.update(row_digest.encode())
        digest = table_hasher.hexdigest()

        self._insert(
            "tables",
            data=[(req.project_id, digest, final_row_digests)],
            column_names=["project_id", "digest", "row_digests"],
        )
        return tsi.TableUpdateRes(digest=digest, updated_row_digests=updated_digests)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        conds = []
        pb = ParamBuilder()
        if req.filter:
            if req.filter.row_digests:
                conds.append(
                    f"tr.digest IN {{{pb.add_param(req.filter.row_digests)}: Array(String)}}"
                )

        sort_fields = []
        if req.sort_by:
            for sort in req.sort_by:
                # TODO: better splitting of escaped dots (.) in field names
                extra_path = sort.field.split(".")
                field = OrderField(
                    field=QueryBuilderDynamicField(
                        field=VAL_DUMP_COLUMN_NAME, extra_path=extra_path
                    ),
                    direction="ASC" if sort.direction.lower() == "asc" else "DESC",
                )
                sort_fields.append(field)
        rows = self._table_query(
            req.project_id,
            req.digest,
            pb,
            sql_safe_conditions=conds,
            sort_fields=sort_fields,
            limit=req.limit,
            offset=req.offset,
        )
        return tsi.TableQueryRes(rows=rows)

    def _table_query(
        self,
        project_id: str,
        digest: str,
        pb: ParamBuilder,
        *,
        # using the `sql_safe_*` prefix is a way to signal to the caller
        # that these strings should have been santized by the caller.
        sql_safe_conditions: Optional[list[str]] = None,
        sort_fields: Optional[list[OrderField]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[tsi.TableRowSchema]:
        if not sort_fields:
            sort_fields = [
                OrderField(
                    field=QueryBuilderField(field=ROW_ORDER_COLUMN_NAME),
                    direction="ASC",
                )
            ]

        if (
            len(sort_fields) == 1
            and sort_fields[0].field.field == ROW_ORDER_COLUMN_NAME
            and not sql_safe_conditions
        ):
            query = make_natural_sort_table_query(
                project_id,
                digest,
                pb,
                limit=limit,
                offset=offset,
                natural_direction=sort_fields[0].direction,
            )
        else:
            order_by_components = ", ".join(
                [sort_field.as_sql(pb, TABLE_ROWS_ALIAS) for sort_field in sort_fields]
            )
            sql_safe_sort_clause = f"ORDER BY {order_by_components}"
            query = make_standard_table_query(
                project_id,
                digest,
                pb,
                sql_safe_conditions=sql_safe_conditions,
                sql_safe_sort_clause=sql_safe_sort_clause,
                limit=limit,
                offset=offset,
            )

        query_result = self.ch_client.query(query, parameters=pb.get_params())

        return [
            tsi.TableRowSchema(digest=r[0], val=json.loads(r[1]))
            for r in query_result.result_rows
        ]

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        parameters: Dict[str, Any] = {
            "project_id": req.project_id,
            "digest": req.digest,
        }

        query = """
        SELECT length(row_digests)
        FROM tables
        WHERE project_id = {project_id:String} AND digest = {digest:String}
        """

        query_result = self.ch_client.query(query, parameters=parameters)
        count = query_result.result_rows[0][0] if query_result.result_rows else 0

        return tsi.TableQueryStatsRes(count=count)

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        # TODO: This reads one ref at a time, it should read them in batches
        # where it can. Like it should group by object that we need to read.
        # And it should also batch into table refs (like when we are reading a bunch
        # of rows from a single Dataset)
        if len(req.refs) > 1000:
            raise ValueError("Too many refs")

        # First, parse the refs
        parsed_raw_refs = [ri.parse_internal_uri(r) for r in req.refs]

        # Business logic to ensure that we don't have raw TableRefs (not allowed)
        if any(isinstance(r, ri.InternalTableRef) for r in parsed_raw_refs):
            raise ValueError("Table refs not supported")

        parsed_refs = cast(ObjRefListType, parsed_raw_refs)
        vals = self._parsed_refs_read_batch(parsed_refs)

        return tsi.RefsReadBatchRes(vals=vals)

    def _parsed_refs_read_batch(
        self,
        parsed_refs: ObjRefListType,
        root_val_cache: Optional[Dict[str, Any]] = None,
    ) -> list[Any]:
        # Next, group the refs by project_id
        refs_by_project_id: dict[str, ObjRefListType] = defaultdict(list)
        for ref in parsed_refs:
            refs_by_project_id[ref.project_id].append(ref)

        # Lookup data for each project, scoped to each project
        final_result_cache: Dict[str, Any] = {}

        def make_ref_cache_key(ref: ri.InternalObjectRef) -> str:
            return ref.uri()

        for project in refs_by_project_id:
            project_refs = refs_by_project_id[project]
            project_results = self._refs_read_batch_within_project(
                project,
                refs_by_project_id[project],
                root_val_cache,
            )
            for ref, result in zip(project_refs, project_results):
                final_result_cache[make_ref_cache_key(ref)] = result

        # Return the final data payload
        return [final_result_cache[make_ref_cache_key(ref)] for ref in parsed_refs]

    def _refs_read_batch_within_project(
        self,
        project_id_scope: str,
        parsed_refs: ObjRefListType,
        root_val_cache: Optional[Dict[str, Any]],
    ) -> list[Any]:
        if root_val_cache is None:
            root_val_cache = {}

        def make_root_ref_cache_key(ref: ri.InternalObjectRef) -> str:
            return f"{ref.project_id}/{ref.name}/{ref.version}"

        def make_obj_cache_key(obj: SelectableCHObjSchema) -> str:
            return f"{obj.project_id}/{obj.object_id}/{obj.digest}"

        def get_object_refs_root_val(
            refs: list[ri.InternalObjectRef],
        ) -> Any:
            conds: list[str] = []
            object_id_conds: list[str] = []
            parameters = {}

            for ref_index, ref in enumerate(refs):
                if ref.version == "latest":
                    raise ValueError("Reading refs with `latest` is not supported")

                cache_key = make_root_ref_cache_key(ref)

                if cache_key in root_val_cache:
                    continue

                if ref.project_id != project_id_scope:
                    # At some point in the future, we may allow cross-project references.
                    # However, until then, we disallow this feature. Practically, we
                    # should never hit this code path since the `resolve_extra` function
                    # handles this check. However, out of caution, we add this check here.
                    # Hitting this would be a programming error, not a user error.
                    raise ValueError("Will not resolve cross-project refs.")

                object_id_param_key = "object_id_" + str(ref_index)
                version_param_key = "version_" + str(ref_index)
                conds.append(f"digest = {{{version_param_key}: String}}")
                object_id_conds.append(f"object_id = {{{object_id_param_key}: String}}")
                parameters[object_id_param_key] = ref.name
                parameters[version_param_key] = ref.version

            if len(conds) > 0:
                conditions = [combine_conditions(conds, "OR")]
                object_id_conditions = [combine_conditions(object_id_conds, "OR")]
                objs = self._select_objs_query(
                    project_id=project_id_scope,
                    conditions=conditions,
                    object_id_conditions=object_id_conditions,
                    parameters=parameters,
                )
                for obj in objs:
                    root_val_cache[make_obj_cache_key(obj)] = json.loads(obj.val_dump)

            return [
                root_val_cache.get(make_root_ref_cache_key(ref), None) for ref in refs
            ]

        # Represents work left to do for resolving a ref
        @dataclasses.dataclass
        class PartialRefResult:
            remaining_extra: list[str]
            # unresolved_obj_ref and unresolved_table_ref are mutually exclusive
            unresolved_obj_ref: Optional[ri.InternalObjectRef]
            unresolved_table_ref: Optional[ri.InternalTableRef]
            val: Any

        def resolve_extra(extra: list[str], val: Any) -> PartialRefResult:
            for extra_index in range(0, len(extra), 2):
                empty_result = PartialRefResult(
                    remaining_extra=[],
                    unresolved_obj_ref=None,
                    unresolved_table_ref=None,
                    val=None,
                )
                op, arg = extra[extra_index], extra[extra_index + 1]
                if isinstance(val, str) and val.startswith(
                    ri.WEAVE_INTERNAL_SCHEME + "://"
                ):
                    parsed_ref = ri.parse_internal_uri(val)

                    if parsed_ref.project_id != project_id_scope:
                        # This is the primary check to enforce that we do not
                        # traverse into a different project. It is perfectly
                        # reasonable to support this functionality in the
                        # future. At such point in time, we will want to define
                        # a "check read project" function that the client can
                        # use to validate that the project is allowed to be
                        # read. Once this is lifted, other parts of this
                        # function will need to be updated as well, as they will
                        # currently `raise ValueError("Will not resolve
                        # cross-project refs.")` under such conditions.
                        return empty_result

                    if isinstance(parsed_ref, ri.InternalObjectRef):
                        return PartialRefResult(
                            remaining_extra=extra[extra_index:],
                            unresolved_obj_ref=parsed_ref,
                            unresolved_table_ref=None,
                            val=val,
                        )
                    elif isinstance(parsed_ref, ri.InternalTableRef):
                        return PartialRefResult(
                            remaining_extra=extra[extra_index:],
                            unresolved_obj_ref=None,
                            unresolved_table_ref=parsed_ref,
                            val=val,
                        )
                if val is None:
                    return empty_result
                if op == ri.DICT_KEY_EDGE_NAME:
                    val = val.get(arg)
                elif op == ri.OBJECT_ATTR_EDGE_NAME:
                    val = val.get(arg)
                elif op == ri.LIST_INDEX_EDGE_NAME:
                    index = int(arg)
                    if index >= len(val):
                        return empty_result
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
            needed_extra_results: list[Tuple[int, PartialRefResult]] = []
            for i, extra_result in enumerate(extra_results):
                if extra_result.unresolved_obj_ref is not None:
                    needed_extra_results.append((i, extra_result))

            if len(needed_extra_results) > 0:
                refs: list[ri.InternalObjectRef] = []
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
            table_queries: dict[Tuple[str, str], list[Tuple[int, str]]] = {}
            for i, extra_result in enumerate(extra_results):
                if extra_result.unresolved_table_ref is not None:
                    table_ref = extra_result.unresolved_table_ref
                    if not extra_result.remaining_extra:
                        raise ValueError("Table refs must have id extra")
                    op, row_digest = (
                        extra_result.remaining_extra[0],
                        extra_result.remaining_extra[1],
                    )
                    if op != ri.TABLE_ROW_ID_EDGE_NAME:
                        raise ValueError("Table refs must have id extra")
                    table_queries.setdefault(
                        (table_ref.project_id, table_ref.digest), []
                    ).append((i, row_digest))
            # Make the queries
            for (project_id, digest), index_digests in table_queries.items():
                row_digests = [d for i, d in index_digests]
                if project_id != project_id_scope:
                    # At some point in the future, we may allow cross-project references.
                    # However, until then, we disallow this feature. Practically, we
                    # should never hit this code path since the `resolve_extra` function
                    # handles this check. However, out of caution, we add this check here.
                    # Hitting this would be a programming error, not a user error.
                    raise ValueError("Will not resolve cross-project refs.")
                pb = ParamBuilder()
                row_digests_name = pb.add_param(row_digests)
                rows = self._table_query(
                    project_id=project_id_scope,
                    digest=digest,
                    pb=pb,
                    sql_safe_conditions=[
                        f"digest IN {{{row_digests_name}: Array(String)}}"
                    ],
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

        return [r.val for r in extra_results]

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

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        assert_non_null_wb_user_id(req)
        created_at = datetime.datetime.now(ZoneInfo("UTC"))

        costs = []
        for llm_id, cost in req.costs.items():
            cost_id = generate_id()

            row: Row = {
                "id": cost_id,
                "created_by": req.wb_user_id,
                "created_at": created_at,
                "pricing_level": "project",
                "pricing_level_id": req.project_id,
                "provider_id": cost.provider_id if cost.provider_id else "default",
                "llm_id": llm_id,
                "effective_date": (
                    cost.effective_date if cost.effective_date else created_at
                ),
                "prompt_token_cost": cost.prompt_token_cost,
                "completion_token_cost": cost.completion_token_cost,
                "prompt_token_cost_unit": cost.prompt_token_cost_unit,
                "completion_token_cost_unit": cost.completion_token_cost_unit,
            }

            costs.append((cost_id, llm_id))

            prepared = LLM_TOKEN_PRICES_TABLE.insert(row).prepare(
                database_type="clickhouse"
            )
            self._insert(
                LLM_TOKEN_PRICES_TABLE.name, prepared.data, prepared.column_names
            )

        return tsi.CostCreateRes(ids=costs)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        expr = {
            "$and": [
                (
                    req.query.expr_
                    if req.query
                    else {
                        "$eq": [
                            {"$getField": "pricing_level_id"},
                            {"$literal": req.project_id},
                        ],
                    }
                ),
                {
                    "$eq": [
                        {"$getField": "pricing_level"},
                        {"$literal": "project"},
                    ],
                },
            ]
        }
        query_with_pricing_level = tsi.Query(**{"$expr": expr})
        query = LLM_TOKEN_PRICES_TABLE.select()
        query = query.fields(req.fields)
        query = query.where(query_with_pricing_level)
        query = query.order_by(req.sort_by)
        query = query.limit(req.limit).offset(req.offset)
        prepared = query.prepare(database_type="clickhouse")
        query_result = self.ch_client.query(prepared.sql, prepared.parameters)
        results = LLM_TOKEN_PRICES_TABLE.tuples_to_rows(
            query_result.result_rows, prepared.fields
        )
        return tsi.CostQueryRes(results=results)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        validate_cost_purge_req(req)

        expr = {
            "$and": [
                req.query.expr_,
                {
                    "$eq": [
                        {"$getField": "pricing_level_id"},
                        {"$literal": req.project_id},
                    ],
                },
                {
                    "$eq": [
                        {"$getField": "pricing_level"},
                        {"$literal": "project"},
                    ],
                },
            ]
        }
        query_with_pricing_level = tsi.Query(**{"$expr": expr})

        query = LLM_TOKEN_PRICES_TABLE.purge()
        query = query.where(query_with_pricing_level)
        prepared = query.prepare(database_type="clickhouse")
        self.ch_client.query(prepared.sql, prepared.parameters)
        return tsi.CostPurgeRes()

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

    def _insert_call_batch(self, batch: list) -> None:
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
        conditions: Optional[list[str]] = None,
        object_id_conditions: Optional[list[str]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        metadata_only: Optional[bool] = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort_by: Optional[list[tsi.SortBy]] = None,
    ) -> list[SelectableCHObjSchema]:
        """
        Main query for fetching objects.

        conditions:
            conditions should include operations on version_index, digest, kind (is_op)
            ALL conditions are AND'ed together.
        object_id_conditions:
            conditions should include operations on ONLY object_id
            ALL conditions are AND'ed together.
        parameters:
            parameters to be passed to the query. Must include all parameters for both
            conditions and object_id_conditions.
        metadata_only:
            if metadata_only is True, then we return early and dont grab the value.
            Otherwise, make a second query to grab the val_dump from the db
        """
        if not conditions:
            conditions = ["1 = 1"]
        if not object_id_conditions:
            object_id_conditions = ["1 = 1"]

        conditions_part = combine_conditions(conditions, "AND")
        object_id_conditions_part = combine_conditions(object_id_conditions, "AND")

        limit_part = ""
        offset_part = ""
        if limit is not None:
            limit_part = f"LIMIT {int(limit)}"
        if offset is not None:
            offset_part = f" OFFSET {int(offset)}"

        sort_part = ""
        if sort_by:
            valid_sort_fields = {"object_id", "created_at"}
            sort_clauses = []
            for sort in sort_by:
                if sort.field in valid_sort_fields and sort.direction in {
                    "asc",
                    "desc",
                }:
                    sort_clauses.append(f"{sort.field} {sort.direction.upper()}")
            if sort_clauses:
                sort_part = f"ORDER BY {', '.join(sort_clauses)}"

        if parameters is None:
            parameters = {}

        select_without_val_dump_query = f"""
            SELECT
                project_id,
                object_id,
                created_at,
                kind,
                base_object_class,
                refs,
                digest,
                is_op,
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
                    digest,
                    is_op,
                    row_number() OVER (
                        PARTITION BY project_id,
                        kind,
                        object_id
                        ORDER BY created_at ASC
                    ) - 1 AS version_index,
                    count(*) OVER (PARTITION BY project_id, kind, object_id) as version_count,
                    if(version_index + 1 = version_count, 1, 0) AS is_latest
                FROM (
                    SELECT project_id,
                        object_id,
                        created_at,
                        kind,
                        base_object_class,
                        refs,
                        digest,
                        if (kind = 'op', 1, 0) AS is_op,
                        row_number() OVER (
                            PARTITION BY project_id,
                            kind,
                            object_id,
                            digest
                            ORDER BY created_at ASC
                        ) AS rn
                    FROM object_versions
                    WHERE project_id = {{project_id: String}} AND
                        {object_id_conditions_part}
                )
                WHERE rn = 1
            )
            WHERE {conditions_part}
            {sort_part}
            {limit_part}
            {offset_part}
        """
        query_result = self._query_stream(
            select_without_val_dump_query,
            {"project_id": project_id, **parameters},
        )
        result: list[SelectableCHObjSchema] = []
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
                                "digest",
                                "is_op",
                                "version_index",
                                "version_count",
                                "is_latest",
                                "val_dump",
                            ],
                            # Add an empty val_dump to the end of the row
                            list(row) + ["{}"],
                        )
                    )
                )
            )

        # -- Don't make second query for object values if metadata_only --
        if metadata_only:
            return result

        # now get the val_dump for each object
        object_ids = list(set([row.object_id for row in result]))
        digests = list(set([row.digest for row in result]))
        query = """
            SELECT object_id, digest, any(val_dump)
            FROM object_versions
            WHERE project_id = {project_id: String} AND
                object_id IN {object_ids: Array(String)} AND
                digest IN {digests: Array(String)}
            GROUP BY object_id, digest
        """
        parameters = {
            "project_id": project_id,
            "object_ids": object_ids,
            "digests": digests,
        }
        query_result = self._query_stream(query, parameters)
        # Map (object_id, digest) to val_dump
        object_values: Dict[tuple[str, str], Any] = {}
        for row in query_result:
            (object_id, digest, val_dump) = row
            object_values[(object_id, digest)] = val_dump

        # update the val_dump for each object
        for obj in result:
            obj.val_dump = object_values.get((obj.object_id, obj.digest), "{}")
        return result

    def _run_migrations(self) -> None:
        logger.info("Running migrations")
        migrator = wf_migrator.ClickHouseTraceServerMigrator(self._mint_client())
        migrator.apply_migrations(self._database)

    def _query_stream(
        self,
        query: str,
        parameters: Dict[str, Any],
        column_formats: Optional[Dict[str, Any]] = None,
    ) -> Iterator[tuple]:
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
        parameters: Dict[str, Any],
        column_formats: Optional[Dict[str, Any]] = None,
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
        data: Sequence[Sequence[Any]],
        column_names: list[str],
        settings: Optional[Dict[str, Any]] = None,
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
                raise InsertTooLarge(
                    "Database insertion failed. Record too large. "
                    "A likely cause is that a single row or cell exceeded "
                    "the limit. If logging images, save them as `Image.PIL`."
                )
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
        try:
            self._insert_call_batch(self._call_batch)
        except InsertTooLarge:
            logger.info("Retrying with large objects stripped.")
            batch = self._strip_large_values(self._call_batch)
            self._insert_call_batch(batch)

        self._call_batch = []

    def _strip_large_values(self, batch: list[list[Any]]) -> list[list[Any]]:
        """
        Iterate through the batch and replace large values with placeholders.

        If values are larger than 1MiB replace them with placeholder values.
        """
        final_batch = []
        # Set the value byte limit to be anything over 1MiB to catch
        # payloads with multiple large values that are still under the
        # single row insert limit.
        val_byte_limit = 1 * 1024 * 1024
        for item in batch:
            bytes_size = _num_bytes(str(item))
            # If bytes_size > the limit, this item is too large,
            # iterate through the json-dumped item values to find and
            # replace the large values with a placeholder.
            if bytes_size > CLICKHOUSE_SINGLE_ROW_INSERT_BYTES_LIMIT:
                stripped_item = []
                for value in item:
                    # all the values should be json dumps, there are no
                    # non json fields controlled by the user that can
                    # be large enough to strip... (?)
                    if _num_bytes(value) > val_byte_limit:
                        stripped_item += [ENTITY_TOO_LARGE_PAYLOAD]
                    else:
                        stripped_item += [value]
                final_batch.append(stripped_item)
            else:
                final_batch.append(item)
        return final_batch


def _num_bytes(data: Any) -> int:
    """
    Calculate the number of bytes in a string.

    This can be computationally expensive, only call when necessary.
    Never raise on a failed str cast, just return 0.
    """
    try:
        return len(str(data).encode("utf-8"))
    except Exception:
        return 0


def _dict_value_to_dump(
    value: dict,
) -> str:
    if not isinstance(value, dict):
        raise ValueError(f"Value is not a dict: {value}")
    return json.dumps(value)


def _any_value_to_dump(
    value: Any,
) -> str:
    return json.dumps(value)


def _dict_dump_to_dict(val: str) -> Dict[str, Any]:
    res = json.loads(val)
    if not isinstance(res, dict):
        raise ValueError(f"Value is not a dict: {val}")
    return res


def _any_dump_to_any(val: str) -> Any:
    return json.loads(val)


def _ensure_datetimes_have_tz(
    dt: Optional[datetime.datetime] = None,
) -> Optional[datetime.datetime]:
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
    val: Optional[str],
) -> Optional[Dict[str, Any]]:
    return _dict_dump_to_dict(val) if val else None


def _nullable_any_dump_to_any(
    val: Optional[str],
) -> Optional[Any]:
    return _any_dump_to_any(val) if val else None


def _raw_call_dict_to_ch_call(
    call: Dict[str, Any],
) -> SelectableCHCallSchema:
    return SelectableCHCallSchema.model_validate(call)


def _ch_call_to_call_schema(ch_call: SelectableCHCallSchema) -> tsi.CallSchema:
    started_at = _ensure_datetimes_have_tz(ch_call.started_at)
    ended_at = _ensure_datetimes_have_tz(ch_call.ended_at)
    summary = _nullable_any_dump_to_any(ch_call.summary_dump)
    display_name = empty_str_to_none(ch_call.display_name)
    return tsi.CallSchema(
        project_id=ch_call.project_id,
        id=ch_call.id,
        trace_id=ch_call.trace_id,
        parent_id=ch_call.parent_id,
        op_name=ch_call.op_name,
        started_at=started_at,
        ended_at=ended_at,
        attributes=_dict_dump_to_dict(ch_call.attributes_dump or "{}"),
        inputs=_dict_dump_to_dict(ch_call.inputs_dump or "{}"),
        output=_nullable_any_dump_to_any(ch_call.output_dump),
        summary=make_derived_summary_fields(
            summary=summary or {},
            op_name=ch_call.op_name,
            started_at=started_at,
            ended_at=ended_at,
            exception=ch_call.exception,
            display_name=display_name,
        ),
        exception=ch_call.exception,
        wb_run_id=ch_call.wb_run_id,
        wb_user_id=ch_call.wb_user_id,
        display_name=display_name,
    )


# Keep in sync with `_ch_call_to_call_schema`. This copy is for performance
def _ch_call_dict_to_call_schema_dict(ch_call_dict: Dict) -> Dict:
    summary = _nullable_any_dump_to_any(ch_call_dict.get("summary_dump"))
    started_at = _ensure_datetimes_have_tz(ch_call_dict.get("started_at"))
    ended_at = _ensure_datetimes_have_tz(ch_call_dict.get("ended_at"))
    display_name = empty_str_to_none(ch_call_dict.get("display_name"))
    return dict(
        project_id=ch_call_dict.get("project_id"),
        id=ch_call_dict.get("id"),
        trace_id=ch_call_dict.get("trace_id"),
        parent_id=ch_call_dict.get("parent_id"),
        op_name=ch_call_dict.get("op_name"),
        started_at=started_at,
        ended_at=ended_at,
        attributes=_dict_dump_to_dict(ch_call_dict.get("attributes_dump", "{}")),
        inputs=_dict_dump_to_dict(ch_call_dict.get("inputs_dump", "{}")),
        output=_nullable_any_dump_to_any(ch_call_dict.get("output_dump")),
        summary=make_derived_summary_fields(
            summary=summary or {},
            op_name=ch_call_dict.get("op_name", ""),
            started_at=started_at,
            ended_at=ended_at,
            exception=ch_call_dict.get("exception"),
            display_name=display_name,
        ),
        exception=ch_call_dict.get("exception"),
        wb_run_id=ch_call_dict.get("wb_run_id"),
        wb_user_id=ch_call_dict.get("wb_user_id"),
        display_name=display_name,
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
        summary_dump=_dict_value_to_dump(dict(end_call.summary)),
        output_dump=_any_value_to_dump(end_call.output),
        output_refs=extract_refs_from_values(end_call.output),
    )


def _process_parameters(
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
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


def get_type(val: Any) -> str:
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


def get_kind(val: Any) -> str:
    val_type = get_type(val)
    if val_type == "Op":
        return "op"
    return "object"


def get_base_object_class(val: Any) -> Optional[str]:
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


def find_call_descendants(
    root_ids: list[str],
    all_calls: list[tsi.CallSchema],
) -> list[str]:
    # make a map of call_id to children list
    children_map = defaultdict(list)
    for call in all_calls:
        if call.parent_id is not None:
            children_map[call.parent_id].append(call.id)

    # do DFS to get all descendants
    def find_all_descendants(root_ids: list[str]) -> Set[str]:
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
