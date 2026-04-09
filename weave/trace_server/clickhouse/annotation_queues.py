"""Annotation queue methods for the ClickHouse trace server.

This module extracts annotation queue CRUD operations and related
queue-item / progress-update logic into a mixin class so that
`ClickHouseTraceServer` can compose them without growing unboundedly.
"""

import datetime
from collections.abc import Iterator
from zoneinfo import ZoneInfo

import ddtrace

from weave.shared.trace_server_interface_util import assert_non_null_wb_user_id
from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse.protocol import CHInfraProtocol
from weave.trace_server.clickhouse.utilities import (
    ensure_datetimes_have_tz,
)
from weave.trace_server.common_interface import AnnotationQueueItemsFilter
from weave.trace_server.errors import NotFoundError
from weave.trace_server.ids import generate_id
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.annotation_queues_query_builder import (
    make_annotator_progress_update_query,
    make_queue_add_calls_check_duplicates_query,
    make_queue_add_calls_fetch_calls_query,
    make_queue_create_query,
    make_queue_delete_query,
    make_queue_items_query,
    make_queue_read_query,
    make_queue_update_query,
    make_queues_query,
    make_queues_stats_query,
)


class AnnotationQueuesMixin(CHInfraProtocol):
    """Mixin providing annotation-queue operations for ClickHouseTraceServer.

    Relies on the following attributes / methods supplied by the host class
    via MRO:
        self._query(...)
        self._insert(...)
        self._command(...)
        self._query_stream(...)
        self.ch_client
        self.table_routing_resolver
        self.clickhouse_cluster_name
    """

    # ------------------------------------------------------------------
    # Annotation Queue CRUD
    # ------------------------------------------------------------------

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.annotation_queue_create")
    def annotation_queue_create(
        self, req: tsi.AnnotationQueueCreateReq
    ) -> tsi.AnnotationQueueCreateRes:
        """Create a new annotation queue."""
        assert_non_null_wb_user_id(req)
        pb = ParamBuilder()

        # Generate UUIDv7 for the queue
        queue_id = generate_id()

        # Get wb_user_id from request (should be set by auth layer)
        created_by = req.wb_user_id
        assert created_by is not None  # Ensured by assert_non_null_wb_user_id

        # Build and execute INSERT query
        query = make_queue_create_query(
            project_id=req.project_id,
            queue_id=queue_id,
            name=req.name,
            description=req.description,
            scorer_refs=req.scorer_refs,
            created_by=created_by,
            pb=pb,
        )

        self._command(query, parameters=pb.get_params())

        return tsi.AnnotationQueueCreateRes(id=queue_id)

    @ddtrace.tracer.wrap(
        name="clickhouse_trace_server_batched.annotation_queues_query_stream"
    )
    def annotation_queues_query_stream(
        self, req: tsi.AnnotationQueuesQueryReq
    ) -> Iterator[tsi.AnnotationQueueSchema]:
        """Stream annotation queues for a project."""
        pb = ParamBuilder()

        query = make_queues_query(
            project_id=req.project_id,
            pb=pb,
            name=req.name,
            sort_by=req.sort_by,
            limit=req.limit,
            offset=req.offset,
        )

        # Stream the results using _query_stream
        raw_res = self._query_stream(query, pb.get_params())

        for row in raw_res:
            (
                queue_id,
                project_id,
                name,
                description,
                scorer_refs,
                created_at,
                created_by,
                updated_at,
                deleted_at,
            ) = row

            # Ensure datetimes have timezone info
            created_at_with_tz = ensure_datetimes_have_tz(created_at)
            updated_at_with_tz = ensure_datetimes_have_tz(updated_at)
            deleted_at_with_tz = ensure_datetimes_have_tz(deleted_at)

            if created_at_with_tz is None or updated_at_with_tz is None:
                # Skip queues without valid timestamps
                continue

            yield tsi.AnnotationQueueSchema(
                id=str(queue_id),  # Convert UUID to string
                project_id=project_id,
                name=name,
                description=description,
                scorer_refs=scorer_refs,
                created_at=created_at_with_tz,
                created_by=created_by,
                updated_at=updated_at_with_tz,
                deleted_at=deleted_at_with_tz,
            )

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.annotation_queue_read")
    def annotation_queue_read(
        self, req: tsi.AnnotationQueueReadReq
    ) -> tsi.AnnotationQueueReadRes:
        """Read a specific annotation queue."""
        pb = ParamBuilder()

        query = make_queue_read_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            pb=pb,
        )

        result = self.ch_client.query(query, parameters=pb.get_params())
        rows = result.named_results()

        try:
            row = next(rows)
        except StopIteration:
            raise NotFoundError(f"Queue {req.queue_id} not found") from None
        queue = tsi.AnnotationQueueSchema(
            id=str(row["id"]),
            project_id=row["project_id"],
            name=row["name"],
            description=row["description"],
            scorer_refs=row["scorer_refs"],
            created_at=ensure_datetimes_have_tz(row["created_at"]),
            created_by=row["created_by"],
            updated_at=ensure_datetimes_have_tz(row["updated_at"]),
            deleted_at=ensure_datetimes_have_tz(row["deleted_at"]),
        )

        return tsi.AnnotationQueueReadRes(queue=queue)

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.annotation_queue_update")
    def annotation_queue_update(
        self, req: tsi.AnnotationQueueUpdateReq
    ) -> tsi.AnnotationQueueUpdateRes:
        """Update an annotation queue.

        Only updates the fields that are provided (name, description, scorer_refs).
        Always updates the updated_at timestamp.
        """
        assert_non_null_wb_user_id(req)

        # First, verify the queue exists and is not already deleted
        pb = ParamBuilder()
        read_query = make_queue_read_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            pb=pb,
        )
        result = self.ch_client.query(read_query, parameters=pb.get_params())
        res = result.named_results()
        try:
            row = next(res)
        except StopIteration:
            raise NotFoundError(
                f"Queue {req.queue_id} not found or already deleted"
            ) from None
        finally:
            res.close()

        # Check if any fields are actually being updated
        has_updates = any(
            [
                req.name is not None,
                req.description is not None,
                req.scorer_refs is not None,
            ]
        )

        if not has_updates:
            # No updates requested, just return the existing queue
            queue = tsi.AnnotationQueueSchema(
                id=str(row["id"]),
                project_id=row["project_id"],
                name=row["name"],
                description=row["description"],
                scorer_refs=row["scorer_refs"],
                created_at=ensure_datetimes_have_tz(row["created_at"]),
                created_by=row["created_by"],
                updated_at=ensure_datetimes_have_tz(row["updated_at"]),
                deleted_at=ensure_datetimes_have_tz(row["deleted_at"]),
            )
            return tsi.AnnotationQueueUpdateRes(queue=queue)

        # Perform the update
        pb = ParamBuilder()  # Reset parameter builder
        update_query = make_queue_update_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            pb=pb,
            cluster_name=self.clickhouse_cluster_name,
            name=req.name,
            description=req.description,
            scorer_refs=req.scorer_refs,
        )

        self._command(
            update_query,
            pb.get_params(),
            settings=ch_settings.CLICKHOUSE_LIGHTWEIGHT_UPDATE_SETTINGS,
        )

        # Build the response with updated values
        # Use the new values if provided, otherwise keep the old ones
        updated_at = datetime.datetime.now(tz=ZoneInfo("UTC"))
        name = req.name if req.name is not None else row["name"]
        description = (
            req.description if req.description is not None else row["description"]
        )
        scorer_refs = (
            req.scorer_refs if req.scorer_refs is not None else row["scorer_refs"]
        )

        queue = tsi.AnnotationQueueSchema(
            id=str(row["id"]),
            project_id=row["project_id"],
            name=name,
            description=description,
            scorer_refs=scorer_refs,
            created_at=ensure_datetimes_have_tz(row["created_at"]),
            created_by=row["created_by"],
            updated_at=updated_at,
            deleted_at=None,  # Can't be deleted since we just updated it
        )

        return tsi.AnnotationQueueUpdateRes(queue=queue)

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.annotation_queue_delete")
    def annotation_queue_delete(
        self, req: tsi.AnnotationQueueDeleteReq
    ) -> tsi.AnnotationQueueDeleteRes:
        """Soft-delete an annotation queue by setting deleted_at timestamp."""
        pb = ParamBuilder()

        # First, verify the queue exists and is not already deleted
        read_query = make_queue_read_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            pb=pb,
        )
        result = self._query(read_query, pb.get_params())
        rows = list(result.named_results())

        if len(rows) == 0:
            raise NotFoundError(f"Queue {req.queue_id} not found or already deleted")

        # Store the queue data before deletion
        row = rows[0]

        # Now perform the soft delete
        pb = ParamBuilder()  # Reset parameter builder
        delete_query = make_queue_delete_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            pb=pb,
            cluster_name=self.clickhouse_cluster_name,
        )

        self._command(
            delete_query,
            pb.get_params(),
            settings=ch_settings.CLICKHOUSE_LIGHTWEIGHT_UPDATE_SETTINGS,
        )

        # Build the response with updated timestamps
        deleted_at = datetime.datetime.now(tz=ZoneInfo("UTC"))
        updated_at = deleted_at

        queue = tsi.AnnotationQueueSchema(
            id=str(row["id"]),
            project_id=row["project_id"],
            name=row["name"],
            description=row["description"],
            scorer_refs=row["scorer_refs"],
            created_at=ensure_datetimes_have_tz(row["created_at"]),
            created_by=row["created_by"],
            updated_at=updated_at,
            deleted_at=deleted_at,
        )

        return tsi.AnnotationQueueDeleteRes(queue=queue)

    # ------------------------------------------------------------------
    # Annotation Queue Items
    # ------------------------------------------------------------------

    @ddtrace.tracer.wrap(
        name="clickhouse_trace_server_batched.annotation_queue_add_calls"
    )
    def annotation_queue_add_calls(
        self, req: tsi.AnnotationQueueAddCallsReq
    ) -> tsi.AnnotationQueueAddCallsRes:
        """Add calls to an annotation queue in batch with duplicate prevention."""
        assert_non_null_wb_user_id(req)
        pb = ParamBuilder()

        # Step 0: Determine which table to query based on project data residence
        read_table = self.table_routing_resolver.resolve_read_table(
            req.project_id, self.ch_client
        )

        # Step 1: Check for existing calls (duplicate prevention)
        dup_query = make_queue_add_calls_check_duplicates_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            call_ids=req.call_ids,
            pb=pb,
        )

        dup_result = self._query(dup_query, parameters=pb.get_params())
        existing_call_ids = {row[0] for row in dup_result.result_rows}
        new_call_ids = [cid for cid in req.call_ids if cid not in existing_call_ids]

        if not new_call_ids:
            return tsi.AnnotationQueueAddCallsRes(
                added_count=0, duplicates=len(req.call_ids)
            )

        # Step 2: Fetch call details for caching
        pb2 = ParamBuilder()
        calls_query = make_queue_add_calls_fetch_calls_query(
            project_id=req.project_id,
            call_ids=new_call_ids,
            pb=pb2,
            read_table=read_table,
        )

        calls_result = self._query(calls_query, parameters=pb2.get_params())
        calls_data = list(calls_result.named_results())

        if not calls_data:
            # No calls found in database
            return tsi.AnnotationQueueAddCallsRes(
                added_count=0, duplicates=len(existing_call_ids)
            )

        # Step 3: Create queue items
        queue_items_rows = []
        added_by = req.wb_user_id

        for call in calls_data:
            queue_item_id = generate_id()

            # Queue item row (must be tuple in column order)
            queue_items_rows.append(
                (
                    queue_item_id,
                    req.project_id,
                    req.queue_id,
                    call["id"],
                    call["started_at"],
                    call["ended_at"],
                    call["op_name"] or "",
                    call["trace_id"] or "",
                    req.display_fields,
                    added_by,
                    added_by,
                )
            )

        # Step 4: Batch insert queue items
        self._insert(
            "annotation_queue_items",
            queue_items_rows,
            column_names=[
                "id",
                "project_id",
                "queue_id",
                "call_id",
                "call_started_at",
                "call_ended_at",
                "call_op_name",
                "call_trace_id",
                "display_fields",
                "added_by",
                "created_by",
            ],
        )

        return tsi.AnnotationQueueAddCallsRes(
            added_count=len(calls_data), duplicates=len(existing_call_ids)
        )

    @ddtrace.tracer.wrap(
        name="clickhouse_trace_server_batched.annotation_queue_items_query"
    )
    def annotation_queue_items_query(
        self, req: tsi.AnnotationQueueItemsQueryReq
    ) -> tsi.AnnotationQueueItemsQueryRes:
        """Query items in an annotation queue with pagination, sorting, and filtering."""
        pb = ParamBuilder()

        query = make_queue_items_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            pb=pb,
            filter=req.filter,
            sort_by=req.sort_by,
            limit=req.limit,
            offset=req.offset,
            include_position=req.include_position,
        )

        result = self.ch_client.query(query, parameters=pb.get_params())

        items = []
        for row in result.named_results():
            items.append(
                tsi.AnnotationQueueItemSchema(
                    id=row["id"],
                    project_id=row["project_id"],
                    queue_id=row["queue_id"],
                    call_id=row["call_id"],
                    call_started_at=row["call_started_at"],
                    call_ended_at=row["call_ended_at"],
                    call_op_name=row["call_op_name"],
                    call_trace_id=row["call_trace_id"],
                    display_fields=row["display_fields"],
                    added_by=row["added_by"],
                    annotation_state=row["annotation_state"],
                    created_at=row["created_at"],
                    created_by=row["created_by"],
                    updated_at=row["updated_at"],
                    deleted_at=row["deleted_at"],
                    position_in_queue=row.get("position_in_queue"),
                    annotator_user_id=row.get("annotator_user_id"),
                )
            )

        return tsi.AnnotationQueueItemsQueryRes(items=items)

    # ------------------------------------------------------------------
    # Annotation Queue Stats
    # ------------------------------------------------------------------

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.annotation_queues_stats")
    def annotation_queues_stats(
        self, req: tsi.AnnotationQueuesStatsReq
    ) -> tsi.AnnotationQueuesStatsRes:
        """Get stats for multiple annotation queues."""
        if not req.queue_ids:
            # Return empty stats if no queue IDs provided
            return tsi.AnnotationQueuesStatsRes(stats=[])

        pb = ParamBuilder()

        query = make_queues_stats_query(
            project_id=req.project_id,
            queue_ids=req.queue_ids,
            pb=pb,
        )

        result = self.ch_client.query(query, parameters=pb.get_params())

        stats = []
        for row in result.result_rows:
            # Row order: queue_id, total_items, completed_items
            queue_id, total_items, completed_items = row
            stats.append(
                tsi.AnnotationQueueStatsSchema(
                    queue_id=str(queue_id),
                    total_items=int(total_items),
                    completed_items=int(completed_items),
                )
            )

        return tsi.AnnotationQueuesStatsRes(stats=stats)

    # ------------------------------------------------------------------
    # Annotator Progress
    # ------------------------------------------------------------------

    def _fetch_queue_item_for_progress_update(
        self, project_id: str, queue_id: str, item_id: str
    ) -> tsi.AnnotatorQueueItemsProgressUpdateRes:
        """Fetch a queue item and return it wrapped in progress update response."""
        pb = ParamBuilder()
        fetch_query = make_queue_items_query(
            project_id=project_id,
            queue_id=queue_id,
            pb=pb,
            filter=AnnotationQueueItemsFilter(id=item_id),
            sort_by=None,
            limit=1,
            offset=None,
            include_position=False,
        )
        fetch_result = self.ch_client.query(fetch_query, parameters=pb.get_params())

        for row in fetch_result.named_results():
            item = tsi.AnnotationQueueItemSchema(
                id=row["id"],
                project_id=row["project_id"],
                queue_id=row["queue_id"],
                call_id=row["call_id"],
                call_started_at=row["call_started_at"],
                call_ended_at=row["call_ended_at"],
                call_op_name=row["call_op_name"],
                call_trace_id=row["call_trace_id"],
                display_fields=row["display_fields"],
                added_by=row["added_by"],
                annotation_state=row["annotation_state"],
                created_at=row["created_at"],
                created_by=row["created_by"],
                updated_at=row["updated_at"],
                deleted_at=row["deleted_at"],
                position_in_queue=None,
                annotator_user_id=row.get("annotator_user_id"),
            )
            return tsi.AnnotatorQueueItemsProgressUpdateRes(item=item)

        raise ValueError(f"Failed to fetch queue item '{item_id}'")

    @ddtrace.tracer.wrap(
        name="clickhouse_trace_server_batched.annotator_queue_items_progress_update"
    )
    def annotator_queue_items_progress_update(
        self, req: tsi.AnnotatorQueueItemsProgressUpdateReq
    ) -> tsi.AnnotatorQueueItemsProgressUpdateRes:
        """Update annotation state for a queue item using ClickHouse lightweight update.

        Validates state transitions:
        - Allowed: (absence) -> 'in_progress', 'completed' or 'skipped'
        - Allowed: 'in_progress' or 'unstarted' -> 'completed' or 'skipped'
        - Idempotent: same_state -> same_state (no-op, returns existing item)
        - Rejected: any other transition (including updating to 'in_progress' when record exists)
        """
        # Validate annotation_state
        allowed_states = {"completed", "skipped", "in_progress"}
        if req.annotation_state not in allowed_states:
            raise ValueError(
                f"Invalid annotation_state '{req.annotation_state}'. "
                f"Must be one of: {', '.join(sorted(allowed_states))}"
            )

        # Get the annotator ID from the session
        annotator_id = req.wb_user_id
        if not annotator_id:
            raise ValueError("wb_user_id is required")

        pb = ParamBuilder()
        project_id_param = pb.add(req.project_id)
        queue_id_param = pb.add(req.queue_id)
        item_id_param = pb.add(req.item_id)
        annotator_id_param = pb.add(annotator_id)

        # First, check current state and validate the queue item exists
        check_query = f"""
        SELECT
            annotation_state,
            COUNT(*) as record_exists
        FROM annotator_queue_items_progress
        WHERE project_id = {project_id_param}
          AND queue_item_id = {item_id_param}
          AND annotator_id = {annotator_id_param}
          AND deleted_at IS NULL
        GROUP BY annotation_state
        """

        check_result = self.ch_client.query(check_query, parameters=pb.get_params())
        current_state = None
        has_record = False

        for row in check_result.named_results():
            current_state = row["annotation_state"]
            has_record = row["record_exists"] > 0
            break

        # Idempotent: if already in the requested state, skip the update
        if current_state == req.annotation_state:
            return self._fetch_queue_item_for_progress_update(
                req.project_id, req.queue_id, req.item_id
            )

        # Special handling for 'in_progress': only allow when no record exists
        if req.annotation_state == "in_progress" and has_record:
            raise ValueError(
                "Cannot transition to 'in_progress' when a record already exists. "
                "'in_progress' can only be set on new items."
            )

        # Validate state transition for other states
        # Record exists - only allow transition from 'in_progress' or 'unstarted'
        if (
            current_state is not None
            and req.annotation_state != "in_progress"
            and current_state not in {"in_progress", "unstarted"}
        ):
            raise ValueError(
                f"Invalid state transition from '{current_state}' to '{req.annotation_state}'. "
                f"Only transitions from 'in_progress' or 'unstarted' are allowed."
            )

        # Also verify the queue item exists in annotation_queue_items
        item_check_query = f"""
        SELECT id
        FROM annotation_queue_items
        WHERE id = {item_id_param}
          AND project_id = {project_id_param}
          AND queue_id = {queue_id_param}
          AND deleted_at IS NULL
        LIMIT 1
        """

        item_check_result = self.ch_client.query(
            item_check_query, parameters=pb.get_params()
        )
        if not list(item_check_result.named_results()):
            raise ValueError(
                f"Queue item '{req.item_id}' not found in queue '{req.queue_id}'"
            )

        if has_record:
            # Use ClickHouse lightweight UPDATE for existing record
            update_query = make_annotator_progress_update_query(
                project_id=req.project_id,
                queue_item_id=req.item_id,
                annotator_id=annotator_id,
                annotation_state=req.annotation_state,
                pb=pb,
                cluster_name=self.clickhouse_cluster_name,
            )
            self._command(
                update_query,
                parameters=pb.get_params(),
                settings=ch_settings.CLICKHOUSE_LIGHTWEIGHT_UPDATE_SETTINGS,
            )
        else:
            # Create new record
            progress_id = generate_id()
            progress_id_param = pb.add(progress_id)
            new_state_param = pb.add(req.annotation_state)
            now = datetime.datetime.now(datetime.timezone.utc)
            now_param = pb.add(now)

            insert_query = f"""
            INSERT INTO annotator_queue_items_progress
                (id, project_id, queue_item_id, queue_id, annotator_id,
                 annotation_state, created_at, updated_at, deleted_at)
            VALUES
                ({progress_id_param}, {project_id_param}, {item_id_param},
                 {queue_id_param}, {annotator_id_param}, {new_state_param},
                 {now_param}, {now_param}, NULL)
            """
            self._command(insert_query, parameters=pb.get_params())

        return self._fetch_queue_item_for_progress_update(
            req.project_id, req.queue_id, req.item_id
        )
