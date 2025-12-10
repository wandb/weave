"""In-memory trace server implementation for testing.

This module provides a simple in-memory implementation of the trace server
interface that can be used for fast unit tests without any database.
"""

from __future__ import annotations

import datetime
import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from weave.trace_server import object_creation_utils
from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import InvalidRequest, NotFoundError, ObjectDeletedError
from weave.trace_server.ids import generate_id
from weave.trace_server.object_class_util import process_incoming_object_val
from weave.trace_server.trace_server_interface_util import (
    bytes_digest,
    extract_refs_from_values,
    str_digest,
)


@dataclass
class StoredCall:
    """In-memory representation of a call."""

    project_id: str
    id: str
    trace_id: str
    op_name: str
    started_at: datetime.datetime
    parent_id: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    ended_at: datetime.datetime | None = None
    exception: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    inputs: dict[str, Any] = field(default_factory=dict)
    output: Any = None
    summary: dict[str, Any] | None = None
    input_refs: list[str] = field(default_factory=list)
    output_refs: list[str] = field(default_factory=list)
    display_name: str | None = None
    wb_user_id: str | None = None
    wb_run_id: str | None = None
    wb_run_step: int | None = None
    wb_run_step_end: int | None = None
    deleted_at: datetime.datetime | None = None

    def to_call_schema(self) -> tsi.CallSchema:
        return tsi.CallSchema(
            id=self.id,
            project_id=self.project_id,
            op_name=self.op_name,
            display_name=self.display_name,
            trace_id=self.trace_id,
            parent_id=self.parent_id,
            thread_id=self.thread_id,
            turn_id=self.turn_id,
            started_at=self.started_at,
            ended_at=self.ended_at,
            exception=self.exception,
            attributes=self.attributes,
            inputs=self.inputs,
            output=self.output,
            summary=self.summary,
            wb_user_id=self.wb_user_id,
            wb_run_id=self.wb_run_id,
            deleted_at=self.deleted_at,
        )


@dataclass
class StoredObject:
    """In-memory representation of an object."""

    project_id: str
    object_id: str
    digest: str
    val: Any
    kind: str = "object"
    base_object_class: str | None = None
    leaf_object_class: str | None = None
    refs: list[str] = field(default_factory=list)
    wb_user_id: str | None = None
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    version_index: int = 0
    is_latest: bool = True
    deleted_at: datetime.datetime | None = None

    def to_obj_schema(self) -> tsi.ObjSchema:
        return tsi.ObjSchema(
            project_id=self.project_id,
            object_id=self.object_id,
            created_at=self.created_at,
            digest=self.digest,
            version_index=self.version_index,
            is_latest=1 if self.is_latest else 0,
            kind=self.kind,
            base_object_class=self.base_object_class,
            leaf_object_class=self.leaf_object_class,
            val=self.val,
        )


@dataclass
class StoredFile:
    """In-memory representation of a file."""

    project_id: str
    digest: str
    content: bytes


@dataclass
class StoredTable:
    """In-memory representation of a table."""

    project_id: str
    digest: str
    row_digests: list[str]


@dataclass
class StoredTableRow:
    """In-memory representation of a table row."""

    project_id: str
    digest: str
    val: dict[str, Any]


class InMemoryTraceServer(tsi.FullTraceServerInterface):
    """In-memory implementation of the trace server interface.

    This is a simple implementation for testing that stores all data in memory
    using Python data structures. It implements the core operations needed
    for most tests.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Storage: project_id -> id -> StoredCall
        self._calls: dict[str, dict[str, StoredCall]] = {}
        # Storage: project_id -> (object_id, digest) -> StoredObject
        self._objects: dict[str, dict[tuple[str, str], StoredObject]] = {}
        # Storage: project_id -> digest -> StoredFile
        self._files: dict[str, dict[str, StoredFile]] = {}
        # Storage: project_id -> id -> feedback dict
        self._feedback: dict[str, dict[str, dict[str, Any]]] = {}
        # Storage: project_id -> digest -> StoredTable
        self._tables: dict[str, dict[str, StoredTable]] = {}
        # Storage: project_id -> digest -> StoredTableRow
        self._table_rows: dict[str, dict[str, StoredTableRow]] = {}

    def _get_project_calls(self, project_id: str) -> dict[str, StoredCall]:
        if project_id not in self._calls:
            self._calls[project_id] = {}
        return self._calls[project_id]

    def _get_project_objects(self, project_id: str) -> dict[tuple[str, str], StoredObject]:
        if project_id not in self._objects:
            self._objects[project_id] = {}
        return self._objects[project_id]

    def _get_project_files(self, project_id: str) -> dict[str, StoredFile]:
        if project_id not in self._files:
            self._files[project_id] = {}
        return self._files[project_id]

    def _get_project_tables(self, project_id: str) -> dict[str, StoredTable]:
        if project_id not in self._tables:
            self._tables[project_id] = {}
        return self._tables[project_id]

    def _get_project_table_rows(self, project_id: str) -> dict[str, StoredTableRow]:
        if project_id not in self._table_rows:
            self._table_rows[project_id] = {}
        return self._table_rows[project_id]

    # Call operations
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        with self._lock:
            start = req.start
            call_id = start.id or generate_id()
            trace_id = start.trace_id or generate_id()

            stored_call = StoredCall(
                project_id=start.project_id,
                id=call_id,
                trace_id=trace_id,
                op_name=start.op_name,
                started_at=start.started_at,
                parent_id=start.parent_id,
                thread_id=start.thread_id,
                turn_id=start.turn_id,
                attributes=start.attributes or {},
                inputs=start.inputs or {},
                input_refs=extract_refs_from_values(list((start.inputs or {}).values())),
                display_name=start.display_name,
                wb_user_id=start.wb_user_id,
                wb_run_id=start.wb_run_id,
                wb_run_step=start.wb_run_step,
            )

            project_calls = self._get_project_calls(start.project_id)
            project_calls[call_id] = stored_call

            return tsi.CallStartRes(id=call_id, trace_id=trace_id)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        with self._lock:
            end = req.end
            # Find the call across all projects
            for project_calls in self._calls.values():
                if end.id in project_calls:
                    call = project_calls[end.id]
                    call.ended_at = end.ended_at
                    call.exception = end.exception
                    call.output = end.output
                    call.summary = end.summary
                    if end.output:
                        parsable = end.output if isinstance(end.output, dict) else {"output": end.output}
                        call.output_refs = extract_refs_from_values(list(parsable.values()))
                    return tsi.CallEndRes()

            return tsi.CallEndRes()

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        res = []
        for item in req.batch:
            if item.mode == "start":
                res.append(self.call_start(item.req))
            elif item.mode == "end":
                res.append(self.call_end(item.req))
        return tsi.CallCreateBatchRes(res=res)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        with self._lock:
            project_calls = self._get_project_calls(req.project_id)
            call = project_calls.get(req.id)
            if call and call.deleted_at is None:
                return tsi.CallReadRes(call=call.to_call_schema())
            return tsi.CallReadRes(call=None)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        with self._lock:
            project_calls = self._get_project_calls(req.project_id)
            results: list[tsi.CallSchema] = []

            for call in project_calls.values():
                if call.deleted_at is not None:
                    continue

                # Apply filters
                if req.filter:
                    if req.filter.call_ids and call.id not in req.filter.call_ids:
                        continue
                    if req.filter.trace_ids and call.trace_id not in req.filter.trace_ids:
                        continue
                    if req.filter.op_names and call.op_name not in req.filter.op_names:
                        continue
                    if req.filter.parent_ids and call.parent_id not in req.filter.parent_ids:
                        continue

                results.append(call.to_call_schema())

            # Apply limit
            if req.limit:
                results = results[: req.limit]

            return tsi.CallsQueryRes(calls=results)

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        result = self.calls_query(req)
        yield from result.calls

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        with self._lock:
            project_calls = self._get_project_calls(req.project_id)
            now = datetime.datetime.now(datetime.timezone.utc)
            num_deleted = 0
            for call_id in req.call_ids:
                if call_id in project_calls and project_calls[call_id].deleted_at is None:
                    project_calls[call_id].deleted_at = now
                    num_deleted += 1
            return tsi.CallsDeleteRes(num_deleted=num_deleted)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        result = self.calls_query(
            tsi.CallsQueryReq(project_id=req.project_id, filter=req.filter)
        )
        return tsi.CallsQueryStatsRes(count=len(result.calls))

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        with self._lock:
            project_calls = self._get_project_calls(req.project_id)
            if req.call_id in project_calls:
                project_calls[req.call_id].display_name = req.display_name
            return tsi.CallUpdateRes()

    # Object operations
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        with self._lock:
            obj = req.obj
            processed = process_incoming_object_val(obj.val)
            val = processed.get("val", obj.val)
            base_object_class = processed.get("base_object_class")
            leaf_object_class = processed.get("leaf_object_class")
            digest = str_digest(json.dumps(val))

            # Extract refs from val
            refs = extract_refs_from_values([val]) if val else []

            project_objs = self._get_project_objects(obj.project_id)

            # Check if this exact version already exists
            key = (obj.object_id, digest)
            if key in project_objs:
                existing = project_objs[key]
                if existing.deleted_at is None:
                    return tsi.ObjCreateRes(digest=digest)

            # Update is_latest for existing versions
            version_index = 0
            for existing_key, existing_obj in project_objs.items():
                if existing_key[0] == obj.object_id and existing_obj.deleted_at is None:
                    existing_obj.is_latest = False
                    version_index = max(version_index, existing_obj.version_index + 1)

            # Determine kind based on base_object_class or weave_type
            is_op = base_object_class == "Op"
            # Also check for CustomWeaveType with weave_type.type == "Op"
            if not is_op and isinstance(val, dict):
                if val.get("_type") == "CustomWeaveType":
                    weave_type = val.get("weave_type", {})
                    if isinstance(weave_type, dict) and weave_type.get("type") == "Op":
                        is_op = True
            kind = "op" if is_op else "object"

            stored_obj = StoredObject(
                project_id=obj.project_id,
                object_id=obj.object_id,
                digest=digest,
                val=val,
                kind=kind,
                base_object_class=base_object_class,
                leaf_object_class=leaf_object_class,
                refs=refs,
                wb_user_id=obj.wb_user_id,
                version_index=version_index,
                is_latest=True,
            )

            project_objs[key] = stored_obj
            return tsi.ObjCreateRes(digest=digest)

    def obj_create_batch(self, batch: list[tsi.ObjSchemaForInsert]) -> list[tsi.ObjCreateRes]:
        # Validate all objects are for the same project
        if batch:
            project_ids = {obj.project_id for obj in batch}
            if len(project_ids) > 1:
                raise InvalidRequest("obj_create_batch only supports updating a single project.")

        results = []
        for obj in batch:
            results.append(self.obj_create(tsi.ObjCreateReq(obj=obj)))
        return results

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        with self._lock:
            project_objs = self._get_project_objects(req.project_id)

            # Handle "latest" digest
            if req.digest == "latest":
                for (obj_id, _), obj in project_objs.items():
                    if obj_id == req.object_id and obj.is_latest and obj.deleted_at is None:
                        return tsi.ObjReadRes(obj=obj.to_obj_schema())
                raise NotFoundError(f"Object {req.object_id} not found")

            # Find by specific digest
            key = (req.object_id, req.digest)
            if key in project_objs:
                obj = project_objs[key]
                if obj.deleted_at is not None:
                    raise ObjectDeletedError(
                        f"Object {req.object_id}:{req.digest} has been deleted",
                        deleted_at=obj.deleted_at,
                    )
                return tsi.ObjReadRes(obj=obj.to_obj_schema())

            raise NotFoundError(f"Object {req.object_id}:{req.digest} not found")

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        with self._lock:
            project_objs = self._get_project_objects(req.project_id)
            results: list[tsi.ObjSchema] = []

            for (obj_id, digest), obj in project_objs.items():
                if obj.deleted_at is not None:
                    continue

                # Apply filters
                if req.filter:
                    if req.filter.object_ids and obj_id not in req.filter.object_ids:
                        continue
                    if req.filter.latest_only and not obj.is_latest:
                        continue
                    if req.filter.is_op is not None:
                        is_op = obj.kind == "op"
                        if req.filter.is_op != is_op:
                            continue
                    if req.filter.base_object_classes:
                        if obj.base_object_class not in req.filter.base_object_classes:
                            continue

                results.append(obj.to_obj_schema())

            # Apply offset and limit
            if req.offset:
                results = results[req.offset :]
            if req.limit:
                results = results[: req.limit]

            return tsi.ObjQueryRes(objs=results)

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        with self._lock:
            project_objs = self._get_project_objects(req.project_id)
            now = datetime.datetime.now(datetime.timezone.utc)
            num_deleted = 0

            # First, find matching objects
            matching_objects = []
            if req.digests is None:
                # Find all versions of the object
                for (obj_id, digest), obj in project_objs.items():
                    if obj_id == req.object_id and obj.deleted_at is None:
                        matching_objects.append((obj_id, digest, obj))
            else:
                # Find specific versions
                for digest in req.digests:
                    key = (req.object_id, digest)
                    if key in project_objs and project_objs[key].deleted_at is None:
                        matching_objects.append((req.object_id, digest, project_objs[key]))

            # Raise NotFoundError if no matching objects
            if not matching_objects:
                raise NotFoundError(
                    f"Object {req.object_id} ({req.digests}) not found when deleting."
                )

            # Delete the matching objects
            for obj_id, digest, obj in matching_objects:
                obj.deleted_at = now
                num_deleted += 1

            return tsi.ObjDeleteRes(num_deleted=num_deleted)

    # File operations
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        with self._lock:
            content = req.content
            if isinstance(content, str):
                content = content.encode("utf-8")
            digest = bytes_digest(content)

            project_files = self._get_project_files(req.project_id)
            if digest not in project_files:
                project_files[digest] = StoredFile(
                    project_id=req.project_id,
                    digest=digest,
                    content=content,
                )

            return tsi.FileCreateRes(digest=digest)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        with self._lock:
            project_files = self._get_project_files(req.project_id)
            if req.digest in project_files:
                return tsi.FileContentReadRes(content=project_files[req.digest].content)
            raise NotFoundError(f"File {req.digest} not found")

    # Feedback operations
    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        with self._lock:
            feedback_id = generate_id()
            now = datetime.datetime.now(datetime.timezone.utc)

            if req.project_id not in self._feedback:
                self._feedback[req.project_id] = {}

            self._feedback[req.project_id][feedback_id] = {
                "id": feedback_id,
                "project_id": req.project_id,
                "weave_ref": req.weave_ref,
                "feedback_type": req.feedback_type,
                "payload": req.payload,
                "creator": req.creator,
                "created_at": now,
                "wb_user_id": req.wb_user_id,
            }

            return tsi.FeedbackCreateRes(
                id=feedback_id,
                created_at=now,
                wb_user_id=req.wb_user_id,
                payload=req.payload or {},
            )

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        with self._lock:
            if req.project_id not in self._feedback:
                return tsi.FeedbackQueryRes(result=[])

            results = []
            for fb in self._feedback[req.project_id].values():
                results.append(
                    tsi.Feedback(
                        id=fb["id"],
                        project_id=fb["project_id"],
                        weave_ref=fb["weave_ref"],
                        feedback_type=fb["feedback_type"],
                        payload=fb["payload"],
                        creator=fb.get("creator"),
                        created_at=fb["created_at"],
                        wb_user_id=fb.get("wb_user_id"),
                    )
                )

            return tsi.FeedbackQueryRes(result=results)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        with self._lock:
            if req.project_id in self._feedback:
                self._feedback[req.project_id].clear()
            return tsi.FeedbackPurgeRes()

    # Table operations
    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        with self._lock:
            import hashlib

            project_tables = self._get_project_tables(req.table.project_id)
            project_rows = self._get_project_table_rows(req.table.project_id)

            row_digests = []
            for row in req.table.rows:
                if not isinstance(row, dict):
                    raise TypeError("All rows must be dictionaries")
                row_json = json.dumps(row)
                row_digest = str_digest(row_json)
                row_digests.append(row_digest)

                if row_digest not in project_rows:
                    project_rows[row_digest] = StoredTableRow(
                        project_id=req.table.project_id,
                        digest=row_digest,
                        val=row,
                    )

            # Calculate table digest
            table_hasher = hashlib.sha256()
            for row_digest in row_digests:
                table_hasher.update(row_digest.encode())
            digest = table_hasher.hexdigest()

            if digest not in project_tables:
                project_tables[digest] = StoredTable(
                    project_id=req.table.project_id,
                    digest=digest,
                    row_digests=row_digests,
                )

            return tsi.TableCreateRes(digest=digest, row_digests=row_digests)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        # Simple stub - just return a new digest
        return tsi.TableUpdateRes(digest="stub")

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        with self._lock:
            project_tables = self._get_project_tables(req.project_id)
            project_rows = self._get_project_table_rows(req.project_id)

            if req.digest not in project_tables:
                return tsi.TableQueryRes(rows=[])

            table = project_tables[req.digest]
            rows = []
            for row_digest in table.row_digests:
                if row_digest in project_rows:
                    rows.append(
                        tsi.TableRowSchema(
                            digest=row_digest,
                            val=project_rows[row_digest].val,
                        )
                    )
            return tsi.TableQueryRes(rows=rows)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        result = self.table_query(req)
        yield from result.rows

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        with self._lock:
            project_tables = self._get_project_tables(req.project_id)
            if req.digest not in project_tables:
                return tsi.TableQueryStatsRes(count=0)
            return tsi.TableQueryStatsRes(count=len(project_tables[req.digest].row_digests))

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return tsi.RefsReadBatchRes(vals=[])

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        return tsi.CostCreateRes(ids=[])

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        return tsi.CostQueryRes(results=[])

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        return tsi.CostPurgeRes()

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        return tsi.ActionsExecuteBatchRes(results=[])

    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        raise NotImplementedError("completions_create not supported in mock")

    def execute_batch_action(
        self, req: tsi.ExecuteBatchActionReq
    ) -> tsi.ExecuteBatchActionRes:
        return tsi.ExecuteBatchActionRes()

    def process_server_pushdown_scalars(
        self, req: tsi.ProcessServerPushdownScalarsReq
    ) -> tsi.ProcessServerPushdownScalarsRes:
        return tsi.ProcessServerPushdownScalarsRes(results=[])

    # Op V2 API operations
    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        """Create an op object by delegating to obj_create."""
        # Store source code as a file (use placeholder if not provided)
        source_code = req.source_code or object_creation_utils.PLACEHOLDER_OP_SOURCE
        source_file_req = tsi.FileCreateReq(
            project_id=req.project_id,
            name=object_creation_utils.OP_SOURCE_FILE_NAME,
            content=source_code.encode("utf-8"),
        )
        source_file_res = self.file_create(source_file_req)

        # Build the op object value structure with the file digest
        op_val = object_creation_utils.build_op_val(source_file_res.digest)
        object_id = object_creation_utils.make_object_id(req.name, "Op")

        # Create the object
        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=object_id,
                val=op_val,
            )
        )
        obj_result = self.obj_create(obj_req)

        # Query back to get version_index
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=object_id,
            digest=obj_result.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        return tsi.OpCreateRes(
            digest=obj_result.digest,
            object_id=object_id,
            version_index=obj_read_res.obj.version_index,
        )

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        """Get a specific op object by delegating to obj_read."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
            metadata_only=False,
        )
        result = self.obj_read(obj_req)

        # Extract code from the file storage
        val = result.obj.val
        code = ""

        # Check if this is a file-based op
        if isinstance(val, dict) and val.get("_type") == "CustomWeaveType":
            files = val.get("files", {})
            if object_creation_utils.OP_SOURCE_FILE_NAME in files:
                file_digest = files[object_creation_utils.OP_SOURCE_FILE_NAME]
                try:
                    file_content_res = self.file_content_read(
                        tsi.FileContentReadReq(
                            project_id=req.project_id, digest=file_digest
                        )
                    )
                    code = file_content_res.content.decode("utf-8")
                except Exception:
                    pass

        return tsi.OpReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            code=code,
        )

    def op_list(self, req: tsi.OpListReq) -> Iterator[tsi.OpReadRes]:
        """List op objects by delegating to objs_query with op filtering."""
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(
                is_op=True,
                latest_only=True,
            ),
            limit=req.limit,
            offset=req.offset,
            metadata_only=False,
        )
        result = self.objs_query(obj_query_req)

        for obj in result.objs:
            code = ""

            try:
                val = obj.val
                if isinstance(val, dict) and val.get("_type") == "CustomWeaveType":
                    files = val.get("files", {})
                    if object_creation_utils.OP_SOURCE_FILE_NAME in files:
                        file_digest = files[object_creation_utils.OP_SOURCE_FILE_NAME]
                        try:
                            file_content_res = self.file_content_read(
                                tsi.FileContentReadReq(
                                    project_id=req.project_id, digest=file_digest
                                )
                            )
                            code = file_content_res.content.decode("utf-8")
                        except Exception:
                            pass
            except Exception:
                pass

            yield tsi.OpReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                code=code,
            )

    def op_delete(self, req: tsi.OpDeleteReq) -> tsi.OpDeleteRes:
        """Delete op objects by delegating to obj_delete."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.OpDeleteRes(num_deleted=result.num_deleted)

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        """Legacy op query method."""
        obj_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(
                is_op=True,
                latest_only=req.filter.latest_only if req.filter else True,
            ),
        )
        result = self.objs_query(obj_req)
        return tsi.OpQueryRes(
            op_objs=[
                tsi.OpObjSchema(
                    project_id=obj.project_id,
                    object_id=obj.object_id,
                    created_at=obj.created_at,
                    digest=obj.digest,
                    version_index=obj.version_index,
                    is_latest=obj.is_latest,
                    val=obj.val,
                )
                for obj in result.objs
            ]
        )

    def threads_query(self, req: tsi.ThreadsQueryReq) -> tsi.ThreadsQueryRes:
        return tsi.ThreadsQueryRes(results=[])

    def image_generation_create(
        self, req: tsi.ImageGenerationCreateReq
    ) -> tsi.ImageGenerationCreateRes:
        raise NotImplementedError("image_generation_create not supported in mock")

    def prompt_create(self, req: tsi.PromptCreateReq) -> tsi.PromptCreateRes:
        raise NotImplementedError("prompt_create not supported in mock")

    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        return tsi.OtelExportRes()

    # Dataset V2 API operations
    def dataset_create(self, req: tsi.DatasetCreateReq) -> tsi.DatasetCreateRes:
        """Create a dataset object by first creating a table for rows, then creating the dataset object."""
        # Create a safe ID for the dataset
        dataset_id = object_creation_utils.make_object_id(req.name, "Dataset")

        # Create a table and get its ref
        table_req = tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=req.project_id,
                rows=req.rows,
            )
        )
        table_res = self.table_create(table_req)
        table_ref = ri.InternalTableRef(
            project_id=req.project_id,
            digest=table_res.digest,
        ).uri()

        # Create the dataset object
        dataset_val = object_creation_utils.build_dataset_val(
            name=req.name,
            description=req.description,
            table_ref=table_ref,
        )
        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=dataset_id,
                val=dataset_val,
                wb_user_id=None,
            )
        )
        obj_result = self.obj_create(obj_req)

        # Query the object back to get its version index
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=dataset_id,
            digest=obj_result.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        return tsi.DatasetCreateRes(
            digest=obj_result.digest,
            object_id=dataset_id,
            version_index=obj_read_res.obj.version_index,
        )

    def dataset_read(self, req: tsi.DatasetReadReq) -> tsi.DatasetReadRes:
        """Get a dataset object by delegating to obj_read."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self.obj_read(obj_req)
        val = result.obj.val

        # Extract name, description, and rows ref from val data
        name = val.get("name")
        description = val.get("description")
        rows_ref = val.get("rows", "")

        return tsi.DatasetReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=name,
            description=description,
            rows=rows_ref,
        )

    def dataset_list(self, req: tsi.DatasetListReq) -> Iterator[tsi.DatasetReadRes]:
        """List dataset objects by delegating to objs_query with Dataset filtering."""
        dataset_filter = tsi.ObjectVersionFilter(
            base_object_classes=["Dataset"], is_op=False
        )
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=dataset_filter,
            limit=req.limit,
            offset=req.offset,
        )
        obj_res = self.objs_query(obj_query_req)

        for obj in obj_res.objs:
            if not hasattr(obj, "val") or not obj.val:
                continue

            val = obj.val
            if not isinstance(val, dict):
                continue

            name = val.get("name")
            description = val.get("description")
            rows_ref = val.get("rows", "")

            yield tsi.DatasetReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=name,
                description=description,
                rows=rows_ref,
            )

    def dataset_delete(self, req: tsi.DatasetDeleteReq) -> tsi.DatasetDeleteRes:
        """Delete dataset objects by delegating to obj_delete."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.DatasetDeleteRes(num_deleted=result.num_deleted)

    # Scorer V2 API operations
    def scorer_create(self, req: tsi.ScorerCreateReq) -> tsi.ScorerCreateRes:
        """Create a scorer object by first creating its score op, then creating the scorer object."""
        # Generate a safe ID for the scorer
        scorer_id = object_creation_utils.make_object_id(req.name, "Scorer")

        # Create the score op first
        score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{scorer_id}_score",
            source_code=req.op_source_code,
        )
        score_op_res = self.op_create(score_op_req)
        score_op_ref = score_op_res.digest

        # Create the default summarize op
        summarize_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{scorer_id}_summarize",
            source_code=object_creation_utils.PLACEHOLDER_SCORER_SUMMARIZE_OP_SOURCE,
        )
        summarize_op_res = self.op_create(summarize_op_req)
        summarize_op_ref = summarize_op_res.digest

        # Create the scorer object using shared utility for val
        scorer_val = object_creation_utils.build_scorer_val(
            name=req.name,
            description=req.description,
            score_op_ref=score_op_ref,
            summarize_op_ref=summarize_op_ref,
        )

        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=scorer_id,
                val=scorer_val,
                wb_user_id=None,
            )
        )
        obj_result = self.obj_create(obj_req)

        # Query back to get version_index
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=scorer_id,
            digest=obj_result.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        # Construct the scorer reference using InternalObjectRef
        scorer_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=scorer_id,
            version=obj_result.digest,
        ).uri()

        return tsi.ScorerCreateRes(
            digest=obj_result.digest,
            object_id=scorer_id,
            version_index=obj_read_res.obj.version_index,
            scorer=scorer_ref,
        )

    def scorer_read(self, req: tsi.ScorerReadReq) -> tsi.ScorerReadRes:
        """Get scorer objects by delegating to obj_read."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self.obj_read(obj_req)
        val = result.obj.val

        # Extract name and description from val data
        name = val.get("name", result.obj.object_id)
        description = val.get("description")

        return tsi.ScorerReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=name,
            description=description,
            score_op=val.get("score", ""),
        )

    def scorer_list(self, req: tsi.ScorerListReq) -> Iterator[tsi.ScorerReadRes]:
        """List scorer objects by delegating to objs_query with Scorer filtering."""
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(base_object_classes=["Scorer"], is_op=False),
            limit=req.limit,
            offset=req.offset,
        )
        result = self.objs_query(obj_query_req)

        for obj in result.objs:
            # Extract name, description, and score_op from val data
            name = obj.object_id  # fallback to object_id
            description = None
            score_op = ""

            if hasattr(obj, "val") and obj.val:
                val = obj.val
                if isinstance(val, dict):
                    name = val.get("name", obj.object_id)
                    description = val.get("description")
                    score_op = val.get("score", "")

            yield tsi.ScorerReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=name,
                description=description,
                score_op=score_op,
            )

    def scorer_delete(self, req: tsi.ScorerDeleteReq) -> tsi.ScorerDeleteRes:
        """Delete scorer objects by delegating to obj_delete."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.ScorerDeleteRes(num_deleted=result.num_deleted)

    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        with self._lock:
            calls = self._get_project_calls(req.project_id)
            return tsi.ProjectStatsRes(
                trace_count=len(set(c.trace_id for c in calls.values() if c.deleted_at is None))
            )

    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        raise NotImplementedError("evaluate_model not supported in mock")

    def evaluation_status(self, req: tsi.EvaluationStatusReq) -> tsi.EvaluationStatusRes:
        raise NotImplementedError("evaluation_status not supported in mock")

    # Utility methods
    def clear(self) -> None:
        """Clear all stored data."""
        with self._lock:
            self._calls.clear()
            self._objects.clear()
            self._files.clear()
            self._feedback.clear()
            self._tables.clear()
            self._table_rows.clear()
