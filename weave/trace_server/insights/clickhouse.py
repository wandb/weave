"""ClickHouse handlers for the insights endpoints."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from typing import TYPE_CHECKING, Any

from clickhouse_connect.driver.query import QueryResult

from weave.trace_server.clickhouse.utilities import insert_with_empty_query_retry
from weave.trace_server.datadog import record_db_insert
from weave.trace_server.insights import writer
from weave.trace_server.insights.types import (
    InsightContextQueryReq,
    InsightContextQueryRes,
    InsightContextSignature,
    InsightSignatureCursor,
    InsightSignatureGroup,
    InsightSignatureRow,
    InsightSignaturesQueryReq,
    InsightSignaturesQueryRes,
    InsightSignaturesWriteReq,
    InsightSignaturesWriteRes,
    InsightWriteCounts,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.insights_query_builder import (
    FAILURE_TABLE,
    INTENT_TABLE,
    PARAM_NAMESPACE,
    make_context_query,
    make_signature_groups_query,
    make_signature_rows_query,
)

if TYPE_CHECKING:
    from weave.trace_server.clickhouse_trace_server_batched import (
        ClickHouseTraceServer,
    )


def insights_signatures_write(
    server: ClickHouseTraceServer, req: InsightSignaturesWriteReq
) -> InsightSignaturesWriteRes:
    """Insert everything a batch of judged turns emitted.

    Retry safety comes from the tables: same `id`, later `inserted_at`, and
    ReplacingMergeTree keeps the newer row. Nothing here supplies a version,
    because `inserted_at` is MATERIALIZED and the server owns that clock.
    """
    if req.intents and req.failures:
        raise writer.InsightWriteRejected(
            "one write carries one space: intents and failures name different configs"
        )
    writer.validate_config_sha("failure" if req.failures else "intent", req.config_sha)

    dropped: dict[str, int] = {}
    written = InsightWriteCounts()

    if req.intents:
        rows, gates = writer.prepare_intents(
            req.project_id, req.config_sha, req.intents
        )
        _merge(dropped, gates)
        written.intents = _insert(server, INTENT_TABLE, rows)
    if req.failures:
        rows, gates = writer.prepare_failures(
            req.project_id, req.config_sha, req.failures
        )
        _merge(dropped, gates)
        written.failures = _insert(server, FAILURE_TABLE, rows)

    return InsightSignaturesWriteRes(written=written, dropped=dropped)


def insights_context_query(
    server: ClickHouseTraceServer, req: InsightContextQueryReq
) -> InsightContextQueryRes:
    """Everything already distilled about the caller's turns, both lenses.

    Empty in, empty out: an `IN ()` over no turns is a scan that cannot match.
    """
    if not req.turn_trace_ids:
        return InsightContextQueryRes()
    pb = ParamBuilder(PARAM_NAMESPACE)
    sql = make_context_query(pb, req)
    result = server._query(sql, pb.get_params())
    rows = _newest_per_key(
        _as_dicts(result), lambda row: (row["lens"], row["id"], row["turn_trace_id"])
    )
    return InsightContextQueryRes(
        signatures=[
            InsightContextSignature(
                lens=row["lens"],
                turn_trace_id=row["turn_trace_id"],
                signature=row["signature"],
                signature_display=row["signature_display"],
                category=row["category"],
                config_sha=row["config_sha"],
                source_started_at=row["source_started_at"],
            )
            for row in rows
        ]
    )


def insights_signatures_query(
    server: ClickHouseTraceServer, req: InsightSignaturesQueryReq
) -> InsightSignaturesQueryRes:
    pb = ParamBuilder(PARAM_NAMESPACE)
    if req.mode == "rows":
        sql = make_signature_rows_query(pb, req)
    elif req.mode == "groups":
        sql = make_signature_groups_query(pb, req)
    else:
        raise ValueError(f"unknown insights query mode {req.mode!r}")

    dicts = _as_dicts(server._query(sql, pb.get_params()))
    if req.mode == "groups":
        return InsightSignaturesQueryRes(
            groups=[_group(row, req.group_by) for row in dicts],
            cost_is_additive=req.lens == "intent",
        )

    rows = _newest_per_key(dicts, lambda row: row["id"])
    cursor = None
    if req.order == "key" and rows:
        last = rows[-1]
        cursor = InsightSignatureCursor(
            day=last["source_started_at"].date(), id=last["id"]
        )
    return InsightSignaturesQueryRes(
        rows=[InsightSignatureRow(**row) for row in rows],
        next_cursor=cursor,
        cost_is_additive=req.lens == "intent",
    )


def _as_dicts(result: QueryResult) -> list[dict[str, Any]]:
    """Column-named rows with `id` rendered as text.

    `id` is a UUID column, so the driver hands back a `uuid.UUID`. Every model
    and every cursor spells it as a string, so it is normalized once here rather
    than at each of the four places that read it.
    """
    rows = [
        dict(zip(result.column_names, row, strict=True)) for row in result.result_rows
    ]
    for row in rows:
        if "id" in row:
            row["id"] = str(row["id"])
    return rows


def _newest_per_key(
    rows: list[dict[str, Any]], key: Callable[[dict[str, Any]], Hashable]
) -> list[dict[str, Any]]:
    """Keep the highest `inserted_at` per key, preserving first-seen order.

    A re-judged row is a version rather than a second occurrence, and collapsing
    them in SQL cost 7.62 GiB against 51.9 MiB on this schema.
    """
    best: dict[Hashable, dict[str, Any]] = {}
    for row in rows:
        row_key = key(row)
        current = best.get(row_key)
        if current is None or row["inserted_at"] > current["inserted_at"]:
            best[row_key] = row
    return list(best.values())


def _group(row: dict[str, Any], group_by: Sequence[str]) -> InsightSignatureGroup:
    keys = {field: str(row[_group_alias(field)]) for field in group_by}
    return InsightSignatureGroup(
        keys=keys,
        occurrences=row["occurrences"],
        conversations=row["conversations"],
        users=row["users"],
        modal_category=row["modal_category"],
        avg_cost_usd=row["avg_cost_usd"],
        p50_duration_ms=row["p50_duration_ms"],
        configs=list(row["configs"]),
    )


def _group_alias(field: str) -> str:
    return "day" if field == "day" else field


def _insert(
    server: ClickHouseTraceServer, table: str, rows: list[dict[str, object]]
) -> int:
    if not rows:
        return 0
    columns = list(rows[0].keys())
    insert_with_empty_query_retry(
        server.ch_client,
        table,
        data=[[row[column] for column in columns] for row in rows],
        column_names=columns,
        settings=server._async_insert_settings(),
    )
    record_db_insert(table=table, count=len(rows))
    return len(rows)


def _merge(dropped: dict[str, int], gates: dict[str, int]) -> None:
    for gate, count in gates.items():
        dropped[gate] = dropped.get(gate, 0) + count
