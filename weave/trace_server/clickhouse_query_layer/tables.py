# ClickHouse Tables - Table CRUD operations

import hashlib
import json
import logging
from collections.abc import Iterator, Sequence
from typing import Any, cast

import ddtrace

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_query_layer.client import ClickHouseClient
from weave.trace_server.clickhouse_query_layer.query_builders.calls.calls_query_builder import (
    OrderField,
    QueryBuilderDynamicField,
    QueryBuilderField,
)
from weave.trace_server.clickhouse_query_layer.query_builders.tables import (
    ROW_ORDER_COLUMN_NAME,
    TABLE_ROWS_ALIAS,
    VAL_DUMP_COLUMN_NAME,
    make_natural_sort_table_query,
    make_standard_table_query,
    make_table_stats_query_with_storage_size,
)
from weave.trace_server.errors import InvalidRequest, NotFoundError
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.trace_server_interface_util import (
    extract_refs_from_values,
    str_digest,
)

logger = logging.getLogger(__name__)


class TablesRepository:
    """Repository for table CRUD operations."""

    def __init__(self, ch_client: ClickHouseClient):
        self._ch_client = ch_client

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        """Create a new table with rows."""
        insert_rows = []
        for r in req.table.rows:
            if not isinstance(r, dict):
                raise TypeError(
                    f"Validation Error: Encountered a non-dictionary row when "
                    f"creating a table. Please ensure that all rows are "
                    f"dictionaries. Violating row:\n{r}."
                )
            row_json = json.dumps(r)
            row_digest = str_digest(row_json)
            insert_rows.append(
                (
                    req.table.project_id,
                    row_digest,
                    extract_refs_from_values(r),
                    row_json,
                )
            )

        self._ch_client.insert(
            "table_rows",
            data=insert_rows,
            column_names=["project_id", "digest", "refs", "val_dump"],
        )

        row_digests = [r[1] for r in insert_rows]

        table_hasher = hashlib.sha256()
        for row_digest in row_digests:
            table_hasher.update(row_digest.encode())
        digest = table_hasher.hexdigest()

        self._ch_client.insert(
            "tables",
            data=[(req.table.project_id, digest, row_digests)],
            column_names=["project_id", "digest", "row_digests"],
        )
        return tsi.TableCreateRes(digest=digest, row_digests=row_digests)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        """Update a table with append, pop, or insert operations."""
        query = """
            SELECT *
            FROM (
                    SELECT *,
                        row_number() OVER (PARTITION BY project_id, digest) AS rn
                    FROM tables
                    WHERE project_id = {project_id:String} AND digest = {digest:String}
                )
            WHERE rn = 1
            ORDER BY project_id, digest
        """

        row_digest_result_query = self._ch_client.ch_client.query(
            query,
            parameters={
                "project_id": req.project_id,
                "digest": req.base_digest,
            },
        )

        if len(row_digest_result_query.result_rows) == 0:
            raise NotFoundError(f"Table {req.project_id}:{req.base_digest} not found")

        final_row_digests: list[str] = row_digest_result_query.result_rows[0][2]
        new_rows_needed_to_insert = []
        known_digests = set(final_row_digests)

        def add_new_row_needed_to_insert(row_data: Any) -> str:
            if not isinstance(row_data, dict):
                raise TypeError("All rows must be dictionaries")
            row_json = json.dumps(row_data)
            row_digest = str_digest(row_json)
            if row_digest not in known_digests:
                new_rows_needed_to_insert.append(
                    (
                        req.project_id,
                        row_digest,
                        extract_refs_from_values(row_data),
                        row_json,
                    )
                )
                known_digests.add(row_digest)
            return row_digest

        updated_digests = []
        for update in req.updates:
            if isinstance(update, tsi.TableAppendSpec):
                new_digest = add_new_row_needed_to_insert(update.append.row)
                final_row_digests.append(new_digest)
                updated_digests.append(new_digest)
            elif isinstance(update, tsi.TablePopSpec):
                if update.pop.index >= len(final_row_digests) or update.pop.index < 0:
                    raise ValueError("Index out of range")
                popped_digest = final_row_digests.pop(update.pop.index)
                updated_digests.append(popped_digest)
            elif isinstance(update, tsi.TableInsertSpec):
                if (
                    update.insert.index > len(final_row_digests)
                    or update.insert.index < 0
                ):
                    raise ValueError("Index out of range")
                new_digest = add_new_row_needed_to_insert(update.insert.row)
                final_row_digests.insert(update.insert.index, new_digest)
                updated_digests.append(new_digest)
            else:
                raise TypeError("Unrecognized update", update)

        if new_rows_needed_to_insert:
            self._ch_client.insert(
                "table_rows",
                data=new_rows_needed_to_insert,
                column_names=["project_id", "digest", "refs", "val_dump"],
            )

        table_hasher = hashlib.sha256()
        for row_digest in final_row_digests:
            table_hasher.update(row_digest.encode())
        digest = table_hasher.hexdigest()

        self._ch_client.insert(
            "tables",
            data=[(req.project_id, digest, final_row_digests)],
            column_names=["project_id", "digest", "row_digests"],
        )
        return tsi.TableUpdateRes(digest=digest, updated_row_digests=updated_digests)

    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes:
        """Create a table by specifying row digests instead of actual rows."""
        table_hasher = hashlib.sha256()
        for row_digest in req.row_digests:
            table_hasher.update(row_digest.encode())
        digest = table_hasher.hexdigest()

        self._ch_client.insert(
            "tables",
            data=[(req.project_id, digest, req.row_digests)],
            column_names=["project_id", "digest", "row_digests"],
        )

        return tsi.TableCreateFromDigestsRes(digest=digest)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        """Query table rows and return all results."""
        rows = list(self.table_query_stream(req))
        return tsi.TableQueryRes(rows=rows)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        """Stream table rows that match the query."""
        conds = []
        pb = ParamBuilder()
        if req.filter and req.filter.row_digests:
            conds.append(
                f"tr.digest IN {{{pb.add_param(req.filter.row_digests)}: Array(String)}}"
            )

        sort_fields = []
        if req.sort_by:
            for sort in req.sort_by:
                if not sort.field or not sort.field.strip():
                    raise InvalidRequest("Sort field cannot be empty")

                if (
                    sort.field.startswith(".")
                    or sort.field.endswith(".")
                    or ".." in sort.field
                ):
                    raise InvalidRequest(
                        f"Invalid sort field '{sort.field}': field names cannot "
                        f"start/end with dots or contain consecutive dots"
                    )

                extra_path = sort.field.split(".")

                if any(not component.strip() for component in extra_path):
                    raise InvalidRequest(
                        f"Invalid sort field '{sort.field}': field path "
                        f"components cannot be empty"
                    )

                field = OrderField(
                    field=QueryBuilderDynamicField(
                        field=VAL_DUMP_COLUMN_NAME, extra_path=extra_path
                    ),
                    direction="ASC" if sort.direction.lower() == "asc" else "DESC",
                )
                sort_fields.append(field)

        rows = self._table_query_stream(
            req.project_id,
            req.digest,
            pb,
            sql_safe_conditions=conds,
            sort_fields=sort_fields,
            limit=req.limit,
            offset=req.offset,
        )
        yield from rows

    @ddtrace.tracer.wrap(name="tables_repository._table_query_stream")
    def _table_query_stream(
        self,
        project_id: str,
        digest: str,
        pb: ParamBuilder,
        *,
        sql_safe_conditions: list[str] | None = None,
        sort_fields: list[OrderField] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Iterator[tsi.TableRowSchema]:
        """Internal method for streaming table rows."""
        if not sort_fields:
            sort_fields = [
                OrderField(
                    field=QueryBuilderField(field=ROW_ORDER_COLUMN_NAME),
                    direction="ASC",
                )
            ]

        if (
            len(sort_fields) == 1
            and sort_fields[0].field.field == ROW_ORDER_COLUMN_NAME
            and not sql_safe_conditions
        ):
            query = make_natural_sort_table_query(
                project_id,
                digest,
                pb,
                limit=limit,
                offset=offset,
                natural_direction=sort_fields[0].direction,
            )
        else:
            order_by_components = ", ".join(
                [sort_field.as_sql(pb, TABLE_ROWS_ALIAS) for sort_field in sort_fields]
            )
            sql_safe_sort_clause = f"ORDER BY {order_by_components}"
            query = make_standard_table_query(
                project_id,
                digest,
                pb,
                sql_safe_conditions=sql_safe_conditions,
                sql_safe_sort_clause=sql_safe_sort_clause,
                limit=limit,
                offset=offset,
            )

        res = self._ch_client.query_stream(query, parameters=pb.get_params())

        for row in res:
            yield tsi.TableRowSchema(
                digest=row[0], val=json.loads(row[1]), original_index=row[2]
            )

    def table_row_read(self, project_id: str, row_digest: str) -> tsi.TableRowSchema:
        """Read a single table row by digest.

        Args:
            project_id: The project ID.
            row_digest: The digest of the row to read.

        Returns:
            The table row schema.

        Raises:
            NotFoundError: If the row is not found.
        """
        query = """
            SELECT digest, val_dump
            FROM table_rows
            WHERE project_id = {project_id:String} AND digest = {row_digest:String}
            LIMIT 1
        """
        result = self._ch_client.ch_client.query(
            query,
            parameters={
                "project_id": project_id,
                "row_digest": row_digest,
            },
        )
        if len(result.result_rows) == 0:
            raise NotFoundError(f"Row {row_digest} not found")

        row = result.result_rows[0]
        return tsi.TableRowSchema(digest=row[0], val=json.loads(row[1]))

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        """Get stats for a single table (legacy endpoint)."""
        batch_req = tsi.TableQueryStatsBatchReq(
            project_id=req.project_id, digests=[req.digest]
        )

        res = self.table_query_stats_batch(batch_req)

        if len(res.tables) != 1:
            logger.exception(RuntimeError("Unexpected number of results", res))

        count = res.tables[0].count
        return tsi.TableQueryStatsRes(count=count)

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        """Get stats for multiple tables."""
        parameters: dict[str, Any] = {
            "project_id": req.project_id,
            "digests": req.digests,
        }

        query = """
        SELECT digest, any(length(row_digests))
        FROM tables
        WHERE project_id = {project_id:String} AND digest IN {digests:Array(String)}
        GROUP BY digest
        """

        if req.include_storage_size:
            pb = ParamBuilder()
            query = make_table_stats_query_with_storage_size(
                project_id=req.project_id,
                table_digests=cast(list[str], req.digests),
                pb=pb,
            )
            parameters = pb.get_params()

        query_result = self._ch_client.ch_client.query(query, parameters=parameters)

        tables = [
            ch_table_stats_to_table_stats_schema(row)
            for row in query_result.result_rows
        ]

        return tsi.TableQueryStatsBatchRes(tables=tables)


# =============================================================================
# Converters
# =============================================================================


def ch_table_stats_to_table_stats_schema(
    ch_table_stats_row: Sequence[Any],
) -> tsi.TableStatsRow:
    """Convert a CH table stats row to TableStatsRow schema."""
    row_tuple = tuple(ch_table_stats_row)
    digest, count = row_tuple[:2]
    storage_size_bytes = row_tuple[2] if len(row_tuple) > 2 else cast(Any, None)

    return tsi.TableStatsRow(
        count=count,
        digest=digest,
        storage_size_bytes=storage_size_bytes,
    )
