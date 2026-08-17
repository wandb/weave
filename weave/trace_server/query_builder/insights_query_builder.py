"""Hand-written SQL for the insights endpoints.

Every builder is a pure function of its request, so a test asserts the exact
string and the exact parameters.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from weave.trace_server.insights.enums import InsightGroupField, InsightSignatureType
from weave.trace_server.insights.read_types import (
    InsightSignatureCursor,
    InsightSignaturesQueryReq,
)
from weave.trace_server.orm import ParamBuilder

PARAM_NAMESPACE = "insights"

# The day bucket every read shares: the partition key, the `order="key"` sort
# prefix, the window filter, and the `day` group field are all this expression.
DAY_COLUMN = "toDate(trace_started_at)"
DAY_EXPRESSION = f"{DAY_COLUMN} AS day"
DAY_KEY = "day"

SHARED_ROW_COLUMNS = (
    "id",
    "signature",
    "category",
    "conversation_id",
    "user_id",
    "agent_name",
    "turn_duration_ms",
    "turn_cost_usd",
    "trace_started_at",
    "inserted_at",
)


@dataclass(frozen=True)
class SignatureTypeSpec:
    """Everything that differs between the two signature types, in one place.

    Adding a third type is one entry here rather than a new branch in each builder.
    """

    table: str
    # Turn-scoped measures collapse on this, because one turn emits several signatures.
    turn_id_column: str
    row_columns: tuple[str, ...]
    # A turn drilldown is equality on intents and array membership on failures.
    turn_filter: Callable[[str], str]


SPECS: dict[InsightSignatureType, SignatureTypeSpec] = {
    "intent": SignatureTypeSpec(
        table="intent_signatures",
        turn_id_column="trace_id",
        row_columns=("trace_id", "language", "sentiment"),
        turn_filter=lambda slot: f"trace_id = {{{slot}:String}}",
    ),
    "failure": SignatureTypeSpec(
        table="failure_signatures",
        turn_id_column="current_trace_id",
        row_columns=(
            "current_trace_id",
            "affected_trace_ids",
            "evidence_span_ids",
            "failure_reason",
            "severity",
        ),
        turn_filter=lambda slot: f"has(affected_trace_ids, {{{slot}:String}})",
    ),
}

GROUP_EXPRESSIONS: dict[InsightGroupField, str] = {
    "signature": "signature",
    "category": "category",
    "sentiment": "sentiment",
    "severity": "severity",
    "agent_name": "agent_name",
    "day": DAY_EXPRESSION,
}
TYPE_ONLY_GROUP_FIELDS: dict[InsightGroupField, InsightSignatureType] = {
    "sentiment": "intent",
    "severity": "failure",
}


def spec_for(signature_type: InsightSignatureType) -> SignatureTypeSpec:
    spec = SPECS.get(signature_type)
    if spec is None:
        raise ValueError(f"unknown insights signature type {signature_type!r}")
    return spec


def make_signature_rows_query(pb: ParamBuilder, req: InsightSignaturesQueryReq) -> str:
    """One page of occurrences.

    A `key` page also selects `day`, so the cursor echoes the value ClickHouse
    sorted on rather than one Python re-derives from a timestamp.
    """
    spec = spec_for(req.signature_type)
    columns = [*SHARED_ROW_COLUMNS, *spec.row_columns]

    where = _filters(pb, req, spec)
    if req.order == "key":
        order_by = f"{DAY_COLUMN}, id"
        columns.append(DAY_EXPRESSION)
        if req.cursor is not None:
            where.append(_cursor_predicate(pb, req.cursor))
    elif req.order == "recent":
        order_by = "trace_started_at DESC, id"
    else:
        raise ValueError(f"unknown insights row order {req.order!r}")
    if req.include_vector:
        columns.append("vector")

    limit = pb.add_param(req.limit)
    return f"""
SELECT {", ".join(columns)}
FROM {spec.table}
WHERE {" AND ".join(where)}
ORDER BY {order_by}
LIMIT {{{limit}:UInt32}}
""".strip()


def make_signature_groups_query(
    pb: ParamBuilder, req: InsightSignaturesQueryReq
) -> str:
    """Facet mix and pre-clustering ranking.

    The inner query collapses to one row per turn per group, so `turn_cost_usd`
    and `turn_duration_ms` count a turn once however many signatures it emitted.
    The outer query keeps `occurrences`, `modal_category`, and `configs`
    occurrence-weighted, which is what those three describe.
    """
    spec = spec_for(req.signature_type)
    group_exprs = [
        _group_expression(field, req.signature_type) for field in req.group_by
    ]
    group_keys = [expr.split(" AS ")[-1] for expr in group_exprs]

    where = _filters(pb, req, spec)
    limit = pb.add_param(req.limit)
    return f"""
SELECT
    {", ".join(group_keys)},
    sum(turn_occurrences) AS occurrences,
    count() AS turns,
    uniq(conversation_id) AS conversations,
    uniq(user_id) AS users,
    topKMerge(1)(category_state)[1] AS modal_category,
    avg(turn_cost_usd) AS avg_turn_cost_usd,
    quantileTDigest(0.5)(turn_duration_ms) AS p50_turn_duration_ms,
    topKMerge(3)(config_state) AS configs
FROM (
    SELECT
        {", ".join(group_exprs)},
        conversation_id,
        user_id,
        count() AS turn_occurrences,
        any(turn_cost_usd) AS turn_cost_usd,
        any(turn_duration_ms) AS turn_duration_ms,
        topKState(1)(category) AS category_state,
        topKState(3)(config_sha) AS config_state
    FROM {spec.table}
    WHERE {" AND ".join(where)}
    GROUP BY {", ".join(group_keys)}, conversation_id, user_id, {spec.turn_id_column}
)
GROUP BY {", ".join(group_keys)}
ORDER BY occurrences DESC
LIMIT {{{limit}:UInt32}}
""".strip()


def _filters(
    pb: ParamBuilder, req: InsightSignaturesQueryReq, spec: SignatureTypeSpec
) -> list[str]:
    project = pb.add_param(req.project_id)
    day_start = pb.add_param(req.day_start)
    day_end = pb.add_param(req.day_end)
    where = [
        f"project_id = {{{project}:String}}",
        f"{DAY_COLUMN} >= {{{day_start}:Date}}",
        f"{DAY_COLUMN} <= {{{day_end}:Date}}",
    ]
    if req.trace_id is not None:
        where.append(spec.turn_filter(pb.add_param(req.trace_id)))
    if req.conversation_id is not None:
        conversation = pb.add_param(req.conversation_id)
        where.append(f"conversation_id = {{{conversation}:String}}")
    if req.categories:
        categories = pb.add_param(req.categories)
        where.append(f"category IN {{{categories}:Array(String)}}")
    if req.signatures:
        signatures = pb.add_param(req.signatures)
        where.append(f"signature IN {{{signatures}:Array(String)}}")
    return where


def _cursor_predicate(pb: ParamBuilder, cursor: InsightSignatureCursor) -> str:
    """Keyset seek that ClickHouse can push into the primary-key condition.

    ClickHouse 26.6 does not push the equivalent tuple comparison into that
    condition, so its scan grows with page position.
    """
    day = pb.add_param(cursor.day)
    row_id = pb.add_param(str(cursor.id))
    return (
        f"({DAY_COLUMN} > {{{day}:Date}}"
        f" OR ({DAY_COLUMN} = {{{day}:Date}}"
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
