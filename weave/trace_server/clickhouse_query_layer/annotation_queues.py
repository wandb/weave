# ClickHouse Annotation Queues - Annotation queue CRUD operations

from collections.abc import Iterator
from typing import Any

import ddtrace

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.annotation_queues_query_builder import (
    make_queue_add_calls_check_duplicates_query,
    make_queue_add_calls_fetch_calls_query,
    make_queue_add_calls_insert_query,
    make_queue_call_items_query,
    make_queue_create_query,
    make_queue_delete_call_items_query,
    make_queue_pop_calls_query,
    make_queue_read_query,
    make_queue_update_query,
    make_queues_query,
)
from weave.trace_server.clickhouse_query_layer.client import ClickHouseClient, ensure_datetimes_have_tz
from weave.trace_server.errors import NotFoundError
from weave.trace_server.ids import generate_id
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.project_version import TableRoutingResolver
from weave.trace_server.trace_server_interface_util import assert_non_null_wb_user_id


class AnnotationQueuesRepository:
    """Repository for annotation queue CRUD operations."""

    def __init__(
        self,
        ch_client: ClickHouseClient,
        table_routing_resolver: TableRoutingResolver,
    ):
        self._ch_client = ch_client
        self._table_routing_resolver = table_routing_resolver

    @ddtrace.tracer.wrap(name="annotation_queues.annotation_queue_create")
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

        self._ch_client.command(query, parameters=pb.get_params())

        return tsi.AnnotationQueueCreateRes(id=queue_id)

    @ddtrace.tracer.wrap(name="annotation_queues.annotation_queues_query_stream")
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

        # Stream the results using query_stream
        raw_res = self._ch_client.query_stream(query, pb.get_params())

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

    @ddtrace.tracer.wrap(name="annotation_queues.annotation_queue_read")
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

        result = self._ch_client.ch_client.query(query, parameters=pb.get_params())
        rows = result.named_results()

        if not rows:
            raise NotFoundError(f"Queue {req.queue_id} not found")

        row = next(rows)
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

    @ddtrace.tracer.wrap(name="annotation_queues.annotation_queue_add_calls")
    def annotation_queue_add_calls(
        self, req: tsi.AnnotationQueueAddCallsReq
    ) -> tsi.AnnotationQueueAddCallsRes:
        """Add calls to an annotation queue in batch with duplicate prevention."""
        assert_non_null_wb_user_id(req)
        pb = ParamBuilder()

        # Determine which table to query based on project data residence
        read_table = self._table_routing_resolver.resolve_read_table(
            req.project_id, self._ch_client.ch_client
        )

        # Step 1: Check for existing calls (duplicate prevention)
        dup_query = make_queue_add_calls_check_duplicates_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            call_ids=req.call_ids,
            pb=pb,
        )

        dup_result = self._ch_client.query(dup_query, parameters=pb.get_params())
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

        calls_result = self._ch_client.query(calls_query, parameters=pb2.get_params())
        calls_data = list(calls_result.named_results())

        # Step 3: Insert into annotation_queue_items
        pb3 = ParamBuilder()
        insert_query = make_queue_add_calls_insert_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            calls_data=calls_data,
            added_by=req.wb_user_id,
            pb=pb3,
        )

        if insert_query:
            self._ch_client.command(insert_query, parameters=pb3.get_params())

        return tsi.AnnotationQueueAddCallsRes(
            added_count=len(calls_data),
            duplicates=len(req.call_ids) - len(new_call_ids),
        )

    @ddtrace.tracer.wrap(name="annotation_queues.annotation_queue_pop_calls")
    def annotation_queue_pop_calls(
        self, req: tsi.AnnotationQueuePopCallsReq
    ) -> tsi.AnnotationQueuePopCallsRes:
        """Pop calls from an annotation queue for annotation."""
        pb = ParamBuilder()

        query = make_queue_pop_calls_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            limit=req.limit,
            pb=pb,
        )

        result = self._ch_client.query(query, parameters=pb.get_params())
        call_ids = [row[0] for row in result.result_rows]

        return tsi.AnnotationQueuePopCallsRes(call_ids=call_ids)

    @ddtrace.tracer.wrap(name="annotation_queues.annotation_queue_call_items_query_stream")
    def annotation_queue_call_items_query_stream(
        self, req: tsi.AnnotationQueueCallItemsQueryReq
    ) -> Iterator[tsi.AnnotationQueueCallItemSchema]:
        """Stream call items in an annotation queue."""
        pb = ParamBuilder()

        query = make_queue_call_items_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            pb=pb,
            call_ids=req.call_ids,
            sort_by=req.sort_by,
            limit=req.limit,
            offset=req.offset,
        )

        raw_res = self._ch_client.query_stream(query, pb.get_params())

        for row in raw_res:
            (
                call_id,
                queue_id,
                added_at,
                added_by,
                op_name,
                started_at,
                inputs_dump,
                output_dump,
            ) = row

            yield tsi.AnnotationQueueCallItemSchema(
                call_id=call_id,
                queue_id=str(queue_id),
                added_at=ensure_datetimes_have_tz(added_at),
                added_by=added_by,
                op_name=op_name,
                started_at=ensure_datetimes_have_tz(started_at),
            )

    @ddtrace.tracer.wrap(name="annotation_queues.annotation_queue_delete_call_items")
    def annotation_queue_delete_call_items(
        self, req: tsi.AnnotationQueueDeleteCallItemsReq
    ) -> tsi.AnnotationQueueDeleteCallItemsRes:
        """Delete call items from an annotation queue."""
        assert_non_null_wb_user_id(req)
        pb = ParamBuilder()

        query = make_queue_delete_call_items_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            call_ids=req.call_ids,
            pb=pb,
        )

        self._ch_client.command(query, parameters=pb.get_params())

        return tsi.AnnotationQueueDeleteCallItemsRes(deleted_count=len(req.call_ids))

    @ddtrace.tracer.wrap(name="annotation_queues.annotation_queue_update")
    def annotation_queue_update(
        self, req: tsi.AnnotationQueueUpdateReq
    ) -> tsi.AnnotationQueueUpdateRes:
        """Update an annotation queue."""
        assert_non_null_wb_user_id(req)
        pb = ParamBuilder()

        query = make_queue_update_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            name=req.name,
            description=req.description,
            scorer_refs=req.scorer_refs,
            pb=pb,
        )

        self._ch_client.command(query, parameters=pb.get_params())

        return tsi.AnnotationQueueUpdateRes()
