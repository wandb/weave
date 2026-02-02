# ClickHouse Stats - Project and call statistics


from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_query_layer.client import ClickHouseClient
from weave.trace_server.clickhouse_query_layer.query_builders.project import (
    make_project_stats_query,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.project_version import TableRoutingResolver


class StatsRepository:
    """Repository for project and call statistics."""

    def __init__(
        self,
        ch_client: ClickHouseClient,
        table_routing_resolver: TableRoutingResolver,
    ):
        self._ch_client = ch_client
        self._table_routing_resolver = table_routing_resolver

    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        """Get storage and count statistics for a project."""

        def _default_true(val: bool | None) -> bool:
            return True if val is None else val

        # Resolve which table to read from based on project data residence
        read_table = self._table_routing_resolver.resolve_read_table(
            req.project_id, self._ch_client.ch_client
        )

        pb = ParamBuilder()
        query, columns = make_project_stats_query(
            req.project_id,
            pb,
            include_trace_storage_size=_default_true(req.include_trace_storage_size),
            include_objects_storage_size=_default_true(req.include_object_storage_size),
            include_tables_storage_size=_default_true(req.include_table_storage_size),
            include_files_storage_size=_default_true(req.include_file_storage_size),
            read_table=read_table,
        )
        query_result = self._ch_client.ch_client.query(
            query, parameters=pb.get_params()
        )

        if len(query_result.result_rows) != 1:
            raise RuntimeError("Unexpected number of results", query_result)

        return tsi.ProjectStatsRes(
            **dict(zip(columns, query_result.result_rows[0], strict=False))
        )
