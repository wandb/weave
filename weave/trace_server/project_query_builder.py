from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable


def make_project_stats_query(
    project_id: str,
    pb: ParamBuilder,
    include_trace_storage_size: bool,
    include_objects_storage_size: bool,
    include_tables_storage_size: bool,
    include_files_storage_size: bool,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
) -> tuple[str, list[str]]:
    """Build a SQL query for computing project storage statistics.

    Args:
        project_id: The project ID to query stats for.
        pb: ParamBuilder instance for parameterized query construction.
        include_trace_storage_size: Include trace storage size in results.
        include_objects_storage_size: Include objects storage size in results.
        include_tables_storage_size: Include tables storage size in results.
        include_files_storage_size: Include files storage size in results.
        read_table: Which calls table to use for trace storage stats.

    Returns:
        A tuple of (sql_query, column_names).

    Raises:
        ValueError: If all include_* parameters are False.
    """
    if (
        not include_trace_storage_size
        and not include_objects_storage_size
        and not include_tables_storage_size
        and not include_files_storage_size
    ):
        raise ValueError(
            "At least one of include_trace_storage_size, include_objects_storage_size, include_table_storage_size, or include_files_storage_size must be True"
        )
    project_id_param = pb.add_param(project_id)

    # Select stats table based on read_table
    if read_table == ReadTable.CALLS_COMPLETE:
        calls_stats_table = "calls_complete_stats"
    else:
        calls_stats_table = "calls_merged_stats"

    columns = []
    sub_sqls = []
    if include_trace_storage_size:
        columns.append("trace_storage_size_bytes")
        sub_sqls.append(
            f"""
            (SELECT sum(
                COALESCE(attributes_size_bytes, 0) +
                COALESCE(inputs_size_bytes, 0) +
                COALESCE(output_size_bytes, 0) +
                COALESCE(summary_size_bytes, 0)
                )
                FROM {calls_stats_table}
                WHERE project_id = {{{project_id_param}: String}}
            ) AS {columns[-1]}
            """
        )
    if include_objects_storage_size:
        columns.append("objects_storage_size_bytes")
        sub_sqls.append(
            f"""
            (SELECT sum(size_bytes)
                FROM object_versions_stats
                WHERE project_id = {{{project_id_param}: String}}
            ) AS {columns[-1]}
        """
        )
    if include_tables_storage_size:
        columns.append("tables_storage_size_bytes")
        sub_sqls.append(
            f"""
            (SELECT sum(size_bytes)
                FROM table_rows_stats
                WHERE project_id = {{{project_id_param}: String}}
            ) AS {columns[-1]}
        """
        )
    if include_files_storage_size:
        columns.append("files_storage_size_bytes")
        sub_sqls.append(
            f"""
            (SELECT sum(size_bytes)
                FROM files_stats
                WHERE project_id = {{{project_id_param}: String}}
            ) AS {columns[-1]}
        """
        )

    sql = f"""
        SELECT {", ".join(s.strip() for s in sub_sqls)}
    """

    return sql, columns
