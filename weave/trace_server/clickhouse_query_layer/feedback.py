# ClickHouse Feedback - Feedback CRUD operations

import ddtrace

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_query_layer.client import ClickHouseClient
from weave.trace_server.datadog import set_root_span_dd_tags
from weave.trace_server.feedback import (
    TABLE_FEEDBACK,
    format_feedback_to_res,
    format_feedback_to_row,
    process_feedback_payload,
    validate_feedback_create_req,
    validate_feedback_purge_req,
)
from weave.trace_server.trace_server_interface_util import assert_non_null_wb_user_id


class FeedbackRepository:
    """Repository for feedback CRUD operations."""

    def __init__(self, ch_client: ClickHouseClient, trace_server: "Any"):
        self._ch_client = ch_client
        self._trace_server = trace_server

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        """Create a new feedback item."""
        assert_non_null_wb_user_id(req)
        validate_feedback_create_req(req, self._trace_server)

        processed_payload = process_feedback_payload(req)
        row = format_feedback_to_row(req, processed_payload)
        prepared = TABLE_FEEDBACK.insert(row).prepare(database_type="clickhouse")
        self._ch_client.insert(
            TABLE_FEEDBACK.name,
            prepared.data,
            prepared.column_names,
            # Always do sync inserts for speedy response times
            do_sync_insert=True,
        )

        return format_feedback_to_res(row)

    @ddtrace.tracer.wrap(name="feedback_repository.feedback_create_batch")
    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        """Create multiple feedback items in a batch efficiently."""
        rows_to_insert = []
        results = []

        set_root_span_dd_tags({"feedback_create_batch.count": len(req.batch)})

        for feedback_req in req.batch:
            assert_non_null_wb_user_id(feedback_req)
            validate_feedback_create_req(feedback_req, self._trace_server)

            processed_payload = process_feedback_payload(feedback_req)
            row = format_feedback_to_row(feedback_req, processed_payload)
            rows_to_insert.append(row)
            results.append(format_feedback_to_res(row))

        # Batch insert all rows at once
        if rows_to_insert:
            insert_query = TABLE_FEEDBACK.insert()
            for row in rows_to_insert:
                insert_query.row(row)
            prepared = insert_query.prepare(database_type="clickhouse")
            self._ch_client.insert(
                TABLE_FEEDBACK.name, prepared.data, prepared.column_names
            )

        return tsi.FeedbackCreateBatchRes(res=results)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        """Query feedback items."""
        query = TABLE_FEEDBACK.select()
        query = query.project_id(req.project_id)
        query = query.fields(req.fields)
        query = query.where(req.query)
        query = query.order_by(req.sort_by)
        query = query.limit(req.limit).offset(req.offset)
        prepared = query.prepare(database_type="clickhouse")
        query_result = self._ch_client.ch_client.query(prepared.sql, prepared.parameters)
        result = TABLE_FEEDBACK.tuples_to_rows(
            query_result.result_rows, prepared.fields
        )
        return tsi.FeedbackQueryRes(result=result)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        """Purge (delete) feedback items matching a query."""
        validate_feedback_purge_req(req)
        query = TABLE_FEEDBACK.purge()
        query = query.project_id(req.project_id)
        query = query.where(req.query)
        prepared = query.prepare(database_type="clickhouse")
        self._ch_client.ch_client.query(prepared.sql, prepared.parameters)
        return tsi.FeedbackPurgeRes()

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        """Replace a feedback item (purge then create)."""
        # To replace, first purge, then if successful, create.
        query = tsi.Query(
            **{
                "$expr": {
                    "$eq": [
                        {"$getField": "id"},
                        {"$literal": req.feedback_id},
                    ],
                }
            }
        )
        purge_request = tsi.FeedbackPurgeReq(
            project_id=req.project_id,
            query=query,
        )
        self.feedback_purge(purge_request)
        create_req = tsi.FeedbackCreateReq(**req.model_dump(exclude={"feedback_id"}))
        create_result = self.feedback_create(create_req)
        return tsi.FeedbackReplaceRes(
            id=create_result.id,
            created_at=create_result.created_at,
            wb_user_id=create_result.wb_user_id,
            payload=create_result.payload,
        )


# Type hint for forward reference
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass
