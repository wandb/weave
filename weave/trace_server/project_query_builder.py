from weave.trace_server.orm import ParamBuilder


def make_project_stats_query(
    project_id: str,
    pb: ParamBuilder,
    include_trace_storage_size: bool,
    include_objects_storage_size: bool,
    include_tables_storage_size: bool,
    include_files_storage_size: bool,
) -> tuple[str, list[str]]:
    if (
        not include_trace_storage_size
        and not include_objects_storage_size
        and not include_tables_storage_size
        and not include_files_storage_size
    ):
        raise ValueError(
            "At least one of include_trace_storage_size, include_objects_storage_size, include_table_storage_size, or include_files_storage_size must be True"
        )
    project_id = pb.add_param(project_id)

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
                FROM calls_merged_stats
                WHERE project_id = {{{project_id}: String}}
            ) AS {columns[-1]}
            """
        )
    if include_objects_storage_size:
        columns.append("objects_storage_size_bytes")
        sub_sqls.append(
            f"""
            (SELECT sum(size_bytes)
                FROM object_versions_stats
                WHERE project_id = {{{project_id}: String}}
            ) AS {columns[-1]}
        """
        )
    if include_tables_storage_size:
        columns.append("tables_storage_size_bytes")
        sub_sqls.append(
            f"""
            (SELECT sum(size_bytes)
                FROM table_rows_stats
                WHERE project_id = {{{project_id}: String}}
            ) AS {columns[-1]}
        """
        )
    if include_files_storage_size:
        columns.append("files_storage_size_bytes")
        sub_sqls.append(
            f"""
            (SELECT sum(size_bytes)
                FROM files_stats
                WHERE project_id = {{{project_id}: String}}
            ) AS {columns[-1]}
        """
        )

    sql = f"""
        SELECT {", ".join(sub_sqls)}
    """

    return sql, columns
