from typing import Optional

from weave.trace_server.orm import ParamBuilder

# TODO: Test when there are multple of the same row digest in the table
# TODO: test when there are multiple rows with the same digest

# NOTE: This query looks a little odd, but the clickhouse query planner
# is not smart enough if do it differently. Future versions of clickhouse
# may differ.

TABLE_ROWS_ALIAS = "tr"
VAL_DUMP_COLUMN_NAME = "val_dump"
ROW_ORDER_COLUMN_NAME = "row_order"


def make_natural_sort_table_query(
    project_id: str,
    digest: str,
    pb: ParamBuilder,
    *,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    natural_direction: str = "ASC",
) -> str:
    project_id_name = pb.add_param(project_id)
    digest_name = pb.add_param(digest)
    sql_safe_dir = "ASC" if natural_direction == "ASC" else "DESC"
    sql_safe_limit = ""
    if limit is not None:
        limit_name = pb.add_param(limit)
        sql_safe_limit = f"LIMIT {{{limit_name}: Int64}}"

    sql_safe_offset = ""
    if offset is not None:
        offset_name = pb.add_param(offset)
        sql_safe_offset = f"OFFSET {{{offset_name}: Int64}}"

    query = f"""
    SELECT DISTINCT tr.digest, tr.val_dump, t.row_order
    FROM table_rows tr
    RIGHT JOIN (
        SELECT row_digest, row_number() OVER () AS row_order
        FROM tables
        ARRAY JOIN row_digests AS row_digest
        WHERE project_id = {{{project_id_name}: String}}
        AND digest = {{{digest_name}: String}}
        ORDER BY row_order {sql_safe_dir}
        {sql_safe_limit}
        {sql_safe_offset}
    ) AS t ON tr.digest = t.row_digest
    WHERE tr.project_id = {{{project_id_name}: String}}
    ORDER BY row_order {sql_safe_dir}
    """

    return query


def make_standard_table_query(
    project_id: str,
    digest: str,
    pb: ParamBuilder,
    *,
    sql_safe_conditions: Optional[list[str]] = None,
    sql_safe_sort_clause: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> str:
    project_id_name = pb.add_param(project_id)
    digest_name = pb.add_param(digest)

    if sql_safe_sort_clause is None:
        sql_safe_sort_clause = ""

    sql_safe_filter_clause = ""
    if sql_safe_conditions is not None and len(sql_safe_conditions) > 0:
        sql_safe_filter_clause = "AND " + "AND ".join(sql_safe_conditions)

    sql_safe_limit = ""
    if limit is not None:
        limit_name = pb.add_param(limit)
        sql_safe_limit = f"LIMIT {{{limit_name}: Int64}}"

    sql_safe_offset = ""
    if offset is not None:
        offset_name = pb.add_param(offset)
        sql_safe_offset = f"OFFSET {{{offset_name}: Int64}}"

    query = f"""
    SELECT tr.digest, tr.val_dump, tr.row_order FROM
    (
        SELECT DISTINCT tr.digest, tr.val_dump, t.row_order
        FROM table_rows tr
        RIGHT JOIN (
            SELECT row_digest, row_number() OVER () AS row_order
            FROM tables
            ARRAY JOIN row_digests AS row_digest
            WHERE project_id = {{{project_id_name}: String}}
            AND digest = {{{digest_name}: String}}
        ) AS t ON tr.digest = t.row_digest
        WHERE tr.project_id = {{{project_id_name}: String}}
        {sql_safe_filter_clause}
    ) AS tr
    {sql_safe_sort_clause}
    {sql_safe_limit}
    {sql_safe_offset}
    """
    return query
