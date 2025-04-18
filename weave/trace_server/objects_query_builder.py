from collections.abc import Iterator
from typing import Any, Optional

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_schema import SelectableCHObjSchema
from weave.trace_server.orm import combine_conditions
from weave.trace_server.trace_server_common import digest_is_version_like

VALID_OBJECT_SORT_FIELDS = {"created_at", "object_id"}
VALID_SORT_DIRECTIONS = {"asc", "desc"}
OBJECT_METADATA_COLUMNS = [
    "project_id",
    "object_id",
    "created_at",
    "refs",
    "kind",
    "base_object_class",
    "digest",
    "version_index",
    "is_latest",
    "deleted_at",
    "wb_user_id",
    # columns not used in SelectableCHObjSchema:
    "version_count",
    "is_op",
]


def _make_optional_part(query_keyword: str, part: Optional[str]) -> str:
    if part is None or part == "":
        return ""
    return f"{query_keyword} {part}"


def _make_limit_part(limit: Optional[int]) -> str:
    if limit is None:
        return ""
    return _make_optional_part("LIMIT", str(limit))


def _make_offset_part(offset: Optional[int]) -> str:
    if offset is None:
        return ""
    return _make_optional_part("OFFSET", str(offset))


def _make_sort_part(sort_by: Optional[list[tsi.SortBy]]) -> str:
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


def _make_conditions_part(conditions: Optional[list[str]]) -> str:
    if not conditions:
        return ""
    conditions_str = combine_conditions(conditions, "AND")
    return _make_optional_part("WHERE", conditions_str)


def _make_object_id_conditions_part(
    object_id_conditions: Optional[list[str]], add_where_clause: bool = False
) -> str:
    """
    Formats object_id_conditions into a query string. In this file is it only
    used after the WHERE project_id... clause, but passing add_where_clause=True
    adds a WHERE clause to the query string.
    """
    if not object_id_conditions:
        return ""
    conditions_str = combine_conditions(object_id_conditions, "AND")
    conditions_str_with_and = " " + _make_optional_part("AND", conditions_str)
    if add_where_clause:
        return "WHERE " + conditions_str_with_and
    return conditions_str_with_and


def format_metadata_objects_from_query_result(
    query_result: Iterator[tuple[Any, ...]],
    include_storage_size: bool = False,
) -> list[SelectableCHObjSchema]:
    result = []
    for row in query_result:
        # Add an empty val_dump to the end of the row
        row_with_val_dump = row + ("{}",)
        columns_with_val_dump = list(OBJECT_METADATA_COLUMNS)

        if include_storage_size:
            columns_with_val_dump += ["size_bytes"]

        columns_with_val_dump += ["val_dump"]

        row_dict = dict(zip(columns_with_val_dump, row_with_val_dump))

        row_model = SelectableCHObjSchema.model_validate(row_dict)
        result.append(row_model)
    return result


class ObjectMetadataQueryBuilder:
    def __init__(
        self,
        project_id: str,
        conditions: Optional[list[str]] = None,
        object_id_conditions: Optional[list[str]] = None,
        parameters: Optional[dict[str, Any]] = None,
        include_deleted: bool = False,
    ):
        self.project_id = project_id
        self.parameters: dict[str, Any] = parameters or {}
        if not self.parameters.get(project_id):
            self.parameters.update({"project_id": project_id})
        self._conditions: list[str] = conditions or []
        self._object_id_conditions: list[str] = object_id_conditions or []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._sort_by: list[tsi.SortBy] = []
        self._include_deleted: bool = include_deleted
        self.include_storage_size: bool = False

    @property
    def conditions_part(self) -> str:
        _conditions = list(self._conditions)
        if not self._include_deleted:
            _conditions.append("deleted_at IS NULL")
        return _make_conditions_part(_conditions)

    @property
    def object_id_conditions_part(self) -> str:
        return _make_object_id_conditions_part(self._object_id_conditions)

    @property
    def sort_part(self) -> str:
        if not self._sort_by:
            return "ORDER BY created_at ASC"
        return _make_sort_part(self._sort_by)

    @property
    def limit_part(self) -> str:
        return _make_limit_part(self._limit)

    @property
    def offset_part(self) -> str:
        return _make_offset_part(self._offset)

    def _make_digest_condition(
        self, digest: str, param_key: Optional[str] = None, index: Optional[int] = None
    ) -> str:
        """
        If digest is "latest", return the condition for the latest version.
        Otherwise, return the condition for the version with the given digest.
        If digest is a version like "v123", return the condition for the version
        with the given version index.
        If digest is a hash like "sha256" return the hash
        Use index to make the param_key unique if there are multiple digests.
        """
        if digest == "latest":
            return "is_latest = 1"

        (is_version, version_index) = digest_is_version_like(digest)
        if is_version:
            param_key = param_key or "version_index"
            return self._make_version_index_condition(version_index, param_key, index)
        else:
            param_key = param_key or "version_digest"
            return self._make_version_digest_condition(digest, param_key, index)

    def _make_version_digest_condition(
        self, digest: str, param_key: str, index: Optional[int] = None
    ) -> str:
        if index is not None:
            param_key = f"{param_key}_{index}"
        self.parameters.update({param_key: digest})
        return f"digest = {{{param_key}: String}}"

    def _make_version_index_condition(
        self, version_index: int, param_key: str, index: Optional[int] = None
    ) -> str:
        if index is not None:
            param_key = f"{param_key}_{index}"
        self.parameters.update({param_key: version_index})
        return f"version_index = {{{param_key}: Int64}}"

    def add_digests_conditions(self, *digests: str) -> None:
        digest_conditions = []
        for i, digest in enumerate(digests):
            condition = self._make_digest_condition(digest, None, i)
            digest_conditions.append(condition)

        digests_condition = combine_conditions(digest_conditions, "OR")
        self._conditions.append(digests_condition)

    def add_object_ids_condition(
        self, object_ids: list[str], param_key: Optional[str] = None
    ) -> None:
        if len(object_ids) == 1:
            param_key = param_key or "object_id"
            self._object_id_conditions.append(f"object_id = {{{param_key}: String}}")
            self.parameters.update({param_key: object_ids[0]})
        else:
            param_key = param_key or "object_ids"
            self._object_id_conditions.append(
                f"object_id IN {{{param_key}: Array(String)}}"
            )
            self.parameters.update({param_key: object_ids})

    def add_is_latest_condition(self) -> None:
        self._conditions.append("is_latest = 1")

    def add_is_op_condition(self, is_op: bool) -> None:
        if is_op:
            self._conditions.append("is_op = 1")
        else:
            self._conditions.append("is_op = 0")

    def add_base_object_classes_condition(self, base_object_classes: list[str]) -> None:
        self._conditions.append(
            "base_object_class IN {base_object_classes: Array(String)}"
        )
        self.parameters.update({"base_object_classes": base_object_classes})

    def add_order(self, field: str, direction: str) -> None:
        direction = direction.lower()
        if direction not in ("asc", "desc"):
            raise ValueError(f"Direction {direction} is not allowed")
        self._sort_by.append(tsi.SortBy(field=field, direction=direction))

    def set_limit(self, limit: int) -> None:
        if limit < 0:
            raise ValueError("Limit must be a positive integer")
        if self._limit is not None:
            raise ValueError("Limit can only be set once")
        self._limit = limit

    def set_offset(self, offset: int) -> None:
        if offset < 0:
            raise ValueError("Offset must be a positive integer")
        if self._offset is not None:
            raise ValueError("Offset can only be set once")
        self._offset = offset

    def set_include_deleted(self, include_deleted: bool) -> None:
        self._include_deleted = include_deleted

    def make_metadata_query(self) -> str:
        columns = list(OBJECT_METADATA_COLUMNS)

        main_table_alias = "main"

        if self.include_storage_size:
            columns += ["size_bytes"]
        columns_str = ",\n    ".join(columns)

        join_clause = ""
        if self.include_storage_size:
            join_clause = f"""
            LEFT JOIN (
                SELECT * FROM object_versions_stats WHERE object_versions_stats.project_id = {{project_id: String}}
            ) as object_versions_stats ON object_versions_stats.digest = {main_table_alias}.digest
            """

        query = f"""
SELECT
    {columns_str}
FROM (
    SELECT
        project_id,
        object_id,
        created_at,
        deleted_at,
        kind,
        base_object_class,
        refs,
        digest,
        wb_user_id,
        is_op,
        row_number() OVER (
            PARTITION BY project_id,
            kind,
            object_id
            ORDER BY created_at ASC
        ) - 1 AS version_index,
        count(*) OVER (
            PARTITION BY project_id, kind, object_id
        ) as version_count,
        row_number() OVER (
            PARTITION BY project_id, kind, object_id
            ORDER BY (deleted_at IS NULL) DESC, created_at DESC
        ) AS row_num,
        if (row_num = 1, 1, 0) AS is_latest
    FROM (
        --
        -- Object versions are uniquely identified by (kind, project_id, object_id, digest).
        -- This subquery selects a row to represent each object version. There are multiple rows
        -- for each object version if it has been deleted or recreated prior to a table merge.
        --
        SELECT
            project_id,
            object_id,
            created_at,
            deleted_at,
            kind,
            base_object_class,
            refs,
            digest,
            wb_user_id,
            if (kind = 'op', 1, 0) AS is_op,
            row_number() OVER (
                PARTITION BY project_id,
                kind,
                object_id,
                digest
                --
                -- Prefer the most recent row. If there is a tie, prefer the row
                -- with non-null deleted_at, which represents the deletion event.
                --
                -- Rows for the same object version may have the same created_at
                -- because deletion events inherit the created_at of the last
                -- non-deleted row for the object version.
                --
                ORDER BY created_at DESC, (deleted_at IS NULL) ASC
            ) AS rn
        FROM object_versions
        WHERE project_id = {{project_id: String}}{self.object_id_conditions_part}
    )
    WHERE rn = 1
) as {main_table_alias}
    {join_clause}
"""
        if self.conditions_part:
            query += f"\n{self.conditions_part}"
        if self.sort_part:
            query += f"\n{self.sort_part}"
        if self.limit_part:
            query += f"\n{self.limit_part}"
        if self.offset_part:
            query += f"\n{self.offset_part}"
        return query


def make_objects_val_query_and_parameters(
    project_id: str, object_ids: list[str], digests: list[str]
) -> tuple[str, dict[str, Any]]:
    query = """
        SELECT object_id, digest, argMax(val_dump, created_at)
        FROM object_versions
        WHERE project_id = {project_id: String} AND
            object_id IN {object_ids: Array(String)} AND
            digest IN {digests: Array(String)}
        GROUP BY object_id, digest
    """
    parameters = {
        "project_id": project_id,
        "object_ids": object_ids,
        "digests": digests,
    }
    return query, parameters
