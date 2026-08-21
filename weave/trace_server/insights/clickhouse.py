"""ClickHouse handlers for the insights endpoints."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from weave.trace_server.clickhouse.utilities import insert_with_empty_query_retry
from weave.trace_server.datadog import record_db_insert
from weave.trace_server.insights import writer
from weave.trace_server.insights.read_types import (
    FailureSignatureRow,
    InsightSignatureCursor,
    InsightSignatureGroup,
    InsightSignaturesQueryReq,
    InsightSignaturesQueryRes,
    IntentSignatureRow,
)
from weave.trace_server.insights.write_types import (
    InsightSignaturesWriteReq,
    InsightSignaturesWriteRes,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.insights_query_builder import (
    DAY_KEY,
    PARAM_NAMESPACE,
    make_signature_groups_query,
    make_signature_rows_query,
    spec_for,
)

if TYPE_CHECKING:
    from weave.trace_server.clickhouse_trace_server_batched import (
        ClickHouseTraceServer,
    )


def insights_signatures_write(
    server: ClickHouseTraceServer, req: InsightSignaturesWriteReq
) -> InsightSignaturesWriteRes:
    """Insert everything a batch of judged turns emitted.

    `id` is derived from the occurrence, so a replayed request writes the same ids
    and the ReplacingMergeTree collapses the pair on its next merge. A read between
    the replay and that merge still sees both.
    """
    writer.validate_config_sha(req.signature_type, req.config_sha)
    if req.signature_type == "intent":
        rows, gate_counts = writer.prepare_intents(
            req.project_id, req.config_sha, req.intents
        )
    elif req.signature_type == "failure":
        rows, gate_counts = writer.prepare_failures(
            req.project_id, req.config_sha, req.failures
        )
    else:
        raise ValueError(f"unknown insights signature type {req.signature_type!r}")

    written = _insert(server, spec_for(req.signature_type).table, rows)
    return InsightSignaturesWriteRes(written=written, dropped=dict(gate_counts))


def insights_signatures_query(
    server: ClickHouseTraceServer, req: InsightSignaturesQueryReq
) -> InsightSignaturesQueryRes:
    if req.mode == "rows":
        return _query_rows(server, req)
    if req.mode == "groups":
        return _query_groups(server, req)
    raise ValueError(f"unknown insights query mode {req.mode!r}")


def _query_rows(
    server: ClickHouseTraceServer, req: InsightSignaturesQueryReq
) -> InsightSignaturesQueryRes:
    """One page of occurrences, plus the cursor to resume a `key` walk.

    `next_cursor` is set only on a full page, so a caller stops on a short page
    rather than spending a request to discover the walk is over.
    """
    pb = ParamBuilder(PARAM_NAMESPACE)
    result_rows = _run(server, make_signature_rows_query(pb, req), pb)

    cursor = None
    if req.order == "key" and len(result_rows) == req.limit:
        last = result_rows[-1]
        cursor = InsightSignatureCursor(day=last[DAY_KEY], id=last["id"])

    # `day` exists to carry the cursor, and is not part of a row.
    fields = [{k: v for k, v in row.items() if k != DAY_KEY} for row in result_rows]
    if req.signature_type == "intent":
        return InsightSignaturesQueryRes(
            rows=[IntentSignatureRow(**row) for row in fields], next_cursor=cursor
        )
    if req.signature_type == "failure":
        return InsightSignaturesQueryRes(
            rows=[FailureSignatureRow(**row) for row in fields], next_cursor=cursor
        )
    raise ValueError(f"unknown insights signature type {req.signature_type!r}")


def _query_groups(
    server: ClickHouseTraceServer, req: InsightSignaturesQueryReq
) -> InsightSignaturesQueryRes:
    pb = ParamBuilder(PARAM_NAMESPACE)
    result_rows = _run(server, make_signature_groups_query(pb, req), pb)
    return InsightSignaturesQueryRes(
        groups=[_group(row, req.group_by) for row in result_rows]
    )


def _run(
    server: ClickHouseTraceServer, sql: str, pb: ParamBuilder
) -> list[dict[str, Any]]:
    result = server._query(sql, pb.get_params())
    return [
        dict(zip(result.column_names, row, strict=True)) for row in result.result_rows
    ]


def _group(row: dict[str, Any], group_by: Sequence[str]) -> InsightSignatureGroup:
    keys = {field: str(row[field]) for field in group_by}
    return InsightSignatureGroup(
        keys=keys,
        occurrences=row["occurrences"],
        turns=row["turns"],
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
    # Every column any row carries, so a row missing one raises rather than
    # silently shifting the insert by a position.
    columns = sorted({column for row in rows for column in row})
    insert_with_empty_query_retry(
        server.ch_client,
        table,
        data=[[row[column] for column in columns] for row in rows],
        column_names=columns,
        settings=server._async_insert_settings(),
    )
    record_db_insert(table=table, count=len(rows))
    return len(rows)
