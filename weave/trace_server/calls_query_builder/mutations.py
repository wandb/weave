"""Mutation query builders for the calls table.

Builds UPDATE and DELETE queries for the calls_complete table.
"""

import logging

from weave.trace_server.calls_query_builder.utils import safely_format_sql
from weave.trace_server.clickhouse_trace_server_settings import LOCAL_TABLE_SUFFIX

logger = logging.getLogger(__name__)


def _format_table_name_with_cluster(table_name: str, cluster_name: str | None) -> str:
    """Format a table name with ON CLUSTER clause if cluster_name is provided.

    In distributed mode, mutations (UPDATE, DELETE, etc.) must target the local
    table with the ON CLUSTER clause to execute across all cluster nodes.
    """
    if cluster_name:
        return f"{table_name}{LOCAL_TABLE_SUFFIX} ON CLUSTER {cluster_name}"
    return table_name


def build_calls_complete_update_end_query(
    table_name: str,
    project_id_param: str,
    id_param: str,
    ended_at_param: str,
    exception_param: str,
    output_dump_param: str,
    summary_dump_param: str,
    output_refs_param: str,
    wb_run_step_end_param: str,
    started_at_param: str | None = None,
    cluster_name: str | None = None,
) -> str:
    """Build the calls_complete UPDATE query for call end data.

    Args:
        table_name (str): The calls_complete table name.
        project_id_param (str): Param slot key for project_id.
        id_param (str): Param slot key for call id.
        ended_at_param (str): Param slot key for ended_at (Int64 microseconds).
        exception_param (str): Param slot key for exception.
        output_dump_param (str): Param slot key for output_dump.
        summary_dump_param (str): Param slot key for summary_dump.
        output_refs_param (str): Param slot key for output_refs.
        wb_run_step_end_param (str): Param slot key for wb_run_step_end.
        started_at_param (str | None): Optional param slot key for started_at
            (Int64 microseconds). When provided, enables more efficient queries
            by utilizing the ClickHouse primary key (project_id, started_at, id).
        cluster_name (str | None): Optional ClickHouse cluster name for ON CLUSTER
            clause in distributed mode. When provided, the UPDATE will be executed
            across all cluster nodes.

    Returns:
        str: The formatted ClickHouse UPDATE statement.

    Note:
        started_at and ended_at params are passed as Int64 microseconds since epoch
        because clickhouse-connect truncates datetime objects to whole seconds.
        We use fromUnixTimestamp64Micro() to convert back to DateTime64(6).
    """
    # Build WHERE clause - include started_at if provided for better primary key usage
    where_clauses = [f"project_id = {{{project_id_param}:String}}"]
    if started_at_param is not None:
        where_clauses.append(
            f"started_at = fromUnixTimestamp64Micro({{{started_at_param}:Int64}}, 'UTC')"
        )
    else:
        # TODO: try to optimistically parse uuidv7, grabbing timestamps from the ID
        # then use that to narrow the granules we need to search.
        pass

    where_clauses.append(f"id = {{{id_param}:String}}")
    where_clause = " AND ".join(where_clauses)

    # Format table name with ON CLUSTER if cluster_name is provided
    formatted_table = _format_table_name_with_cluster(table_name, cluster_name)

    # Use fromUnixTimestamp64Micro to convert Int64 microseconds to DateTime64(6)
    # This preserves full microsecond precision that would be lost with datetime params
    return f"""
        UPDATE {formatted_table}
        SET
            ended_at = fromUnixTimestamp64Micro({{{ended_at_param}:Int64}}, 'UTC'),
            exception = {{{exception_param}:String}},
            output_dump = {{{output_dump_param}:String}},
            summary_dump = {{{summary_dump_param}:String}},
            output_refs = {{{output_refs_param}:Array(String)}},
            wb_run_step_end = {{{wb_run_step_end_param}:UInt64}},
            updated_at = now64(3)
        WHERE {where_clause}
        """


def build_calls_complete_delete_query(
    table_name: str,
    project_id_param: str,
    call_ids_param: str,
    cluster_name: str | None = None,
) -> str:
    """Build the calls_complete DELETE query for call end data."""
    formatted_table = _format_table_name_with_cluster(table_name, cluster_name)
    raw_sql = f"""
        DELETE FROM {formatted_table}
        WHERE project_id = {{{project_id_param}:String}} AND id IN {{{call_ids_param}:Array(String)}}
        """
    return safely_format_sql(raw_sql, logger)


def build_calls_complete_update_query(
    table_name: str,
    project_id_param: str,
    id_param: str,
    display_name_param: str,
    cluster_name: str | None = None,
) -> str:
    """Build the calls_complete UPDATE query for call end data."""
    formatted_table = _format_table_name_with_cluster(table_name, cluster_name)
    raw_sql = f"""
        UPDATE {formatted_table}
        SET display_name = {{{display_name_param}:String}}
        WHERE project_id = {{{project_id_param}:String}} AND id = {{{id_param}:String}}
        """
    return safely_format_sql(raw_sql, logger)
