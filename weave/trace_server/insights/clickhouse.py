"""ClickHouse handlers for the insights endpoints."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from weave.trace_server.clickhouse.utilities import insert_with_empty_query_retry
from weave.trace_server.datadog import record_db_insert
from weave.trace_server.insights import writer
from weave.trace_server.insights.types import (
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

    No `id` is supplied, so a replayed request inserts new rows rather than
    replacing the originals. Callers dedupe upstream, on the turns they judge.
    """
    if req.intents and req.failures:
        raise writer.InsightWriteRejected(
            "one write carries one signature type: intents and failures name "
            "different configs"
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

    result = server._query(sql, pb.get_params())
    dicts = [
        dict(zip(result.column_names, row, strict=True)) for row in result.result_rows
    ]
    additive = req.signature_type == "intent"
    if req.mode == "groups":
        return InsightSignaturesQueryRes(
            groups=[_group(row, req.group_by) for row in dicts],
            cost_is_additive=additive,
        )

    cursor = None
    if req.order == "key" and dicts:
        last = dicts[-1]
        cursor = InsightSignatureCursor(
            day=last["trace_started_at"].date(), id=last["id"]
        )
    return InsightSignaturesQueryRes(
        rows=[InsightSignatureRow(**row) for row in dicts],
        next_cursor=cursor,
        cost_is_additive=additive,
    )


def _group(row: dict[str, Any], group_by: Sequence[str]) -> InsightSignatureGroup:
    keys = {field: str(row[field]) for field in group_by}
    return InsightSignatureGroup(
        keys=keys,
        occurrences=row["occurrences"],
        conversations=row["conversations"],
        users=row["users"],
        modal_category=row["modal_category"],
        avg_turn_cost_usd=row["avg_turn_cost_usd"],
        p50_turn_duration_ms=row["p50_turn_duration_ms"],
        configs=list(row["configs"]),
    )


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
