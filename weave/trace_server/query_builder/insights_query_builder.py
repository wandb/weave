"""Hand-written SQL for the insights endpoints.

Every builder is a pure function of its request, so a test asserts the exact
string and the exact parameters.
"""

from __future__ import annotations

from weave.trace_server.insights.types import (
    InsightGroupField,
    InsightSignatureCursor,
    InsightSignaturesQueryReq,
    InsightSignatureType,
)
from weave.trace_server.orm import ParamBuilder

PARAM_NAMESPACE = "insights"

INTENT_TABLE = "intent_signatures"
FAILURE_TABLE = "failure_signatures"

SHARED_ROW_COLUMNS = (
    "id",
    "signature",
    "hex(sipHash128(signature)) AS signature_hash",
    "category",
    "conversation_id",
    "user_id",
    "agent_name",
    "turn_duration_ms",
    "turn_cost_usd",
    "trace_started_at",
    "inserted_at",
)
INTENT_ROW_COLUMNS = ("trace_id", "sentiment")
FAILURE_ROW_COLUMNS = (
    "current_trace_id",
    "affected_trace_ids",
    "evidence_span_ids",
    "failure_reason",
    "severity",
)

GROUP_EXPRESSIONS: dict[InsightGroupField, str] = {
    "signature": "signature",
    "category": "category",
    "sentiment": "sentiment",
    "severity": "severity",
    "agent_name": "agent_name",
    "day": "toDate(trace_started_at) AS day",
}
TYPE_ONLY_GROUP_FIELDS: dict[InsightGroupField, InsightSignatureType] = {
    "sentiment": "intent",
    "severity": "failure",
}


def table_for_signature_type(signature_type: InsightSignatureType) -> str:
    if signature_type == "intent":
        return INTENT_TABLE
    if signature_type == "failure":
        return FAILURE_TABLE
    raise ValueError(f"unknown insights signature type {signature_type!r}")


def make_signature_rows_query(pb: ParamBuilder, req: InsightSignaturesQueryReq) -> str:
    """One page of occurrences.

    Nothing collapses versions, because nothing shares an `id`: the tables mint
    it with `generateUUIDv7()`, so one judged occurrence is exactly one row.
    """
    columns = list(SHARED_ROW_COLUMNS)
    columns.extend(
        INTENT_ROW_COLUMNS if req.signature_type == "intent" else FAILURE_ROW_COLUMNS
    )
    if req.include_vector:
        columns.append("vector")

    where = _filters(pb, req)
    if req.order == "key":
        order_by = "toDate(trace_started_at), id"
        if req.cursor is not None:
            where.append(_cursor_predicate(pb, req.cursor))
    elif req.order == "recent":
        order_by = "trace_started_at DESC, id"
    else:
        raise ValueError(f"unknown insights row order {req.order!r}")

    limit = pb.add_param(req.limit)
    return f"""
SELECT {", ".join(columns)}
FROM {table_for_signature_type(req.signature_type)}
WHERE {" AND ".join(where)}
ORDER BY {order_by}
LIMIT {{{limit}:UInt32}}
""".strip()


def make_signature_groups_query(
    pb: ParamBuilder, req: InsightSignaturesQueryReq
) -> str:
    """Facet mix and pre-clustering ranking.

    `uniq(conversation_id)` and `uniq(user_id)` stay separate, and `avg`/`quantile`
    never `sum` because failure windows overlap on a turn.
    """
    if not req.group_by:
        raise ValueError("groups mode requires at least one group_by field")
    group_exprs = [
        _group_expression(field, req.signature_type) for field in req.group_by
    ]
    group_keys = [expr.split(" AS ")[-1] for expr in group_exprs]

    where = _filters(pb, req)
    limit = pb.add_param(req.limit)
    return f"""
SELECT
    {", ".join(group_exprs)},
    count() AS occurrences,
    uniq(conversation_id) AS conversations,
    uniq(user_id) AS users,
    topK(1)(category)[1] AS modal_category,
    avg(turn_cost_usd) AS avg_turn_cost_usd,
    quantile(0.5)(turn_duration_ms) AS p50_turn_duration_ms,
    topK(3)(config_sha) AS configs
FROM {table_for_signature_type(req.signature_type)}
WHERE {" AND ".join(where)}
GROUP BY {", ".join(group_keys)}
ORDER BY occurrences DESC
LIMIT {{{limit}:UInt32}}
""".strip()


def _filters(pb: ParamBuilder, req: InsightSignaturesQueryReq) -> list[str]:
    project = pb.add_param(req.project_id)
    day_start = pb.add_param(req.day_start)
    day_end = pb.add_param(req.day_end)
    where = [
        f"project_id = {{{project}:String}}",
        f"toDate(trace_started_at) >= {{{day_start}:Date}}",
        f"toDate(trace_started_at) <= {{{day_end}:Date}}",
    ]
    if req.trace_id is not None:
        trace = pb.add_param(req.trace_id)
        if req.signature_type == "intent":
            where.append(f"trace_id = {{{trace}:String}}")
        else:
            where.append(f"has(affected_trace_ids, {{{trace}:String}})")
    if req.conversation_id is not None:
        conversation = pb.add_param(req.conversation_id)
        where.append(f"conversation_id = {{{conversation}:String}}")
    if req.categories:
        categories = pb.add_param(req.categories)
        where.append(f"category IN {{{categories}:Array(String)}}")
    if req.signature_hashes:
        hashes = pb.add_param([h.upper() for h in req.signature_hashes])
        where.append(f"hex(sipHash128(signature)) IN {{{hashes}:Array(String)}}")
    return where


def _cursor_predicate(pb: ParamBuilder, cursor: InsightSignatureCursor) -> str:
    """Keyset seek that ClickHouse can push into the primary-key condition.

    ClickHouse 26.6 does not push the equivalent tuple comparison into that
    condition, so its scan grows with page position.
    """
    day = pb.add_param(cursor.day)
    row_id = pb.add_param(str(cursor.id))
    return (
        f"(toDate(trace_started_at) > {{{day}:Date}}"
        f" OR (toDate(trace_started_at) = {{{day}:Date}}"
        f" AND id > {{{row_id}:UUID}}))"
    )


def _group_expression(
    field: InsightGroupField, signature_type: InsightSignatureType
) -> str:
    required = TYPE_ONLY_GROUP_FIELDS.get(field)
    if required is not None and required != signature_type:
        raise ValueError(
            f"group field {field!r} is only valid on the {required} signature type"
        )
    expression = GROUP_EXPRESSIONS.get(field)
    if expression is None:
        raise ValueError(f"unknown insights group field {field!r}")
    return expression
