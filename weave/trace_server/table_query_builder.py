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
    limit: int | None = None,
    offset: int | None = None,
    natural_direction: str = "ASC",
) -> str:
    """Generate a query for natural sorting of table rows.

    This query is optimized for performance when sorting by the original row order.
    Uses a CTE to compute the sliced digests array once, then:
    1. Pre-filters table_rows using IN clause with the digests (uses primary key efficiently)
    2. Drives the JOIN from the small enumerated digests table
    3. Joins to the pre-filtered table_rows for val_dump lookup
    """
    project_id_name = pb.add_param(project_id)
    digest_name = pb.add_param(digest)

    # Build the array selection expression (with optional reverse and slice)
    row_digests_selection = "row_digests"
    if natural_direction.lower() == "desc":
        row_digests_selection = f"reverse({row_digests_selection})"
    if limit is not None and offset is None:
        offset = 0

    offset_param = pb.add_param(offset or 0)
    if offset is not None:
        if limit is None:
            row_digests_selection = (
                f"arraySlice({row_digests_selection}, 1 + {{{offset_param}: Int64}})"
            )
        else:
            limit_param = pb.add_param(limit)
            row_digests_selection = f"arraySlice({row_digests_selection}, 1 + {{{offset_param}: Int64}}, {{{limit_param}: Int64}})"

    # Use CTE with any() + ifNull to guarantee exactly one row (handles empty table case)
    # Pre-filter table_rows with IN clause for efficient primary key usage
    query = f"""
    WITH digests_arr AS (
        SELECT ifNull(any({row_digests_selection}), []) AS arr
        FROM tables
        WHERE project_id = {{{project_id_name}: String}}
          AND digest = {{{digest_name}: String}}
    )
    SELECT DISTINCT
        t.row_digest AS digest,
        tr.val_dump,
        t.original_index + {{{offset_param}: Int64}} - 1 AS original_index
    FROM (
        SELECT row_digest, original_index
        FROM (
            SELECT
                (SELECT arr FROM digests_arr) AS row_digests,
                arrayEnumerate((SELECT arr FROM digests_arr)) AS original_indices
        )
        ARRAY JOIN row_digests AS row_digest, original_indices AS original_index
    ) AS t
    INNER JOIN (
        SELECT digest, val_dump
        FROM table_rows
        WHERE project_id = {{{project_id_name}: String}}
          AND digest IN (SELECT arrayJoin(arr) FROM digests_arr)
    ) AS tr ON tr.digest = t.row_digest
    ORDER BY original_index ASC
    """

    return query


def make_standard_table_query(
    project_id: str,
    digest: str,
    pb: ParamBuilder,
    *,
    # using the `sql_safe_*` prefix is a way to signal to the caller
    # that these strings should have been sanitized by the caller.
    sql_safe_conditions: list[str] | None = None,
    sql_safe_sort_clause: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> str:
    """Generate a standard query for table rows with custom sorting and filtering.
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

    # Use CTE with any() + ifNull to guarantee exactly one row (handles empty table case)
    # Pre-filter table_rows with IN clause to force primary key usage
    query = f"""
    WITH digests_arr AS (
        SELECT ifNull(any(row_digests), []) AS arr
        FROM tables
        WHERE project_id = {{{project_id_name}: String}}
          AND digest = {{{digest_name}: String}}
    )
    SELECT tr.digest, tr.val_dump, tr.original_index FROM
    (
        SELECT DISTINCT
            t.row_digest AS digest,
            tr.val_dump,
            t.row_index AS original_index
        FROM (
            SELECT row_digest, original_index - 1 AS row_index
            FROM (
                SELECT
                    (SELECT arr FROM digests_arr) AS row_digests,
                    arrayEnumerate((SELECT arr FROM digests_arr)) AS original_indices
            )
            ARRAY JOIN row_digests AS row_digest, original_indices AS original_index
        ) AS t
        INNER JOIN (
            SELECT digest, val_dump
            FROM table_rows
            WHERE project_id = {{{project_id_name}: String}}
              AND digest IN (SELECT arrayJoin(arr) FROM digests_arr)
        ) AS tr ON tr.digest = t.row_digest
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
