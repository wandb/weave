from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable, TableConfig


def make_project_stats_query(
    project_id: str,
    pb: ParamBuilder,
    include_trace_storage_size: bool,
    include_objects_storage_size: bool,
    include_tables_storage_size: bool,
    include_files_storage_size: bool,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
) -> tuple[str, list[str]]:
    """Build a query for project storage statistics.

    Args:
        project_id: The project ID to query stats for.
        pb: Parameter builder for query parameterization.
        include_trace_storage_size: Include trace storage size in results.
        include_objects_storage_size: Include objects storage size in results.
        include_tables_storage_size: Include tables storage size in results.
        include_files_storage_size: Include files storage size in results.
        read_table: Which calls table to read from (affects which stats table is used).

    Returns:
        Tuple of (SQL query string, list of column names in the result).

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

    # Get the appropriate stats table name based on the read table
    config = TableConfig.from_read_table(read_table)
    stats_table_name = config.stats_table_name

    project_id_param = pb.add_param(project_id)

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
                FROM {stats_table_name}
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
        SELECT {", ".join(sub_sqls)}
    """

    return sql, columns
