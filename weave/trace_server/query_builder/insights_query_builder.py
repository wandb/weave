"""Hand-written SQL for the insights endpoints.

Every builder is a pure function of its request, so a test asserts the exact
string and the exact parameters.
"""

from __future__ import annotations

from weave.trace_server.insights.types import (
    InsightContextQueryReq,
    InsightGroupField,
    InsightLens,
    InsightSignatureCursor,
    InsightSignaturesQueryReq,
)
from weave.trace_server.orm import ParamBuilder

PARAM_NAMESPACE = "insights"

INTENT_TABLE = "intent_signatures"
FAILURE_TABLE = "failure_signatures"

SHARED_ROW_COLUMNS = (
    "id",
    "signature",
    "signature_display",
    "hex(sipHash128(signature)) AS signature_hash",
    "category",
    "conversation_id",
    "user_id",
    "agent_name",
    "duration_ms",
    "cost_usd",
    "source_started_at",
    "inserted_at",
)
INTENT_ROW_COLUMNS = (
    "turn_trace_id",
    "language",
    "sentiment",
    "sentiment_confidence",
)
FAILURE_ROW_COLUMNS = (
    "onset_turn_trace_id",
    "turn_trace_ids",
    "evidence_span_ids",
    "failure_reason",
    "severity",
)

CONTEXT_COLUMNS = (
    "lens",
    "turn_trace_id",
    "signature",
    "signature_display",
    "category",
    "config_sha",
    "source_started_at",
    "id",
    "inserted_at",
)

GROUP_EXPRESSIONS: dict[InsightGroupField, str] = {
    "signature": "signature",
    "category": "category",
    "sentiment": "sentiment",
    "severity": "severity",
    "agent_name": "agent_name",
    "day": "toDate(source_started_at) AS day",
}
LENS_ONLY_GROUP_FIELDS: dict[InsightGroupField, InsightLens] = {
    "sentiment": "intent",
    "severity": "failure",
}


def table_for_lens(lens: InsightLens) -> str:
    if lens == "intent":
        return INTENT_TABLE
    elif lens == "failure":
        return FAILURE_TABLE
    else:
        raise ValueError(f"unknown insights lens {lens!r}")


def make_context_query(pb: ParamBuilder, req: InsightContextQueryReq) -> str:
    """Everything already distilled about a named set of turns, both lenses.

    One round trip over both signature tables, because that is the whole data
    model: there is no per-turn table to read instead. Intents attribute to one
    turn; a failure attributes to every turn in `turn_trace_ids`, so it is
    unnested and emitted once per requested turn it touched.

    Versions are not collapsed here. A re-judged turn leaves two rows sharing an
    `id` until a merge, and the caller keeps the highest `inserted_at`, which
    costs one pass over a page instead of a `GROUP BY` over the table.
    """
    project = pb.add_param(req.project_id)
    conversation = pb.add_param(req.conversation_id)
    day_start = pb.add_param(req.day_start)
    day_end = pb.add_param(req.day_end)
    turns = pb.add_param(req.turn_trace_ids)
    scope = (
        f"project_id = {{{project}:String}}\n"
        f"      AND conversation_id = {{{conversation}:String}}\n"
        f"      AND toDate(source_started_at) >= {{{day_start}:Date}}\n"
        f"      AND toDate(source_started_at) <= {{{day_end}:Date}}"
    )
    # `arrayFilter` inside the unnest keeps only the turns that were asked for, so
    # a failure spanning ten turns cannot return the nine nobody wanted. `hasAny`
    # stays in the WHERE because that is what the `turn_trace_ids` bloom index can
    # actually prune on.
    return f"""
SELECT {", ".join(CONTEXT_COLUMNS)}
FROM
(
    SELECT
        'intent' AS lens,
        turn_trace_id,
        signature,
        signature_display,
        category,
        config_sha,
        source_started_at,
        id,
        inserted_at
    FROM {INTENT_TABLE}
    WHERE {scope}
      AND turn_trace_id IN {{{turns}:Array(String)}}
    UNION ALL
    SELECT
        'failure' AS lens,
        arrayJoin(arrayFilter(t -> has({{{turns}:Array(String)}}, t), turn_trace_ids)) AS turn_trace_id,
        signature,
        signature_display,
        category,
        config_sha,
        source_started_at,
        id,
        inserted_at
    FROM {FAILURE_TABLE}
    WHERE {scope}
      AND hasAny(turn_trace_ids, {{{turns}:Array(String)}})
)
ORDER BY source_started_at ASC, lens ASC, id ASC
""".strip()


def make_signature_rows_query(pb: ParamBuilder, req: InsightSignaturesQueryReq) -> str:
    """One page of occurrences.

    Duplicate versions are not collapsed here: measured on this schema a
    `GROUP BY id` dedup cost 7.62 GiB against 51.9 MiB without it, so the caller
    over-fetches and keeps the highest `inserted_at` per `id` on the page.
    """
    columns = list(SHARED_ROW_COLUMNS)
    columns.extend(INTENT_ROW_COLUMNS if req.lens == "intent" else FAILURE_ROW_COLUMNS)
    if req.include_vector:
        columns.append("vector")

    where = _filters(pb, req)
    if req.order == "key":
        order_by = "toDate(source_started_at), id"
        if req.cursor is not None:
            where.append(_cursor_predicate(pb, req.cursor))
    elif req.order == "recent":
        order_by = "source_started_at DESC, id"
    else:
        raise ValueError(f"unknown insights row order {req.order!r}")

    limit = pb.add_param(req.limit)
    return f"""
SELECT {", ".join(columns)}
FROM {table_for_lens(req.lens)}
WHERE {" AND ".join(where)}
ORDER BY {order_by}
LIMIT {{{limit}:UInt32}}
""".strip()


def make_signature_groups_query(
    pb: ParamBuilder, req: InsightSignaturesQueryReq
) -> str:
    """Facet mix and pre-clustering ranking.

    `uniqExact(id)` rather than `count()` so an unmerged replacement row cannot
    inflate the total, `uniq(conversation_id)` and `uniq(user_id)` stay separate,
    and `avg`/`quantile` never `sum` because failure windows overlap on a turn.
    """
    if not req.group_by:
        raise ValueError("groups mode requires at least one group_by field")
    group_exprs = [_group_expression(field, req.lens) for field in req.group_by]
    group_keys = [expr.split(" AS ")[-1] for expr in group_exprs]

    where = _filters(pb, req)
    limit = pb.add_param(req.limit)
    return f"""
SELECT
    {", ".join(group_exprs)},
    uniqExact(id) AS occurrences,
    uniq(conversation_id) AS conversations,
    uniq(user_id) AS users,
    topK(1)(category)[1] AS modal_category,
    avg(cost_usd) AS avg_cost_usd,
    quantile(0.5)(duration_ms) AS p50_duration_ms,
    topK(3)(config_sha) AS configs
FROM {table_for_lens(req.lens)}
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
        f"toDate(source_started_at) >= {{{day_start}:Date}}",
        f"toDate(source_started_at) <= {{{day_end}:Date}}",
    ]
    if req.turn_trace_id is not None:
        turn = pb.add_param(req.turn_trace_id)
        if req.lens == "intent":
            where.append(f"turn_trace_id = {{{turn}:String}}")
        else:
            where.append(f"has(turn_trace_ids, {{{turn}:String}})")
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
    """Keyset seek, spelled out rather than written as a tuple comparison.

    Measured on ClickHouse 26.6: `(toDate(source_started_at), id) > (day, id)` is
    not pushed into the primary-key condition at all and its cost grows with page
    position, while this form prunes and stays flat.
    """
    day = pb.add_param(cursor.day)
    row_id = pb.add_param(cursor.id)
    return (
        f"(toDate(source_started_at) > {{{day}:Date}}"
        f" OR (toDate(source_started_at) = {{{day}:Date}}"
        f" AND id > {{{row_id}:UUID}}))"
    )


def _group_expression(field: InsightGroupField, lens: InsightLens) -> str:
    required_lens = LENS_ONLY_GROUP_FIELDS.get(field)
    if required_lens is not None and required_lens != lens:
        raise ValueError(
            f"group field {field!r} is only valid on the {required_lens} lens"
        )
    expression = GROUP_EXPRESSIONS.get(field)
    if expression is None:
        raise ValueError(f"unknown insights group field {field!r}")
    return expression
