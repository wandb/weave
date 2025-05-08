from typing import Optional

from weave.trace_server.orm import ParamBuilder

# Constants for table and column names
TABLE_ROWS_ALIAS = "tr"
VAL_DUMP_COLUMN_NAME = "val_dump"
ROW_ORDER_COLUMN_NAME = "original_index"


def make_natural_sort_table_query(
    project_id: str,
    digest: str,
    pb: ParamBuilder,
    *,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    natural_direction: str = "ASC",
) -> str:
    """
    Generate a query for natural sorting of table rows.
    This query is optimized for performance when sorting by the original row order.
    """
    project_id_name = pb.add_param(project_id)
    digest_name = pb.add_param(digest)

    row_digests_selection = "row_digests"
    if natural_direction.lower() == "desc":
        row_digests_selection = f"reverse({row_digests_selection})"
    if limit is not None and offset is None:
        offset = 0
    if offset is not None:
        if limit is None:
            row_digests_selection = f"arraySlice({row_digests_selection}, 1 + {{{pb.add_param(offset)}: Int64}})"
        else:
            row_digests_selection = f"arraySlice({row_digests_selection}, 1 + {{{pb.add_param(offset)}: Int64}}, {{{pb.add_param(limit)}: Int64}})"

    query = f"""
    SELECT DISTINCT tr.digest, tr.val_dump, t.original_index + {{{pb.add_param(offset or 0)}: Int64}} - 1 as original_index
    FROM table_rows tr
    INNER JOIN (
        SELECT row_digest, original_index
        FROM (
            SELECT {row_digests_selection} as row_digests,
                   arrayEnumerate(row_digests) as original_indices
            FROM tables
            WHERE project_id = {{{project_id_name}: String}}
            AND digest = {{{digest_name}: String}}
            LIMIT 1
        )
        ARRAY JOIN row_digests AS row_digest, original_indices AS original_index
    ) AS t ON tr.digest = t.row_digest
    WHERE tr.project_id = {{{project_id_name}: String}}
    ORDER BY original_index ASC
    """

    return query


def make_standard_table_query(
    project_id: str,
    digest: str,
    pb: ParamBuilder,
    *,
    # using the `sql_safe_*` prefix is a way to signal to the caller
    # that these strings should have been santized by the caller.
    sql_safe_conditions: Optional[list[str]] = None,
    sql_safe_sort_clause: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> str:
    """
    Generate a standard query for table rows with custom sorting and filtering.
    This query is more flexible but may be less performant than the natural sort query.
    """
    project_id_name = pb.add_param(project_id)
    digest_name = pb.add_param(digest)

    sql_safe_sort_clause = sql_safe_sort_clause or ""
    sql_safe_filter_clause = (
        f"AND {' AND '.join(sql_safe_conditions)}" if sql_safe_conditions else ""
    )

    sql_safe_limit = (
        f"LIMIT {{{pb.add_param(limit)}: Int64}}" if limit is not None else ""
    )
    sql_safe_offset = (
        f"OFFSET {{{pb.add_param(offset)}: Int64}}" if offset is not None else ""
    )

    query = f"""
    SELECT tr.digest, tr.val_dump, tr.original_index FROM
    (
        SELECT DISTINCT tr.digest, tr.val_dump, t.row_index as original_index
        FROM table_rows tr
        INNER JOIN (
            SELECT row_digest, original_index - 1 as row_index
            FROM (
                SELECT row_digests,
                       arrayEnumerate(row_digests) as original_indices
                FROM tables
                WHERE project_id = {{{project_id_name}: String}}
                AND digest = {{{digest_name}: String}}
                LIMIT 1
            )
            ARRAY JOIN row_digests AS row_digest, original_indices AS original_index
        ) AS t ON tr.digest = t.row_digest
        WHERE tr.project_id = {{{project_id_name}: String}}
        {sql_safe_filter_clause}
    ) AS tr
    {sql_safe_sort_clause}
    {sql_safe_limit}
    {sql_safe_offset}
    """
    return query


def make_table_stats_query_with_storage_size(
    project_id: str,
    table_digests: list[str],
    pb: ParamBuilder,
) -> str:
    """Generate a query for table stats with storage size and length(num of rows)."""
    project_id_name = pb.add_param(project_id)
    digest_ids = pb.add_param(table_digests)

    query = f"""
    SELECT tb_digest, any(length), sum(size_bytes) FROM
    (
        SELECT digest as tb_digest, length(row_digests) as length, row_digests
        FROM tables
        WHERE project_id = {{{project_id_name}: String}} AND digest in {{{digest_ids}: Array(String)}}
    ) AS sub ARRAY JOIN row_digests as row_digest
    LEFT JOIN
    (
        SELECT * FROM table_rows_stats WHERE table_rows_stats.project_id = {{{project_id_name}: String}}
    ) as table_rows_stats ON table_rows_stats.digest = row_digest

    GROUP BY tb_digest
    """
    return query
