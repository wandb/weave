"""Mock Trace Server for testing without real database backends.

This module provides an in-memory mock implementation of the TraceServerInterface
that can be used in tests to avoid dependencies on ClickHouse or SQLite.
"""

from __future__ import annotations

import copy
import datetime
import functools
import hashlib
import json
from collections.abc import Iterator
from typing import Any

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server.interface import query as q
from weave.trace_server.trace_server_interface_util import bytes_digest, str_digest
from weave.trace_server.object_class_util import process_incoming_object_val
from weave.trace_server.trace_server_common import make_derived_summary_fields


def _get_type(val: Any) -> str:
    """Get the type of a value for kind determination."""
    if isinstance(val, dict):
        if "_class_name" in val:
            return val["_class_name"]
        return "dict"
    elif isinstance(val, list):
        return "list"
    return "unknown"


def _get_kind(val: Any) -> str:
    """Get the kind (op or object) from a value."""
    val_type = _get_type(val)
    if val_type == "Op":
        return "op"
    return "object"


def _get_nested_value(obj: Any, path: str) -> Any:
    """Get a nested value from an object using a dotted path.

    Supports:
    - Object attributes (e.g., "started_at")
    - Dict keys (e.g., "inputs.in_val.prim")
    - List indices (e.g., "inputs.list.0")
    """
    parts = path.split(".")
    value = obj

    for part in parts:
        if value is None:
            return None

        # Try as object attribute first
        if hasattr(value, part) and not isinstance(value, dict):
            value = getattr(value, part)
        elif isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list):
            # Try to parse as integer index
            try:
                idx = int(part)
                value = value[idx] if 0 <= idx < len(value) else None
            except (ValueError, IndexError):
                return None
        else:
            return None

    return value


def _evaluate_operand(operand: q.Operand, call: tsi.CallSchema) -> Any:
    """Evaluate a query operand against a call."""
    if isinstance(operand, q.LiteralOperation):
        return operand.literal_
    elif isinstance(operand, q.GetFieldOperator):
        return _get_nested_value(call, operand.get_field_)
    elif isinstance(operand, q.ConvertOperation):
        value = _evaluate_operand(operand.convert_.input, call)
        target_type = operand.convert_.to
        if target_type == "int":
            return int(value) if value is not None else None
        elif target_type == "double":
            return float(value) if value is not None else None
        elif target_type == "string":
            return str(value) if value is not None else None
        elif target_type == "bool":
            return bool(value) if value is not None else None
        elif target_type == "exists":
            return value is not None
        return value
    elif isinstance(operand, (q.AndOperation, q.OrOperation, q.NotOperation,
                               q.EqOperation, q.GtOperation, q.GteOperation,
                               q.InOperation, q.ContainsOperation)):
        return _evaluate_operation(operand, call)
    return None


def _evaluate_operation(operation: q.Operation, call: tsi.CallSchema) -> bool:
    """Evaluate a query operation against a call."""
    if isinstance(operation, q.AndOperation):
        return all(_evaluate_operand(op, call) for op in operation.and_)
    elif isinstance(operation, q.OrOperation):
        return any(_evaluate_operand(op, call) for op in operation.or_)
    elif isinstance(operation, q.NotOperation):
        return not _evaluate_operand(operation.not_[0], call)
    elif isinstance(operation, q.EqOperation):
        left = _evaluate_operand(operation.eq_[0], call)
        right = _evaluate_operand(operation.eq_[1], call)
        return left == right
    elif isinstance(operation, q.GtOperation):
        left = _evaluate_operand(operation.gt_[0], call)
        right = _evaluate_operand(operation.gt_[1], call)
        if left is None or right is None:
            return False
        return left > right
    elif isinstance(operation, q.GteOperation):
        left = _evaluate_operand(operation.gte_[0], call)
        right = _evaluate_operand(operation.gte_[1], call)
        if left is None or right is None:
            return False
        return left >= right
    elif isinstance(operation, q.InOperation):
        left = _evaluate_operand(operation.in_[0], call)
        right_list = [_evaluate_operand(op, call) for op in operation.in_[1]]
        return left in right_list
    elif isinstance(operation, q.ContainsOperation):
        input_val = _evaluate_operand(operation.contains_.input, call)
        substr = _evaluate_operand(operation.contains_.substr, call)
        if input_val is None or substr is None:
            return False
        if operation.contains_.case_insensitive:
            return str(substr).lower() in str(input_val).lower()
        return str(substr) in str(input_val)
    return False


def _evaluate_query(query: q.Query, call: tsi.CallSchema) -> bool:
    """Evaluate a query against a call."""
    return _evaluate_operation(query.expr_, call)


class NotFoundError(Exception):
    """Exception raised when a resource is not found in the mock server."""
    pass


class MockTraceServer:
    """In-memory mock implementation of TraceServerInterface.

    Stores all data in memory dictionaries for fast, isolated testing.
    """

    def __init__(self):
        # Storage
        self.calls: dict[str, tsi.CallSchema] = {}
        self.objs: dict[str, dict[str, Any]] = {}
        self.tables: dict[str, dict[str, Any]] = {}
        self.files: dict[str, bytes] = {}
        self.feedback: dict[str, tsi.FeedbackDict] = {}
        self.costs: dict[str, Any] = {}
        self.projects: set[str] = set()

        # Track latest timestamps for ordering
        self.call_order: list[str] = []

        # Self-reference for compatibility with client_is_sqlite checks
        # This is used by tests that check `._internal_trace_server`
        self._internal_trace_server = self

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        project_id = f"{entity}/{project}"
        self.projects.add(project_id)
        return tsi.EnsureProjectExistsRes(project_name=project)

    # OTEL API
    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        return tsi.OtelExportRes()

    # Call API
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        call_id = req.start.id or generate_id()
        trace_id = req.start.trace_id or call_id

        # Make deep copies to prevent mutation by client-side deserialization
        inputs_copy = copy.deepcopy(req.start.inputs)
        attributes_copy = copy.deepcopy(req.start.attributes) or {}

        call = tsi.CallSchema(
            id=call_id,
            project_id=req.start.project_id,
            op_name=req.start.op_name,
            display_name=req.start.display_name,
            trace_id=trace_id,
            parent_id=req.start.parent_id,
            thread_id=req.start.thread_id,
            turn_id=req.start.turn_id,
            started_at=req.start.started_at,
            attributes=attributes_copy,
            inputs=inputs_copy,
            ended_at=None,
            exception=None,
            output=None,
            summary=None,
            wb_user_id=req.start.wb_user_id,
            wb_run_id=req.start.wb_run_id,
            wb_run_step=req.start.wb_run_step,
            wb_run_step_end=None,
            deleted_at=None,
        )

        self.calls[call_id] = call
        self.call_order.append(call_id)

        return tsi.CallStartRes(
            id=call_id,
            trace_id=trace_id,
        )

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        if req.end.id not in self.calls:
            raise NotFoundError(f"Call {req.end.id} not found")

        call = self.calls[req.end.id]
        call.ended_at = req.end.ended_at
        call.exception = req.end.exception
        call.output = req.end.output
        call.wb_run_step_end = req.end.wb_run_step_end

        # Process summary to add derived fields (weave.status, weave.latency_ms, etc.)
        summary = copy.deepcopy(req.end.summary) if req.end.summary else {}
        try:
            call.summary = make_derived_summary_fields(
                summary=summary,
                op_name=call.op_name,
                started_at=call.started_at,
                ended_at=call.ended_at,
                exception=call.exception,
                display_name=call.display_name,
            )
        except Exception:
            # If make_derived_summary_fields fails (e.g., due to ref parsing issues),
            # fall back to manual summary construction
            call.summary = self._make_summary_fallback(
                summary=summary,
                call=call,
            )

        return tsi.CallEndRes()

    def _make_summary_fallback(
        self,
        summary: dict[str, Any],
        call: tsi.CallSchema,
    ) -> dict[str, Any]:
        """Fallback summary construction when make_derived_summary_fields fails."""
        weave_summary = summary.pop("weave", {})

        # Determine status
        if call.exception:
            status = tsi.TraceStatus.ERROR
        elif call.ended_at is None:
            status = tsi.TraceStatus.RUNNING
        elif summary.get("status_counts", {}).get(tsi.TraceStatus.ERROR, 0) > 0:
            status = tsi.TraceStatus.DESCENDANT_ERROR
        else:
            status = tsi.TraceStatus.SUCCESS
        weave_summary["status"] = status

        # Calculate latency
        if call.ended_at and call.started_at:
            delta = call.ended_at - call.started_at
            days = delta.days
            seconds = delta.seconds
            milliseconds = delta.microseconds // 1000
            weave_summary["latency_ms"] = (days * 24 * 60 * 60 + seconds) * 1000 + milliseconds

        # Set display_name or trace_name
        if call.display_name:
            weave_summary["display_name"] = call.display_name
        else:
            # Extract trace_name from op_name
            op_name = call.op_name
            # Try to get the name part from URIs like "weave:///entity/project/op/name:hash"
            if op_name.startswith("weave:///"):
                parts = op_name.split("/")
                if len(parts) >= 5 and parts[3] == "op":
                    name_with_hash = parts[4]
                    # Remove the hash suffix (e.g., "x:C6hohMXy..." -> "x")
                    name = name_with_hash.split(":")[0]
                    weave_summary["trace_name"] = name
                else:
                    weave_summary["trace_name"] = op_name
            else:
                weave_summary["trace_name"] = op_name

        summary["weave"] = weave_summary
        return summary

    def _ensure_call_summary(self, call: tsi.CallSchema) -> tsi.CallSchema:
        """Ensure a call has proper summary fields computed."""
        summary = copy.deepcopy(call.summary) if call.summary else {}
        try:
            call.summary = make_derived_summary_fields(
                summary=summary,
                op_name=call.op_name,
                started_at=call.started_at,
                ended_at=call.ended_at,
                exception=call.exception,
                display_name=call.display_name,
            )
        except Exception:
            call.summary = self._make_summary_fallback(
                summary=summary,
                call=call,
            )
        return call

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        if req.id not in self.calls:
            raise NotFoundError(f"Call {req.id} not found")

        # Return a deep copy to prevent mutation by client-side deserialization (from_json pops _type)
        call = copy.deepcopy(self.calls[req.id])
        # Ensure summary is computed
        call = self._ensure_call_summary(call)
        return tsi.CallReadRes(call=call)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        calls = list(self.calls_query_stream(req))
        return tsi.CallsQueryRes(calls=calls)

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        # Filter calls by project_id and compute summaries
        # We compute summaries first so that query filters can access summary fields
        filtered_calls = []
        for call in self.calls.values():
            if call.project_id == req.project_id:
                call_copy = copy.deepcopy(call)
                call_copy = self._ensure_call_summary(call_copy)
                filtered_calls.append(call_copy)

        # Apply filters if provided
        if req.filter:
            filtered_calls = self._apply_call_filters(filtered_calls, req.filter)

        # Apply query filter if provided
        if req.query:
            filtered_calls = [c for c in filtered_calls if _evaluate_query(req.query, c)]

        # Apply sorting - default to started_at ascending (oldest first), matching SQLite
        if req.sort_by is None:
            # Default sort: oldest first
            filtered_calls.sort(key=lambda c: c.started_at)
        elif len(req.sort_by) > 0:
            # Apply custom sort
            for sort_spec in reversed(req.sort_by):
                reverse = sort_spec.direction == "desc"
                field = sort_spec.field

                def get_sort_value(call: tsi.CallSchema, field_path: str):
                    """Get value and type order for sorting.

                    Returns (type_order, value, is_none) where:
                    - type_order: 0 for numbers, 1 for strings, 2 for None
                    - value: the actual value for comparison
                    - is_none: True if the value is None
                    """
                    value = _get_nested_value(call, field_path)
                    if value is None:
                        return (2, None, True)
                    elif isinstance(value, bool):
                        return (0, int(value), False)
                    elif isinstance(value, (int, float)):
                        return (0, value, False)
                    elif isinstance(value, str):
                        return (1, value, False)
                    else:
                        return (1, str(value), False)

                # Custom sort that maintains type order but reverses value order for desc
                def mixed_type_cmp(a: tsi.CallSchema, b: tsi.CallSchema) -> int:
                    a_type, a_val, a_none = get_sort_value(a, field)
                    b_type, b_val, b_none = get_sort_value(b, field)

                    # None always sorts last
                    if a_none and b_none:
                        return 0
                    if a_none:
                        return 1  # a after b
                    if b_none:
                        return -1  # a before b

                    # Different types: numbers before strings (always)
                    if a_type != b_type:
                        return a_type - b_type

                    # Same type: compare values with direction
                    if a_val == b_val:
                        return 0
                    if reverse:
                        return -1 if a_val > b_val else 1  # desc: larger first
                    else:
                        return -1 if a_val < b_val else 1  # asc: smaller first

                filtered_calls.sort(key=functools.cmp_to_key(mixed_type_cmp))

        # Apply limit and offset
        offset = req.offset or 0
        limit = req.limit

        if limit is not None:
            filtered_calls = filtered_calls[offset:offset + limit]
        else:
            filtered_calls = filtered_calls[offset:]

        # Return deep copies (summaries already computed at the start)
        for call in filtered_calls:
            yield copy.deepcopy(call)

    def _apply_call_filters(
        self, calls: list[tsi.CallSchema], filter_obj: tsi.CallsFilter
    ) -> list[tsi.CallSchema]:
        """Apply filters to calls list."""
        filtered = calls

        # Filter by op_names
        if filter_obj.op_names:
            filtered = [c for c in filtered if c.op_name in filter_obj.op_names]

        # Filter by trace_ids
        if filter_obj.trace_ids:
            filtered = [c for c in filtered if c.trace_id in filter_obj.trace_ids]

        # Filter by parent_ids
        if filter_obj.parent_ids:
            filtered = [c for c in filtered if c.parent_id in filter_obj.parent_ids]

        # Filter by call_ids
        if filter_obj.call_ids:
            filtered = [c for c in filtered if c.id in filter_obj.call_ids]

        # Filter by trace_roots_only
        if filter_obj.trace_roots_only:
            filtered = [c for c in filtered if c.parent_id is None]

        # Filter by wb_user_ids
        if filter_obj.wb_user_ids:
            filtered = [c for c in filtered if c.wb_user_id in filter_obj.wb_user_ids]

        # Filter by wb_run_ids
        if filter_obj.wb_run_ids:
            filtered = [c for c in filtered if c.wb_run_id in filter_obj.wb_run_ids]

        # Filter by input_refs - check if any input value contains one of the refs
        if filter_obj.input_refs:
            def has_input_ref(call: tsi.CallSchema, refs: list[str]) -> bool:
                if not call.inputs:
                    return False
                inputs_str = json.dumps(call.inputs)
                return any(ref in inputs_str for ref in refs)
            filtered = [c for c in filtered if has_input_ref(c, filter_obj.input_refs)]

        # Filter by output_refs - check if output value contains one of the refs
        if filter_obj.output_refs:
            def has_output_ref(call: tsi.CallSchema, refs: list[str]) -> bool:
                if not call.output:
                    return False
                output_str = json.dumps(call.output) if isinstance(call.output, (dict, list)) else str(call.output)
                return any(ref in output_str for ref in refs)
            filtered = [c for c in filtered if has_output_ref(c, filter_obj.output_refs)]

        return filtered

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        deleted_count = 0
        for call_id in req.call_ids:
            if call_id in self.calls:
                del self.calls[call_id]
                if call_id in self.call_order:
                    self.call_order.remove(call_id)
                deleted_count += 1

        return tsi.CallsDeleteRes()

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        # Simple implementation - just return count
        calls = [c for c in self.calls.values() if c.project_id == req.project_id]
        return tsi.CallsQueryStatsRes(count=len(calls))

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        if req.call_id not in self.calls:
            raise NotFoundError(f"Call {req.call_id} not found")

        call = self.calls[req.call_id]
        if req.display_name is not None:
            call.display_name = req.display_name

        return tsi.CallUpdateRes()

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        results = []
        for start_req in req.batch:
            result = self.call_start(tsi.CallStartReq(start=start_req))
            results.append(result)
        return tsi.CallCreateBatchRes(results=results)

    # Cost API
    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        cost_id = generate_id()
        self.costs[cost_id] = {
            "id": cost_id,
            "project_id": req.project_id,
            "llm_id": req.llm_id,
            "cost": req.cost,
        }
        return tsi.CostCreateRes(id=cost_id)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        costs = [
            c for c in self.costs.values()
            if c["project_id"] == req.project_id
        ]
        return tsi.CostQueryRes(results=costs)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        to_delete = [
            cid for cid, c in self.costs.items()
            if c["project_id"] == req.project_id
        ]
        for cid in to_delete:
            del self.costs[cid]
        return tsi.CostPurgeRes()

    # Obj API
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        # Process the incoming object value (same as real servers)
        processed_result = process_incoming_object_val(
            req.obj.val, req.obj.builtin_object_class
        )
        processed_val = processed_result["val"]

        # Generate content-based digest (same as ClickHouse/SQLite servers)
        json_val = json.dumps(processed_val)
        digest = str_digest(json_val)

        key = f"{req.obj.project_id}:{req.obj.object_id}:{digest}"
        self.objs[key] = {
            "project_id": req.obj.project_id,
            "object_id": req.obj.object_id,
            "digest": digest,
            "val": processed_val,
            "created_at": datetime.datetime.now(tz=datetime.timezone.utc),
            "kind": _get_kind(processed_val),
            "base_object_class": processed_result["base_object_class"] or "Object",
        }
        return tsi.ObjCreateRes(digest=digest, object_id=req.obj.object_id)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        key = f"{req.project_id}:{req.object_id}:{req.digest}"
        if key not in self.objs:
            raise NotFoundError(f"Object {key} not found")

        obj_data = self.objs[key]
        return tsi.ObjReadRes(
            obj=tsi.ObjSchema(
                project_id=obj_data["project_id"],
                object_id=obj_data["object_id"],
                created_at=obj_data["created_at"],
                digest=obj_data["digest"],
                version_index=0,
                is_latest=1,
                kind=obj_data["kind"],
                base_object_class=obj_data["base_object_class"],
                val=obj_data["val"],
            )
        )

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        objs = []
        for obj_data in self.objs.values():
            if obj_data["project_id"] != req.project_id:
                continue

            # Apply filters (filter is ObjectVersionFilter model, not dict)
            if req.filter:
                # Filter by object_ids
                if req.filter.object_ids and obj_data["object_id"] not in req.filter.object_ids:
                    continue
                # Filter by base_object_classes
                if req.filter.base_object_classes and obj_data.get("base_object_class") not in req.filter.base_object_classes:
                    continue
                # Filter by is_op
                if req.filter.is_op is not None:
                    is_op = obj_data.get("kind") == "op"
                    if req.filter.is_op != is_op:
                        continue
                # Filter by latest_only
                if req.filter.latest_only:
                    # For now, all objects are "latest" in the mock (we don't track versions)
                    pass

            objs.append(
                tsi.ObjSchema(
                    project_id=obj_data["project_id"],
                    object_id=obj_data["object_id"],
                    created_at=obj_data["created_at"],
                    digest=obj_data["digest"],
                    version_index=0,
                    is_latest=1,
                    kind=obj_data["kind"],
                    base_object_class=obj_data["base_object_class"],
                    val=obj_data["val"],
                )
            )

        return tsi.ObjQueryRes(objs=objs)

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        # Delete all versions of the object
        to_delete = [
            key for key in self.objs.keys()
            if key.startswith(f"{req.project_id}:{req.object_id}:")
        ]
        for key in to_delete:
            del self.objs[key]
        return tsi.ObjDeleteRes()

    # Table API
    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        # Calculate row digests and store rows
        row_digests = []
        for r in req.table.rows:
            if not isinstance(r, dict):
                raise TypeError(
                    f"""Validation Error: Encountered a non-dictionary row when creating a table. Please ensure that all rows are dictionaries. Violating row:\n{r}."""
                )
            row_json = json.dumps(r)
            row_digest = str_digest(row_json)
            row_digests.append(row_digest)
            # Store row by digest for later retrieval
            row_key = f"{req.table.project_id}:row:{row_digest}"
            self.files[row_key] = row_json.encode()  # Reuse files storage for row data

        # Calculate table digest from row digests (same as ClickHouse server)
        table_hasher = hashlib.sha256()
        for row_digest in row_digests:
            table_hasher.update(row_digest.encode())
        digest = table_hasher.hexdigest()

        key = f"{req.table.project_id}:{digest}"
        self.tables[key] = {
            "project_id": req.table.project_id,
            "digest": digest,
            "rows": req.table.rows,
            "row_digests": row_digests,
        }

        return tsi.TableCreateRes(digest=digest)

    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes:
        # Calculate table digest from row digests
        table_hasher = hashlib.sha256()
        for row_digest in req.row_digests:
            table_hasher.update(row_digest.encode())
        digest = table_hasher.hexdigest()

        key = f"{req.project_id}:{digest}"
        self.tables[key] = {
            "project_id": req.project_id,
            "digest": digest,
            "rows": [],  # Will be populated on query from row_digests
            "row_digests": req.row_digests,
        }

        return tsi.TableCreateFromDigestsRes(digest=digest)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        key = f"{req.project_id}:{req.base_digest}"
        if key not in self.tables:
            raise NotFoundError(f"Table {key} not found")

        # Get existing row digests
        base_row_digests = list(self.tables[key].get("row_digests", []))
        base_rows = list(self.tables[key]["rows"])
        updated_digests: list[str] = []

        # Apply each update operation in order
        for update in req.updates:
            if hasattr(update, 'append') and update.append is not None:
                # Append operation: add row to end
                row = update.append.row
                row_json = json.dumps(row)
                row_digest = str_digest(row_json)
                base_row_digests.append(row_digest)
                base_rows.append(row)
                updated_digests.append(row_digest)
                # Store row by digest
                row_key = f"{req.project_id}:row:{row_digest}"
                self.files[row_key] = row_json.encode()
            elif hasattr(update, 'pop') and update.pop is not None:
                # Pop operation: remove row at index
                if 0 <= update.pop.index < len(base_row_digests):
                    base_row_digests.pop(update.pop.index)
                    base_rows.pop(update.pop.index)
            elif hasattr(update, 'insert') and update.insert is not None:
                # Insert operation: insert row at index
                row = update.insert.row
                row_json = json.dumps(row)
                row_digest = str_digest(row_json)
                if 0 <= update.insert.index <= len(base_row_digests):
                    base_row_digests.insert(update.insert.index, row_digest)
                    base_rows.insert(update.insert.index, row)
                updated_digests.append(row_digest)
                # Store row by digest
                row_key = f"{req.project_id}:row:{row_digest}"
                self.files[row_key] = row_json.encode()

        # Calculate new table digest from row digests
        table_hasher = hashlib.sha256()
        for row_digest in base_row_digests:
            table_hasher.update(row_digest.encode())
        new_digest = table_hasher.hexdigest()

        new_key = f"{req.project_id}:{new_digest}"
        self.tables[new_key] = {
            "project_id": req.project_id,
            "digest": new_digest,
            "rows": base_rows,
            "row_digests": base_row_digests,
        }

        return tsi.TableUpdateRes(digest=new_digest, updated_row_digests=updated_digests)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        key = f"{req.project_id}:{req.digest}"
        if key not in self.tables:
            raise NotFoundError(f"Table {key} not found")

        table_data = self.tables[key]
        rows = []

        for row in table_data["rows"]:
            rows.append(tsi.TableRowSchema(digest=req.digest, val=row))

        # Apply limit and offset
        offset = req.offset or 0
        limit = req.limit

        if limit is not None:
            rows = rows[offset:offset + limit]
        else:
            rows = rows[offset:]

        return tsi.TableQueryRes(rows=rows)

    def table_query_stream(self, req: tsi.TableQueryReq) -> Iterator[tsi.TableRowSchema]:
        result = self.table_query(req)
        for row in result.rows:
            yield row

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        key = f"{req.project_id}:{req.digest}"
        if key not in self.tables:
            return tsi.TableQueryStatsRes(count=0)

        return tsi.TableQueryStatsRes(count=len(self.tables[key]["rows"]))

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        results = []
        for digest in req.digests:
            stats = self.table_query_stats(
                tsi.TableQueryStatsReq(project_id=req.project_id, digest=digest)
            )
            results.append(stats)
        return tsi.TableQueryStatsBatchRes(results=results)

    # Ref API
    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        vals = []
        for ref in req.refs:
            # Simple implementation - just return the ref URI as the value
            vals.append(ref)
        return tsi.RefsReadBatchRes(vals=vals)

    # File API
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        # Generate content-based digest (same as ClickHouse server)
        digest = bytes_digest(req.content)
        key = f"{req.project_id}:{digest}"
        self.files[key] = req.content
        return tsi.FileCreateRes(digest=digest)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        key = f"{req.project_id}:{req.digest}"
        if key not in self.files:
            raise NotFoundError(f"File {key} not found")

        return tsi.FileContentReadRes(content=self.files[key])

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        # Count files for this project
        count = sum(
            1 for k in self.files.keys()
            if k.startswith(f"{req.project_id}:")
        )
        return tsi.FilesStatsRes(count=count)

    # Feedback API
    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        feedback_id = generate_id()
        created_at = datetime.datetime.now(tz=datetime.timezone.utc)
        payload = req.payload or {}
        wb_user_id = req.wb_user_id or ""

        self.feedback[feedback_id] = {
            "id": feedback_id,
            "project_id": req.project_id,
            "weave_ref": req.weave_ref,
            "feedback_type": req.feedback_type,
            "payload": payload,
            "creator": req.creator,
            "created_at": created_at,
            "wb_user_id": wb_user_id,
        }
        return tsi.FeedbackCreateRes(
            id=feedback_id,
            created_at=created_at,
            wb_user_id=wb_user_id,
            payload=payload,
        )

    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        results = []
        for fb_req in req.batch:
            result = self.feedback_create(fb_req)
            results.append(result)
        return tsi.FeedbackCreateBatchRes(results=results)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        feedback_list = []

        for fb in self.feedback.values():
            if fb["project_id"] != req.project_id:
                continue

            # Apply filters
            if req.query and "weave_ref" in req.query:
                if fb["weave_ref"] != req.query["weave_ref"]:
                    continue

            feedback_list.append(fb)

        return tsi.FeedbackQueryRes(result=feedback_list)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        to_delete = [
            fid for fid, fb in self.feedback.items()
            if fb["project_id"] == req.project_id and fb["weave_ref"] == req.query["weave_ref"]
        ]
        for fid in to_delete:
            del self.feedback[fid]
        return tsi.FeedbackPurgeRes()

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        # Delete existing feedback and create new one
        self.feedback_purge(
            tsi.FeedbackPurgeReq(
                project_id=req.project_id,
                query={"weave_ref": req.weave_ref},
            )
        )
        result = self.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=req.project_id,
                weave_ref=req.weave_ref,
                feedback_type=req.feedback_type,
                payload=req.payload,
                creator=req.creator,
                wb_user_id=req.wb_user_id,
            )
        )
        return tsi.FeedbackReplaceRes(id=result.id)

    # Action API
    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        # Mock implementation - just return empty results
        return tsi.ActionsExecuteBatchRes(results=[])

    # Execute LLM API
    def completions_create(self, req: tsi.CompletionsCreateReq) -> tsi.CompletionsCreateRes:
        # Mock implementation - return empty response
        return tsi.CompletionsCreateRes(
            response={"choices": [{"message": {"content": "mock response"}}]}
        )

    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        # Mock implementation - yield a single chunk
        yield {"choices": [{"delta": {"content": "mock"}}]}

    # Execute Image Generation API
    def image_create(
        self, req: tsi.ImageGenerationCreateReq
    ) -> tsi.ImageGenerationCreateRes:
        # Mock implementation
        return tsi.ImageGenerationCreateRes(response={"data": []})

    # Project statistics API
    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        # Count calls for this project
        call_count = sum(
            1 for c in self.calls.values()
            if c.project_id == req.project_id
        )
        return tsi.ProjectStatsRes(call_count=call_count)

    # Thread API
    def threads_query_stream(self, req: tsi.ThreadsQueryReq) -> Iterator[tsi.ThreadSchema]:
        # Mock implementation - no threads
        return iter([])

    # Evaluation API
    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        # Mock implementation
        eval_id = generate_id()
        return tsi.EvaluateModelRes(evaluation_id=eval_id)

    def evaluation_status(self, req: tsi.EvaluationStatusReq) -> tsi.EvaluationStatusRes:
        # Mock implementation - always return completed
        return tsi.EvaluationStatusRes(status="completed")
