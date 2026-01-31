# ClickHouse Threads - Thread query operations

from collections.abc import Iterator

import ddtrace

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.annotation_queues_query_builder import make_threads_query
from weave.trace_server.clickhouse_query_layer.client import ClickHouseClient, ensure_datetimes_have_tz
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.project_version import TableRoutingResolver


class ThreadsRepository:
    """Repository for thread query operations."""

    def __init__(
        self,
        ch_client: ClickHouseClient,
        table_routing_resolver: TableRoutingResolver,
    ):
        self._ch_client = ch_client
        self._table_routing_resolver = table_routing_resolver

    @ddtrace.tracer.wrap(name="threads_repository.threads_query_stream")
    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        """Stream threads with aggregated statistics sorted by last activity."""
        pb = ParamBuilder()

        # Determine which table to query based on project data residence
        read_table = self._table_routing_resolver.resolve_read_table(
            req.project_id, self._ch_client.ch_client
        )

        query = make_threads_query(
            project_id=req.project_id,
            pb=pb,
            thread_ids=req.thread_ids,
            sort_by=req.sort_by,
            limit=req.limit,
            offset=req.offset,
            read_table=read_table,
        )

        # Stream the results using query_stream
        raw_res = self._ch_client.query_stream(query, pb.get_params())

        for row in raw_res:
            (
                thread_id,
                turn_count,
                start_time,
                last_updated,
                first_turn_id,
                last_turn_id,
                p50_turn_duration_ms,
                p99_turn_duration_ms,
            ) = row

            # Ensure datetimes have timezone info
            start_time_with_tz = ensure_datetimes_have_tz(start_time)
            last_updated_with_tz = ensure_datetimes_have_tz(last_updated)

            if start_time_with_tz is None or last_updated_with_tz is None:
                # Skip threads without valid timestamps
                continue

            yield tsi.ThreadSchema(
                thread_id=thread_id,
                turn_count=turn_count,
                start_time=start_time_with_tz,
                last_updated=last_updated_with_tz,
                first_turn_id=first_turn_id,
                last_turn_id=last_turn_id,
                p50_turn_duration_ms=p50_turn_duration_ms,
                p99_turn_duration_ms=p99_turn_duration_ms,
            )
