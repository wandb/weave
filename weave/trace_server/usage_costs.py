"""Compute per-call LLM costs in Python for the usage endpoints.

Mirrors the ClickHouse cost CTE (`token_costs.py`): for each (call, model) it
picks the best-matching price by effective date and pricing-level specificity,
then applies the same cost formula. Lets the usage endpoints skip the in-SQL
cost CTE (arrayJoin + price join + summary_dump rebuild) and fold costs into the
bottom-up rollup instead.
"""

from __future__ import annotations

import dataclasses
import datetime
from bisect import bisect_right
from typing import Any

from weave.trace_server.orm import ParamBuilder
from weave.trace_server.token_costs import (
    DEFAULT_PRICING_LEVEL_ID,
    LLM_TOKEN_PRICES_TABLE_NAME,
    PRICING_LEVELS,
)

PRICE_COLUMNS = (
    "llm_id",
    "pricing_level",
    "pricing_level_id",
    "effective_date",
    "prompt_token_cost",
    "completion_token_cost",
    "cache_read_input_token_cost",
    "cache_creation_input_token_cost",
)


def prices_query(pb: ParamBuilder, project_id: str, models: list[str]) -> str:
    """Fetch project + default prices for the given models (one cheap query)."""
    models_param = pb.add_param(sorted(models))
    project_param = pb.add_param(project_id)
    default_param = pb.add_param(DEFAULT_PRICING_LEVEL_ID)
    project_level = PRICING_LEVELS["PROJECT"]
    default_level = PRICING_LEVELS["DEFAULT"]
    return f"""
    SELECT {", ".join(PRICE_COLUMNS)}
    FROM {LLM_TOKEN_PRICES_TABLE_NAME}
    WHERE llm_id IN {{{models_param}:Array(String)}}
      AND (
        (pricing_level = '{project_level}'
         AND pricing_level_id = {{{project_param}:String}})
        OR (pricing_level = '{default_level}'
            AND pricing_level_id = {{{default_param}:String}})
      )
    """


def index_prices(rows: list[tuple[Any, ...]]) -> dict[str, ModelPrices]:
    """Group raw price rows by model into project/default lists sorted by date."""
    project: dict[str, list[_Price]] = {}
    default: dict[str, list[_Price]] = {}
    for row in rows:
        record = dict(zip(PRICE_COLUMNS, row, strict=False))
        model = str(record["llm_id"])
        price = _Price(
            effective_ts=_to_ts(record["effective_date"]),
            prompt_token_cost=_to_float(record["prompt_token_cost"]),
            completion_token_cost=_to_float(record["completion_token_cost"]),
            cache_read_input_token_cost=_to_float(
                record["cache_read_input_token_cost"]
            ),
            cache_creation_input_token_cost=_to_float(
                record["cache_creation_input_token_cost"]
            ),
        )
        if record["pricing_level"] == PRICING_LEVELS["PROJECT"]:
            project.setdefault(model, []).append(price)
        elif record["pricing_level"] == PRICING_LEVELS["DEFAULT"]:
            default.setdefault(model, []).append(price)

    index: dict[str, ModelPrices] = {}
    for model in set(project) | set(default):
        index[model] = ModelPrices(
            project=sorted(project.get(model, []), key=lambda p: p.effective_ts),
            default=sorted(default.get(model, []), key=lambda p: p.effective_ts),
        )
    return index


def costs_for_usage(
    usage_map: dict[str, Any],
    started_at: datetime.datetime,
    index: dict[str, ModelPrices],
) -> dict[str, dict[str, float]]:
    """Per-model cost totals, keyed as the rollup's `summary.weave.costs` expects."""
    started_ts = _to_ts(started_at)
    costs: dict[str, dict[str, float]] = {}
    for model_name, usage in usage_map.items():
        if not isinstance(usage, dict):
            continue
        price = _select_price(index.get(str(model_name)), started_ts)
        if price is None:
            continue
        prompt_tokens = _to_int(usage.get("prompt_tokens")) + _to_int(
            usage.get("input_tokens")
        )
        completion_tokens = _to_int(usage.get("completion_tokens")) + _to_int(
            usage.get("output_tokens")
        )
        cache_read = _to_int(usage.get("cache_read_input_tokens"))
        cache_creation = _to_int(usage.get("cache_creation_input_tokens"))
        costs[str(model_name)] = {
            "prompt_tokens_total_cost": (prompt_tokens - cache_read - cache_creation)
            * price.prompt_token_cost,
            "completion_tokens_total_cost": completion_tokens
            * price.completion_token_cost,
            "cache_read_input_tokens_total_cost": cache_read
            * price.cache_read_input_token_cost,
            "cache_creation_input_tokens_total_cost": cache_creation
            * price.cache_creation_input_token_cost,
        }
    return costs


@dataclasses.dataclass(frozen=True)
class _Price:
    effective_ts: float
    prompt_token_cost: float
    completion_token_cost: float
    cache_read_input_token_cost: float
    cache_creation_input_token_cost: float


@dataclasses.dataclass(frozen=True)
class ModelPrices:
    project: list[_Price]
    default: list[_Price]


def _select_price(prices: ModelPrices | None, started_ts: float) -> _Price | None:
    """Best price for a call, matching the CH ranked_prices ROW_NUMBER ordering.

    Prefer effective-on-or-before over future, project over default, latest date.
    """
    if prices is None:
        return None
    return (
        _latest_on_or_before(prices.project, started_ts)
        or _latest_on_or_before(prices.default, started_ts)
        or _farthest_future(prices.project, started_ts)
        or _farthest_future(prices.default, started_ts)
    )


def _latest_on_or_before(prices: list[_Price], started_ts: float) -> _Price | None:
    idx = bisect_right([p.effective_ts for p in prices], started_ts) - 1
    return prices[idx] if idx >= 0 else None


def _farthest_future(prices: list[_Price], started_ts: float) -> _Price | None:
    # CH breaks future-priced rows by `effective_date DESC`, i.e. the latest date.
    if prices and prices[-1].effective_ts > started_ts:
        return prices[-1]
    return None


def _to_ts(value: datetime.datetime | str) -> float:
    if isinstance(value, str):
        value = datetime.datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value.timestamp()


def _to_int(value: Any) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0
