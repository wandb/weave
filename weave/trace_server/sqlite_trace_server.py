# Sqlite Trace Server

import datetime
import json
import typing
import hashlib
import sqlite3

from pydantic import BaseModel


from .trace_server_interface_util import extract_refs_from_values
from . import trace_server_interface as tsi

from weave.trace import refs

MAX_FLUSH_COUNT = 10000
MAX_FLUSH_AGE = 15


class NotFoundError(Exception):
    pass


class SelectableCHObjSchema(BaseModel):
    entity: str
    project: str
    name: str
    created_at: datetime.datetime
    refs: typing.List[str]
    val: str
    type: str
    digest: str
    version_index: int
    is_latest: int


def val_digest(json_val: str):
    hasher = hashlib.sha256()
    hasher.update(json_val.encode())
    return hasher.hexdigest()


class SqliteTraceServer(tsi.TraceServerInterface):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def drop_tables(self) -> None:
        self.cursor.execute("DROP TABLE IF EXISTS calls")
        self.cursor.execute("DROP TABLE IF EXISTS objects")
        self.cursor.execute("DROP TABLE IF EXISTS tables")
        self.cursor.execute("DROP TABLE IF EXISTS table_rows")

    def setup_tables(self) -> None:
        self.cursor.execute(
            """
            CREATE TABLE calls (
                project_id TEXT,
                id TEXT PRIMARY KEY,
                trace_id TEXT,
                parent_id TEXT,
                name TEXT,
                start_datetime TEXT,
                end_datetime TEXT,
                exception TEXT,
                attributes TEXT,
                inputs TEXT,
                input_refs TEXT,
                outputs TEXT,
                output_refs TEXT,
                wb_user_id TEXT,
                wb_run_id TEXT
            )
        """
        )
        self.cursor.execute(
            """
            CREATE TABLE objects (
                entity TEXT,
                project TEXT,
                name TEXT,
                created_at TEXT,
                type TEXT,
                refs TEXT,
                val TEXT,
                digest TEXT UNIQUE,
                version_index INTEGER
            )
        """
        )
        self.cursor.execute(
            """
            CREATE TABLE tables (
                entity TEXT,
                project TEXT,
                digest TEXT UNIQUE,
                row_digests STRING)
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE table_rows (
                entity TEXT,
                project TEXT,
                digest TEXT,
                val TEXT)
            """
        )

    # Creates a new call
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        # Converts the user-provided call details into a clickhouse schema.
        # This does validation and conversion of the input data as well
        # as enforcing business rules and defaults
        self.cursor.execute(
            """INSERT INTO calls (
                project_id,
                id,
                trace_id,
                parent_id,
                name,
                start_datetime,
                attributes,
                inputs,
                input_refs,
                wb_user_id,
                wb_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                req.start.project_id,
                req.start.id,
                req.start.trace_id,
                req.start.parent_id,
                req.start.name,
                req.start.start_datetime.isoformat(),
                json.dumps(req.start.attributes),
                json.dumps(req.start.inputs),
                json.dumps(extract_refs_from_values(list(req.start.inputs.values()))),
                req.start.wb_user_id,
                req.start.wb_run_id,
            ),
        )
        self.conn.commit()

        # Returns the id of the newly created call
        return tsi.CallStartRes(
            id=req.start.id,
            trace_id=req.start.trace_id,
        )

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        self.cursor.execute(
            """UPDATE calls SET
                end_datetime = ?,
                exception = ?,
                outputs = ?,
                output_refs = ?
            WHERE id = ?""",
            (
                req.end.end_datetime.isoformat(),
                req.end.exception,
                json.dumps(req.end.outputs),
                json.dumps(extract_refs_from_values(list(req.end.outputs.values()))),
                req.end.id,
            ),
        )
        self.conn.commit()
        return tsi.CallEndRes()

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        raise NotImplementedError()

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        self.cursor.execute("SELECT * FROM calls")
        query_result = self.cursor.fetchall()
        return tsi.CallsQueryRes(
            calls=[
                tsi.CallSchema(
                    project_id=row[0],
                    id=row[1],
                    trace_id=row[2],
                    parent_id=row[3],
                    name=row[4],
                    start_datetime=row[5],
                    end_datetime=row[6],
                    exception=row[7],
                    attributes=json.loads(row[8]),
                    inputs=json.loads(row[9]),
                    outputs=None if row[11] is None else json.loads(row[11]),
                    wb_user_id=row[13],
                    wb_run_id=row[14],
                )
                for row in query_result
            ]
        )

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        raise NotImplementedError()

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        raise NotImplementedError()

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        raise NotImplementedError()

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        json_val = json.dumps(req.obj.val)
        digest = val_digest(json_val)

        req_obj = req.obj
        entity, project = req_obj.project_id.split("/")
        try:
            # TODO: version index isn't right here, what if we delete stuff?
            self.cursor.execute("BEGIN TRANSACTION")
            # first get version count
            self.cursor.execute(
                """SELECT COUNT(*) FROM objects WHERE entity = ? AND project = ? AND name = ?""",
                (entity, project, req_obj.name),
            )
            version_index = self.cursor.fetchone()[0]

            self.cursor.execute(
                """INSERT INTO objects (
                    entity,
                    project,
                    name,
                    created_at,
                    type,
                    refs,
                    val,
                    digest,
                    version_index
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entity,
                    project,
                    req_obj.name,
                    datetime.datetime.now().isoformat(),
                    get_type(req_obj.val),
                    json.dumps([]),
                    json_val,
                    digest,
                    version_index,
                ),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            self.conn.rollback()
        return tsi.ObjCreateRes(version_digest=digest)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        conds = [
            f"name = '{req.name}'",
            f"digest = '{req.version_digest}'",
        ]
        objs = self._select_objs_query(
            req.entity,
            req.project,
            conditions=conds,
        )
        if len(objs) == 0:
            raise NotFoundError(f"Obj {req.name}:{req.version_digest} not found")

        return tsi.ObjReadRes(obj=_ch_obj_to_obj_schema(objs[0]))

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        conds: list[str] = []
        if req.filter:
            if req.filter.is_op is not None:
                if req.filter.is_op:
                    conds.append("type = 'OpDef'")
                else:
                    conds.append("type != 'OpDef'")
            if req.filter.object_names:
                in_list = ", ".join([f"'{n}'" for n in req.filter.object_names])
                conds.append(f"name IN ({in_list})")
            if req.filter.latest_only:
                conds.append("is_latest = 1")
        print(req.project_id)
        entity, project = req.project_id.split("/")
        objs = self._select_objs_query(
            entity,
            project,
            conditions=conds,
        )

        return tsi.ObjQueryRes(objs=[_ch_obj_to_obj_schema(obj) for obj in objs])

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        entity, project = req.table.project_id.split("/")
        insert_rows = []
        for r in req.table.rows:
            if not isinstance(r, dict):
                raise ValueError("All rows must be dictionaries")
            row_json = json.dumps(r)
            row_digest = val_digest(row_json)
            insert_rows.append((entity, project, row_digest, row_json))
        self.cursor.executemany(
            "INSERT INTO table_rows (entity, project, digest, val) VALUES (?, ?, ?, ?)",
            insert_rows,
        )

        row_digests = [r[2] for r in insert_rows]

        table_hasher = hashlib.sha256()
        for row_digest in row_digests:
            table_hasher.update(row_digest.encode())
        table_digest = table_hasher.hexdigest()

        self.cursor.execute(
            "INSERT INTO tables (entity, project, digest, row_digests) VALUES (?, ?, ?, ?)",
            (entity, project, table_digest, json.dumps(row_digests)),
        )
        self.conn.commit()

        return tsi.TableCreateRes(digest=table_digest)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        entity, project = req.project_id.split("/")
        conds = []
        if req.filter:
            if req.filter.row_digests:
                in_list = ", ".join([f"'{rd}'" for rd in req.filter.row_digests])
                conds.append(f"tr.digest IN ({in_list})")
        else:
            conds.append("1 = 1")
        rows = self._table_query(entity, project, req.table_digest, conditions=conds)
        return tsi.TableQueryRes(rows=rows)

    def _table_query(
        self,
        entity: str,
        project: str,
        table_digest: str,
        conditions: typing.Optional[typing.List[str]] = None,
        limit: typing.Optional[int] = None,
        parameters: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.List[tsi.TableRowSchema]:
        conds = ["entity = {entity: String}", "project = {project: String}"]
        if conditions:
            conds.extend(conditions)

        predicate = " AND ".join(conds)
        # First get the row IDs by querying tables
        self.cursor.execute(
            """
            SELECT digest, row_digests FROM tables
            WHERE entity = ? AND project = ? AND digest = ?
            """,
            (entity, project, table_digest),
        )
        query_result = self.cursor.fetchone()
        if query_result is None:
            raise NotFoundError(f"Table {table_digest} not found")
        row_digests = json.loads(query_result[1])

        # Now get the rows
        row_digests_pred = ", ".join(["?"] * len(row_digests))
        self.cursor.execute(
            f"""
            SELECT digest, val FROM table_rows
            WHERE entity = ? AND project = ? AND digest IN ({row_digests_pred})
            """,
            [entity, project, *row_digests],
        )
        query_result = self.cursor.fetchall()
        return [
            tsi.TableRowSchema(digest=r[0], val=json.loads(r[1])) for r in query_result
        ]

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        # TODO: This reads one ref at a time, it should read them in batches
        # where it can. Like it should group by object that we need to read.
        # And it should also batch into table refs (like when we are reading a bunch
        # of rows from a single Dataset)
        if len(req.refs) > 1000:
            raise ValueError("Too many refs")

        parsed_refs = [refs.parse_uri(r) for r in req.refs]
        if any(isinstance(r, refs.TableRef) for r in parsed_refs):
            raise ValueError("Table refs not supported")
        parsed_refs = typing.cast(typing.List[refs.ObjectRef], parsed_refs)

        def read_ref(r: refs.ObjectRef) -> typing.Any:
            conds = [
                f"name = '{r.name}'",
                f"digest = '{r.version}'",
            ]
            objs = self._select_objs_query(
                r.entity,
                r.project,
                conditions=conds,
            )
            if len(objs) == 0:
                raise NotFoundError(f"Obj {r.name}:{r.version} not found")
            obj = objs[0]
            val = json.loads(obj.val)
            extra = r.extra
            for extra_index in range(0, len(extra), 2):
                op, arg = extra[extra_index], extra[extra_index + 1]
                if op == "key":
                    val = val[arg]
                elif op == "attr":
                    val = val[arg]
                elif op == "index":
                    val = val[int(arg)]
                elif op == "id":
                    if isinstance(val, str) and val.startswith("weave://"):
                        table_ref = refs.parse_uri(val)
                        if not isinstance(table_ref, refs.TableRef):
                            raise ValueError(
                                "invalid data layout encountered, expected TableRef when resolving id"
                            )
                        rows = self._table_query(
                            entity=table_ref.entity,
                            project=table_ref.project,
                            table_digest=table_ref.digest,
                            conditions=["digest = {digest: String}"],
                            limit=1,
                            parameters={"digest": arg},
                        )
                        if len(rows) == 0:
                            raise NotFoundError(f"Row {val} not found")
                        val = rows[0].val
                    else:
                        raise ValueError(
                            "invalid data layout encountered, expected TableRef when resolving id"
                        )
                else:
                    raise ValueError(f"Unknown ref type: {extra[extra_index]}")
            return val

        return tsi.RefsReadBatchRes(vals=[read_ref(r) for r in parsed_refs])

    def _select_objs_query(
        self,
        entity: str,
        project: str,
        conditions: typing.Optional[typing.List[str]] = None,
        limit: typing.Optional[int] = None,
    ) -> typing.List[SelectableCHObjSchema]:
        pred = " AND ".join(conditions or ["1 = 1"])
        self.cursor.execute(
            """SELECT * FROM objects WHERE entity = ? AND project = ? AND """ + pred,
            (entity, project),
        )
        query_result = self.cursor.fetchall()
        result: typing.List[SelectableCHObjSchema] = []
        for row in query_result:
            result.append(
                SelectableCHObjSchema.model_validate(
                    {
                        "entity": row[0],
                        "project": row[1],
                        "name": row[2],
                        "created_at": row[3],
                        "type": row[4],
                        "refs": json.loads(row[5]),
                        "val": row[6],
                        "digest": row[7],
                        "version_index": row[8],
                        "is_latest": 1,
                    }
                )
            )

        return result


def _ch_obj_to_obj_schema(ch_obj: SelectableCHObjSchema) -> tsi.ObjSchema:
    return tsi.ObjSchema(
        # entity=ch_obj.entity,
        # project=ch_obj.project,
        project_id=f"{ch_obj.entity}/{ch_obj.project}",
        name=ch_obj.name,
        created_at=ch_obj.created_at,
        version_index=ch_obj.version_index,
        is_latest=ch_obj.is_latest,
        digest=ch_obj.digest,
        type=ch_obj.type,
        val=json.loads(ch_obj.val),
    )


def get_type(val):
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
