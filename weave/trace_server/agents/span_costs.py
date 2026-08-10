"""Query-time cost computation for GenAI agent spans.

Unlike the older calls cost path (see `weave/trace_server/token_costs.py`),
spans store token usage and the model name as first-class columns, and every
span carries exactly one model. That makes per-span cost a clean LEFT JOIN
against the best-matching row in `llm_token_prices` rather than the
`arrayJoin` over a per-model usage JSON blob that the calls path needs.

The pricing source of truth is shared: the same `llm_token_prices` table,
the same project > default pricing-level precedence, and the same "latest
`effective_date` wins" tie-break used by `token_costs.build_model_prices_query`.

Cost is never stored on the span; it is computed at read time only when a
caller opts in (`include_costs` on the spans query, or a cost derived metric
on the stats query). Callers stitch three pieces into their own SQL:

  * `cost_join_sql` — the `LEFT JOIN` against ranked prices, keyed on the
    span's model.
  * `cost_select_exprs` — the `<expr> AS <name>` cost projections.
  * `COST_COLUMN_NAMES` — the resulting column names, for projections and
    response hydration.

Keeping the SQL here makes it unit-testable without a live ClickHouse and lets
the spans list, grouped, and stats query builders share one definition of how
cost is computed.
"""

from __future__ import annotations

from weave.trace_server.orm import ParamBuilder
from weave.trace_server.token_costs import (
    DEFAULT_PRICING_LEVEL_ID,
    LLM_TOKEN_PRICES_TABLE_NAME,
    PRICING_LEVELS,
)

# Cost columns produced by `cost_select_exprs`, in projection order. These are
# also added to `AgentSpanSchema` so the list-query projection validates and
# the response hydrates them.
COST_INPUT = "input_cost_usd"
COST_OUTPUT = "output_cost_usd"
COST_CACHE_READ = "cache_read_cost_usd"
COST_CACHE_CREATION = "cache_creation_cost_usd"
COST_TOTAL = "total_cost_usd"

COST_COLUMN_NAMES: tuple[str, ...] = (
    COST_INPUT,
    COST_OUTPUT,
    COST_CACHE_READ,
    COST_CACHE_CREATION,
    COST_TOTAL,
)

# Grouped-query sum aggregates over the per-span cost columns.
GROUPED_COST_ALIASES: tuple[str, ...] = (
    "total_cost_usd",
    "total_input_cost_usd",
    "total_output_cost_usd",
)

# Stats derived metrics that read a cost column. These resolve only when the
# query's span source is cost-augmented (see the stats / spans query builders).
# Single source of truth for both builders and the AgentSpanStatsDerivedMetric
# Literal in agents/types.py — keep those in sync with this set.
COST_DERIVED_METRIC_NAMES: frozenset[str] = frozenset(
    {COST_TOTAL, COST_INPUT, COST_OUTPUT}
)

_PRICE_ALIAS = "mp"
# Sentinel column selected from the ranked-price subquery so a LEFT JOIN miss
# (ClickHouse fills non-nullable price columns with 0, not NULL) is
# distinguishable from a genuine $0 price.
_PRICE_MATCHED = "price_matched"


def model_match_sql(span_alias: str) -> str:
    """SQL for the model key used to join a span to its price.

    Prefer the model the provider actually served (`response_model`); fall
    back to the requested model when the response model is absent.
    """
    return (
        f"if({span_alias}.response_model != '', "
        f"{span_alias}.response_model, {span_alias}.request_model)"
    )


def ranked_model_prices_sql(pb: ParamBuilder, project_id: str) -> str:
    """Build a subquery returning the single best price per `llm_id`.

    Mirrors `token_costs.build_model_prices_query`: project-level pricing
    wins over default, ties broken by the most recent `effective_date`. Only
    the rank-1 row per model survives. Parameterized (no f-string project_id),
    so it is safe to embed directly in a JOIN.
    """
    pid_slot = pb.add(project_id, param_type="String")
    default_slot = pb.add(DEFAULT_PRICING_LEVEL_ID, param_type="String")
    project_level = PRICING_LEVELS["PROJECT"]
    default_level = PRICING_LEVELS["DEFAULT"]
    return f"""
        SELECT
            llm_id,
            prompt_token_cost,
            completion_token_cost,
            cache_read_input_token_cost,
            cache_creation_input_token_cost,
            1 AS {_PRICE_MATCHED}
        FROM (
            SELECT
                llm_id,
                prompt_token_cost,
                completion_token_cost,
                cache_read_input_token_cost,
                cache_creation_input_token_cost,
                ROW_NUMBER() OVER (
                    PARTITION BY llm_id
                    ORDER BY
                        CASE
                            WHEN pricing_level = '{project_level}'
                                AND pricing_level_id = {pid_slot} THEN 1
                            WHEN pricing_level = '{default_level}'
                                AND pricing_level_id = {default_slot} THEN 2
                            ELSE 3
                        END,
                        effective_date DESC
                ) AS rank
            FROM {LLM_TOKEN_PRICES_TABLE_NAME}
            WHERE (pricing_level = '{project_level}' AND pricing_level_id = {pid_slot})
               OR (pricing_level = '{default_level}' AND pricing_level_id = {default_slot})
        )
        WHERE rank = 1
    """


def cost_join_sql(
    pb: ParamBuilder,
    project_id: str,
    *,
    span_alias: str = "s",
    price_alias: str = _PRICE_ALIAS,
) -> str:
    """Return the `LEFT JOIN` that attaches ranked prices to spans.

    The join is on the span's model; spans whose model has no matching price
    keep NULL cost columns (see `cost_select_exprs`) so they are excluded
    from aggregates rather than counted as $0.
    """
    prices = ranked_model_prices_sql(pb, project_id)
    return (
        f"LEFT JOIN ({prices}) {price_alias} "
        f"ON {price_alias}.llm_id = {model_match_sql(span_alias)}"
    )


def cost_select_exprs(
    *,
    span_alias: str = "s",
    price_alias: str = _PRICE_ALIAS,
) -> list[str]:
    """Return the per-span `<expr> AS <name>` cost projections.

    Cost formulas mirror the calls path (`token_costs._build_cost_summary_dump_snippet`):
    cached input tokens are billed at the cache rate, so they are subtracted
    from the regular input-token cost. Reasoning tokens are not priced
    separately — providers fold them into `output_tokens` — matching the
    calls behavior. When no price matched, every cost column is NULL.
    """
    matched = f"{price_alias}.{_PRICE_MATCHED} = 1"
    s = span_alias
    p = price_alias
    input_cost_usd = (
        f"({s}.input_tokens - {s}.cache_read_input_tokens "
        f"- {s}.cache_creation_input_tokens) * {p}.prompt_token_cost"
    )
    output_cost_usd = f"{s}.output_tokens * {p}.completion_token_cost"
    cache_read_cost_usd = (
        f"{s}.cache_read_input_tokens * {p}.cache_read_input_token_cost"
    )
    cache_creation_cost_usd = (
        f"{s}.cache_creation_input_tokens * {p}.cache_creation_input_token_cost"
    )
    total_cost_usd = (
        f"({input_cost_usd}) + ({output_cost_usd}) "
        f"+ ({cache_read_cost_usd}) + ({cache_creation_cost_usd})"
    )
    return [
        f"if({matched}, {input_cost_usd}, NULL) AS {COST_INPUT}",
        f"if({matched}, {output_cost_usd}, NULL) AS {COST_OUTPUT}",
        f"if({matched}, {cache_read_cost_usd}, NULL) AS {COST_CACHE_READ}",
        f"if({matched}, {cache_creation_cost_usd}, NULL) AS {COST_CACHE_CREATION}",
        f"if({matched}, {total_cost_usd}, NULL) AS {COST_TOTAL}",
    ]


def cost_augmented_source_sql(
    pb: ParamBuilder,
    project_id: str,
    *,
    span_alias: str = "s",
    base_relation: str = "spans",
) -> str:
    """Return a `spans`-shaped relation with the cost columns appended.

    The result is a parenthesized subquery exposing every `spans` column
    (`s.*`) plus `COST_COLUMN_NAMES` as real columns. Callers substitute it
    for `spans` wherever they need cost available downstream — grouped
    aggregates (`sum(s.total_cost_usd)`) and stats derived metrics
    (`s.total_cost_usd`) — without rewriting their grouping or bucketing logic.
    Span-level WHERE filters applied by the caller push down to the inner
    `spans` scan, so this does not force a full-table materialization.

    `base_relation` is the relation the cost columns are read from; it defaults
    to the raw `spans` table but may be any `spans`-shaped subquery (e.g. an
    already-limited page), in which case the price JOIN runs over just those
    rows. It is interpolated as raw SQL and must be a trusted, internal fragment
    (a relation name), never user input.
    """
    exprs = cost_select_exprs(span_alias=span_alias)
    cost_projection = ",\n            ".join(exprs)
    join = cost_join_sql(pb, project_id, span_alias=span_alias)
    return f"""(
        SELECT {span_alias}.*,
            {cost_projection}
        FROM {base_relation} {span_alias}
        {join}
    )"""
