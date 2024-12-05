from typing import Any, Iterator
from weave.trace_server.clickhouse_schema import SelectableCHObjSchema
from weave.trace_server.orm import Column, Table, combine_conditions
from weave.trace_server import trace_server_interface as tsi

VALID_OBJECT_SORT_FIELDS = {"created_at", "object_id"}
VALID_SORT_DIRECTIONS = {"asc", "desc"}
OBJECT_COLUMNS = [
    "project_id",
    "object_id",
    "created_at",
    "kind",
    "base_object_class",
    "refs",
    "digest",
    "is_op",
    "version_index",
    "version_count",
    "is_latest",
    "val_dump",
]


def _make_optional_part(query_keyword: str, part: str | None) -> str:
    if part is None or part == "":
        return ""
    return f"{query_keyword} {part}"


def _make_limit_part(limit: int | None) -> str:
    return _make_optional_part("LIMIT", str(limit))


def _make_offset_part(offset: int | None) -> str:
    return _make_optional_part("OFFSET", str(offset))


def _make_sort_part(sort_by: list[tsi.SortBy] | None) -> str:
    if not sort_by:
        return ""

    sort_clauses = []
    for sort in sort_by:
        if (
            sort.field in VALID_OBJECT_SORT_FIELDS
            and sort.direction in VALID_SORT_DIRECTIONS
        ):
            sort_clause = f"{sort.field} {sort.direction.upper()}"
            sort_clauses.append(sort_clause)
    return _make_optional_part("ORDER BY", ", ".join(sort_clauses))


def _make_conditions_part(conditions: list[str] | None) -> str:
    if not conditions:
        return ""
    conditions_str = combine_conditions(conditions, "AND")
    return _make_optional_part("WHERE", conditions_str)


def _make_object_id_conditions_part(object_id_conditions: list[str] | None) -> str:
    if not object_id_conditions:
        return ""
    conditions_str = combine_conditions(object_id_conditions, "AND")
    return _make_optional_part("AND", conditions_str)


def _make_select_object_metadata_query(
    conditions_part: str,
    object_id_conditions_part: str,
    limit_part: str,
    offset_part: str,
    sort_part: str,
) -> str:
    return f"""
        SELECT
            project_id,
            object_id,
            created_at,
            kind,
            base_object_class,
            refs,
            digest,
            is_op,
            version_index,
            version_count,
            is_latest
        FROM (
            SELECT project_id,
                object_id,
                created_at,
                kind,
                base_object_class,
                refs,
                digest,
                is_op,
                row_number() OVER (
                    PARTITION BY project_id,
                    kind,
                    object_id
                    ORDER BY created_at ASC
                ) - 1 AS version_index,
                count(*) OVER (PARTITION BY project_id, kind, object_id) as version_count,
                if(version_index + 1 = version_count, 1, 0) AS is_latest
            FROM (
                SELECT project_id,
                    object_id,
                    created_at,
                    kind,
                    base_object_class,
                    refs,
                    digest,
                    if (kind = 'op', 1, 0) AS is_op,
                    row_number() OVER (
                        PARTITION BY project_id,
                        kind,
                        object_id,
                        digest
                        ORDER BY created_at ASC
                    ) AS rn
                FROM object_versions
                WHERE project_id = {{project_id: String}} {object_id_conditions_part}
            )
            WHERE rn = 1
        )
        {conditions_part}
        {sort_part}
        {limit_part}
        {offset_part}
    """


def select_object_metadata_clickhouse_query(
    conditions: list[str] | None,
    object_id_conditions: list[str] | None,
    limit: int | None,
    offset: int | None,
    sort_by: list[tsi.SortBy] | None,
) -> str:
    conditions_part = _make_conditions_part(conditions)
    object_id_conditions_part = _make_object_id_conditions_part(object_id_conditions)
    limit_part = _make_limit_part(limit)
    offset_part = _make_offset_part(offset)
    sort_part = _make_sort_part(sort_by)

    query_str = _make_select_object_metadata_query(
        conditions_part,
        object_id_conditions_part,
        limit_part,
        offset_part,
        sort_part,
    )
    return query_str


def format_objects_from_query_result(
    query_result: Iterator[tuple[Any, ...]]
) -> list[SelectableCHObjSchema]:
    result = []
    for row in query_result:
        # Add an empty val_dump to the end of the row
        row_with_val_dump = row + ("{}",)
        row_dict = dict(zip(OBJECT_COLUMNS, row_with_val_dump))
        row_model = SelectableCHObjSchema.model_validate(row_dict)
        result.append(row_model)
    return result
